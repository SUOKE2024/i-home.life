"""实时语音 WebSocket 端点 —— 对接 Qwen-Audio-3.0-Realtime

提供全双工实时语音交互能力：
- WebSocket 连接 (ws://host/api/voice/realtime?token=xxx)
- 真双工：客户端 ↔ 后端 ↔ Qwen-Audio-3.0-Realtime (WebSocket 桥接)
- 流式语音识别 + 流式音频输出
- FunctionCall 工具自主调用
- 双工打断 (barge-in)
- Mock 模式降级（无 API Key 时可用）
"""

import asyncio
import json
import logging
import re

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.concierge import check_escalation
from app.agents.orchestrator import OrchestratorAgent
from app.auth.paseto_handler import verify_token, TokenExpiredError, TokenInvalidError
from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db, async_session
from app.models.user import User
from app.models.project import Project
from app.services.voice_realtime_service import voice_session_manager, VoiceRealtimeSession
from app.services.agent_tool_registry import tool_registry

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["实时语音"])

# ── 会话实例映射：websocket_id → session ──
_active_voice_ws: dict[int, VoiceRealtimeSession] = {}

# ── 索克家居语音助手系统指令 ──
VOICE_SYSTEM_INSTRUCTIONS = (
    "你是索克生活 APP 的智能语音助手，专注于装修、家居和设计领域。"
    "你可以帮助用户进行：装修预算分析、设计方案推荐、物料搜索、施工进度查询、质量检测。"
    "当用户提出与装修相关的问题时，主动调用合适的工具获取信息。"
    "保持友好、专业的语气。如果用户情绪低落，给予适当的安慰和帮助。"
    "所有价格以人民币计价，所有工期以工作日为准。"
)

# Qwen-Audio-3.0-Realtime Plus 增强指令（启用情感感知 + 副语言）
VOICE_SYSTEM_INSTRUCTIONS_PLUS = (
    VOICE_SYSTEM_INSTRUCTIONS
    + "你使用 Qwen-Audio-3.0-Realtime Plus 模型，支持情感感知生成与副语言信息处理。"
    "请根据用户语气动态调整回复的韵律、停顿和情感表达，"
    "在用户语气焦急时简化回复、加快动作；在用户分享喜悦时给予积极回应。"
    "能够识别笑声、叹息、犹豫等非语言信号并适当回应。"
)


class VoiceTextRequest(BaseModel):
    """语音文本处理请求"""
    text: str = Field(min_length=1, max_length=2000)
    project_id: str | None = None
    emotion_enabled: bool = True


class VoiceTextResponse(BaseModel):
    """语音文本处理响应"""
    transcript: str
    intent: str = "general"
    reply: str
    emotion: dict | None = None
    actions: list[dict] = []
    tool_calls: list[dict] = []
    need_escalation: bool = False


# ── REST 端点：文本语音处理 ──

