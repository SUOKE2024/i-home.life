"""TTS 三级降级链 —— 借鉴 suoke_life 的 tts_chain 设计。

按 provider priority 依次尝试，直至成功返回 MP3 音频字节：

1. **Qwen3-TTS**（阿里云百炼 DashScope，质量最优，首选）
2. **CosyVoice**（同样基于 DashScope，音色更自然，作为备选）
3. **Doubao TTS**（火山引擎 ARK，兜底）

所有供应商均采用 OpenAI 兼容 ``/audio/speech`` 端点，通过 ``httpx.AsyncClient``
调用，单次请求超时 30s，确保不会挂起。任一供应商失败（超时、非 200、空响应体）
均记录 warning 并自动降级到下一档。

Usage::

    from app.services.tts_chain import tts_chain

    audio_bytes = await tts_chain.synthesize("你好，欢迎使用智能家居", voice="cherry")
"""

import logging
from typing import Any

import httpx

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class TTSProvider:
    """TTS 供应商配置注册表 —— 定义三级降级链中各供应商的端点、凭证与模型。

    借鉴 ``app/agents/base.py`` 的 ``PROVIDER_REGISTRY`` 模式，使用 lambda 延迟
    读取 settings，确保运行时获取最新配置（支持 .env 热加载场景）。

    三档供应商:

    - ``qwen3_tts``: Qwen3-TTS，使用 ``settings.qwen_api_base`` +
      ``settings.qwen_api_key``，模型 ``qwen3-tts``。完整端点路径为
      ``{qwen_api_base}/audio/speech``（DashScope 兼容模式 api_base 已含
      ``/compatible-mode/v1`` 前缀）。
    - ``cosyvoice``: CosyVoice-v2，同样基于 DashScope，复用 Qwen 的 api_base
      与 api_key，模型 ``cosyvoice-v2``。
    - ``doubao``: Doubao TTS，使用 ``settings.doubao_api_base`` +
      ``settings.doubao_api_key``，模型 ``doubao-tts``。完整端点路径为
      ``{doubao_api_base}/audio/speech``（ARK api_base 已含 ``/api/v3`` 前缀）。
    """

    QWEN3_TTS = "qwen3_tts"
    COSYVOICE = "cosyvoice"
    DOUBAO = "doubao"

    # OpenAI 兼容 TTS 端点路径（相对于各供应商 api_base）
    # httpx 会将 base_url 与此路径拼接，得到完整 URL
    _AUDIO_SPEECH_ENDPOINT = "/audio/speech"

    REGISTRY: dict[str, dict[str, Any]] = {
        "qwen3_tts": {
            "api_base": lambda: settings.qwen_api_base,
            "api_key": lambda: settings.qwen_api_key,
            "model": "qwen3-tts",
        },
        "cosyvoice": {
            "api_base": lambda: settings.qwen_api_base,
            "api_key": lambda: settings.qwen_api_key,
            "model": "cosyvoice-v2",
        },
        "doubao": {
            "api_base": lambda: settings.doubao_api_base,
            "api_key": lambda: settings.doubao_api_key,
            "model": "doubao-tts",
        },
    }


