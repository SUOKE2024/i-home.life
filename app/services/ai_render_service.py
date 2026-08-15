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

from app.agents.base import BaseAgent, get_pref_hint_cached
from app.config import get_settings
from app.services.ai_content_labeling import annotate_output

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

# ── v1.3.0 P3: AI 渲染接入契约固化（ControlNet + Depth Anything V2 + SDXL-Turbo）──
# 对标 2026 行业强制 Geometry Locking：ControlNet 几何约束作硬边界，不 hallucinate 墙体/承重柱
# 接入链：Depth Anything V2（深度图预处理）→ ControlNet（几何锁定）→ SDXL-Turbo（快速预览可选）

# ControlNet 类型（controlnet_type 受支持集合）
CONTROLNET_TYPES = ["depth", "canny", "mlsd", "lineart"]
# 采样器（2026 主流：dpm++_2m_karras 稳定 / uni_pc 快速）
RENDER_SCHEDULERS = ["dpm++_2m_karras", "uni_pc"]
# 置信度阈值：< 0.7 自动降级（对标行业 AI 渲染可信度红线）
CONFIDENCE_THRESHOLD = 0.7
# SDXL-Turbo 契约：15s 内 95% 空间准确度（快速预览场景）
SDXL_TURBO_TARGET_SPATIAL_ACCURACY = 0.95
SDXL_TURBO_TARGET_LATENCY_S = 15.0

# 降级链级别（透明披露给客户端）
DEGRADATION_LEVELS = {
    0: "controlnet",      # L0: 真实 ControlNet 几何锁定（置信度 >= 0.7）
    1: "mock-geometry",   # L1: 后端返回但置信度 < 0.7 → 自动降级到几何锁定 mock
    2: "placeholder",     # L2: 后端未配置/不可达 → 占位图
    3: "error",           # L3: contract_strict + require_real → 503 诚实报错
}

# 渲染契约 schema（供 /capabilities 端点与测试核验，固化后续一键接入真实后端的接口）
RENDER_CONTRACT = {
    "request": {
        "input_image": "str (base64) | URL",
        "depth_map": "str (Depth Anything V2 预处理深度图, base64)",
        "controlnet_type": CONTROLNET_TYPES,
        "controlnet_weight": "float 0.7-0.9",
        "prompt": "str (英文 SD 提示词)",
        "negative_prompt": "str (含 'structural changes:1.5' 权重防幻觉)",
        "scheduler": RENDER_SCHEDULERS,
        "steps": "int 25-30",
        "guidance_scale": "float 7-9",
    },
    "response": {
        "images": "list[str] (URL/base64)",
        "confidence": "float 0-1",
        "spatial_accuracy": "float 0-1",
        "processing_time": "float 秒",
        "backend_version": "str",
    },
    "degradation_chain": DEGRADATION_LEVELS,
    "confidence_threshold": CONFIDENCE_THRESHOLD,
    "backends": {
        "controlnet": "几何锁定，置信度>=0.7 可用（对标 2026 行业强制）",
        "sdxl_turbo": f"{SDXL_TURBO_TARGET_LATENCY_S:.0f}s 内 {SDXL_TURBO_TARGET_SPATIAL_ACCURACY*100:.0f}% 空间准确度，快速预览",
        "mock": "占位图，reconstruction_available=False",
    },
}


