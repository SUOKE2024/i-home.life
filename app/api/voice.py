"""语音处理 API — 关键词匹配 + LLM 语义意图分类"""
import json
import logging
import re
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import PROVIDER_REGISTRY
from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.services.reply_templates import ReplyTemplates

router = APIRouter(prefix="/voice", tags=["语音"])

settings = get_settings()
logger = logging.getLogger(__name__)

# ── LLM 语义分类 prompt ──────────────────────────────────────

VOICE_INTENT_CLASSIFICATION_PROMPT = """你是一个智能家居平台的意图分类器。根据用户的语音转文字输入，判断用户意图属于以下哪个类别。

类别定义：
- design: 室内设计、户型布局、方案生成、画墙、添加房间、建造
- measurement: 测量、丈量、激光扫描、LiDAR、量房、测距、面积计算
- budget: 预算、报价、价格、费用、成本
- procurement: 采购、购买、材料、建材、供应商
- construction: 施工、进度、验收、质检、工地管理
- settlement: 结算、对账、尾款、付款、账单
- qa: 质量检查、整改、返工、验收标准
- smart_home: 智能家居、设备控制、场景联动、Matter、能耗
- scene: 场景模式、离家模式、回家模式、观影模式
- general: 其他通用问题、闲聊、问候

请严格只输出一个 JSON 对象，格式为：{"intent": "<类别>"}
不要输出任何其他内容。"""


# ── 关键词匹配规则（快速降级路径） ──────────────────────────

_KEYWORD_INTENT_MAP: list[tuple[list[str], str]] = [
    # 每项: (关键词列表, 意图)
    (["设计", "布局", "方案", "户型", "画", "墙", "房间", "添加", "加一个", "新建", "建造", "装修"], "design"),
    (["测量", "丈量", "扫描", "激光", "LiDAR", "摄像头", "拍照测量", "量房", "测距", "面积"], "measurement"),
    (["预算", "价格", "费用", "成本", "多少钱", "报价"], "budget"),
    (["采购", "买", "材料", "建材", "供应商"], "procurement"),
    (["施工", "进度", "验收", "质检", "工地", "工序"], "construction"),
    (["结算", "对账", "尾款", "付款", "账单", "发票"], "settlement"),
    (["整改", "返工", "验收标准", "质检报告", "不合格"], "qa"),
    (["智能家居", "智能设备", "Matter", "能耗", "节能", "灯", "空调", "窗帘", "传感器"], "smart_home"),
    (["离家模式", "回家模式", "观影模式", "场景", "一键"], "scene"),
]


def _classify_by_keywords(text: str) -> str:
    """基于关键词的意图分类（快速降级路径）。"""
    for keywords, intent in _KEYWORD_INTENT_MAP:
        if any(kw in text for kw in keywords):
            return intent
    return "general"


# ── LLM 语义分类 ────────────────────────────────────────────

# 语义分类的 fallback chain 顺序：deepseek → glm → qwen
_VOICE_LLM_FALLBACK_CHAIN = ["deepseek", "glm", "qwen"]


