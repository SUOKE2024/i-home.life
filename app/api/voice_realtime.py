"""实时语音 WebSocket 端点 —— 对接 Qwen-Audio-3.0-Realtime

提供全双工实时语音交互能力：
- WebSocket 连接 (ws://host/api/voice/realtime/{session_id}?token=xxx)
- 流式语音识别 + 情感检测
- Agent 意图分类 + 工具调用
- 流式 TTS 语音合成
"""

import asyncio
import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel, Field

from app.auth.paseto_handler import verify_token, TokenExpiredError, TokenInvalidError
from app.config import get_settings
from app.services.voice_realtime_service import voice_session_manager, VoiceRealtimeSession
from app.services.agent_tool_registry import tool_registry
from app.agents.orchestrator import OrchestratorAgent
from app.agents.concierge import ConciergeAgent

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["实时语音"])

# ── 会话实例映射：websocket_id → session ──
_active_voice_ws: dict[int, VoiceRealtimeSession] = {}


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
):
    """增强版语音文本处理：情绪检测 + Agent 路由 + 自动工具调用

    相比 /voice/process，新增：
    - 用户情绪检测
    - 自动工具调用 (FunctionCall)
    - 是否需要人工升级判断
    """
    text = data.text

    # 1. 情绪检测
    emotion = None
    if data.emotion_enabled and settings.voice_emotion_detection:
        session = voice_session_manager.create_session(user_id="api", project_id=data.project_id)
        try:
            await session.connect()
            emotion = await session._detect_emotion_from_text(text)
        finally:
            await session.close()

    # 2. 意图分类
    intent = "general"
    from app.agents.orchestrator import OrchestratorAgent
    if not settings.deepseek_api_key and not settings.glm_api_key:
        classification = OrchestratorAgent.fallback_classify(text)
    else:
        agent = OrchestratorAgent()
        try:
            classification = await agent.classify_intent(text)
        finally:
            await agent.close()
    intent = classification.get("intent", "general")

    # 3. 自动工具调用
    tool_calls = []
    reply = ""
    actions = []

    if settings.agent_function_call_enabled and intent != "general":
        tool_calls = await _auto_tool_call(intent, text)
        if tool_calls:
            reply = _format_tool_results(intent, tool_calls)
        else:
            reply = _get_enhanced_reply(text, intent, emotion)
    else:
        reply = _get_enhanced_reply(text, intent, emotion)

    # 4. 升级判断
    need_escalation = False
    if settings.voice_duplex_mode:
        from app.agents.concierge import check_escalation
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


async def _auto_tool_call(intent: str, text: str) -> list[dict]:
    """根据意图自动选择并执行工具调用"""
    results = []

    # 解析文本中的关键参数
    import re

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


# ── WebSocket 端点：实时语音双工会话 ──

@router.websocket("/realtime")
async def voice_realtime_websocket(websocket: WebSocket):
    """实时语音双工会话 WebSocket 端点

    协议：
    - 客户端发送 JSON: {"type": "audio", "data": "<base64>", "format": "pcm16"}
    - 服务端推送 JSON:
      {"type": "transcript", "text": "...", "is_final": true}
      {"type": "emotion", "data": {...}}
      {"type": "reply", "text": "...", "audio": "<base64_wav>"}
      {"type": "tool_call", "name": "...", "result": {...}}
      {"type": "escalation", "reason": "..."}
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
    project_id = websocket.query_params.get("project_id")

    if not user_id:
        await websocket.close(code=4001, reason="令牌格式无效")
        return

    await websocket.accept()

    # 创建会话
    session = voice_session_manager.create_session(user_id, project_id)
    await session.connect()

    ws_id = id(websocket)
    _active_voice_ws[ws_id] = session

    try:
        # 发送欢迎消息
        await websocket.send_json({
            "type": "connected",
            "session_id": session._session_id,
            "mode": "realtime" if settings.qwen_audio_api_key else "mock",
            "emotion_enabled": settings.voice_emotion_detection,
            "duplex_enabled": settings.voice_duplex_mode,
            "tool_call_enabled": settings.agent_function_call_enabled,
        })

        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type", "")

            if msg_type == "audio":
                # 收到音频数据 → ASR
                audio_b64 = msg.get("data", "")
                try:
                    audio_data = bytes.fromhex(audio_b64) if audio_b64 else b""
                except (ValueError, TypeError):
                    audio_data = audio_b64.encode() if isinstance(audio_b64, str) else audio_b64

                # ASR 转写
                transcript = await session.transcribe(audio_data, msg.get("format", "pcm16"))

                await websocket.send_json({
                    "type": "transcript",
                    "text": transcript["text"],
                    "is_final": transcript.get("is_final", True),
                    "confidence": transcript.get("confidence", 0),
                })

                # 情绪检测
                if settings.voice_emotion_detection:
                    emotion = await session.detect_emotion_from_audio(audio_data)
                    await websocket.send_json({
                        "type": "emotion",
                        "data": emotion,
                    })

                # 意图处理
                text = transcript["text"]
                if text and transcript.get("is_final"):
                    # 添加到上下文
                    session.add_to_context("user", text)

                    # 意图分类
                    intent = OrchestratorAgent.fallback_classify(text)
                    intent_name = intent.get("intent", "general")

                    # 自动工具调用
                    if settings.agent_function_call_enabled and intent_name != "general":
                        tool_results = await _auto_tool_call(intent_name, text)
                        for tr in tool_results:
                            await websocket.send_json({
                                "type": "tool_call",
                                "name": tr["tool"],
                                "result": tr["result"],
                            })

                    # 生成回复
                    reply = _get_enhanced_reply(text, intent_name, transcript.get("emotion"))
                    session.add_to_context("assistant", reply, intent_name)

                    # TTS 合成
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

                    # 升级检查
                    from app.agents.concierge import check_escalation
                    esc = check_escalation(text)
                    if esc.get("need_human"):
                        await websocket.send_json({
                            "type": "escalation",
                            "reason": esc.get("reason", ""),
                            "urgency": esc.get("urgency", "low"),
                        })

            elif msg_type == "text":
                # 文本消息（用于快速测试）
                text = msg.get("content", "")
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

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

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
        _active_voice_ws.pop(ws_id, None)
        await session.close()
