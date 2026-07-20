"""AI 渲染服务层 — 提供 2D 效果图、3D 场景、照片重布置三种能力

PRD §7.x: AI 渲染端点
- 2D 渲染：调用 LLM 生成 Stable Diffusion / ControlNet 风格 prompt + 自然语言描述 + 占位图 URL
- 3D 渲染：生成 SpatialGen 风格多视角 prompt + 3D 高斯重建参数
- 照片重布置：基于照片的 inpainting / full_regen 模式

设计原则：
1. 复用 BaseAgent._chat() 调用 LLM（DeepSeek / GLM），避免重复实现 HTTP 客户端
2. L4 自适应学习：注入 BaseAgent.get_user_preference_hint() few-shot 示例
3. Mock 模式：settings.deepseek_api_key / glm_api_key 均为空时返回预设响应，
   便于无 API Key 环境下进行功能验证与测试
"""

import json
import logging
import time

from app.agents.base import BaseAgent
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# 支持的渲染风格（仅作推荐列表展示，style 字段允许自由文本）
SUPPORTED_STYLES = [
    "modern", "nordic", "japanese", "luxury",
    "chinese", "industrial", "coastal",
]

# 支持的照片重布置模式
SUPPORTED_RESTAGE_MODES = ["inpainting", "full_regen"]


