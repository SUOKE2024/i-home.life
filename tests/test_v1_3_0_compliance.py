"""v1.3.0 合规与一致性测试

覆盖：
- 版本号一致性（app_version == 1.3.0）
- 新增 feature flag 默认值正确
- 国标合规：GB/T 50500-2024 / GB/T 50854-2024 已入 standards.json
- 国标年份笔误修正（50327-2017 / 50303-2016 应为空）
- 算量 Agent system_prompt 注入 GB/T 50854-2024
- ForwardTakeoffResult.compliance 字段存在
- AI 渲染接入契约 schema 完整性（ControlNet + Depth Anything V2 + SDXL-Turbo）
- AI 渲染 4 级降级链
"""

import json
import os

from app.agents.takeoff_agent import TakeoffAgent
from app.config import get_settings
from app.services.ai_render_service import (
    AIRenderService,
    CONFIDENCE_THRESHOLD,
    CONTROLNET_TYPES,
    DEGRADATION_LEVELS,
    RENDER_CONTRACT,
    RENDER_SCHEDULERS,
    SDXL_TURBO_TARGET_LATENCY_S,
    SDXL_TURBO_TARGET_SPATIAL_ACCURACY,
)


# === 版本号一致性 ===


def test_app_version_is_1_13_6():
    """app_version == 1.13.6"""
    assert get_settings().app_version == "1.13.6"


def test_mcp_server_version_is_1_13_6():
    """MCP SERVER_VERSION == 1.13.6"""
    from app.mcp.server import mcp_server
    assert mcp_server.SERVER_VERSION == "1.13.6"


# === 新增 feature flag 默认值 ===


def test_new_feature_flags_defaults():
    """v1.3.0 新增 feature flag 默认值正确"""
    s = get_settings()
    # MCP 2026-07-28 对齐 flag（默认启用）
    assert s.mcp_discover_enabled is True
    assert s.mcp_mrtr_enabled is True
    assert s.mcp_tasks_extension_enabled is True
    # 缓存硬约束 strict 模式（默认启用）
    assert s.cache_user_isolation_strict is True
    # AI 渲染契约（默认启用 strict，real 默认关闭）
    assert s.ai_render_contract_strict is True
    assert s.ai_render_backend_type == "controlnet"
    # P4 灰度 flag（H-IFC v1.13.2 起默认开启；MEP 叠加 v1.13.5 起默认开启——
    # SVG 纯 Python 生成零外部依赖，规则派生 + 占位示意诚实标注）
    assert s.ifc_h_ifc_extension_enabled is True
    assert s.construction_drawing_mep_enabled is True


# === 国标合规：standards.json ===


def test_standards_json_contains_gb_50500_2024():
    """standards.json 含 GB/T 50500-2024 清单计价标准"""
    std_path = os.path.join(os.path.dirname(__file__), "..", "knowledge", "standards.json")
    with open(std_path, encoding="utf-8") as f:
        data = json.load(f)
    # standards.json 为顶层列表
    standards = data if isinstance(data, list) else data.get("standards", [])
    numbers = [s.get("standard_number", "") for s in standards]
    assert "GB/T 50500-2024" in numbers, "缺 GB/T 50500-2024 清单计价标准条目"


def test_standards_json_contains_gb_50854_2024():
    """standards.json 含 GB/T 50854-2024 工程量计算标准"""
    std_path = os.path.join(os.path.dirname(__file__), "..", "knowledge", "standards.json")
    with open(std_path, encoding="utf-8") as f:
        data = json.load(f)
    standards = data if isinstance(data, list) else data.get("standards", [])
    numbers = [s.get("standard_number", "") for s in standards]
    assert "GB/T 50854-2024" in numbers, "缺 GB/T 50854-2024 工程量计算标准条目"


# === 国标年份笔误修正（应为 0 命中）===


