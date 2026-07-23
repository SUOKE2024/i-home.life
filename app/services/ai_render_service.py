"""AI 渲染服务层 — 提供 2D 效果图、3D 场景、照片重布置三种能力

v1.2.0 P1 修复（诊断报告 D1）：去 stub，诚实降级
- real_ai_render_enabled + ai_render_backend_url 配置时调用真实 ControlNet 几何锁定渲染后端
  （对标 2026 行业强制 Geometry Locking：几何约束作硬边界，不 hallucinate 墙体/承重柱）
- 未配置时诚实降级：render_backend="mock"，reconstruction_available=False
  （不再把 reconstruction_params 伪造成"已执行"的 3DGS 参数）
- _detect_room_type 不再用 len(photo_data)%len(rooms) 伪随机，诚实返回 "unknown"
  （需 spatial_perception_enabled=True 接入真实视觉模型）

设计原则：
1. 复用 BaseAgent._chat() 调用 LLM 生成 SD prompt
2. L4 自适应学习：注入 BaseAgent.get_user_preference_hint() few-shot
3. Mock 模式：无 API Key 或无渲染后端时诚实降级，保留 placeholder_* 字段向后兼容测试
"""

import json
import logging
import time

try:
    import httpx
except ImportError:  # httpx 为可选依赖，缺失时禁用真实后端调用
    httpx = None  # type: ignore

from app.agents.base import BaseAgent
from app.config import get_settings

logger = logging.getLogger(__name__)

# 支持的渲染风格（仅作推荐列表展示，style 字段允许自由文本）
SUPPORTED_STYLES = [
    "modern", "nordic", "japanese", "luxury",
    "chinese", "industrial", "coastal",
]

# 支持的照片重布置模式
SUPPORTED_RESTAGE_MODES = ["inpainting", "full_regen"]

# 真实渲染后端调用超时（秒）
_RENDER_BACKEND_TIMEOUT = 60.0


class _RenderAgent(BaseAgent):
    """渲染 Agent — 复用 BaseAgent._chat() 调用 LLM 生成 SD prompt

    agent_name 设为 "designer" 以匹配 L4 偏好 hint 的查询维度
    """

    agent_name = "designer"
    system_prompt = (
        "你是索克家居（i-home.life）AI 渲染提示词工程师。"
        "根据用户输入的布局 JSON / 户型 / 照片元数据 + 风格，"
        "生成 Stable Diffusion / ControlNet 兼容的 prompt。"
        "请直接输出 JSON：{\"prompt\": \"英文SD提示词\", \"description\": \"中文描述\"}。"
        "不要输出推理过程或额外解释。"
    )
    provider = "deepseek"