class RenderUnavailableError(Exception):
    """v1.3.0 P3: 真实渲染后端不可用且契约严格模式要求真实（L3 诚实报错）

    由 render_2d/render_3d 在降级链 L3 时抛出，API 层捕获后转 HTTP 503。
    """

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


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
        require_real: bool = False,
    ) -> dict:
        """2D 效果图生成 — LLM 生成 SD prompt + 真实渲染后端 / 诚实降级

        v1.3.0 P3: 接入契约固化（ControlNet + Depth Anything V2 + SDXL-Turbo），
        4 级降级链（L0 controlnet / L1 mock-geometry / L2 placeholder / L3 503）。
        require_real=True 且 contract_strict=True 时，后端不可用抛 RenderUnavailableError。
        """
        start = time.perf_counter()

        # v1.14.0 P0-2: 渲染前输入侧确定性几何一致性校验
        # （像素级输出↔参考一致性需视觉模型，本层仅校验输入几何，诚实标注）
        consistency_check = None
        if get_settings().render_consistency_check_enabled:
            from app.services.spatial_semantics_service import validate_floorplan_consistency
            fp_ref = layout_json.get("floorplan", layout_json) if isinstance(layout_json, dict) else layout_json
            consistency_check = validate_floorplan_consistency(fp_ref)

        # v1.13.4（评估体系维度）：走缓存版偏好查询（与 /chat 端点一致）
        preference_hint = await get_pref_hint_cached(
            user_id, "designer", db,
            max_examples=get_settings().agent_learning_max_examples,
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

        # v1.3.0 P3: 接入契约 + 4 级降级链
        placeholder_url = self._placeholder_url("2d", style)
        real_raw = None
        backend_reachable = False
        if settings.real_ai_render_enabled and settings.ai_render_backend_url:
            contract_req = self._select_backend_request(sd_prompt)
            contract_req.update({"type": "2d", "style": style, "layout": layout_json})
            real_raw = await self._call_render_backend(contract_req)
            backend_reachable = real_raw is not None

        degraded = self._apply_degradation_chain(
            real_raw, backend_reachable, require_real, placeholder_url
        )
        if degraded.get("error"):
            raise RenderUnavailableError(degraded["degradation_reason"])

        result = {
            "prompt": sd_prompt,
            "description": description,
            "placeholder_image_url": degraded["image_url"],  # 兼容字段名
            "image_url": degraded["image_url"],
            "render_backend": degraded["render_backend"],
            "reconstruction_available": degraded["reconstruction_available"],
            "degradation_chain_level": degraded["level"],
            "degradation_reason": degraded["degradation_reason"],
            "confidence": degraded["confidence"],
            "spatial_accuracy": degraded["spatial_accuracy"],
            "backend_version": degraded["backend_version"],
            "style": style,
            "model_used": settings.deepseek_model,
            "processing_time_ms": processing_ms,
            "consistency_check": consistency_check,
            "preference_hint_applied": hint_applied,
        }
        return annotate_output(result, content_type="render", source="render_2d")

    async def render_3d(
        self,
        floorplan: dict,
        style: str,
        user_id: str,
        db,
        require_real: bool = False,
    ) -> dict:
        """3D 场景生成 — 多视角 prompt + 真实 3D 重建 / 诚实降级

        v1.3.0 P3: 接入契约固化，4 级降级链。reconstruction_available 诚实标识
        3DGS 后端是否真实执行（L0=True，其余 False）。保留 reconstruction_params
        字段向后兼容测试。
        """
        start = time.perf_counter()

        # v1.13.4（评估体系维度）：走缓存版偏好查询（与 /chat 端点一致）
        preference_hint = await get_pref_hint_cached(
            user_id, "designer", db,
            max_examples=get_settings().agent_learning_max_examples,
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

        # v1.3.0 P3: 接入契约 + 4 级降级链（3D 重建场景）
        placeholder_url = self._placeholder_url("3d", style)
        real_raw = None
        backend_reachable = False
        if settings.real_ai_render_enabled and settings.ai_render_backend_url:
            contract_req = self._select_backend_request(prompts[0] if prompts else "")
            contract_req.update({
                "type": "3d", "style": style, "floorplan": floorplan, "prompts": prompts,
            })
            real_raw = await self._call_render_backend(contract_req)
            backend_reachable = real_raw is not None

        degraded = self._apply_degradation_chain(
            real_raw, backend_reachable, require_real, placeholder_url
        )
        if degraded.get("error"):
            raise RenderUnavailableError(degraded["degradation_reason"])

        reconstruction_available = degraded["reconstruction_available"]
        # 保留 reconstruction_params 字段兼容测试
        if reconstruction_available:
            reconstruction_params = {
                "method": "3dgs",
                "available": True,
                "iterations": (real_raw or {}).get("iterations", 30000),
                "resolution": (real_raw or {}).get("resolution", "1024x1024"),
            }
        else:
            reconstruction_params = {
                "method": "3dgs",
                "available": False,
                "reason": degraded["degradation_reason"] or "backend_unavailable",
            }

        result = {
            "prompts": prompts,
            "reconstruction_params": reconstruction_params,
            "reconstruction_available": reconstruction_available,
            "render_backend": degraded["render_backend"],
            "placeholder_model_url": degraded["image_url"],  # 兼容字段名
            "model_url": degraded["image_url"],
            "degradation_chain_level": degraded["level"],
            "degradation_reason": degraded["degradation_reason"],
            "confidence": degraded["confidence"],
            "spatial_accuracy": degraded["spatial_accuracy"],
            "backend_version": degraded["backend_version"],
            "style": style,
            "model_used": settings.deepseek_model,
            "processing_time_ms": processing_ms,
            "preference_hint_applied": hint_applied,
        }
        return annotate_output(result, content_type="render", source="render_3d")

    async def restage_photo(
        self,
        photo_data: bytes,
        mode: str,
        style: str,
        user_id: str,
        db,
        require_real: bool = False,
    ) -> dict:
        """照片重布置 — inpainting 或 full_regen 模式

        v1.3.0 P3: 接入契约固化，4 级降级链。
        v1.2.0: _detect_room_type 诚实化（不再 len%len 伪随机）。
        """
        start = time.perf_counter()

        # v1.13.4（评估体系维度）：走缓存版偏好查询（与 /chat 端点一致，
        # 避免每次渲染重复 DB 查询；TTL 由 pref_hint_cache_ttl 控制）
        preference_hint = await get_pref_hint_cached(
            user_id, "designer", db,
            max_examples=get_settings().agent_learning_max_examples,
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

        # v1.3.0 P3: 接入契约 + 4 级降级链
        # 注：restage 真实接入需将 photo_data 转 base64 作为 input_image（契约字段），
        # 当前 contract固化阶段仅传 prompt + 元数据，真实接入时由适配器层补 base64。
        placeholder_url = self._placeholder_url("restage", style)
        real_raw = None
        backend_reachable = False
        if settings.real_ai_render_enabled and settings.ai_render_backend_url:
            contract_req = self._select_backend_request(sd_prompt)
            contract_req.update({
                "type": "restage", "mode": mode, "style": style,
                "photo_size": len(photo_data),
            })
            real_raw = await self._call_render_backend(contract_req)
            backend_reachable = real_raw is not None

        degraded = self._apply_degradation_chain(
            real_raw, backend_reachable, require_real, placeholder_url
        )
        if degraded.get("error"):
            raise RenderUnavailableError(degraded["degradation_reason"])

        result = {
            "mode": mode,
            "prompt": sd_prompt,
            "placeholder_result_url": degraded["image_url"],  # 兼容字段名
            "result_url": degraded["image_url"],
            "detected_room_type": detected_room_type,
            "render_backend": degraded["render_backend"],
            "reconstruction_available": degraded["reconstruction_available"],
            "degradation_chain_level": degraded["level"],
            "degradation_reason": degraded["degradation_reason"],
            "confidence": degraded["confidence"],
            "spatial_accuracy": degraded["spatial_accuracy"],
            "backend_version": degraded["backend_version"],
            "style": style,
            "model_used": settings.deepseek_model,
            "processing_time_ms": processing_ms,
            "preference_hint_applied": hint_applied,
        }
        return annotate_output(result, content_type="render", source="restage_photo")

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

    # ── v1.3.0 P3: 渲染接入契约方法 ──────────────────────────

    def _build_controlnet_request(
        self,
        prompt: str,
        input_image: str | None = None,
        depth_map: str | None = None,
        controlnet_type: str = "depth",
    ) -> dict:
        """v1.3.0 P3: 构造 ControlNet + Depth Anything V2 标准化请求

        接入契约：客户端可基于本 schema 直接对接真实 ControlNet 后端
        （diffusers / AUTOMATIC1111 API / 第三方渲染服务）。
        几何锁定：controlnet_type=depth 时，depth_map 由 Depth Anything V2
        预处理生成，作为硬边界约束生成不 hallucinate 墙体/承重柱。
        """
        if controlnet_type not in CONTROLNET_TYPES:
            controlnet_type = "depth"
        # negative_prompt 含 structural changes 权重，防止 LLM prompt 触发结构性幻觉
        negative_prompt = (
            "(structural changes:1.5), load-bearing wall removal, "
            "pillar removal, ceiling height change, window enlargement, "
            "low quality, blurry, deformed, watermark"
        )
        return {
            "input_image": input_image or "",
            "depth_map": depth_map or "",
            "controlnet_type": controlnet_type,
            "controlnet_weight": 0.8,  # 0.7-0.9 中位
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "scheduler": "dpm++_2m_karras",
            "steps": 28,  # 25-30 中位
            "guidance_scale": 8.0,  # 7-9 中位
            "backend_type": "controlnet",
        }

    def _build_sdxl_turbo_request(
        self,
        prompt: str,
        input_image: str | None = None,
    ) -> dict:
        """v1.3.0 P3: 构造 SDXL-Turbo 快速预览请求

        契约：15s 内 95% 空间准确度，适合快速预览（非最终交付）。
        减少步数 + 低 guidance 换取延迟，牺牲细节保空间结构。
        """
        return {
            "input_image": input_image or "",
            "prompt": prompt,
            "negative_prompt": "(structural changes:1.5), low quality, blurry",
            "scheduler": "uni_pc",  # 快速采样器
            "steps": 8,  # Turbo 模式少步数
            "guidance_scale": 1.5,  # Turbo 低 guidance
            "backend_type": "sdxl_turbo",
        }

    def _standardize_backend_response(self, raw: dict | None, backend_type: str) -> dict:
        """v1.3.0 P3: 标准化后端响应为契约 schema

        后端返回字段名可能不一致，本方法归一到
        {images, confidence, spatial_accuracy, processing_time, backend_version}。
        """
        if not raw:
            return {
                "images": [],
                "confidence": 0.0,
                "spatial_accuracy": 0.0,
                "processing_time": 0.0,
                "backend_version": "unknown",
            }
        # 兼容多种字段名：images | image_url | model_url
        images = raw.get("images") or []
        if not images:
            for key in ("image_url", "model_url", "url"):
                if raw.get(key):
                    images = [raw[key]]
                    break
        return {
            "images": images,
            "confidence": float(raw.get("confidence", 0.0)),
            "spatial_accuracy": float(raw.get("spatial_accuracy", raw.get("confidence", 0.0))),
            "processing_time": float(raw.get("processing_time", 0.0)),
            "backend_version": raw.get("backend_version", backend_type),
        }

    def _apply_degradation_chain(
        self,
        real_raw: dict | None,
        backend_reachable: bool,
        require_real: bool,
        placeholder_url: str,
    ) -> dict:
        """v1.3.0 P3: 4 级降级链决策

        L0 controlnet      : 后端可达 + 置信度 >= 0.7
        L1 mock-geometry   : 后端可达但置信度 < 0.7 → 自动降级
        L2 placeholder     : 后端不可达/未配置 → 占位图
        L3 error           : contract_strict + require_real → 503（调用方抛 HTTPException）

        Returns:
            降级决策 dict，含 level/render_backend/reconstruction_available/
            degradation_reason/confidence/spatial_accuracy/backend_version/image_url。
            L3 时含 ``"error": True``，调用方据此抛 503。
        """
        settings = get_settings()
        std = self._standardize_backend_response(real_raw, settings.ai_render_backend_type)

        # L0/L1: 后端可达且有响应
        if backend_reachable and real_raw:
            if std["confidence"] >= CONFIDENCE_THRESHOLD:
                return {
                    "level": 0,
                    "render_backend": settings.ai_render_backend_type,
                    "reconstruction_available": True,
                    "degradation_reason": None,
                    "confidence": std["confidence"],
                    "spatial_accuracy": std["spatial_accuracy"],
                    "backend_version": std["backend_version"],
                    "image_url": std["images"][0] if std["images"] else placeholder_url,
                }
            # L1: 置信度不足自动降级
            return {
                "level": 1,
                "render_backend": "mock",
                "reconstruction_available": False,
                "degradation_reason": (
                    f"confidence_below_threshold ({std['confidence']:.2f} < {CONFIDENCE_THRESHOLD})"
                ),
                "confidence": std["confidence"],
                "spatial_accuracy": std["spatial_accuracy"],
                "backend_version": std["backend_version"],
                "image_url": placeholder_url,
            }

        # L3: 严格模式 + 客户端要求真实 → 诚实报错
        if require_real and settings.ai_render_contract_strict:
            return {
                "level": 3,
                "error": True,
                "render_backend": "unavailable",
                "reconstruction_available": False,
                "degradation_reason": "real render required but backend unavailable (contract_strict=true)",
            }

        # L2: 占位图降级
        return {
            "level": 2,
            "render_backend": "mock",
            "reconstruction_available": False,
            "degradation_reason": "backend_unavailable_or_not_configured",
            "confidence": 0.0,
            "spatial_accuracy": 0.0,
            "backend_version": "mock-v1.3.0",
            "image_url": placeholder_url,
        }

    def _select_backend_request(self, prompt: str, input_image: str | None = None) -> dict:
        """v1.3.0 P3: 按 ai_render_backend_type 选择契约请求构造器"""
        settings = get_settings()
        if settings.ai_render_backend_type == "sdxl_turbo":
            return self._build_sdxl_turbo_request(prompt, input_image)
        # 默认 controlnet（含 depth/canny 等）
        return self._build_controlnet_request(prompt, input_image)

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
    def _detect_room_type(photo_data: bytes, room_name: str | None = None) -> str:
        """v1.2.0 P1 修复：诚实化房间类型检测

        优先级：
        1. 如果调用方提供了 room_name（如 API 请求中的房间名），直接使用
        2. 尝试从房间名称中正则推断（含中文房间名映射）
        3. spatial_perception_enabled=True 时标识视觉能力待接入
        4. 诚实降级返回 "unknown"

        Args:
            photo_data: 照片二进制数据（用于未来视觉模型推断）
            room_name: 可选的房间名称（来自 API 请求 / 户型数据）
        """
        # 优先级 1：直接使用提供的房间名
        if room_name:
            logger.info(
                "room_type_from_name: room_name=%s", room_name,
                extra={"source": "api_request"},
            )
            return room_name

        # 优先级 2：正则回退 — 从可能的上下文数据中推断
        # photo_data 中可能包含文件名/元数据，尝试从字节中解析
        try:
            text_hint = photo_data[:512].decode("utf-8", errors="ignore")
        except Exception:
            text_hint = ""

        import re
        room_patterns = {
            "living_room": r"(客厅|起居室|living\s*room)",
            "bedroom":     r"(卧室|主卧|次卧|bedroom)",
            "kitchen":     r"(厨房|kitchen)",
            "bathroom":    r"(卫生间|浴室|厕所|bathroom)",
            "study":       r"(书房|study)",
            "balcony":     r"(阳台|balcony)",
            "dining_room": r"(餐厅|dining\s*room)",
            "hallway":     r"(走廊|玄关|过道|hallway)",
        }
        for room_type, pattern in room_patterns.items():
            if re.search(pattern, text_hint, re.IGNORECASE):
                logger.info(
                    "room_type_from_regex: detected=%s", room_type,
                    extra={"source": "regex_fallback"},
                )
                return room_type

        # 优先级 3：视觉模型开关已开但模型未接入
        settings = get_settings()
        if settings.spatial_perception_enabled:
            logger.info(
                "room_type_visual_pending: spatial_perception enabled but model not wired",
                extra={"source": "visual_pending"},
            )
            return "visual-pending"

        # 优先级 4：诚实降级
        logger.info(
            "room_type_unknown: no name, no regex match, spatial perception disabled",
            extra={"source": "unknown_fallback"},
        )
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