def test_no_national_standard_year_typos():
    """国标年份笔误应为 0 命中：50327-2017 不存在；50303-2016 应为 2015"""
    import subprocess
    root = os.path.join(os.path.dirname(__file__), "..")
    # 在 app/ 与 app/standards/ 下搜索笔误
    result = subprocess.run(
        ["grep", "-rn", "-E", "50327-2017|50303-2016", "app/"],
        cwd=root, capture_output=True, text=True,
    )
    assert result.returncode == 1, f"仍存在国标年份笔误：\n{result.stdout}"
    assert result.stdout == "", f"国标年份笔误未清零：\n{result.stdout}"


# === 算量 Agent GB/T 50854-2024 注入 ===


def test_takeoff_agent_prompt_includes_gb_50854_2024():
    """TakeoffAgent system_prompt 注入 GB/T 50854-2024 工程量计算规则"""
    prompt = TakeoffAgent.agent_name  # noqa: F841 确认类可访问
    agent = TakeoffAgent.__new__(TakeoffAgent)  # 不走 __init__（需依赖）
    system_prompt = TakeoffAgent.system_prompt.fget(agent)
    assert "GB/T 50854-2024" in system_prompt
    assert "工程量计算标准" in system_prompt


def test_forward_takeoff_result_has_compliance_field():
    """ForwardTakeoffResult 数据类含 compliance 字段"""
    from app.services.quantity_takeoff_service import ForwardTakeoffResult
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(ForwardTakeoffResult)}
    assert "compliance" in field_names, "ForwardTakeoffResult 缺 compliance 字段"


# === AI 渲染接入契约 schema 完整性 ===


def test_render_contract_request_schema_complete():
    """AI 渲染契约 request schema 含 ControlNet + Depth Anything V2 全字段"""
    req = RENDER_CONTRACT["request"]
    assert "input_image" in req
    assert "depth_map" in req  # Depth Anything V2 预处理
    assert "controlnet_type" in req
    assert "controlnet_weight" in req
    assert "prompt" in req
    assert "negative_prompt" in req
    assert "scheduler" in req
    assert "steps" in req
    assert "guidance_scale" in req


def test_render_contract_response_schema_complete():
    """AI 渲染契约 response schema 含置信度 + 空间准确度"""
    resp = RENDER_CONTRACT["response"]
    assert "images" in resp
    assert "confidence" in resp
    assert "spatial_accuracy" in resp
    assert "processing_time" in resp
    assert "backend_version" in resp


def test_controlnet_types_includes_depth():
    """ControlNet 类型集合含 depth（对标 Depth Anything V2 几何锁定）"""
    assert "depth" in CONTROLNET_TYPES
    assert CONTROLNET_TYPES == ["depth", "canny", "mlsd", "lineart"]


def test_render_schedulers_are_2026_mainstream():
    """采样器为 2026 主流：dpm++_2m_karras / uni_pc"""
    assert "dpm++_2m_karras" in RENDER_SCHEDULERS
    assert "uni_pc" in RENDER_SCHEDULERS


def test_confidence_threshold_is_0_7():
    """置信度阈值 0.7（行业 AI 渲染可信度红线）"""
    assert CONFIDENCE_THRESHOLD == 0.7


def test_sdxl_turbo_contract_targets():
    """SDXL-Turbo 契约：15s 内 95% 空间准确度"""
    assert SDXL_TURBO_TARGET_LATENCY_S == 15.0
    assert SDXL_TURBO_TARGET_SPATIAL_ACCURACY == 0.95


def test_degradation_chain_has_4_levels():
    """4 级降级链：controlnet / mock-geometry / placeholder / error"""
    assert DEGRADATION_LEVELS[0] == "controlnet"
    assert DEGRADATION_LEVELS[1] == "mock-geometry"
    assert DEGRADATION_LEVELS[2] == "placeholder"
    assert DEGRADATION_LEVELS[3] == "error"


# === AI 渲染降级链决策逻辑 ===


def test_degradation_l2_placeholder_when_backend_unavailable():
    """L2: 后端不可达 → 占位图降级（reconstruction_available=False）"""
    svc = AIRenderService()
    degraded = svc._apply_degradation_chain(
        real_raw=None, backend_reachable=False, require_real=False,
        placeholder_url="https://example.com/placeholder.png",
    )
    assert degraded["level"] == 2
    assert degraded["render_backend"] == "mock"
    assert degraded["reconstruction_available"] is False
    assert degraded["degradation_reason"] == "backend_unavailable_or_not_configured"


