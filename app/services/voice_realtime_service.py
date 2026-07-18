"""实时语音服务 —— 对接 Qwen-Audio-3.0-Realtime (阿里云百炼)

提供基于 WebSocket 的实时语音交互能力：
- 流式语音识别 (ASR)
- 流式语音合成 (TTS)
- 双工对话交互
- 情感感知
- 工具调用 (FunctionCall)
"""

import json
import logging
from typing import Any, AsyncGenerator

import httpx

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


# websockets 是 FastAPI/uvicorn 的传递依赖（实测 v16+ 可用）
# 仅在 qwen_audio_api_key 配置时才会实际使用 WebSocket 连接
try:
    import websockets  # noqa: F401
    _HAS_WEBSOCKETS = True
except ImportError:  # pragma: no cover
    _HAS_WEBSOCKETS = False


# ── 情绪标签映射 ──
EMOTION_LABELS = {
    "anxious": "焦虑",
    "excited": "兴奋",
    "tired": "疲惫",
    "calm": "平静",
    "angry": "愤怒",
    "sad": "难过",
    "happy": "开心",
    "hesitant": "犹豫",
    "confident": "自信",
    "neutral": "中性",
}


class VoiceRealtimeSession:
    """Qwen-Audio-3.0-Realtime 实时语音会话"""

    def __init__(
        self,
        user_id: str,
        project_id: str | None = None,
        model: str | None = None,
        voice: str | None = None,
    ):
        self.user_id = user_id
        self.project_id = project_id
        self.model = model or settings.qwen_audio_model
        self.voice = voice or settings.qwen_audio_voice
        self._ws: Any | None = None
        self._session_id: str | None = None
        self._emotion_history: list[dict] = []
        self._conversation_context: list[dict] = []

    # ── 会话管理 ──

    async def connect(self) -> dict:
        """建立与百炼的 WebSocket 连接并初始化语音会话。

        注意：此方法在无 API Key 时返回 mock 模式。
        """
        if not settings.qwen_audio_api_key:
            logger.info("voice_realtime: API Key 未配置，使用 mock 模式")
            self._session_id = f"mock_session_{self.user_id}"
            return {"mode": "mock", "session_id": self._session_id}

        if not _HAS_WEBSOCKETS:
            logger.warning(
                "voice_realtime: websockets 库未安装，降级为 mock 模式"
                "（pip install websockets 启用实时语音）"
            )
            self._session_id = f"mock_session_{self.user_id}"
            return {"mode": "mock", "session_id": self._session_id}

        try:
            # 使用 websockets 库建立百炼 Realtime WebSocket 连接
            # 协议: wss://dashscope.aliyuncs.com/api-ws/v1/realtime
            headers = {
                "Authorization": f"Bearer {settings.qwen_audio_api_key}",
                "X-DashScope-DataInspection": "enable",
            }
            self._ws = await websockets.connect(
                settings.qwen_audio_ws_url,
                additional_headers=headers,
                open_timeout=30,
                max_size=2 ** 20,  # 1MB 音频帧
            )
            self._session_id = f"qwen_audio_{self.user_id}_{id(self)}"
            logger.info(f"voice_realtime: 会话已创建 session={self._session_id}")
            return {"mode": "realtime", "session_id": self._session_id}
        except Exception as e:
            logger.error(f"voice_realtime: 连接失败 {e}，降级为 fallback 模式")
            self._ws = None
            self._session_id = f"fallback_session_{self.user_id}"
            return {"mode": "fallback", "session_id": self._session_id, "error": str(e)}

    async def close(self):
        """关闭会话"""
        if self._ws is not None:
            try:
                # websockets v14+ ClientConnection 用 close()，
                # 旧版 WebSocketClientProtocol 也支持 close()（aclose 已废弃）
                await self._ws.close()
            except Exception as e:
                logger.warning(f"voice_realtime: close 异常 {e}")
            self._ws = None
        self._session_id = None
        logger.info("voice_realtime: 会话已关闭")

    # ── Qwen-Audio-3.0-Realtime 原生协议方法 ──

    async def init_realtime_session(
        self,
        tools: list[dict] | None = None,
        modalities: list[str] | None = None,
        turn_detection: dict | None = None,
        instructions: str | None = None,
    ) -> None:
        """初始化 Realtime 会话 —— 发送 session.update 配置。

        必须在 connect() 成功（mode == "realtime"）后调用。
        参数对齐 Qwen-Audio-3.0-Realtime 的 session.update 事件 schema。

        Args:
            tools: FunctionCall 工具 schema 列表
            modalities: 模态列表，默认 ["text", "audio"]
            turn_detection: 轮次检测配置（None 则从 settings 读取）
            instructions: 系统指令/角色设定
        """
        if self._ws is None:
            logger.warning("voice_realtime: 未连接，跳过 session.update")
            return

        # 轮次检测模式：
        #   server_vad: 声学 VAD（默认，适合安静环境）
        #   smart_turn: 声学+语义智能检测（过滤"嗯""啊"，适合嘈杂工地）
        #   none: push-to-talk 手动控制
        if turn_detection is None:
            td_type = settings.voice_turn_detection
            if td_type in ("smart_turn", "server_vad"):
                turn_detection = {
                    "type": td_type,
                    "threshold": settings.voice_vad_threshold,
                    "silence_duration_ms": settings.voice_vad_silence_ms,
                }
            elif td_type == "none":
                turn_detection = None  # push-to-talk
            else:
                turn_detection = {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "silence_duration_ms": 800,
                }

        session_cfg: dict[str, Any] = {
            "modalities": modalities or ["text", "audio"],
            "voice": self.voice,
        }
        if turn_detection is not None:
            session_cfg["turn_detection"] = turn_detection
        if tools:
            session_cfg["tools"] = tools
        if instructions:
            session_cfg["instructions"] = instructions

        # 说话人增强：传入目标用户预录音频样本，锁定声纹，屏蔽旁人 + 背景噪声
        # 适用于工地现场（多人嘈杂）场景
        if settings.voice_audio_prompt_enabled:
            session_cfg["audio_prompt"] = {
                "enabled": True,
                "mode": "speaker_focus",
            }

        await self._send_raw_json({
            "type": "session.update",
            "session": session_cfg,
        })
        logger.info(
            "voice_realtime: session.update sent "
            f"modalities={session_cfg['modalities']} "
            f"turn_detection={turn_detection.get('type') if turn_detection else 'manual'} "
            f"tools={len(tools) if tools else 0} "
            f"audio_prompt={settings.voice_audio_prompt_enabled}"
        )

    async def send_input_audio_buffer_append(self, audio_b64: str) -> None:
        """发送音频块到 Realtime 缓冲区"""
        if self._ws is None:
            return
        await self._send_raw_json({
            "type": "input_audio_buffer.append",
            "audio": audio_b64,
        })

    async def send_input_audio_buffer_commit(self) -> None:
        """提交音频缓冲区，触发模型推理"""
        if self._ws is None:
            return
        await self._send_raw_json({"type": "input_audio_buffer.commit"})

    async def send_input_audio_buffer_clear(self) -> None:
        """清空音频缓冲区（用于取消当前输入）"""
        if self._ws is None:
            return
        await self._send_raw_json({"type": "input_audio_buffer.clear"})

    async def send_text_input(self, text: str) -> None:
        """发送文本输入（创建 user message 并触发响应）"""
        if self._ws is None:
            return
        await self._send_raw_json({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": text}],
            },
        })
        await self._send_raw_json({"type": "response.create"})

    async def send_response_create(self) -> None:
        """触发模型生成响应"""
        if self._ws is None:
            return
        await self._send_raw_json({"type": "response.create"})

    async def send_response_cancel(self) -> None:
        """取消当前正在生成的响应（用于双工打断）"""
        if self._ws is None:
            return
        await self._send_raw_json({"type": "response.cancel"})

    async def send_function_call_output(self, call_id: str, output: dict) -> None:
        """写入工具调用结果并触发后续推理"""
        if self._ws is None:
            return
        await self._send_raw_json({
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": json.dumps(output, ensure_ascii=False),
            },
        })
        await self._send_raw_json({"type": "response.create"})

    async def receive_events(self) -> AsyncGenerator[dict[str, Any], None]:
        """异步生成器：逐条接收 Realtime 服务端事件。

        Yields:
            JSON 事件字典，如 {"type": "response.audio.delta", ...}
            连接断开时自动结束迭代。
        """
        if self._ws is None:
            return
        try:
            async for raw in self._ws:
                try:
                    yield json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning(f"voice_realtime: 无效 JSON: {str(raw)[:100]}")
        except Exception as e:
            logger.warning(f"voice_realtime: receive_events 异常: {e}")

    async def _send_raw_json(self, msg: dict) -> None:
        """发送原始 JSON 到 Qwen-Audio Realtime WS（内部使用）"""
        if self._ws is None:
            return
        try:
            await self._ws.send(json.dumps(msg, ensure_ascii=False))
        except Exception as e:
            logger.error(f"voice_realtime: send_raw_json 失败: {e}")

    @property
    def is_realtime(self) -> bool:
        """是否处于真实 Realtime 连接模式"""
        return self._ws is not None and self._session_id is not None

    # ── 语音识别 (ASR) ──

    async def transcribe(self, audio_data: bytes, audio_format: str = "pcm16") -> dict:
        """流式语音识别 → 文本转录

        Args:
            audio_data: 音频数据 (PCM/WAV)
            audio_format: 音频格式 (pcm16 | wav | mp3)

        Returns:
            {"text": "...", "confidence": 0.95, "is_final": True, "emotion": {...}}
        """
        if not settings.qwen_audio_api_key:
            # Mock ASR 模式：返回模拟转写结果
            return await self._mock_transcribe(audio_data)

        try:
            # 调用百炼 ASR API（使用 REST 接口）
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription",
                    headers={"Authorization": f"Bearer {settings.qwen_audio_api_key}"},
                    json={
                        "model": settings.voice_asr_model,
                        "input": {"audio": audio_data.hex() if isinstance(audio_data, bytes) else audio_data},
                        "parameters": {"format": audio_format, "sample_rate": 16000},
                    },
                )
                data = response.json()
                text = data.get("output", {}).get("text", "")
                return {
                    "text": text,
                    "confidence": data.get("output", {}).get("confidence", 0.9),
                    "is_final": True,
                    "emotion": await self._detect_emotion_from_text(text),
                }
        except Exception as e:
            logger.warning(f"voice_realtime: ASR 失败，使用 mock: {e}")
            return await self._mock_transcribe(audio_data)

    async def _mock_transcribe(self, audio_data: bytes) -> dict:
        """Mock ASR 转写"""
        text = "收到您的语音消息，正在为您处理..."
        if len(audio_data) > 1000:
            text = "语音输入已接收，请说出您的装修需求"
        return {
            "text": text,
            "confidence": 0.85,
            "is_final": True,
            "emotion": {"label": "neutral", "name": "中性", "confidence": 0.8},
        }

    # ── 语音合成 (TTS) ──

    async def synthesize_speech(
        self, text: str, emotion: str | None = None, voice: str | None = None
    ) -> bytes | None:
        """文本 → 语音合成

        Args:
            text: 要合成的文本
            emotion: 情感标签（可选，影响语调）
            voice: 音色名称（可选）

        Returns:
            音频数据 (WAV/PCM)，失败返回 None
        """
        if not settings.qwen_audio_api_key:
            logger.info("voice_realtime: TTS mock 模式，返回空音频")
            return None

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                params = {
                    "model": settings.voice_tts_model,
                    "input": {"text": text},
                    "parameters": {
                        "voice": voice or self.voice,
                        "language_type": "Chinese",
                        "format": "wav",
                    },
                }
                if emotion and emotion in EMOTION_LABELS:
                    params["parameters"]["emotion"] = emotion

                response = await client.post(
                    "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/speech",
                    headers={"Authorization": f"Bearer {settings.qwen_audio_api_key}"},
                    json=params,
                )
                data = response.json()
                audio_hex = data.get("output", {}).get("audio", "")
                if audio_hex:
                    return bytes.fromhex(audio_hex)
                return None
        except Exception as e:
            logger.warning(f"voice_realtime: TTS 失败: {e}")
            return None

    # ── 情感检测 ──

    async def _detect_emotion_from_text(self, text: str) -> dict:
        """从文本检测情感（轻量级规则 + 关键词）

        完整实现应接入 Qwen-Audio 的 EmoSync 17 维声学特征分析，
        这里提供文本侧的关键词规则检测作为降级方案。
        """
        if not settings.voice_emotion_detection:
            return {"label": "neutral", "name": "中性", "confidence": 1.0}

        # 情绪关键词映射
        emotion_keywords = {
            "anxious": ["着急", "担心", "焦虑", "怎么办", "急", "快点", "赶紧"],
            "excited": ["太好了", "开心", "期待", "兴奋", "棒", "赞"],
            "tired": ["累", "疲劳", "辛苦", "不容易"],
            "angry": ["生气", "投诉", "差劲", "过分", "愤怒", "不满"],
            "sad": ["难过", "失望", "遗憾", "伤心"],
            "happy": ["喜欢", "满意", "不错", "满意", "好"],
            "hesitant": ["不确定", "犹豫", "考虑", "再看看", "纠结"],
        }

        scores = {}
        for label, keywords in emotion_keywords.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[label] = score / len(keywords)

        if not scores:
            return {"label": "neutral", "name": "中性", "confidence": 0.7}

        best_label = max(scores, key=scores.get)
        confidence = min(scores[best_label] * 2, 0.95)

        result = {
            "label": best_label,
            "name": EMOTION_LABELS.get(best_label, best_label),
            "confidence": round(confidence, 2),
            "all_scores": {
                EMOTION_LABELS.get(k, k): round(v, 2) for k, v in scores.items()
            },
        }

        # 记录情绪历史
        self._emotion_history.append({"text": text[:100], "emotion": result})
        if len(self._emotion_history) > 50:
            self._emotion_history = self._emotion_history[-50:]

        logger.debug(f"voice_realtime: 情绪检测 {text[:50]}... -> {best_label}")
        return result

    async def detect_emotion_from_audio(self, audio_data: bytes) -> dict:
        """从音频数据检测情绪（声学特征分析）

        当前为规则降级方案。完整实现需通过 Qwen-Audio-3.0-Realtime 的
        EmoSync 2.0 模块分析基频抖动、语速微变、停顿节奏等 17 维声学特征。
        """
        # 对音频数据进行基本的能量/语速分析（简化实现）
        # 生产环境建议使用 Qwen-Audio-3.0-Realtime 内置的 EmoSync 模块

        if not settings.voice_emotion_detection:
            return {"label": "neutral", "name": "中性", "confidence": 1.0}

        # 简单的音频能量分析
        audio_len = len(audio_data) if audio_data else 0
        if audio_len < 100:
            return {"label": "hesitant", "name": "犹豫", "confidence": 0.6}

        # 计算平均振幅（简化）
        try:
            samples = list(audio_data[:min(4000, audio_len)])
            avg_amplitude = sum(abs(b - 128) for b in samples) / max(len(samples), 1)

            if avg_amplitude > 40:
                label = "excited"
            elif avg_amplitude > 25:
                label = "confident"
            elif avg_amplitude > 10:
                label = "neutral"
            else:
                label = "tired"

            return {
                "label": label,
                "name": EMOTION_LABELS.get(label, label),
                "confidence": min(0.7, round(avg_amplitude / 60, 2)),
                "avg_amplitude": round(avg_amplitude, 1),
            }
        except Exception:
            return {"label": "neutral", "name": "中性", "confidence": 0.5}

    # ── 对话上下文 ──

    def add_to_context(self, role: str, content: str, agent_type: str = ""):
        """添加消息到对话上下文"""
        self._conversation_context.append({
            "role": role,
            "content": content,
            "agent_type": agent_type,
        })
        # 保留最近 20 轮
        if len(self._conversation_context) > 20:
            self._conversation_context = self._conversation_context[-20:]

    def get_context(self, last_n: int = 10) -> list[dict]:
        return self._conversation_context[-last_n:] if self._conversation_context else []

    # ── 情绪趋势 ──

    def get_emotion_trend(self) -> dict:
        """获取对话过程中的情绪变化趋势"""
        if not self._emotion_history:
            return {"trend": "stable", "samples": 0}

        # 统计最近 10 条的情绪分布
        recent = self._emotion_history[-10:]
        emotion_counts: dict[str, int] = {}
        for entry in recent:
            label = entry["emotion"]["label"]
            emotion_counts[label] = emotion_counts.get(label, 0) + 1

        dominant = max(emotion_counts, key=emotion_counts.get)

        # 判断趋势
        if len(recent) >= 3:
            first_half = [e["emotion"]["label"] for e in recent[: len(recent) // 2]]
            second_half = [e["emotion"]["label"] for e in recent[len(recent) // 2 :]]

            negative = {"anxious", "angry", "sad", "tired"}
            positive = {"happy", "excited", "confident"}

            first_neg = sum(1 for lbl in first_half if lbl in negative)
            second_neg = sum(1 for lbl in second_half if lbl in negative)
            second_pos = sum(1 for lbl in second_half if lbl in positive)

            if second_neg > first_neg:
                trend = "declining"
            elif second_pos > first_neg:
                trend = "improving"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "dominant_emotion": EMOTION_LABELS.get(dominant, dominant),
            "samples": len(self._emotion_history),
            "distribution": {
                EMOTION_LABELS.get(k, k): v for k, v in emotion_counts.items()
            },
        }


# ── 会话管理器 ──

class VoiceSessionManager:
    """语音会话管理器（单例）"""

    _instance = None
    _sessions: dict[str, VoiceRealtimeSession] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def create_session(
        self, user_id: str, project_id: str | None = None
    ) -> VoiceRealtimeSession:
        """创建或获取语音会话"""
        session_key = f"{user_id}:{project_id or 'default'}"
        if session_key not in self._sessions:
            self._sessions[session_key] = VoiceRealtimeSession(
                user_id=user_id, project_id=project_id
            )
        return self._sessions[session_key]

    def get_session(self, user_id: str, project_id: str | None = None) -> VoiceRealtimeSession | None:
        session_key = f"{user_id}:{project_id or 'default'}"
        return self._sessions.get(session_key)

    async def close_session(self, user_id: str, project_id: str | None = None):
        session_key = f"{user_id}:{project_id or 'default'}"
        session = self._sessions.pop(session_key, None)
        if session:
            await session.close()

    async def close_all(self):
        for session in self._sessions.values():
            await session.close()
        self._sessions.clear()


voice_session_manager = VoiceSessionManager()