@router.post("/process-enhanced", response_model=VoiceTextResponse)
async def process_voice_enhanced(
    data: VoiceTextRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """增强版语音文本处理：情绪检测 + Agent 路由 + 自动工具调用

    相比 /voice/process，新增：
    - 用户情绪检测
    - 自动工具调用 (FunctionCall)
    - 是否需要人工升级判断
    """
    # 校验项目归属（若指定了 project_id），防止越权发起会话
    if data.project_id:
        result = await db.execute(select(Project).where(Project.id == data.project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        if current_user.role != "admin" and project.owner_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")

    text = data.text

    # 1. 情绪检测
    emotion = None
    if data.emotion_enabled and settings.voice_emotion_detection:
        session = voice_session_manager.create_session(user_id=current_user.id, project_id=data.project_id)
        try:
            await session.connect()
            emotion = await session._detect_emotion_from_text(text)
        finally:
            await session.close()

    # 2. 意图分类
    intent = "general"
    if not settings.deepseek_api_key and not settings.glm_api_key:
        classification = OrchestratorAgent.fallback_classify(text)
    else:
        agent = OrchestratorAgent()
        try:
            # classify_intent 内部已对 LLM 失败做 fallback 到 fallback_classify
            classification = await agent.classify_intent(text)
        finally:
            await agent.close()
    intent = classification.get("intent", "general")

    # 3. 路由到专业 Agent 管道（修复语音→Agent 断点）
    reply = ""
    tool_calls = []
    actions = []

    if intent != "general":
        try:
            reply = await _route_voice_to_agent(text, intent, current_user.name, emotion=emotion)
        except Exception as e:
            logger.warning(f"route_voice_to_agent_failed: intent={intent}, error={e}")
            # 降级：硬编码工具调用 + 模板回复
            if settings.agent_function_call_enabled:
                tool_calls = await _auto_tool_call(intent, text)
                if tool_calls:
                    reply = _format_tool_results(intent, tool_calls)
            if not reply:
                reply = _get_enhanced_reply(text, intent, emotion)
    else:
        reply = _get_enhanced_reply(text, intent, emotion)

    # 4. 升级判断
    need_escalation = False
    if settings.voice_duplex_mode:
        esc_result = check_escalation(text)
        need_escalation = esc_result.get("need_human", False)

    return VoiceTextResponse(
        transcript=text,
        intent=intent,
        reply=reply,
        emotion=emotion,
        actions=actions,
        tool_calls=tool_calls,
        need_escalation=need_escalation,
    )


# ── Agent 管道路由（修复语音→Agent 断点） ──

def _get_emotion_aware_system_prefix(emotion: dict | None) -> str:
    """根据用户情绪生成 Agent 系统指令前缀。

    Qwen-Audio-3.0-Realtime Plus 支持情感感知生成，但需要在 instructions 中
    显式提示 Agent 根据情绪调整语气。情绪路由层在意图路由之前生效。
    """
    if not emotion:
        return ""
    label = emotion.get("label", "neutral")
    score = float(emotion.get("score", 0))
    if score < 0.4:
        return ""  # 置信度低，不注入
    prefixes = {
        "anxious": "【用户情绪：焦虑】请用温和、安抚的语气，先确认用户需求再给出方案，避免一次性输出过多信息。",
        "angry": "【用户情绪：不满】请用专业、歉意的语气，先承认问题再提供解决方案，避免推诿。",
        "sad": "【用户情绪：低落】请用温暖、共情的语气，适度使用安慰性语言。",
        "tired": "【用户情绪：疲惫】请简化回复，突出关键信息，避免长篇大论。",
        "excited": "【用户情绪：兴奋】请用热情、积极的语气回应，与用户情绪共振。",
        "happy": "【用户情绪：愉悦】请用轻松、明快的语气回应。",
        "neutral": "",
    }
    return prefixes.get(label, "")


async def _route_voice_to_agent(  # noqa: C901
    text: str,
    intent: str,
    user_name: str,
    context: str = "",
    emotion: dict | None = None,
) -> str:
    """将语音意图路由到专业 Agent 管道，获取 LLM 驱动的回复。

    替代原有的 _auto_tool_call() + _get_enhanced_reply() 硬编码模板，
    使语音路径享有与文本路径同等的 Agent 推理能力。

    Args:
        text: 用户文本
        intent: 意图分类结果
        user_name: 用户名（用于上下文）
        context: 可选的对话历史上下文

    Returns:
        LLM 生成的专业回复文本
    """
    from app.agents.designer import DesignerAgent
    from app.agents.budget import BudgetAgent
    from app.agents.procurement import ProcurementAgent
    from app.agents.construction import ConstructionAgent
    from app.agents.qa_inspector import QAInspectorAgent
    from app.agents.settlement import SettlementAgent
    from app.agents.concierge import ConciergeAgent

    user_ctx = f"用户: {user_name}"
    if context:
        user_ctx = f"{context}\n{user_ctx}"
    # 情绪路由层：在意图路由之前注入情绪感知系统指令前缀
    emotion_prefix = _get_emotion_aware_system_prefix(emotion)
    if emotion_prefix:
        user_ctx = f"{emotion_prefix}\n{user_ctx}" if user_ctx else emotion_prefix
    mock_mode = not settings.deepseek_api_key and not settings.glm_api_key

    # ── design ──
    if intent in ("design",):
        agent = DesignerAgent()
        try:
            if mock_mode:
                layouts = await agent.generate_layouts(text)
                reply = layouts.get("reply", _get_enhanced_reply(text, intent, None))
            else:
                raw_reply = await agent.think(text, user_ctx)
                from app.api.agents import _extract_reply_from_llm_json
                reply = _extract_reply_from_llm_json(raw_reply)
        finally:
            await agent.close()
        return reply

    # ── budget ──
    if intent in ("budget",):
        agent = BudgetAgent()
        try:
            if mock_mode:
                reply = _get_enhanced_reply(text, intent, None)
            else:
                result = await agent.think_with_tools(text, user_ctx)
                reply = result.get("final_reply", _get_enhanced_reply(text, intent, None))
        finally:
            await agent.close()
        return reply

    # ── procurement ──
    if intent in ("procurement",):
        agent = ProcurementAgent()
        try:
            if mock_mode:
                reply = _get_enhanced_reply(text, intent, None)
            else:
                result = await agent.think_with_tools(text, user_ctx)
                reply = result.get("final_reply", _get_enhanced_reply(text, intent, None))
        finally:
            await agent.close()
        return reply

    # ── construction ──
    if intent in ("construction",):
        agent = ConstructionAgent()
        try:
            if mock_mode:
                reply = _get_enhanced_reply(text, intent, None)
            else:
                result = await agent.think_with_tools(text, user_ctx)
                reply = result.get("final_reply", _get_enhanced_reply(text, intent, None))
        finally:
            await agent.close()
        return reply

    # ── qa_inspector ──
    if intent in ("qa_inspector",):
        agent = QAInspectorAgent()
        try:
            if mock_mode:
                reply = _get_enhanced_reply(text, intent, None)
            else:
                reply = await agent.think(text, user_ctx)
        finally:
            await agent.close()
        return reply

    # ── settlement ──
    if intent in ("settlement",):
        agent = SettlementAgent()
        try:
            if mock_mode:
                reply = _get_enhanced_reply(text, intent, None)
            else:
                reply = await agent.think(text, user_ctx)
        finally:
            await agent.close()
        return reply

    # ── concierge ──
    if intent in ("concierge",):
        agent = ConciergeAgent()
        try:
            if mock_mode:
                reply = agent.answer_faq(text)
            else:
                reply = await agent.generate_response(text, user_ctx)
        finally:
            await agent.close()
        return reply

    # ── ar_measurement ──
    if intent in ("ar_measurement",):
        return (
            "AR 空间测量功能需要在移动端 App 上使用。请打开索克家居 App，"
            "进入项目后点击「AR 扫描」即可开始测量。支持 RoomPlan 全屋扫描、"
            "激光测距仪辅助校准和墙面特征自动识别。"
        )

    # ── 新增业务模块（引导回复，后续可接入实际 Service） ──
    if intent in ("floorplans",):
        return "户型管理功能可以帮助您查看、保存和修改户型方案。您可以在项目中查看已保存的户型平面图。"
    if intent in ("structural",):
        return "土建结构模块支持梁、柱、墙、板等结构元素的设计与分析。请告诉我具体的结构设计需求。"
    if intent in ("lighting",):
        return "灯光设计模块支持照明方案规划、照度计算和色温推荐。请告诉我您想为哪个房间设计灯光方案。"
    if intent in ("smart_home",):
        return "智能家居模块支持设备配置、场景联动和 Matter/Zigbee 协议。请告诉我您想配置哪种智能设备。"
    if intent in ("scene_automation",):
        return "场景自动化支持创建和编辑智能场景联动规则，如离家模式、回家模式、睡眠模式等。"
    if intent in ("custom_furniture",):
        return "定制家具模块支持参数化设计柜体（衣柜、橱柜、书柜等），自动计算板材用量和价格。"
    if intent in ("tasks",):
        return "任务协调模块支持施工任务的分派、跟踪和管理。请告诉我您想创建或查看什么任务。"
    if intent in ("change_orders",):
        return "变更管理模块支持工程变更的申请、审批和跟踪。请告诉我您想做什么样的变更。"
    if intent in ("crews",):
        return "工程队管理模块支持班组匹配和施工队调度。请告诉我您的项目需求，我来帮您匹配合适的施工队。"
    if intent in ("vr_panorama",):
        return "VR 全景查看器支持 360° 沉浸式漫游和场景切换。请打开 VR 全景页面开始体验。"
    if intent in ("ai_render",):
        return "AI 渲染模块支持 2D/3D 效果图生成和风格迁移。请告诉我您想渲染什么内容。"
    if intent in ("sketch_to_3d",):
        return "草图转3D 功能可以将手绘草图智能转换为 3D 模型。请上传您的草图，我来帮您转换。"
    if intent in ("soft_furnishing",):
        return "软装设计模块支持窗帘、布艺、地毯、饰品等软装配饰的选择与搭配。"
    if intent in ("hard_decoration",):
        return "硬装设计模块支持吊顶、墙面装饰、地面铺装等硬装方案设计。"
    if intent in ("takeoff",):
        return "工程量计算模块支持材料清单生成和用量估算。请告诉我您需要计算哪些项目的工程量。"
    if intent in ("points",):
        return "积分系统支持积分累计、等级提升和积分兑换。您可以通过完成装修任务获取积分。"
    if intent in ("cad_import",):
        return "CAD 导入模块支持 DXF/DWG 格式的户型图纸导入和墙体解析。"

    # ── general / 其他 ──
    return _get_enhanced_reply(text, intent, None)


# ── 原有辅助函数（保留用于降级和特殊情况） ──

async def _auto_tool_call(intent: str, text: str) -> list[dict]:
    """根据意图自动选择并执行工具调用"""
    results = []

    # 解析文本中的关键参数
    area_match = re.search(r"(\d+)\s*[平㎡m²]", text)
    area = float(area_match.group(1)) if area_match else 0

    style_map = {
        "现代": "modern", "简约": "modern", "北欧": "nordic",
        "日式": "japanese", "轻奢": "luxury", "中式": "chinese",
    }
    style = next((v for k, v in style_map.items() if k in text), "")

    try:
        if intent == "budget" and area > 0:
            result = await tool_registry.execute("get_budget", {"area": area, "style": style})
            results.append({"tool": "get_budget", "result": result})
        elif intent == "design" and area > 0:
            result = await tool_registry.execute("get_design_layout", {"area": area, "style": style or "modern"})
            results.append({"tool": "get_design_layout", "result": result})
        elif intent == "procurement":
            for kw in ["瓷砖", "地板", "涂料"]:
                if kw in text:
                    result = await tool_registry.execute("search_materials", {"keyword": kw})
                    results.append({"tool": "search_materials", "result": result})
                    break
        elif intent == "construction":
            result = await tool_registry.execute("get_construction_progress", {})
            results.append({"tool": "get_construction_progress", "result": result})
        elif intent == "qa_inspector":
            result = await tool_registry.execute("run_qa_inspection", {"phase": "all"})
            results.append({"tool": "run_qa_inspection", "result": result})
    except Exception as e:
        logger.warning(f"auto_tool_call_error: intent={intent}, error={e}")

    return results


def _format_tool_results(intent: str, tool_calls: list[dict]) -> str:
    """格式化工具调用结果为自然语言回复"""
    if not tool_calls:
        return ""

    parts = []
    for tc in tool_calls:
        tool_name = tc["tool"]
        result = tc.get("result", {})

        if tool_name == "get_budget":
            tiers = result.get("tiers", {})
            comfort = tiers.get("comfort", {})
            parts.append(
                f"💰 **预算分析**\n\n"
                f"舒适型装修预估：{comfort.get('total_estimate', 'N/A')} 元\n\n"
                f"分项明细：\n"
            )
            for k, v in comfort.get("breakdown", {}).items():
                parts.append(f"- {k}：约 {v} 元")

        elif tool_name == "get_design_layout":
            parts.append(
                f"🎨 **设计方案**\n\n"
                f"风格：{result.get('style', '')}\n"
                f"配色：{', '.join(result.get('color_palette', []))}\n"
                f"特点：{', '.join(result.get('design_features', []))}\n"
                f"预估工期：{result.get('estimated_duration_days', 45)} 天"
            )

        elif tool_name == "search_materials":
            results = result.get("results", [])
            parts.append(f"🛒 **物料搜索结果**（共 {result.get('total', 0)} 条）\n")
            for r in results[:3]:
                parts.append(f"- {r['name']} | {r.get('price', '')} | 评分 {r.get('rating', '')}")

        elif tool_name == "get_construction_progress":
            parts.append(
                f"🔨 **施工进度**\n\n"
                f"整体进度：{result.get('overall_progress', 0)}%\n"
                f"预计剩余：{result.get('estimated_remaining_days', 0)} 天"
            )

        elif tool_name == "run_qa_inspection":
            parts.append(
                f"🔍 **质检结果**\n\n"
                f"合格率：{result.get('pass_rate', 0)}%\n"
                f"通过/总计：{result.get('passed', 0)}/{result.get('total_items', 0)}\n"
                f"结论：{result.get('conclusion', '')}"
            )

    return "\n\n".join(parts) if parts else "工具调用已完成，以上是分析结果。"


def _get_enhanced_reply(text: str, intent: str, emotion: dict | None) -> str:
    """生成增强版回复（含情绪感知）"""
    emotion_label = emotion.get("label", "neutral") if emotion else "neutral"

    replies = {
        "design": "收到设计需求，正在为您分析户型并生成布局方案...",
        "budget": "正在为您进行预算分析，请稍候...",
        "procurement": "正在搜索匹配的物料和供应商...",
        "construction": "正在查询施工进度和质检状态...",
        "qa_inspector": "正在执行质量检测，请稍候...",
        "concierge": "您好，我是索克家居 AI 客服，请问有什么可以帮您？",
        "general": "收到您的消息，我是索克家居 AI 助手，可以帮您进行设计、预算、采购、施工管理。",
    }

    base_reply = replies.get(intent, replies["general"])

    # 根据情绪调整回复语气
    if emotion_label in ("anxious", "angry", "sad", "tired"):
        prefix = "理解您的心情，我马上帮您处理。"
        return f"{prefix}\n\n{base_reply}"

    return base_reply


# ── Realtime 事件转发 ──

async def _qwen_events_to_client(  # noqa: C901
    websocket: WebSocket,
    session: VoiceRealtimeSession,
    user_id: str,
) -> None:
    """后台任务：接收 Qwen-Audio Realtime 事件并转发给客户端。

    处理的事件类型：
    - 转写: response.audio_transcript.delta / .done
    - 音频输出: response.audio.delta / .done
    - 语音活动: input_audio_buffer.speech_started / .stopped
    - 工具调用: response.function_call_arguments.done → 执行 → 写回
    - 响应生命周期: response.done, error
    """
    try:
        async for event in session.receive_events():
            event_type = event.get("type", "")

            # ── 转写事件 ──
            if event_type == "response.audio_transcript.delta":
                await websocket.send_json({
                    "type": "transcript_delta",
                    "text": event.get("delta", ""),
                })

            elif event_type == "response.audio_transcript.done":
                await websocket.send_json({
                    "type": "transcript_done",
                    "text": event.get("transcript", ""),
                    "is_final": True,
                })

            # ── 音频输出事件 ──
            elif event_type == "response.audio.delta":
                await websocket.send_json({
                    "type": "audio_delta",
                    "data": event.get("delta", ""),
                })

            elif event_type == "response.audio.done":
                await websocket.send_json({"type": "audio_done"})

            # ── 语音活动事件（用于双工打断） ──
            elif event_type == "input_audio_buffer.speech_started":
                await websocket.send_json({"type": "speech_started"})

            elif event_type == "input_audio_buffer.speech_stopped":
                await websocket.send_json({"type": "speech_stopped"})

            # ── 工具调用事件 ──
            elif event_type == "response.function_call_arguments.done":
                call_id = event.get("call_id", "")
                func_name = event.get("name", "")
                try:
                    args = json.loads(event.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}

                try:
                    result = await tool_registry.execute(func_name, args)
                    await websocket.send_json({
                        "type": "tool_call",
                        "name": func_name,
                        "arguments": args,
                        "result": result,
                    })
                    await session.send_function_call_output(call_id, result)
                except Exception as e:
                    logger.error(f"tool_execute_error: {func_name}: {e}")
                    await session.send_function_call_output(
                        call_id, {"error": f"工具执行失败: {e}"}
                    )

            # ── 响应完成 ──
            elif event_type == "response.done":
                await websocket.send_json({
                    "type": "response_done",
                    "usage": event.get("response", {}).get("usage", {}),
                })

            # ── 错误 ──
            elif event_type == "error":
                error_info = event.get("error", event)
                await websocket.send_json({
                    "type": "error",
                    "message": str(error_info.get("message", error_info)),
                    "code": error_info.get("code", "unknown"),
                })

            # ── 其他事件 ──
            elif event_type in ("session.created", "session.updated"):
                logger.debug(f"voice_realtime: {event_type}")
            elif event_type in (
                "conversation.item.created",
                "response.created",
                "response.output_item.added",
                "response.content_part.added",
                "response.content_part.done",
                "response.output_item.done",
                "input_audio_buffer.committed",
                "conversation.item.input_audio_transcription.delta",
                "conversation.item.input_audio_transcription.completed",
            ):
                # 内部事件，仅日志
                pass

    except Exception as e:
        logger.info(f"qwen_events_to_client 结束: user={user_id}, reason={e}")


# ── Mock 模式处理 ──

async def _handle_mock_audio(
    websocket: WebSocket,
    session: VoiceRealtimeSession,
    audio_data: bytes,
    audio_format: str,
) -> None:
    """Mock 模式下的音频处理（ASR → 意图分类 → 工具调用 → TTS）"""
    transcript = await session.transcribe(audio_data, audio_format)

    await websocket.send_json({
        "type": "transcript",
        "text": transcript["text"],
        "is_final": transcript.get("is_final", True),
        "confidence": transcript.get("confidence", 0),
    })

    if settings.voice_emotion_detection:
        emotion = await session.detect_emotion_from_audio(audio_data)
        await websocket.send_json({"type": "emotion", "data": emotion})

    text = transcript["text"]
    if text and transcript.get("is_final"):
        session.add_to_context("user", text)
        intent_result = OrchestratorAgent.fallback_classify(text)
        intent_name = intent_result.get("intent", "general")

        # 路由到专业 Agent 管道（修复语音→Agent 断点）
        # 传递语音会话上下文，实现跨轮次对话记忆
        voice_context = ""
        if session._conversation_context:
            ctx_lines = []
            for c in session._conversation_context[-10:]:
                ctx_lines.append(f"{c.get('role', 'user')}: {c.get('content', '')[:500]}")
            voice_context = "\n".join(ctx_lines)
        try:
            reply = await _route_voice_to_agent(
                text, intent_name, "user", voice_context,
                emotion=transcript.get("emotion"),
            )
        except Exception as e:
            logger.warning(f"mock_agent_route_failed: intent={intent_name}, error={e}")
            # 降级：硬编码工具调用 + 模板回复
            if settings.agent_function_call_enabled and intent_name != "general":
                tool_results = await _auto_tool_call(intent_name, text)
                for tr in tool_results:
                    await websocket.send_json({
                        "type": "tool_call",
                        "name": tr["tool"],
                        "result": tr["result"],
                    })
            reply = _get_enhanced_reply(text, intent_name, transcript.get("emotion"))
        session.add_to_context("assistant", reply, intent_name)

        audio_response = None
        if settings.qwen_audio_api_key:
            audio_response = await session.synthesize_speech(reply)
            if audio_response:
                audio_response = audio_response.hex()

        await websocket.send_json({
            "type": "reply",
            "text": reply,
            "intent": intent_name,
            "audio": audio_response,
        })

        esc = check_escalation(text)
        if esc.get("need_human"):
            await websocket.send_json({
                "type": "escalation",
                "reason": esc.get("reason", ""),
                "urgency": esc.get("urgency", "low"),
            })


# ── WebSocket 端点：实时语音双工会话 ──

@router.websocket("/realtime")
async def voice_realtime_websocket(websocket: WebSocket):  # noqa: C901
    """实时语音双工会话 WebSocket 端点

    协议（Realtime 模式）：
    - 客户端发送 JSON:
      {"type": "audio", "data": "<base64_pcm16>", "format": "pcm16"}
      {"type": "audio_end"}                          # 提交音频缓冲区
      {"type": "text", "content": "..."}              # 文本输入
      {"type": "interrupt"}                           # 打断当前响应
      {"type": "ping"}                                # 心跳
      {"type": "get_emotion_trend"}                   # 获取情绪趋势
    - 服务端推送 JSON:
      {"type": "connected", "session_id": "...", "mode": "realtime|mock"}
      {"type": "transcript_delta", "text": "..."}     # 流式转写
      {"type": "transcript_done", "text": "...", "is_final": true}
      {"type": "audio_delta", "data": "<base64>"}     # 流式音频
      {"type": "audio_done"}
      {"type": "speech_started"}                       # 用户开始说话
      {"type": "speech_stopped"}                       # 用户停止说话
      {"type": "tool_call", "name": "...", "result": {...}}  # FunctionCall
      {"type": "response_done", "usage": {...}}
      {"type": "emotion_trend", "data": {...}}
      {"type": "error", "message": "..."}
    """
    # 认证
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="缺少认证令牌")
        return

    try:
        payload = verify_token(token)
    except (TokenExpiredError, TokenInvalidError):
        await websocket.close(code=4001, reason="令牌无效或已过期")
        return

    user_id = payload.get("sub")
    user_role = payload.get("role", "homeowner")
    project_id = websocket.query_params.get("project_id")

    if not user_id:
        await websocket.close(code=4001, reason="令牌格式无效")
        return

    # ── 项目归属校验: 若指定 project_id 必须验证用户对该项目的访问权限 ──
    if project_id:
        async with async_session() as db:
            result = await db.execute(select(Project).where(Project.id == project_id))
            project = result.scalar_one_or_none()
            if not project:
                await websocket.close(code=4004, reason="项目不存在")
                return
            if user_role != "admin" and project.owner_id != user_id:
                await websocket.close(code=4003, reason="无权访问此项目")
                return

    await websocket.accept()

    # 创建并连接会话
    session = voice_session_manager.create_session(user_id, project_id)
    conn_result = await session.connect()
    is_realtime = conn_result.get("mode") == "realtime"

    ws_id = id(websocket)
    _active_voice_ws[ws_id] = session

    # ── Realtime 模式：初始化会话 + 启动后台事件转发 ──
    qwen_task: asyncio.Task | None = None
    if is_realtime:
        await session.init_realtime_session(
            tools=tool_registry.get_qwen_schemas(),
            instructions=(
                VOICE_SYSTEM_INSTRUCTIONS_PLUS
                if settings.qwen_audio_model.endswith("-plus")
                else VOICE_SYSTEM_INSTRUCTIONS
            ),
        )
        qwen_task = asyncio.create_task(
            _qwen_events_to_client(websocket, session, user_id)
        )

    try:
        # 发送欢迎消息
        await websocket.send_json({
            "type": "connected",
            "session_id": session._session_id,
            "mode": conn_result.get("mode", "mock"),
            "emotion_enabled": settings.voice_emotion_detection,
            "duplex_enabled": settings.voice_duplex_mode,
            "tool_call_enabled": settings.agent_function_call_enabled,
        })

        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type", "")

            # ── 音频输入 ──
            if msg_type == "audio":
                audio_b64 = msg.get("data", "")
                audio_format = msg.get("format", "pcm16")

                if is_realtime:
                    # 真双工：直接转发音频到 Qwen-Audio Realtime
                    await session.send_input_audio_buffer_append(audio_b64)
                else:
                    # Mock/降级模式
                    try:
                        audio_data = bytes.fromhex(audio_b64) if audio_b64 else b""
                    except (ValueError, TypeError):
                        audio_data = (
                            audio_b64.encode()
                            if isinstance(audio_b64, str) else audio_b64
                        )
                    await _handle_mock_audio(websocket, session, audio_data, audio_format)

            # ── 音频结束标记 ──
            elif msg_type == "audio_end":
                if is_realtime:
                    await session.send_input_audio_buffer_commit()

            # ── 打断 ──
            elif msg_type == "interrupt":
                if is_realtime:
                    await session.send_response_cancel()
                    await session.send_input_audio_buffer_clear()
                    await websocket.send_json({"type": "interrupt_ack"})

            # ── 文本输入 ──
            elif msg_type == "text":
                text = msg.get("content", "")
                if is_realtime:
                    await session.send_text_input(text)
                else:
                    # Mock 模式文本处理
                    session.add_to_context("user", text)
                    intent = OrchestratorAgent.fallback_classify(text)
                    intent_name = intent.get("intent", "general")
                    reply = _get_enhanced_reply(text, intent_name, None)
                    session.add_to_context("assistant", reply, intent_name)
                    await websocket.send_json({
                        "type": "reply",
                        "text": reply,
                        "intent": intent_name,
                    })

            # ── 心跳 ──
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            # ── 情绪趋势查询 ──
            elif msg_type == "get_emotion_trend":
                trend = session.get_emotion_trend()
                await websocket.send_json({
                    "type": "emotion_trend",
                    "data": trend,
                })

    except WebSocketDisconnect:
        logger.info(f"voice_ws_disconnect: user={user_id}")
    except Exception as e:
        logger.error(f"voice_ws_error: user={user_id}, error={e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        # 取消后台任务
        if qwen_task and not qwen_task.done():
            qwen_task.cancel()
            try:
                await qwen_task
            except asyncio.CancelledError:
                pass
        _active_voice_ws.pop(ws_id, None)
        await session.close()
