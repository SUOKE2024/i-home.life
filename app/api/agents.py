import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.project import Project
from app.auth import get_current_user
from app.database import get_db
from app.rbac import verify_project_access
from app.agents.orchestrator import OrchestratorAgent
from app.agents.designer import DesignerAgent
from app.agents.budget import BudgetAgent
from app.agents.procurement import ProcurementAgent
from app.agents.construction import ConstructionAgent
from app.agents.settlement import SettlementAgent
from app.agents.qa_inspector import QAInspectorAgent
from app.agents.concierge import ConciergeAgent
from app.agents.content_publisher import ContentPublisherAgent
from app.agents.admin import AdminAgent
from app.config import get_settings
from app.ws import ws_manager

router = APIRouter(prefix="/agents", tags=["AI Agent"])


class AgentMessage(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    agent_type: str = Field(default="orchestrator")
    project_id: str | None = None
    history: list[dict] = Field(
        default_factory=list, max_length=20,
        description="最近 N 轮对话历史，每项含 role/content/agent_type",
    )


class DesignRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    project_id: str | None = None
    room_info: str | None = Field(None, description="房间信息（户型、面积等）")


class CirculationAnalysisRequest(BaseModel):
    rooms: list[dict] = Field(..., description="房间布局列表，含 name/type/x/y/w/h")


class AgentResponse(BaseModel):
    agent_type: str
    reply: str
    suggestions: list[str] = []


class DesignPlanResponse(BaseModel):
    agent_type: str = "designer"
    space_planning: str = ""
    style_suggestion: str = ""
    circulation_analysis: str = ""
    material_plan: str = ""
    full_reply: str = ""


class BudgetAnalysisResponse(BaseModel):
    agent_type: str = "budget"
    summary: str = ""
    category_breakdown: str = ""
    cost_saving_tips: str = ""
    full_reply: str = ""


class ProcurementAnalysisResponse(BaseModel):
    agent_type: str = "procurement"
    purchase_plan: str = ""
    supplier_recommendation: str = ""
    timeline: str = ""
    full_reply: str = ""


class ConstructionPlanResponse(BaseModel):
    agent_type: str = "construction"
    phases: str = ""
    schedule: str = ""
    quality_checklist: str = ""
    full_reply: str = ""


class AcceptanceReportRequest(BaseModel):
    project_id: str = ""
    project_name: str = ""
    inspector: str = ""
    acceptance_date: str = ""
    phases: list[str] = []
    inspection_results: dict = {}


class CompareDesignRequest(BaseModel):
    project_id: str = ""
    phase: str = ""
    images: list[dict] = []
    design_reference: dict = {}
    expected_dimensions: dict = {}


class DefectDetectionRequest(BaseModel):
    project_id: str = ""
    phase: str = ""
    images: list[dict] = []
    check_categories: list[str] = []


class FAQRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class ClassifyInquiryRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ConciergeChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    context: str = ""


settings = get_settings()

logger = logging.getLogger(__name__)

# 显式 agent_type → intent 映射，用于跳过 OrchestratorAgent.classify_intent
# 当客户端明确指定 agent_type（非 "orchestrator"）时，直接路由到对应 Agent，
# 避免 ~10s 的 LLM 分类调用，提升响应速度并尊重客户端选择。
# 同时支持别名（如 Web 前端发送 "design" 而非 "designer"）以保持兼容性。
AGENT_TYPE_TO_INTENT: dict[str, str] = {
    "designer": "design",
    "design": "design",  # Web 前端兼容别名
    "budget": "budget",
    "procurement": "procurement",
    "construction": "construction",
    "qa_inspector": "qa_inspector",
    "settlement": "settlement",
    "concierge": "concierge",
    "content_publisher": "content_publish",
    "admin": "admin",
    # "orchestrator" 不在此表中 → 触发自动分类
}


def _extract_reply_from_llm_json(raw: str) -> str:
    """从 LLM 的 JSON 输出中提取用户友好的 reply 字段。

    DesignerAgent 的 system_prompt 要求 LLM 输出 JSON（含 plans/recommendation/
    materials/reply 字段）。若直接把原始 JSON 返回给前端，用户会看到一大段
    结构化数据而非自然语言摘要。本函数剥离 ```json``` 包裹并提取 reply 字段；
    若解析失败或无 reply 字段，则原样返回（保留 LLM 的自然语言输出）。
    """
    if not raw:
        return raw
    text = raw.strip()
    # 剥离 ```json ... ``` 或 ``` ... ``` 包裹
    if text.startswith("```"):
        lines = text.split("\n")
        # 去掉首行（```json 或 ```）和末行（```）
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        # 非 JSON（LLM 返回了自然语言），原样返回
        return raw
    if isinstance(parsed, dict):
        reply = parsed.get("reply")
        if isinstance(reply, str) and reply.strip():
            return reply
        # JSON 有效但无 reply 字段：返回简要摘要
        plans = parsed.get("plans")
        if isinstance(plans, list) and plans:
            rec = parsed.get("recommendation", "")
            return f"已为您生成 {len(plans)} 套设计方案。{rec}".strip()
    return raw


def _looks_like_reasoning_leak(text: str) -> bool:
    """检测文本是否为 LLM reasoning_content 泄漏（思维链）。

    DeepSeek-V4-Pro 等推理模型在 max_tokens 不足时，content 字段为空，
    BaseAgent._chat 会 fallback 到 reasoning_content。DesignerAgent 的
    system_prompt 要求 JSON 输出，但 reasoning_content 是自然语言思维链，
    _extract_reply_from_llm_json 解析失败后原样返回，导致用户看到 LLM
    内部思维而非友好回复（v1.0.16 同类问题复发）。

    思维链特征：第一人称元描述（"我需要理解/我应该生成/首先分析"等）。
    """
    if not text or len(text) < 10:
        return False
    reasoning_starts = (
        "我们需要理解", "我需要理解", "我应该", "我们要",
        "首先,", "首先，", "第一步",
        "分析用户", "理解用户",
        "让我", "让我思考", "让我分析",
    )
    reasoning_keywords = (
        "应该输出", "应该生成", "需要输出", "JSON格式",
        "输出格式", "需要生成", "按照格式",
        "思维链", "reasoning", "接下来我",
    )
    text_stripped = text.strip()
    if any(text_stripped.startswith(p) for p in reasoning_starts):
        return True
    head = text_stripped[:200]
    keyword_count = sum(1 for kw in reasoning_keywords if kw in head)
    if keyword_count >= 2:
        return True
    return False


@router.post("/chat", response_model=AgentResponse)
async def chat_with_agent(  # noqa: C901
    data: AgentMessage,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 校验项目归属（若指定了 project_id）
    if data.project_id:
        result = await db.execute(select(Project).where(Project.id == data.project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        if current_user.role != "admin" and project.owner_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    # 构建 history 上下文（多轮对话支持）
    history_ctx = ""
    if data.history:
        recent = data.history[-10:]  # 仅取最近 10 轮，防止 token 超限
        lines = []
        for h in recent:
            role = h.get("role", "user")
            content = h.get("content", "")[:500]  # 截断超长消息
            agent_t = h.get("agent_type", "")
            prefix = f"[{agent_t}] " if agent_t and role == "assistant" else ""
            lines.append(f"{prefix}{role}: {content}")
        history_ctx = "\n".join(lines)
    user_ctx = f"用户: {current_user.name}"
    if history_ctx:
        user_ctx = f"{history_ctx}\n{user_ctx}"
    # Hybrid routing: LLM classify (with API key) or rule-based (mock mode)
    agent = OrchestratorAgent()
    try:
        # 若客户端显式指定了 agent_type（非 orchestrator），直接路由到对应 Agent，
        # 跳过 LLM classify 调用以降低延迟
        explicit_intent = AGENT_TYPE_TO_INTENT.get(data.agent_type)
        if explicit_intent:
            intent = explicit_intent
        else:
            classification = await agent.classify_intent(data.message)
            intent = classification.get("intent", "general")

        # L4 自适应学习：注入用户历史正向反馈作为 few-shot 示例提示
        if settings.agent_learning_enabled:
            from app.agents.base import BaseAgent
            # intent → agent_name 映射（与下方路由分支一致）
            intent_to_agent = {
                "design": "designer", "budget": "budget",
                "procurement": "procurement", "construction": "construction",
                "settlement": "settlement", "qa_inspector": "qa_inspector",
                "concierge": "concierge", "content_publish": "content_publisher",
                "admin": "admin",
            }
            agent_name_for_hint = intent_to_agent.get(intent, "orchestrator")
            preference_hint = await BaseAgent.get_user_preference_hint(
                current_user.id, agent_name_for_hint, db,
                max_examples=settings.agent_learning_max_examples,
            )
            if preference_hint:
                user_ctx = f"{preference_hint}\n{user_ctx}"

        # Route to specialized agent based on intent
        suggestions_map = {
            "designer": ["调整方案", "查看材料清单", "不同风格对比"],
            "budget": ["查看明细", "调整预算", "导出报表"],
            "procurement": ["查看供应商", "发起询价", "生成订单"],
            "construction": ["查看进度", "上传日志", "发起验收"],
            "qa_inspector": ["生成验收报告", "图纸比对", "缺陷检测"],
            "concierge": ["查看常见问题", "转人工客服", "提交报修"],
            "content_publisher": ["生成产品文案", "发布产品", "编辑产品信息"],
            "ar_measurement": ["打开AR扫描", "测量客厅面积", "扫描户型结构"],
            "floorplans": ["查看户型方案", "保存当前户型", "修改户型布局"],
            "structural": ["查看结构分析", "梁柱计算", "承重评估"],
            "lighting": ["灯光方案设计", "照度计算", "色温推荐"],
            "smart_home": ["设备配置", "场景联动", "查看设备列表"],
            "scene_automation": ["编辑场景", "添加触发条件", "测试场景"],
            "custom_furniture": ["设计柜体", "计算板材", "查看报价"],
            "tasks": ["查看任务列表", "分派任务", "更新进度"],
            "change_orders": ["发起变更", "查看变更单", "审批变更"],
            "crews": ["匹配班组", "查看施工队", "调度工人"],
            "vr_panorama": ["打开全景", "切换场景", "播放语音讲解"],
            "ai_render": ["生成效果图", "风格迁移", "调整配色"],
            "sketch_to_3d": ["上传草图", "生成3D模型", "调整精度"],
            "soft_furnishing": ["选择窗帘", "搭配软装", "查看布艺方案"],
            "hard_decoration": ["硬装设计", "选地砖", "选吊顶方案"],
            "takeoff": ["计算工程量", "生成材料清单", "查看辅料用量"],
            "points": ["查看积分", "积分兑换", "会员权益"],
            "cad_import": ["导入CAD", "查看图纸", "转换DXF"],
            "orchestrator": ["开始设计", "查看预算", "浏览材料", "施工进度"],
        }

        if intent in ("content_publish",):
            # 使用专用的 ContentPublisherAgent 处理产品管理/内容发布
            cp_agent = ContentPublisherAgent()
            try:
                product_intent = ContentPublisherAgent.classify_intent(data.message)
                if product_intent != "create_product" or any(
                    kw in data.message for kw in ["修改", "更新", "下架", "库存", "我的产品", "列表"]
                ):
                    # 产品管理操作
                    reply = await cp_agent.think(
                        f"供应商 {current_user.name} 请求管理产品：{data.message}", user_ctx
                    )
                else:
                    # 内容发布引导
                    reply = await cp_agent.generate_content_publish_reply(data.message, current_user.name)
                return AgentResponse(
                    agent_type="content_publisher", reply=reply,
                    suggestions=suggestions_map["content_publisher"],
                )
            finally:
                await cp_agent.close()

        if intent in ("design",):
            des_agent = DesignerAgent()
            try:
                raw_reply = await des_agent.think(data.message, user_ctx)
                # DesignerAgent 的 system_prompt 要求 LLM 输出 JSON，
                # 提取其中的 reply 字段作为用户友好回复
                reply = _extract_reply_from_llm_json(raw_reply)
                # DeepSeek-V4-Pro 推理模型在 max_tokens 不足时会 fallback
                # 到 reasoning_content，导致 reply 为思维链文本。检测到
                # 泄漏时降级到预设布局方案。
                # 同时处理 mock 模式（API key 为空时 _chat 返回 [mock] 占位文本）
                if _looks_like_reasoning_leak(reply) or "稍后重试" in reply or raw_reply.startswith("[mock]"):
                    logger.warning(
                        "designer_reply_leak: falling back to layouts; "
                        "raw_head=%r", raw_reply[:200],
                    )
                    layouts = await des_agent.generate_layouts(data.message)
                    reply = layouts["reply"]
                return AgentResponse(agent_type="designer", reply=reply, suggestions=suggestions_map["designer"])
            finally:
                await des_agent.close()

        elif intent in ("budget",):
            bud_agent = BudgetAgent()
            try:
                # FunctionCall: LLM 可调用 get_budget 工具查询结构化预算数据
                result = await bud_agent.think_with_tools(data.message, user_ctx)
                reply = result["final_reply"]
                return AgentResponse(agent_type="budget", reply=reply, suggestions=suggestions_map["budget"])
            finally:
                await bud_agent.close()

        elif intent in ("procurement",):
            proc_agent = ProcurementAgent()
            try:
                # FunctionCall: LLM 可调用 search_materials 工具搜索物料
                result = await proc_agent.think_with_tools(data.message, user_ctx)
                reply = result["final_reply"]
                return AgentResponse(agent_type="procurement", reply=reply, suggestions=suggestions_map["procurement"])
            finally:
                await proc_agent.close()

        elif intent in ("construction",):
            cons_agent = ConstructionAgent()
            try:
                # FunctionCall: LLM 可调用 get_construction_progress 查询施工进度
                result = await cons_agent.think_with_tools(data.message, user_ctx)
                reply = result["final_reply"]
                return AgentResponse(
                    agent_type="construction", reply=reply,
                    suggestions=suggestions_map["construction"],
                )
            finally:
                await cons_agent.close()

        elif intent in ("settlement",):
            sett_agent = SettlementAgent()
            try:
                reply = await sett_agent.think(data.message, user_ctx)
                return AgentResponse(agent_type="settlement", reply=reply, suggestions=["查看结算明细", "确认结算", "导出报表"])
            finally:
                await sett_agent.close()

        elif intent in ("qa_inspector",):
            qa_agent = QAInspectorAgent()
            try:
                # FunctionCall: LLM 可调用 run_qa_inspection 执行质量检测
                result = await qa_agent.think_with_tools(data.message, user_ctx)
                reply = result["final_reply"]
                return AgentResponse(
                    agent_type="qa_inspector", reply=reply,
                    suggestions=suggestions_map["qa_inspector"],
                )
            finally:
                await qa_agent.close()

        elif intent in ("concierge",):
            conc_agent = ConciergeAgent()
            try:
                reply = await conc_agent.generate_response(data.message, f"业主: {current_user.name}")
                return AgentResponse(agent_type="concierge", reply=reply, suggestions=suggestions_map["concierge"])
            finally:
                await conc_agent.close()

        elif intent in ("admin", "user_manage", "platform_stats", "identity_review"):
            admin_agent = AdminAgent()
            try:
                reply = await admin_agent.think(data.message, user_ctx)
                suggestions = ["查看用户列表", "修改用户角色", "平台统计", "审核认证"]
                return AgentResponse(agent_type="admin", reply=reply, suggestions=suggestions)
            finally:
                await admin_agent.close()

        elif intent in ("ar_measurement",):
            # AR 空间测量引导：返回 AR 扫描功能的使用指南
            reply_lines = [
                "AR 空间测量功能可以帮助您快速测量房间尺寸、墙面面积等数据。",
                "",
                "使用方法：",
                "1. 打开索克家居 App（支持 iOS/Android/鸿蒙）",
                "2. 进入项目后点击「AR 扫描」或「量房」功能",
                "3. 按照指引移动设备扫描房间",
                f"4. 扫描完成后，数据将自动同步到项目 {data.project_id or ''} 中",
                "",
                "支持的功能：",
                "- RoomPlan 全屋扫描（iPhone Pro 系列 LiDAR）",
                "- 视觉 SLAM 空间建模（普通摄像头）",
                "- 激光测距仪辅助校准",
                "- 墙面特征自动识别（门窗、管道、电箱）",
                "- 精度报告生成（RMS 误差分析）",
                "",
                "如果您正在使用移动端 App，可以直接打开 AR 扫描功能开始测量。",
            ]
            reply = "\n".join(reply_lines)
            return AgentResponse(
                agent_type="ar_measurement", reply=reply,
                suggestions=suggestions_map["ar_measurement"],
            )

        elif intent in ("floorplans",):
            reply = (
                "户型管理功能可以帮助您查看、保存和修改户型方案。\n\n"
                "您可以在项目中查看已保存的户型平面图，也可以上传新的户型方案。\n"
                "如需帮助，请告诉我具体想对户型做什么操作。"
            )
            return AgentResponse(
                agent_type="floorplans", reply=reply,
                suggestions=suggestions_map["floorplans"],
            )

        elif intent in ("structural",):
            reply = (
                "土建结构模块支持梁、柱、墙、板等结构元素的设计与分析。\n\n"
                "功能包括：结构计算、承重分析、框架设计、剪力墙布置等。\n"
                "请告诉我具体的结构设计需求，我来帮您分析。"
            )
            return AgentResponse(
                agent_type="structural", reply=reply,
                suggestions=suggestions_map["structural"],
            )

        elif intent in ("lighting",):
            reply = (
                "灯光设计模块支持照明方案规划、照度计算和色温推荐。\n\n"
                "功能包括：灯具选型、轨道灯/筒灯/射灯布置、氛围灯光设计。\n"
                "请告诉我您想为哪个房间设计灯光方案。"
            )
            return AgentResponse(
                agent_type="lighting", reply=reply,
                suggestions=suggestions_map["lighting"],
            )

        elif intent in ("smart_home",):
            reply = (
                "智能家居模块支持设备配置、场景联动和 Matter/Zigbee 协议。\n\n"
                "功能包括：智能开关/插座/窗帘电机配置、传感器联动、温控系统。\n"
                "请告诉我您想配置哪种智能设备或场景。"
            )
            return AgentResponse(
                agent_type="smart_home", reply=reply,
                suggestions=suggestions_map["smart_home"],
            )

        elif intent in ("scene_automation",):
            reply = (
                "场景自动化支持创建和编辑智能场景联动规则。\n\n"
                "常用场景：离家模式（关灯关空调）、回家模式（开灯开窗帘）、"
                "睡眠模式（调暗灯光）、会客模式（全屋明亮）。\n"
                "请告诉我您想创建哪种场景。"
            )
            return AgentResponse(
                agent_type="scene_automation", reply=reply,
                suggestions=suggestions_map["scene_automation"],
            )

        elif intent in ("custom_furniture",):
            reply = (
                "定制家具模块支持参数化设计柜体（衣柜、橱柜、书柜等），"
                "自动计算板材用量和价格。\n\n"
                "功能包括：柜体尺寸设计、板材展开面积/投影面积计算、报价生成。\n"
                "请告诉我您想定制什么家具，以及大概尺寸。"
            )
            return AgentResponse(
                agent_type="custom_furniture", reply=reply,
                suggestions=suggestions_map["custom_furniture"],
            )

        elif intent in ("tasks",):
            reply = (
                "任务协调模块支持施工任务的分派、跟踪和管理。\n\n"
                "功能包括：创建施工任务、分派给工人、更新进度、查看任务列表。\n"
                "请告诉我您想创建什么任务，或者查看哪些任务。"
            )
            return AgentResponse(
                agent_type="tasks", reply=reply,
                suggestions=suggestions_map["tasks"],
            )

        elif intent in ("change_orders",):
            reply = (
                "变更管理模块支持工程变更的申请、审批和跟踪。\n\n"
                "功能包括：发起设计变更、提交变更单、审批流程、变更记录查询。\n"
                "请告诉我您想做什么样的变更。"
            )
            return AgentResponse(
                agent_type="change_orders", reply=reply,
                suggestions=suggestions_map["change_orders"],
            )

        elif intent in ("crews",):
            reply = (
                "工程队管理模块支持班组匹配和施工队调度。\n\n"
                "功能包括：查看可选班组、匹配合适施工队、派工调度、施工队评价。\n"
                "请告诉我您的项目阶段和需求，我来帮您匹配合适的施工队。"
            )
            return AgentResponse(
                agent_type="crews", reply=reply,
                suggestions=suggestions_map["crews"],
            )

        elif intent in ("vr_panorama",):
            reply = (
                "VR 全景查看器支持 360° 沉浸式漫游和场景切换。\n\n"
                "功能包括：全屋漫游、热点信息查看、语音讲解播放、VR 头显支持。\n"
                "请打开 VR 全景页面开始体验，或告诉我您想查看哪个场景。"
            )
            return AgentResponse(
                agent_type="vr_panorama", reply=reply,
                suggestions=suggestions_map["vr_panorama"],
            )

        elif intent in ("ai_render",):
            reply = (
                "AI 渲染模块支持 2D/3D 效果图生成和风格迁移。\n\n"
                "功能包括：一键生成效果图、风格切换（现代/北欧/日式/轻奢）、"
                "配色调整、精度设置。\n"
                "请告诉我您想渲染什么内容，以及想要的风格。"
            )
            return AgentResponse(
                agent_type="ai_render", reply=reply,
                suggestions=suggestions_map["ai_render"],
            )

        elif intent in ("sketch_to_3d",):
            reply = (
                "草图转3D 功能可以将手绘草图智能转换为 3D 模型。\n\n"
                "使用方法：\n"
                "1. 上传手绘户型草图或家具设计图\n"
                "2. AI 自动识别轮廓和尺寸比例\n"
                "3. 生成可编辑的 3D 模型\n"
                "请上传您的草图，我来帮您转换成 3D 模型。"
            )
            return AgentResponse(
                agent_type="sketch_to_3d", reply=reply,
                suggestions=suggestions_map["sketch_to_3d"],
            )

        elif intent in ("soft_furnishing",):
            reply = (
                "软装设计模块支持窗帘、布艺、地毯、饰品等软装配饰的选择与搭配。\n\n"
                "功能包括：窗帘款式设计、布艺搭配、装饰画选配、摆件推荐。\n"
                "请告诉我您想为哪个房间搭配软装。"
            )
            return AgentResponse(
                agent_type="soft_furnishing", reply=reply,
                suggestions=suggestions_map["soft_furnishing"],
            )

        elif intent in ("hard_decoration",):
            reply = (
                "硬装设计模块支持吊顶、墙面装饰、地面铺装等硬装方案设计。\n\n"
                "功能包括：吊顶造型设计、背景墙设计、瓷砖/地板/石材选型。\n"
                "请告诉我您想设计哪个区域的硬装。"
            )
            return AgentResponse(
                agent_type="hard_decoration", reply=reply,
                suggestions=suggestions_map["hard_decoration"],
            )

        elif intent in ("takeoff",):
            reply = (
                "工程量计算模块支持材料清单生成和用量估算。\n\n"
                "功能包括：自动计算材料用量、生成辅料清单、工程量统计。\n"
                "请告诉我您需要计算哪些项目的工程量。"
            )
            return AgentResponse(
                agent_type="takeoff", reply=reply,
                suggestions=suggestions_map["takeoff"],
            )

        elif intent in ("points",):
            reply = (
                "积分系统支持积分累计、等级提升和积分兑换。\n\n"
                "功能包括：查看积分余额、积分兑换商品、会员等级权益。\n"
                "您可以通过完成装修任务和参与平台活动获取积分。"
            )
            return AgentResponse(
                agent_type="points", reply=reply,
                suggestions=suggestions_map["points"],
            )

        elif intent in ("cad_import",):
            reply = (
                "CAD 导入模块支持 DXF/DWG 格式的户型图纸导入。\n\n"
                "功能包括：DXF R12/R14 格式支持、LINE/LWPOLYLINE 实体解析、"
                "自动识别墙体结构。\n"
                "请上传您的 CAD 图纸文件，我来帮您导入并解析。"
            )
            return AgentResponse(
                agent_type="cad_import", reply=reply,
                suggestions=suggestions_map["cad_import"],
            )

        else:
            # Unknown intent — fallback to orchestrator general reply
            reply = f"我理解您的问题是关于「{data.message[:40]}...」的。\n\n请告诉我具体需要什么帮助，例如：开始设计、查看预算、浏览材料、施工进度等。"
            suggestions = suggestions_map["orchestrator"]
            return AgentResponse(agent_type="orchestrator", reply=reply, suggestions=suggestions)
    finally:
        await agent.close()


@router.post("/chat/stream")
async def chat_stream(  # noqa: C901
    data: AgentMessage,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Agent 聊天 SSE 流式响应 — 逐句/逐词推送回复"""
    # 校验项目归属
    if data.project_id:
        result = await db.execute(select(Project).where(Project.id == data.project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        if current_user.role != "admin" and project.owner_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")

    # 构建 history 上下文（复用 /chat 逻辑）
    history_ctx = ""
    if data.history:
        recent = data.history[-10:]
        lines = []
        for h in recent:
            role = h.get("role", "user")
            content = h.get("content", "")[:500]
            agent_t = h.get("agent_type", "")
            prefix = f"[{agent_t}] " if agent_t and role == "assistant" else ""
            lines.append(f"{prefix}{role}: {content}")
        history_ctx = "\n".join(lines)
    user_ctx = f"用户: {current_user.name}"
    if history_ctx:
        user_ctx = f"{history_ctx}\n{user_ctx}"

    # Hybrid routing
    agent = OrchestratorAgent()
    try:
        # 若客户端显式指定了 agent_type（非 orchestrator），直接路由到对应 Agent
        explicit_intent = AGENT_TYPE_TO_INTENT.get(data.agent_type)
        if explicit_intent:
            intent = explicit_intent
        else:
            classification = await agent.classify_intent(data.message)
            intent = classification.get("intent", "general")

        # 真流式 Agent：LLM 模式下使用 think_stream() 逐 token 推送
        stream_agent = None
        stream_msg = None
        stream_ctx = None

        # 获取回复文本（与 /chat 相同逻辑）
        if intent in ("content_publish",):
            cp_agent = ContentPublisherAgent()
            try:
                product_intent = ContentPublisherAgent.classify_intent(data.message)
                if product_intent != "create_product" or any(
                    kw in data.message for kw in ["修改", "更新", "下架", "库存", "我的产品", "列表"]
                ):
                    reply = await cp_agent.think(
                        f"供应商 {current_user.name} 请求管理产品：{data.message}", user_ctx
                    )
                else:
                    reply = await cp_agent.generate_content_publish_reply(data.message, current_user.name)
            finally:
                await cp_agent.close()
        elif intent in ("design",):
            des_agent = DesignerAgent()
            try:
                raw_reply = await des_agent.think(data.message, user_ctx)
                reply = _extract_reply_from_llm_json(raw_reply)
                if _looks_like_reasoning_leak(reply) or "稍后重试" in reply or raw_reply.startswith("[mock]"):
                    logger.warning(
                        "designer_reply_leak_stream: falling back to layouts; "
                        "raw_head=%r", raw_reply[:200],
                    )
                    layouts = await des_agent.generate_layouts(data.message)
                    reply = layouts["reply"]
            finally:
                await des_agent.close()
        elif intent in ("budget",):
            stream_agent = BudgetAgent()
            stream_msg = data.message
            stream_ctx = user_ctx
        elif intent in ("procurement",):
            stream_agent = ProcurementAgent()
            stream_msg = data.message
            stream_ctx = user_ctx
        elif intent in ("construction",):
            stream_agent = ConstructionAgent()
            stream_msg = data.message
            stream_ctx = user_ctx
        elif intent in ("settlement",):
            stream_agent = SettlementAgent()
            stream_msg = data.message
            stream_ctx = user_ctx
        elif intent in ("qa_inspector",):
            stream_agent = QAInspectorAgent()
            stream_msg = data.message
            stream_ctx = user_ctx
        elif intent in ("concierge",):
            conc_agent = ConciergeAgent()
            try:
                reply = await conc_agent.generate_response(data.message, f"业主: {current_user.name}")
            finally:
                await conc_agent.close()
        elif intent in ("admin", "user_manage", "platform_stats", "identity_review"):
            stream_agent = AdminAgent()
            stream_msg = data.message
            stream_ctx = user_ctx
        elif intent in ("ar_measurement",):
            # AR 测量引导：与 chat_with_agent 中 ar_measurement 分支保持一致
            reply_lines = [
                "AR 空间测量功能可以帮助您快速测量房间尺寸、墙面面积等数据。",
                "",
                "使用方法：",
                "1. 打开索克家居 App（支持 iOS/Android/鸿蒙）",
                "2. 进入项目后点击「AR 扫描」或「量房」功能",
                "3. 按照指引移动设备扫描房间",
                f"4. 扫描完成后，数据将自动同步到项目 {data.project_id or ''} 中",
                "",
                "支持的功能：",
                "- RoomPlan 全屋扫描（iPhone Pro 系列 LiDAR）",
                "- 视觉 SLAM 空间建模（普通摄像头）",
                "- 激光测距仪辅助校准",
                "- 墙面特征自动识别（门窗、管道、电箱）",
                "- 精度报告生成（RMS 误差分析）",
                "",
                "如果您正在使用移动端 App，可以直接打开 AR 扫描功能开始测量。",
            ]
            reply = "\n".join(reply_lines)
        elif intent in ("floorplans",):
            reply = "户型管理功能可以帮助您查看、保存和修改户型方案。您可以在项目中查看已保存的户型平面图。"
        elif intent in ("structural",):
            reply = "土建结构模块支持梁、柱、墙、板等结构元素的设计与分析。请告诉我具体的结构设计需求。"
        elif intent in ("lighting",):
            reply = "灯光设计模块支持照明方案规划、照度计算和色温推荐。请告诉我您想为哪个房间设计灯光方案。"
        elif intent in ("smart_home",):
            reply = "智能家居模块支持设备配置、场景联动和 Matter/Zigbee 协议。请告诉我您想配置哪种智能设备。"
        elif intent in ("scene_automation",):
            reply = "场景自动化支持创建和编辑智能场景联动规则，如离家模式、回家模式、睡眠模式等。"
        elif intent in ("custom_furniture",):
            reply = "定制家具模块支持参数化设计柜体（衣柜、橱柜、书柜等），自动计算板材用量和价格。"
        elif intent in ("tasks",):
            reply = "任务协调模块支持施工任务的分派、跟踪和管理。请告诉我您想创建或查看什么任务。"
        elif intent in ("change_orders",):
            reply = "变更管理模块支持工程变更的申请、审批和跟踪。请告诉我您想做什么样的变更。"
        elif intent in ("crews",):
            reply = "工程队管理模块支持班组匹配和施工队调度。请告诉我您的项目需求，我来帮您匹配合适的施工队。"
        elif intent in ("vr_panorama",):
            reply = "VR 全景查看器支持 360° 沉浸式漫游和场景切换。请打开 VR 全景页面开始体验。"
        elif intent in ("ai_render",):
            reply = "AI 渲染模块支持 2D/3D 效果图生成和风格迁移。请告诉我您想渲染什么内容。"
        elif intent in ("sketch_to_3d",):
            reply = "草图转3D 功能可以将手绘草图智能转换为 3D 模型。请上传您的草图，我来帮您转换。"
        elif intent in ("soft_furnishing",):
            reply = "软装设计模块支持窗帘、布艺、地毯、饰品等软装配饰的选择与搭配。"
        elif intent in ("hard_decoration",):
            reply = "硬装设计模块支持吊顶、墙面装饰、地面铺装等硬装方案设计。"
        elif intent in ("takeoff",):
            reply = "工程量计算模块支持材料清单生成和用量估算。请告诉我您需要计算哪些项目的工程量。"
        elif intent in ("points",):
            reply = "积分系统支持积分累计、等级提升和积分兑换。您可以通过完成装修任务获取积分。"
        elif intent in ("cad_import",):
            reply = "CAD 导入模块支持 DXF/DWG 格式的户型图纸导入和墙体解析。"
        else:
            reply = f"我理解您的问题是关于「{data.message[:40]}...」的。\n\n请告诉我具体需要什么帮助，例如：开始设计、查看预算、浏览材料、施工进度等。"

        # SSE 流式推送
        async def generate_sse():
            # 先发送 agent_type 元信息
            # 将 intent 反向映射为 agent_type，与非流式接口返回值保持一致
            # （如 intent="design" → agent_type="designer"）
            _intent_to_agent_type = {
                "design": "designer",
                "content_publish": "content_publisher",
                "ar_measurement": "ar_measurement",
                "floorplans": "floorplans",
                "structural": "structural",
                "lighting": "lighting",
                "smart_home": "smart_home",
                "scene_automation": "scene_automation",
                "custom_furniture": "custom_furniture",
                "tasks": "tasks",
                "change_orders": "change_orders",
                "crews": "crews",
                "vr_panorama": "vr_panorama",
                "ai_render": "ai_render",
                "sketch_to_3d": "sketch_to_3d",
                "soft_furnishing": "soft_furnishing",
                "hard_decoration": "hard_decoration",
                "takeoff": "takeoff",
                "points": "points",
                "cad_import": "cad_import",
            }
            agent_type_meta = _intent_to_agent_type.get(intent, intent)
            yield f"data: {json.dumps({'event': 'meta', 'agent_type': agent_type_meta})}\n\n"
            await asyncio.sleep(0.05)

            if stream_agent is not None:
                # 真流式：LLM 逐 token 产出，用户即时看到内容
                try:
                    async for chunk in stream_agent.think_stream(stream_msg, stream_ctx):
                        yield f"data: {json.dumps({'event': 'token', 'content': chunk})}\n\n"
                finally:
                    await stream_agent.close()
            else:
                # 假流式：已获取完整 reply，按句子/词组分块推送（mock 模式 / Designer JSON）
                paragraphs = reply.split("\n\n")
                for p_idx, para in enumerate(paragraphs):
                    if p_idx > 0:
                        yield f"data: {json.dumps({'event': 'token', 'content': chr(10) + chr(10)})}\n\n"
                        await asyncio.sleep(0.1)

                    lines = para.split("\n")
                    for l_idx, line in enumerate(lines):
                        if l_idx > 0:
                            yield f"data: {json.dumps({'event': 'token', 'content': chr(10)})}\n\n"
                            await asyncio.sleep(0.03)

                        sents = line.replace("？", "?\x00").replace("！", "!\x00").replace("。", "。\x00").split("\x00")
                        for sent in sents:
                            sent = sent.strip()
                            if not sent:
                                continue
                            i = 0
                            while i < len(sent):
                                chunk = sent[i:i + 4]
                                i += len(chunk)
                                yield f"data: {json.dumps({'event': 'token', 'content': chunk})}\n\n"
                                await asyncio.sleep(0.03)

            # 发送结束信号
            yield f"data: {json.dumps({'event': 'done'})}\n\n"

        return StreamingResponse(
            generate_sse(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    finally:
        await agent.close()


@router.post("/design", response_model=DesignPlanResponse)
async def request_design(
    data: DesignRequest,
    current_user: User = Depends(get_current_user),
):
    agent = DesignerAgent()
    try:
        msg = data.message
        if data.room_info:
            msg = f"户型信息: {data.room_info}\n\n用户需求: {data.message}"

        layouts = await agent.generate_layouts(msg)

        return DesignPlanResponse(
            space_planning=layouts["reply"],
            style_suggestion=layouts["recommendation"],
            circulation_analysis=" | ".join(layouts["materials"][:2]),
            material_plan="\n".join(layouts["materials"]),
            full_reply=json.dumps(layouts, ensure_ascii=False, indent=2),
        )
    finally:
        await agent.close()


@router.post("/design/circulation")
async def analyze_circulation(
    data: CirculationAnalysisRequest,
    current_user: User = Depends(get_current_user),
):
    """F28 智能布局动线分析：访客/家务/居住三条动线评分 + 冲突检测 + 优化建议"""
    agent = DesignerAgent()
    try:
        return agent.analyze_circulation(data.rooms)
    finally:
        await agent.close()


@router.post("/budget", response_model=BudgetAnalysisResponse)
async def analyze_budget(
    data: AgentMessage,
    current_user: User = Depends(get_current_user),
):
    agent = BudgetAgent()
    try:
        reply = await agent.think(data.message, f"业主: {current_user.name}")
        return BudgetAnalysisResponse(
            summary=reply,
            category_breakdown=reply,
            cost_saving_tips=reply,
            full_reply=reply,
        )
    finally:
        await agent.close()


@router.post("/procurement", response_model=ProcurementAnalysisResponse)
async def analyze_procurement(
    data: AgentMessage,
    current_user: User = Depends(get_current_user),
):
    agent = ProcurementAgent()
    try:
        reply = await agent.think(data.message, f"采购经理: {current_user.name}")
        return ProcurementAnalysisResponse(
            purchase_plan=reply,
            supplier_recommendation=reply,
            timeline=reply,
            full_reply=reply,
        )
    finally:
        await agent.close()


@router.post("/construction", response_model=ConstructionPlanResponse)
async def plan_construction(
    data: AgentMessage,
    current_user: User = Depends(get_current_user),
):
    agent = ConstructionAgent()
    try:
        reply = await agent.think(data.message, f"工长: {current_user.name}")
        return ConstructionPlanResponse(
            phases=reply,
            schedule=reply,
            quality_checklist=reply,
            full_reply=reply,
        )
    finally:
        await agent.close()


@router.post("/construction/publish-tasks")
async def construction_publish_tasks(
    project_id: str,
    sub_roles: list[str] | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """施工 Agent 根据位置和项目信息发布工种任务到任务池"""
    from sqlalchemy import select as sql_select
    from app.models.orchestrator_task import OrchestratorTask
    from app.services import points_service

    # 校验项目归属
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)

    # 获取项目信息
    result = await db.execute(sql_select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    project_info = {
        "project_id": project.id,
        "project_name": project.name,
        "address": project.address or "",
        "project_type": project.project_type,
        "total_area": project.total_area or 0,
    }

    agent = ConstructionAgent()
    try:
        sub_task_data = agent.generate_sub_task_cards(
            project_info=project_info,
            sub_roles=sub_roles,
            location=project.address or None,
        )
    finally:
        await agent.close()

    # 将子任务写入任务池
    created_tasks = []
    for task_data in sub_task_data["tasks"]:
        task = OrchestratorTask(
            project_id=project_id,
            task_type=task_data["task_type"],
            title=task_data["title"],
            description=task_data["description"],
            assigned_agent="construction",
            claimable=True,
            claim_role="contractor",
            priority=7,
            created_by=current_user.id,
            status="pending",
        )
        db.add(task)
        created_tasks.append(task)

    await db.commit()

    # WebSocket 推送任务
    for task in created_tasks:
        await ws_manager.broadcast_to_project(project_id, "task.created", {
            "task_id": task.id,
            "title": task.title,
            "task_type": task.task_type,
            "claim_role": task.claim_role,
            "priority": task.priority,
        })

    # 奖励积分
    await points_service.earn_points(
        db, current_user.id, "product_publish",
        reference_id=project_id,
        description=f"发布工种施工任务: {project.name}",
    )

    return {
        "agent_type": "construction",
        "reply": sub_task_data["reply"],
        "sub_roles": sub_task_data["sub_roles"],
        "tasks_created": len(created_tasks),
        "task_ids": [t.id for t in created_tasks],
    }


# === QA Inspector Agent 端点 ===


@router.post("/qa-inspector/acceptance-report")
async def generate_acceptance_report(
    data: AcceptanceReportRequest,
    current_user: User = Depends(get_current_user),
):
    """生成验收报告（分项验收 + 总体验收结论）"""
    agent = QAInspectorAgent()
    try:
        return agent.generate_acceptance_report(data.model_dump())
    finally:
        await agent.close()


@router.post("/qa-inspector/compare-design")
async def compare_with_design(
    data: CompareDesignRequest,
    current_user: User = Depends(get_current_user),
):
    """照片与设计图纸比对"""
    agent = QAInspectorAgent()
    try:
        return agent.compare_with_design(data.model_dump())
    finally:
        await agent.close()


@router.post("/qa-inspector/defects")
async def detect_defects(
    data: DefectDetectionRequest,
    current_user: User = Depends(get_current_user),
):
    """工艺缺陷识别（mock CV 检测）"""
    agent = QAInspectorAgent()
    try:
        return agent.detect_defects(data.model_dump())
    finally:
        await agent.close()


# === Concierge Agent 端点 ===


@router.post("/concierge/faq")
async def answer_faq(
    data: FAQRequest,
    current_user: User = Depends(get_current_user),
):
    """FAQ 知识问答（基于预置知识库匹配）"""
    agent = ConciergeAgent()
    try:
        return agent.answer_faq(data.question)
    finally:
        await agent.close()


@router.post("/concierge/classify")
async def classify_inquiry(
    data: ClassifyInquiryRequest,
    current_user: User = Depends(get_current_user),
):
    """分类用户咨询（类型 + 紧急度 + 是否需人工）"""
    agent = ConciergeAgent()
    try:
        return agent.classify_inquiry(data.message)
    finally:
        await agent.close()


@router.post("/concierge/chat")
async def concierge_chat(
    data: ConciergeChatRequest,
    current_user: User = Depends(get_current_user),
):
    """生成客服回复（调用真实 LLM）"""
    agent = ConciergeAgent()
    try:
        reply = await agent.generate_response(data.message, data.context)
        return {"agent_type": "concierge", "reply": reply}
    finally:
        await agent.close()


def _mock_agent_reply(message: str, agent_type: str) -> tuple[str, list[str]]:
    kw_map = {
        "设计": "designer",
        "布局": "designer",
        "方案": "designer",
        "户型": "designer",
        "预算": "budget",
        "价格": "budget",
        "费用": "budget",
        "成本": "budget",
        "采购": "procurement",
        "材料": "procurement",
        "建材": "procurement",
        "供应商": "procurement",
        "施工": "construction",
        "进度": "construction",
        "验收": "construction",
        "质检": "construction",
    }
    matched = agent_type
    for kw, at in kw_map.items():
        if kw in message:
            matched = at
            break

    replies = {
        "designer": (
            "🎨 **设计方案**\n\n"
            "根据您的需求，我来为您生成布局方案：\n\n"
            "**主流户型规划**\n"
            "- 客厅+餐厅：开放式布局，南北通透\n"
            "- 主卧+次卧+书房：动静分区\n"
            "- 厨房+卫生间：动线最短原则\n\n"
            "推荐风格：现代简约 / 北欧 / 日式侘寂，可结合家庭成员偏好细化。"
        ),
        "budget": (
            "💰 **预算分析**\n\n"
            "根据您提供的项目信息，我来帮您做个预算框架：\n\n"
            "**装修等级估算**\n"
            "- 经济型（800-1200/㎡）：适合出租/简装\n"
            "- 舒适型（1200-2000/㎡）：推荐自住选择\n"
            "- 品质型（2000-3500/㎡）：品牌材料、定制化\n\n"
            "**分项预算参考**\n"
            "- 硬装（水电+墙面+地面）：约 40-50%\n"
            "- 定制柜体：约 15-20%\n"
            "- 软装+家电：约 30-40%\n\n"
            "建议您先确定装修等级，我可以帮您细化每个分项。"
        ),
        "procurement": (
            "🛒 **采购分析**\n\n"
            "根据项目物料清单，为您规划采购方案：\n\n"
            "**第一阶段（开工前）**\n"
            "- 水电材料：电线、水管、开关暗盒\n"
            "- 防水材料：防水涂料\n\n"
            "**第二阶段（水电后）**\n"
            "- 瓷砖/地板：确认花色和用量\n"
            "- 橱柜方案：复尺后下单\n\n"
            "**第三阶段（油漆后）**\n"
            "- 卫浴洁具安装\n"
            "- 灯具/开关面板安装\n\n"
            "建议按施工进度分批采购，避免过早采购占用资金和空间。"
        ),
        "construction": (
            "🔨 **施工计划**\n\n"
            "标准施工流程共 8 个阶段：\n\n"
            "1. **准备阶段**（2-5天）：办理许可、材料进场\n"
            "2. **拆改阶段**（3-7天）：墙体拆改\n"
            "3. **水电阶段**（5-10天）：管线敷设\n"
            "4. **泥瓦阶段**（7-15天）：防水、贴砖\n"
            "5. **木工阶段**（5-10天）：吊顶、柜体\n"
            "6. **油漆阶段**（7-10天）：墙面处理\n"
            "7. **安装阶段**（5-7天）：灯具、卫浴\n"
            "8. **验收阶段**（2-3天）：全面验收\n\n"
            "预计总工期约 40-60 天。需要我为您的项目生成详细排期吗？"
        ),
        "orchestrator": (
            "您好！我是索克家居的 AI 总控 Agent。\n\n"
            "我可以帮您：\n"
            "🏠 **设计规划** - 智能生成平面布局和效果图\n"
            "💰 **预算管理** - 成本估算和预算跟踪\n"
            "🛒 **物料采购** - BOM 生成、供应商匹配\n"
            "🔨 **施工管理** - 进度跟踪、质检报告\n\n"
            "请告诉我您需要什么帮助？"
        ),
    }

    suggestions = {
        "designer": ["调整方案", "查看材料清单", "不同风格对比"],
        "budget": ["查看明细", "调整预算", "导出报表"],
        "procurement": ["查看供应商", "发起询价", "生成订单"],
        "construction": ["查看进度", "上传日志", "发起验收"],
        "orchestrator": ["开始设计", "查看预算", "浏览材料", "施工进度"],
    }
    return replies.get(matched, replies["orchestrator"]), suggestions.get(matched, suggestions["orchestrator"])


def _mock_budget_summary(message: str) -> str:
    return "根据您的项目信息，预估总预算约 18-25 万元（舒适型装修）。详细分项如下："


def _mock_budget_breakdown() -> str:
    return (
        "**分项预算明细**\n\n"
        "| 项目 | 预估金额 |\n"
        "|------|---------|\n"
        "| 硬装（水电+墙面+地面） | 90,000-110,000 |\n"
        "| 定制柜体（橱柜+衣柜） | 35,000-45,000 |\n"
        "| 软装（家具+窗帘+灯具） | 40,000-50,000 |\n"
        "| 家电设备 | 25,000-35,000 |\n"
        "| 管理费+其他 | 10,000-15,000 |"
    )


def _mock_cost_saving() -> str:
    return (
        "**省钱技巧**\n"
        "1. 瓷砖/地板：工厂直购省 15-20%\n"
        "2. 灯具：线上采购省 30%+\n"
        "3. 窗帘：辅材配件费用容易忽视，注意对比\n"
        "4. 家电：618/双11 批量采购，一套省 3000-5000"
    )


def _mock_purchase_plan() -> str:
    return (
        "**采购计划**\n\n"
        "按施工阶段分批采购，避免资金积压和材料损耗。\n"
        "第一阶段（开工）→ 水电材料\n"
        "第二阶段（水电后）→ 瓷砖、防水\n"
        "第三阶段（泥瓦后）→ 定制柜、门\n"
        "第四阶段（油漆后）→ 卫浴、灯具、家电"
    )


def _mock_supplier_rec() -> str:
    return (
        "**推荐供应商**\n\n"
        "- 瓷砖：东鹏、马可波罗（工厂直发）\n"
        "- 地板：圣象、大自然\n"
        "- 橱柜：欧派、索菲亚\n"
        "- 卫浴：科勒、TOTO\n"
        "- 家电：京东自营/天猫旗舰"
    )


def _mock_procurement_timeline() -> str:
    return "采购周期预计 30-45 天，关键节点：开工前 7 天确认水电材料，开工后 10 天确认瓷砖花色，开工后 20 天橱柜复尺下单。"


def _mock_phases() -> str:
    return (
        "**施工阶段**（总工期约 45 天）\n\n"
        "1. 准备阶段：Day 1-3\n"
        "2. 拆改阶段：Day 4-8\n"
        "3. 水电阶段：Day 9-18\n"
        "4. 泥瓦阶段：Day 19-32\n"
        "5. 木工阶段：Day 26-35（可与泥瓦交叉）\n"
        "6. 油漆阶段：Day 33-40\n"
        "7. 安装阶段：Day 40-43\n"
        "8. 验收阶段：Day 44-45"
    )


def _mock_schedule() -> str:
    return (
        "**关键里程碑**\n\n"
        "✅ Day 3：装修许可 & 材料进场\n"
        "✅ Day 8：拆改完成，垃圾清运\n"
        "✅ Day 18：水电验收（打压测试+线路测试）\n"
        "✅ Day 32：防水闭水试验 & 瓷砖铺贴完成\n"
        "✅ Day 40：油漆完成，等待安装\n"
        "✅ Day 45：竣工验收"
    )


def _mock_settlement() -> str:
    return (
        "⏣ **结算分析**\n\n"
        "根据项目进度，为您梳理结算情况：\n\n"
        "**结算公式**\n"
        "应付金额 = 合同金额 + 变更金额 - 扣款金额 - 已付金额\n\n"
        "**结算里程碑**\n"
        "1. 交房节点：支付 30%（约 50,000-75,000 元）\n"
        "2. 水电验收：支付 20%（约 35,000-50,000 元）\n"
        "3. 泥瓦验收：支付 25%（约 45,000-65,000 元）\n"
        "4. 竣工验收：支付 20%（约 35,000-50,000 元）\n"
        "5. 保修期满：支付 5%（约 8,000-12,500 元）\n\n"
        "建议每阶段验收合格后再付款，保留尾款作为质量保障。"
    )


def _mock_quality() -> str:
    return (
        "**质检检查清单**\n\n"
        "- 水电：水管打压 0.8MPa 半小时不掉压\n"
        "- 防水：闭水试验 48h 无渗漏\n"
        "- 瓷砖：空鼓率 < 5%\n"
        "- 墙面：平整度 2m 靠尺 ≤ 3mm\n"
        "- 木工：柜体对角线偏差 ≤ 2mm\n"
        "- 油漆：无色差、无流坠、无漏刷"
    )


def _mock_qa_inspection() -> str:
    return (
        "🔍 **质检报告**\n\n"
        "**分项验收结果**\n"
        "- 水电工程：合格（5/5 项通过）\n"
        "- 泥瓦工程：有条件合格（4/5 项通过，地漏坡度需调整）\n"
        "- 木工工程：合格（4/4 项通过）\n"
        "- 油漆工程：合格（4/4 项通过）\n"
        "- 安装工程：合格（4/4 项通过）\n\n"
        "**总体验收结论**：合格（合格率 95.5%）\n\n"
        "**整改建议**：\n"
        "1. 卫生间地漏坡度不足，建议重新找坡\n"
        "2. 瓷砖空鼓率检测需复检\n\n"
        "建议整改后复验，确认全部合格后签署验收报告。"
    )


# ── L4 自适应学习：用户反馈收集（PRD §5.4 Phase 5 末项，提前布局）──

class AgentFeedbackRequest(BaseModel):
    """用户对 Agent 回复的反馈"""
    agent_name: str = Field(min_length=1, max_length=50)
    feedback_type: str = Field(pattern="^(like|dislike)$")
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str = Field(default="", max_length=500)
    user_message: str = Field(min_length=1, max_length=2000)
    agent_reply: str = Field(min_length=1, max_length=8000)


@router.post("/feedback", status_code=status.HTTP_201_CREATED)
async def submit_agent_feedback(
    payload: AgentFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """记录用户对 Agent 回复的反馈，用于 L4 自适应学习。

    - feedback_type="like"：正向反馈，BaseAgent.think() 后续会将该轮对话
      作为 few-shot 示例注入到同 agent 的 prompt，提升回复质量
    - feedback_type="dislike"：负向反馈，用于离线分析识别低满意度场景
    """
    import hashlib
    from app.models.agent_feedback import AgentFeedback
    message_hash = hashlib.sha256(payload.user_message.encode()).hexdigest()
    feedback = AgentFeedback(
        user_id=current_user.id,
        agent_name=payload.agent_name,
        message_hash=message_hash,
        feedback_type=payload.feedback_type,
        rating=payload.rating,
        comment=payload.comment or None,
        user_message=payload.user_message,
        agent_reply=payload.agent_reply,
    )
    db.add(feedback)
    await db.commit()
    return {"status": "recorded", "feedback_id": feedback.id, "agent_learning_enabled": settings.agent_learning_enabled}