async def _classify_by_llm(text: str) -> str | None:
    """使用 LLM 进行语义意图分类。

    按 fallback chain 尝试每个供应商，成功返回 intent 字符串；
    全部失败返回 None，由调用方降级到关键词匹配。
    """
    messages = [
        {"role": "system", "content": VOICE_INTENT_CLASSIFICATION_PROMPT},
        {"role": "user", "content": text},
    ]

    for provider in _VOICE_LLM_FALLBACK_CHAIN:
        cfg = PROVIDER_REGISTRY[provider]
        api_key = cfg["api_key"]()
        if not api_key:
            logger.debug("voice_llm_classify: 供应商 %s API key 未配置，跳过", provider)
            continue

        try:
            async with httpx.AsyncClient(
                base_url=cfg["api_base"](),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                timeout=httpx.Timeout(15.0),
            ) as client:
                response = await client.post(
                    cfg["chat_path"],
                    json={
                        "model": cfg["model"](),
                        "messages": messages,
                        "temperature": 0.0,
                        "max_tokens": 64,
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"].get("content", "").strip()

                # 解析 LLM 返回的 JSON
                parsed = _parse_intent_response(content)
                if parsed:
                    logger.info(
                        "voice_llm_classify: text=%r → intent=%s (provider=%s)",
                        text[:80], parsed, provider,
                    )
                    return parsed
                logger.warning(
                    "voice_llm_classify: %s 返回无法解析的响应 %r",
                    provider, content[:100],
                )
        except Exception as e:
            logger.warning(
                "voice_llm_classify: 供应商 %s 调用失败 (error=%s)", provider, e,
            )

    return None


def _parse_intent_response(content: str) -> str | None:
    """从 LLM 响应中解析 intent。

    支持多种格式：纯 JSON、JSON 在 markdown code block 中、纯文本中提取。
    """
    if not content:
        return None

    # 尝试直接 JSON 解析
    candidates = [content]
    # 尝试提取 markdown code block 中的 JSON
    code_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
    if code_match:
        candidates.insert(0, code_match.group(1))
    # 尝试提取任意 {...} JSON 对象
    json_match = re.search(r'\{[^{}]*"intent"[^{}]*\}', content)
    if json_match and json_match.group() not in candidates:
        candidates.insert(0, json_match.group())

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            intent = parsed.get("intent", "").strip().lower()
            if intent:
                return intent
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue

    return None


async def _route_intent(text: str) -> str:
    """意图路由：LLM 语义分类优先，关键词匹配降级。

    返回 intent 字符串：design/measurement/budget/procurement/construction/
    settlement/qa/smart_home/scene/general
    """
    # 检查 LLM 路由是否启用
    if settings.voice_llm_routing_enabled:
        llm_intent = await _classify_by_llm(text)
        if llm_intent:
            return llm_intent
        logger.info("voice_route: LLM 分类失败，降级到关键词匹配 (text=%r)", text[:80])

    return _classify_by_keywords(text)


# ════════════════════════════════════════════════════════════════
# Pydantic 模型
# ════════════════════════════════════════════════════════════════


class VoiceMessage(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    project_id: str | None = None


class VoiceResponse(BaseModel):
    transcript: str
    intent: str = "general"
    reply: str
    actions: list[dict] = []
    emotion: dict | None = None  # v1.2.4: emotion detection result


# ════════════════════════════════════════════════════════════════
# 端点
# ════════════════════════════════════════════════════════════════


def _handle_intent(text: str, intent: str) -> tuple[str, list[dict]]:
    """根据意图生成回复和动作。"""
    actions: list[dict] = []
    if intent == "measurement":
        reply = _build_measurement_guide(text)
        actions = _extract_room_from_text(text)
    elif intent == "design":
        reply = ReplyTemplates.design(text)
        if "加" in text or "添加" in text or "建" in text:
            name_match = re.search(r"(客厅|卧室|厨房|卫生间|书房|阳台|餐厅|走廊)", text)
            size_match = re.search(r"(\d+(\.\d+)?)[×xX](\d+(\.\d+)?)", text)
            w = float(size_match.group(1)) if size_match else 4
            h = float(size_match.group(3)) if size_match else 3
            name = name_match.group(1) if name_match else "房间"
            type_map = {
                "客厅": "living_room", "卧室": "bedroom", "厨房": "kitchen",
                "卫生间": "bathroom", "书房": "study", "阳台": "balcony",
                "餐厅": "dining_room", "走廊": "hallway",
            }
            actions = [{
                "action": "add_room", "x": 0, "y": 0, "w": w, "h": h,
                "name": name, "roomType": type_map.get(name, "living_room"),
            }]
            reply = ReplyTemplates.design_room_created(name, w, h)
    elif intent == "budget":
        reply = ReplyTemplates.budget(text)
    elif intent == "procurement":
        reply = ReplyTemplates.procurement(text)
    elif intent == "construction":
        reply = ReplyTemplates.construction(text)
    elif intent == "settlement":
        reply = f"结算分析：「{text}」。正在核对账单明细，请稍候。"
    elif intent == "qa":
        reply = f"质检诉求：「{text}」。已启动质量检查流程，请确认验收标准。"
    elif intent == "smart_home":
        reply = f"智能家居指令：「{text}」。正在为您执行设备操作/场景联动。"
    elif intent == "scene":
        reply = f"场景模式：「{text}」。正在切换场景并同步各设备状态。"
    else:
        reply = ReplyTemplates.general(text)
    return reply, actions


@router.post("/process", response_model=VoiceResponse)
async def process_voice(
    data: VoiceMessage,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """语音处理（关键词匹配路由）。

    使用关键词匹配进行意图分类，并调用 OrchestratorAgent.fallback_classify 作为辅助。
    """
    # 校验项目归属
    if data.project_id:
        result = await db.execute(select(Project).where(Project.id == data.project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        if current_user.role != "admin" and project.owner_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")

    text = data.text
    intent = _classify_by_keywords(text)

    # 辅助分类增强
    from app.agents.orchestrator import OrchestratorAgent
    classification = OrchestratorAgent.fallback_classify(text)
    fallback_intent = classification.get("intent", "general")
    if fallback_intent != "general":
        intent = fallback_intent

    reply, actions = _handle_intent(text, intent)
    return VoiceResponse(transcript=text, intent=intent, reply=reply, actions=actions)


# ════════════════════════════════════════════════════════════════
# 辅助函数：测量 + 房间提取
# ════════════════════════════════════════════════════════════════


def _build_measurement_guide(text: str) -> str:
    """构建测量语音引导回复"""
    guide_parts = ["📐 测量模式已激活。"]
    # 检测场景类型
    scene_hints = {"室内": "indoor", "阳台": "balcony", "室外": "outdoor", "露台": "outdoor"}
    for kw, scene in scene_hints.items():
        if kw in text:
            guide_parts.append(f"检测到{kw}场景，推荐使用{'激光测距仪' if scene == 'indoor' else '户外激光+视觉辅助'}测量。")
            break
    else:
        guide_parts.append("请手持设备沿墙壁扫描，或用激光测距仪逐个测量房间。")

    guide_parts.append("语音引导步骤：1) 站到房间一角 → 2) 说出房间名称和用途 → 3) 沿墙移动设备 → 4) 系统自动计算面积。")
    guide_parts.append("💡 您可以说：「客厅 6米×7米」来直接录入尺寸。")
    return "\n".join(guide_parts)


def _extract_room_from_text(text: str) -> list[dict]:
    """从语音文本中提取房间测量信息"""
    actions: list[dict] = []
    # 匹配模式: "客厅 6×7" 或 "主卧 4米×5米"
    pattern = re.compile(r"(客厅|主卧|次卧|卧室|厨房|卫生间|书房|阳台|餐厅|走廊|玄关).*?(\d+(?:\.\d+)?)[×xX米]*\s*[×xX]*\s*(\d+(?:\.\d+)?)")
    for m in pattern.finditer(text):
        name = m.group(1)
        w = float(m.group(2))
        h = float(m.group(3))
        type_map = {
            "客厅": "living_room", "卧室": "living_room", "主卧": "bedroom",
            "次卧": "bedroom", "厨房": "kitchen", "卫生间": "bathroom",
            "书房": "study", "阳台": "balcony", "餐厅": "dining_room",
            "走廊": "hallway", "玄关": "hallway",
        }
        actions.append({
            "action": "measure_room", "name": name,
            "room_type": type_map.get(name, "living_room"),
            "width": w, "length": h, "area": round(w * h, 2),
        })
    return actions