class TTSChain:
    """TTS 三级降级链 —— 按 provider priority 依次尝试合成语音。

    构造时从 ``settings.tts_provider_priority`` 解析有序供应商列表（默认
    ``qwen3_tts,cosyvoice,doubao``）。``synthesize`` 按序尝试每个供应商，
    任一成功即返回 MP3 字节；全部失败则抛出最后一个异常或返回空字节。

    当 ``settings.tts_enabled = False`` 时，``synthesize`` 直接抛出
    ``RuntimeError("TTS 未启用")``。
    """

    def __init__(self) -> None:
        """解析 provider priority 配置为有序列表。"""
        raw = settings.tts_provider_priority or "qwen3_tts,cosyvoice,doubao"
        self._providers: list[str] = [
            p.strip() for p in raw.split(",") if p.strip()
        ]

    async def synthesize(self, text: str, voice: str = "cherry") -> bytes:
        """按 provider priority 依次尝试合成语音，返回 MP3 音频字节。

        Args:
            text: 待合成的文本内容。
            voice: 音色名称，默认 ``"cherry"``（Qwen3-TTS / CosyVoice 通用音色）。

        Returns:
            MP3 格式的音频字节流 (``bytes``)。

        Raises:
            RuntimeError: ``tts_enabled`` 为 False 时抛出 ``"TTS 未启用"``；
                或所有供应商均失败时抛出记录的最后一个异常。
        """
        if not settings.tts_enabled:
            raise RuntimeError("TTS 未启用")

        if not self._providers:
            logger.warning("tts_chain: provider priority 列表为空，返回空音频")
            return b""

        last_error: Exception | None = None
        for provider in self._providers:
            try:
                audio = await self._try_provider(provider, text, voice)
                if audio:
                    logger.info(
                        "tts_chain: provider=%s 合成成功 (%d bytes, voice=%s)",
                        provider, len(audio), voice,
                    )
                    return audio
                # 返回空字节视为失败，降级
                logger.warning(
                    "tts_chain: provider=%s 返回空音频，降级到下一个供应商",
                    provider,
                )
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "tts_chain: provider=%s 失败 (%s)，降级到下一个供应商",
                    provider, exc,
                )

        # 所有供应商均失败
        if last_error is not None:
            logger.error(
                "tts_chain: 所有 %d 个供应商均失败，抛出最后一个错误: %s",
                len(self._providers), last_error,
            )
            raise last_error

        # 无异常但全部返回空（理论上不会走到这里，防御性处理）
        logger.warning("tts_chain: 所有供应商均返回空音频，返回空字节")
        return b""

    async def _try_provider(
        self, provider: str, text: str, voice: str
    ) -> bytes:
        """调用单个供应商的 TTS 端点，成功返回音频字节。

        使用 OpenAI 兼容协议：POST ``/audio/speech``，请求体为::

            {"model": ..., "input": text, "voice": voice, "response_format": "mp3"}

        响应体应为 ``audio/mpeg`` 字节流。

        Args:
            provider: 供应商名称（``qwen3_tts`` / ``cosyvoice`` / ``doubao``）。
            text: 待合成的文本内容。
            voice: 音色名称。

        Returns:
            MP3 格式的音频字节流。

        Raises:
            ValueError: 未知的供应商名称。
            RuntimeError: API key 未配置 / HTTP 非 200 / 响应体为空 / 网络错误。
        """
        cfg = TTSProvider.REGISTRY.get(provider)
        if not cfg:
            raise ValueError(f"未知 TTS provider: {provider}")

        api_key = cfg["api_key"]()
        if not api_key:
            raise RuntimeError(f"provider={provider} API key 未配置")

        api_base = cfg["api_base"]()
        model = cfg["model"]

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        body = {
            "model": model,
            "input": text,
            "voice": voice,
            "response_format": "mp3",
        }

        # 每次调用创建独立 AsyncClient，确保 30s 超时不会挂起
        # （TTS 调用频率不高，连接复用收益有限，优先保证安全）
        try:
            async with httpx.AsyncClient(
                base_url=api_base,
                timeout=httpx.Timeout(30.0),
            ) as client:
                response = await client.post(
                    TTSProvider._AUDIO_SPEECH_ENDPOINT,
                    json=body,
                    headers=headers,
                )
                response.raise_for_status()

                if not response.content:
                    raise RuntimeError(
                        f"provider={provider} 返回空响应体 "
                        f"(status={response.status_code})"
                    )

                return response.content
        except httpx.HTTPStatusError:
            # raise_for_status 抛出，保留原始异常信息（含状态码）
            raise
        except httpx.HTTPError as exc:
            # 超时 / 连接错误 / 请求错误统一包装
            raise RuntimeError(
                f"provider={provider} 网络错误: {exc}"
            ) from exc


# 模块级单例 —— 全局复用，避免重复解析 provider priority
tts_chain = TTSChain()