class AIRenderService:
    """AI 渲染服务 — 封装 2D / 3D / 照片重布置三种渲染能力"""

    async def render_2d(
        self,
        layout_json: dict,
        style: str,
        user_id: str,
        db,
    ) -> dict:
        """2D 效果图生成 — LLM 生成 SD prompt + 真实渲染后端 / 诚实降级

        v1.2.0: real_ai_render_enabled + ai_render_backend_url 配置时调真实 ControlNet 后端，
        否则诚实降级到 mock（render_backend="mock"）。
        """
        start = time.perf_counter()

        preference_hint = await BaseAgent.get_user_preference_hint(
            user_id, "designer", db
        )
        hint_applied = bool(preference_hint)

        agent = _RenderAgent()
        try:
            user_prompt = self._build_render_prompt(layout_json, style, preference_hint)
            messages = [
                {"role": "system", "content": agent.system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            reply = await agent._chat(messages)
            sd_prompt, description = self._parse_llm_response(reply)
        finally:
            await agent.close()

        processing_ms = int((time.perf_counter() - start) * 1000)
        settings = get_settings()

        # v1.2.0 P1: 真实渲染后端调用（ControlNet 几何锁定）
        render_backend = "mock"
        image_url = self._placeholder_url("2d", style)
        if settings.real_ai_render_enabled and settings.ai_render_backend_url:
            real = await self._call_render_backend({
                "type": "2d",
                "prompt": sd_prompt,
                "style": style,
                "layout": layout_json,
            })
            if real and real.get("image_url"):
                image_url = real["image_url"]
                render_backend = real.get("backend", "controlnet")
            else:
                render_backend = "real-disabled-fallback"

        return {
            "prompt": sd_prompt,
            "description": description,
            "placeholder_image_url": image_url,  # 保留字段名兼容测试
            "render_backend": render_backend,  # v1.2.0 新增：mock | controlnet | real-disabled-fallback
            "style": style,
            "model_used": settings.deepseek_model,
            "processing_time_ms": processing_ms,
            "preference_hint_applied": hint_applied,
        }

    async def render_3d(
        self,
        floorplan: dict,
        style: str,
        user_id: str,
        db,
    ) -> dict:
        """3D 场景生成 — 多视角 prompt + 真实 3D 重建 / 诚实降级

        v1.2.0: real_ai_render_enabled 时调真实 3DGS 后端，reconstruction_available=True；
        否则诚实降级：reconstruction_available=False（不再把伪参数冒充已执行）。
        保留 reconstruction_params.method 字段向后兼容测试，但标注 available=False。
        """
        start = time.perf_counter()

        preference_hint = await BaseAgent.get_user_preference_hint(
            user_id, "designer", db
        )
        hint_applied = bool(preference_hint)

        agent = _RenderAgent()
        try:
            user_prompt = self._build_render_prompt(
                floorplan, style, preference_hint
            ) + "\n\n请生成 4 个视角（俯视/正面/侧面/45度）的 prompt，输出 JSON：{\"prompts\": [\"...\", ...]}"
            messages = [
                {"role": "system", "content": agent.system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            reply = await agent._chat(messages)
            prompts = self._parse_prompts_response(reply)
        finally:
            await agent.close()

        processing_ms = int((time.perf_counter() - start) * 1000)
        settings = get_settings()

        # v1.2.0 P1: 真实 3D 渲染后端（3D Gaussian Splatting）
        render_backend = "mock"
        reconstruction_available = False
        model_url = self._placeholder_url("3d", style)
        # 保留 method 字段兼容测试；available=False 诚实标识未真实执行
        reconstruction_params = {
            "method": "3dgs",
            "available": False,  # v1.2.0 新增：False=未真实执行，True=后端已生成
            "reason": "3DGS backend not configured; enable real_ai_render_enabled + ai_render_backend_url",
        }
        if settings.real_ai_render_enabled and settings.ai_render_backend_url:
            real = await self._call_render_backend({
                "type": "3d",
                "prompts": prompts,
                "style": style,
                "floorplan": floorplan,
            })
            if real and real.get("model_url"):
                model_url = real["model_url"]
                render_backend = real.get("backend", "3dgs")
                reconstruction_available = True
                reconstruction_params = {
                    "method": "3dgs",
                    "available": True,
                    "iterations": real.get("iterations", 30000),
                    "resolution": real.get("resolution", "1024x1024"),
                }
            else:
                render_backend = "real-disabled-fallback"

        return {
            "prompts": prompts,
            "reconstruction_params": reconstruction_params,
            "reconstruction_available": reconstruction_available,  # v1.2.0 新增
            "render_backend": render_backend,  # v1.2.0 新增
            "placeholder_model_url": model_url,  # 保留兼容测试
            "style": style,
            "model_used": settings.deepseek_model,
            "processing_time_ms": processing_ms,
            "preference_hint_applied": hint_applied,
        }

    async def restage_photo(
        self,
        photo_data: bytes,
        mode: str,
        style: str,
        user_id: str,
        db,
    ) -> dict:
        """照片重布置 — inpainting 或 full_regen 模式

        v1.2.0: _detect_room_type 诚实化（不再 len%len 伪随机）。
        """
        start = time.perf_counter()

        preference_hint = await BaseAgent.get_user_preference_hint(
            user_id, "designer", db
        )
        hint_applied = bool(preference_hint)

        # v1.2.0 P1: 房间类型检测诚实化
        detected_room_type = self._detect_room_type(photo_data)

        agent = _RenderAgent()
        try:
            layout_meta = {
                "photo_size_bytes": len(photo_data),
                "detected_room_type": detected_room_type,
            }
            user_prompt = self._build_render_prompt(layout_meta, style, preference_hint)
            user_prompt += (
                f"\n\n模式: {mode}（inpainting=保留主体局部重绘, full_regen=完全重生）"
                "请输出 JSON：{\"prompt\": \"...\"}"
            )
            messages = [
                {"role": "system", "content": agent.system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            reply = await agent._chat(messages)
            sd_prompt, _ = self._parse_llm_response(reply)
        finally:
            await agent.close()

        processing_ms = int((time.perf_counter() - start) * 1000)
        settings = get_settings()

        render_backend = "mock"
        result_url = self._placeholder_url("restage", style)
        if settings.real_ai_render_enabled and settings.ai_render_backend_url:
            real = await self._call_render_backend({
                "type": "restage",
                "mode": mode,
                "prompt": sd_prompt,
                "style": style,
                "photo_size": len(photo_data),
            })
            if real and real.get("image_url"):
                result_url = real["image_url"]
                render_backend = real.get("backend", "controlnet")
            else:
                render_backend = "real-disabled-fallback"

        return {
            "mode": mode,
            "prompt": sd_prompt,
            "placeholder_result_url": result_url,  # 保留兼容测试
            "detected_room_type": detected_room_type,
            "render_backend": render_backend,  # v1.2.0 新增
            "style": style,
            "model_used": settings.deepseek_model,
            "processing_time_ms": processing_ms,
            "preference_hint_applied": hint_applied,
        }

    # ── 真实渲染后端调用（v1.2.0 新增）──────────────────────

    async def _call_render_backend(self, payload: dict) -> dict | None:
        """调用真实渲染后端（ControlNet / 3DGS / inpainting）

        后端协议：POST {ai_render_backend_url} JSON body，返回 {image_url|model_url, backend}
        失败时返回 None，调用方降级到 mock。

        需 httpx 依赖；未安装或后端不可达时降级。
        """
        settings = get_settings()
        if not settings.ai_render_backend_url or httpx is None:
            return None
        try:
            async with httpx.AsyncClient(timeout=_RENDER_BACKEND_TIMEOUT) as client:
                resp = await client.post(
                    settings.ai_render_backend_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(
                    "渲染后端返回非 200: %s %s",
                    resp.status_code, resp.text[:200],
                )
                return None
        except Exception as e:
            logger.warning("渲染后端调用失败，降级到 mock: %s", e)
            return None

    # ── 私有方法 ──────────────────────────────────────────────

    def _build_render_prompt(
        self,
        layout: dict,
        style: str,
        preference_hint: str = "",
    ) -> str:
        layout_str = json.dumps(layout, ensure_ascii=False, default=str)
        prompt = (
            f"请根据以下信息生成 Stable Diffusion 兼容的 prompt：\n"
            f"风格: {style}\n"
            f"布局数据: {layout_str}\n\n"
            f"要求：\n"
            f"1. 输出 JSON 格式：{{\"prompt\": \"...\", \"description\": \"...\"}}\n"
            f"2. prompt 字段为英文 SD 兼容提示词，含材质 / 光影 / 视角关键词\n"
            f"3. description 字段为中文自然语言描述（不超过 100 字）\n"
        )
        if preference_hint:
            prompt += (
                f"\n以下为用户偏好参考（请参考其风格与内容偏好生成 prompt）：\n"
                f"{preference_hint}\n"
            )
        return prompt

    def _get_mock_response(self, render_type: str, style: str) -> dict:
        """无 LLM API Key 时返回预设响应（向后兼容）"""
        if render_type == "2d":
            return {
                "prompt": (
                    f"interior design, {style} style, photorealistic, "
                    f"natural lighting, 8k, highly detailed, architectural visualization, "
                    f"controlnet canny, depth map"
                ),
                "description": f"{style} 风格 2D 效果图（mock 占位）",
                "placeholder_image_url": self._placeholder_url("2d", style),
                "render_backend": "mock",
                "style": style,
                "model_used": "mock-sd-xl",
                "processing_time_ms": 0,
            }
        if render_type == "3d":
            return {
                "prompts": [
                    f"top view, {style} interior, 3d gaussian splatting, photorealistic",
                    f"front view, {style} interior, natural lighting, 8k detailed",
                    f"side view, {style} interior, photorealistic, architectural",
                    f"45 degree view, {style} interior, highly detailed, 8k",
                ],
                "reconstruction_params": {
                    "method": "3dgs",
                    "available": False,
                    "reason": "mock mode",
                },
                "reconstruction_available": False,
                "render_backend": "mock",
                "placeholder_model_url": self._placeholder_url("3d", style),
                "style": style,
                "model_used": "mock-spatialgen",
                "processing_time_ms": 0,
            }
        if render_type == "restage":
            return {
                "mode": "inpainting",
                "prompt": (
                    f"rearranged furniture, {style} style, "
                    f"preserve architecture, photorealistic, 8k"
                ),
                "placeholder_result_url": self._placeholder_url("restage", style),
                "detected_room_type": "unknown",
                "render_backend": "mock",
                "style": style,
                "model_used": "mock-sd-inpaint",
                "processing_time_ms": 0,
            }
        return {}

    @staticmethod
    def _placeholder_url(render_type: str, style: str) -> str:
        """生成占位图 URL（mock 模式使用，真实渲染时被替换）"""
        return f"https://placehold.co/800x600/png?text=AI+Render+{render_type}+{style}"

    @staticmethod
    def _detect_room_type(photo_data: bytes) -> str:
        """v1.2.0 P1 修复：诚实化房间类型检测

        原实现用 len(photo_data) % len(room_types) 伪随机，违反专业性。
        现诚实返回 "unknown"（视觉模型未启用）。
        spatial_perception_enabled=True 时应接入真实视觉模型（CLIP/BLIP），
        当前为占位，返回 "visual-pending" 标识视觉能力待接入。
        """
        settings = get_settings()
        if settings.spatial_perception_enabled:
            # TODO: 接入 CLIP/BLIP 视觉模型，从 photo_data 推断房间类型
            # 当前返回标识，表示视觉能力开关已开但模型未接入
            return "visual-pending"
        # 诚实降级：未启用视觉模型时返回 unknown，不再伪随机
        return "unknown"

    @staticmethod
    def _parse_llm_response(reply: str) -> tuple[str, str]:
        try:
            parsed = json.loads(reply)
            return parsed.get("prompt", reply), parsed.get("description", "")
        except (json.JSONDecodeError, TypeError):
            return reply, ""

    @staticmethod
    def _parse_prompts_response(reply: str) -> list[str]:
        try:
            parsed = json.loads(reply)
            prompts = parsed.get("prompts", [])
            if isinstance(prompts, list) and prompts:
                return [str(p) for p in prompts]
            single = parsed.get("prompt")
            if single:
                return [str(single)]
        except (json.JSONDecodeError, TypeError):
            pass
        return [reply] if reply else []


# 模块级单例，供 API 层复用
ai_render_service = AIRenderService()