def test_degradation_l3_error_when_require_real_and_strict():
    """L3: require_real + contract_strict → 诚实报错（error=True）"""
    svc = AIRenderService()
    degraded = svc._apply_degradation_chain(
        real_raw=None, backend_reachable=False, require_real=True,
        placeholder_url="https://example.com/placeholder.png",
    )
    assert degraded["level"] == 3
    assert degraded["error"] is True
    assert degraded["render_backend"] == "unavailable"


def test_degradation_l0_controlnet_when_confidence_high():
    """L0: 后端可达 + 置信度 >= 0.7 → 真实 ControlNet"""
    svc = AIRenderService()
    raw = {"images": ["https://example.com/render.png"], "confidence": 0.9, "spatial_accuracy": 0.88}
    degraded = svc._apply_degradation_chain(
        real_raw=raw, backend_reachable=True, require_real=False,
        placeholder_url="https://example.com/placeholder.png",
    )
    assert degraded["level"] == 0
    assert degraded["reconstruction_available"] is True
    assert degraded["confidence"] == 0.9


def test_degradation_l1_mock_when_confidence_below_threshold():
    """L1: 后端可达但置信度 < 0.7 → 自动降级到 mock"""
    svc = AIRenderService()
    raw = {"images": ["https://example.com/render.png"], "confidence": 0.5}
    degraded = svc._apply_degradation_chain(
        real_raw=raw, backend_reachable=True, require_real=False,
        placeholder_url="https://example.com/placeholder.png",
    )
    assert degraded["level"] == 1
    assert degraded["render_backend"] == "mock"
    assert degraded["reconstruction_available"] is False
    assert "confidence_below_threshold" in degraded["degradation_reason"]


def test_build_controlnet_request_schema():
    """_build_controlnet_request 构造标准化请求"""
    svc = AIRenderService()
    req = svc._build_controlnet_request("modern living room", controlnet_type="depth")
    assert req["controlnet_type"] == "depth"
    assert req["controlnet_weight"] == 0.8  # 0.7-0.9 中位
    assert req["scheduler"] == "dpm++_2m_karras"
    assert req["steps"] == 28  # 25-30 中位
    assert req["guidance_scale"] == 8.0  # 7-9 中位
    assert req["backend_type"] == "controlnet"
    # negative_prompt 含 structural changes 权重防幻觉
    assert "structural changes:1.5" in req["negative_prompt"]


def test_build_controlnet_request_invalid_type_falls_back_to_depth():
    """非法 controlnet_type 回退到 depth"""
    svc = AIRenderService()
    req = svc._build_controlnet_request("test", controlnet_type="invalid_type")
    assert req["controlnet_type"] == "depth"


def test_build_sdxl_turbo_request_schema():
    """_build_sdxl_turbo_request 构造快速预览请求"""
    svc = AIRenderService()
    req = svc._build_sdxl_turbo_request("test prompt")
    assert req["backend_type"] == "sdxl_turbo"
    assert req["scheduler"] == "uni_pc"  # 快速采样器
    assert req["steps"] == 8  # Turbo 少步数
    assert req["guidance_scale"] == 1.5  # Turbo 低 guidance


def test_standardize_backend_response_handles_none():
    """_standardize_backend_response: None 输入返回零值 schema"""
    svc = AIRenderService()
    std = svc._standardize_backend_response(None, "controlnet")
    assert std["images"] == []
    assert std["confidence"] == 0.0
    assert std["spatial_accuracy"] == 0.0
    assert std["backend_version"] == "unknown"


def test_standardize_backend_response_normalizes_fields():
    """_standardize_backend_response: 兼容 image_url/model_url 字段名"""
    svc = AIRenderService()
    std = svc._standardize_backend_response(
        {"image_url": "https://example.com/x.png", "confidence": 0.85}, "controlnet"
    )
    assert std["images"] == ["https://example.com/x.png"]
    assert std["confidence"] == 0.85