class _RenderAgent(BaseAgent):
    """渲染 Agent — 复用 BaseAgent._chat() 调用 LLM 生成 SD prompt

    agent_name 设为 "designer" 以匹配 L4 偏好 hint 的查询维度
    （BaseAgent.get_user_preference_hint 按 agent_name 索引历史正向反馈）
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
        """2D 效果图生成 — 调用 LLM 生成 SD prompt + 自然语言描述 + 占位图 URL

        Args:
            layout_json: 布局 JSON（含 rooms / walls 等结构化数据）
            style: 装修风格（modern / nordic / japanese / ...）
            user_id: 用户 ID（用于 L4 偏好注入）
            db: 异步数据库会话
        Returns:
            {prompt, description, placeholder_image_url, style,
             model_used, processing_time_ms, preference_hint_applied}
        """
        start = time.perf_counter()

        # L4 自适应学习：查询用户历史正向反馈，构造 few-shot 示例
        preference_hint = await BaseAgent.get_user_preference_hint(
            user_id, "designer", db
        )
        hint_applied = bool(preference_hint)

        # 调用 LLM 生成 prompt
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
        return {
            "prompt": sd_prompt,
            "description": description,
            "placeholder_image_url": self._placeholder_url("2d", style),
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
        """3D 场景生成 — SpatialGen 风格多视角 prompt + 3D 高斯重建参数

        Args:
            floorplan: 户型数据（含房间布局、墙体、门窗等）
            style: 装修风格
            user_id: 用户 ID（用于 L4 偏好注入）
            db: 异步数据库会话
        Returns:
            {prompts: [...], reconstruction_params, placeholder_model_url, style,
             preference_hint_applied}
        """
        start = time.perf_counter()

        # L4 自适应学习
        preference_hint = await BaseAgent.get_user_preference_hint(
            user_id, "designer", db
        )
        hint_applied = bool(preference_hint)

        # 调用 LLM 生成多视角 prompt
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
        return {
            "prompts": prompts,
            "reconstruction_params": {
                "method": "3dgs",  # 3D Gaussian Splatting
                "iterations": 30000,
                "resolution": "1024x1024",
                "densify_grad_threshold": 0.0001,
            },
            "placeholder_model_url": self._placeholder_url("3d", style),
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

        Args:
            photo_data: 照片二进制数据
            mode: 重布置模式 (inpainting=局部重绘 / full_regen=完全重生)
            style: 装修风格
            user_id: 用户 ID
            db: 异步数据库会话
        Returns:
            {mode, prompt, placeholder_result_url, detected_room_type,
             preference_hint_applied}
        """
        start = time.perf_counter()

        # L4 自适应学习
        preference_hint = await BaseAgent.get_user_preference_hint(
            user_id, "designer", db
        )
        hint_applied = bool(preference_hint)

        # 简单根据照片字节数估算房间类型（生产应使用视觉模型）
        detected_room_type = self._detect_room_type(photo_data)

        # 调用 LLM 生成重布置 prompt
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
        return {
            "mode": mode,
            "prompt": sd_prompt,
            "placeholder_result_url": self._placeholder_url("restage", style),
            "detected_room_type": detected_room_type,
            "style": style,
            "model_used": settings.deepseek_model,
            "processing_time_ms": processing_ms,
            "preference_hint_applied": hint_applied,
        }

    # ── 私有方法 ──────────────────────────────────────────────

    def _build_render_prompt(
        self,
        layout: dict,
        style: str,
        preference_hint: str = "",
    ) -> str:
        """构造发送给 LLM 的 SD prompt 生成请求

        Args:
            layout: 布局 JSON / 户型数据 / 照片元数据
            style: 装修风格
            preference_hint: L4 偏好 few-shot 示例字符串（可空）
        Returns:
            发送给 LLM 的 user message 文本
        """
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
        """无 LLM API Key 时返回预设响应

        Args:
            render_type: 2d | 3d | restage
            style: 装修风格
        Returns:
            预设响应字典
        """
        if render_type == "2d":
            return {
                "prompt": (
                    f"interior design, {style} style, photorealistic, "
                    f"natural lighting, 8k, highly detailed, architectural visualization, "
                    f"controlnet canny, depth map"
                ),
                "description": f"{style} 风格 2D 效果图（mock 占位）",
                "placeholder_image_url": self._placeholder_url("2d", style),
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
                    "iterations": 30000,
                    "resolution": "1024x1024",
                    "densify_grad_threshold": 0.0001,
                },
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
                "detected_room_type": "living_room",
                "style": style,
                "model_used": "mock-sd-inpaint",
                "processing_time_ms": 0,
            }
        return {}

    @staticmethod
    def _placeholder_url(render_type: str, style: str) -> str:
        """生成占位图 URL — 使用 placehold.co 服务

        格式：https://placehold.co/800x600/png?text=AI+Render+{type}+{style}
        """
        return f"https://placehold.co/800x600/png?text=AI+Render+{render_type}+{style}"

    @staticmethod
    def _detect_room_type(photo_data: bytes) -> str:
        """根据照片字节数估算房间类型（mock 实现，生产应使用视觉模型）

        简单 hash 分流：根据字节数取模选择房间类型
        """
        size_hash = len(photo_data)
        room_types = [
            "living_room", "bedroom", "kitchen",
            "bathroom", "dining_room",
        ]
        return room_types[size_hash % len(room_types)]

    @staticmethod
    def _parse_llm_response(reply: str) -> tuple[str, str]:
        """解析 LLM 返回的 JSON，提取 prompt 和 description

        Args:
            reply: LLM 回复文本
        Returns:
            (sd_prompt, description) — 解析失败时返回 (reply, "")
        """
        try:
            parsed = json.loads(reply)
            return parsed.get("prompt", reply), parsed.get("description", "")
        except (json.JSONDecodeError, TypeError):
            return reply, ""

    @staticmethod
    def _parse_prompts_response(reply: str) -> list[str]:
        """解析 LLM 返回的 JSON，提取 prompts 列表

        Args:
            reply: LLM 回复文本
        Returns:
            prompt 字符串列表
        """
        try:
            parsed = json.loads(reply)
            prompts = parsed.get("prompts", [])
            if isinstance(prompts, list) and prompts:
                return [str(p) for p in prompts]
            # 兼容单 prompt 字段
            single = parsed.get("prompt")
            if single:
                return [str(single)]
        except (json.JSONDecodeError, TypeError):
            pass
        return [reply] if reply else []


# 模块级单例，供 API 层复用
ai_render_service = AIRenderService()
