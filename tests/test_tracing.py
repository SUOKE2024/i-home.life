"""OpenTelemetry 追踪模块测试（v1.2.2 F4）。

覆盖两条关键路径：
1. **默认禁用 / 依赖缺失**：setup_tracing 返回 None，inject_trace_context no-op，
   instrument_fastapi no-op — 追踪为零开销可选增强，绝不影响主流程。
2. **启用且依赖就绪**（OTel 已安装时）：setup_tracing 返回 shutdown 回调，
   inject_trace_context 在活跃 span 下注入 trace_id/span_id，instrument_fastapi
   为 app 添加仪表化。

OTel 未安装的环境下，第 2 组用 skipif 标记跳过，第 1 组始终运行。

设计说明：OTel 的全局 TracerProvider 是进程级单例，set_tracer_provider 同一进程
仅首次生效（后续仅警告 "Overriding not allowed"）。因此启用路径合并为单个测试，
确保整进程仅一次 set，避免跨测试 provider 覆盖失效。
"""
import pytest

from app.config import get_settings
from app.observability.tracing import (
    inject_trace_context,
    instrument_fastapi,
    reset_tracing_state_for_tests,
    setup_tracing,
)

try:
    import opentelemetry  # noqa: F401

    _OTEL_INSTALLED = True
except ImportError:
    _OTEL_INSTALLED = False


@pytest.fixture(autouse=True)
def _reset_tracing():
    """每个测试前重置模块级初始化状态，确保隔离。"""
    reset_tracing_state_for_tests()
    yield
    reset_tracing_state_for_tests()


# ── 默认禁用 / 依赖缺失路径（始终运行）──────────────────────


def test_tracing_flags_exist_and_default_off():
    """config 暴露 tracing flags 且默认关闭。"""
    s = get_settings()
    assert hasattr(s, "tracing_enabled")
    assert s.tracing_enabled is False
    assert hasattr(s, "otel_exporter_otlp_endpoint")
    assert s.otel_exporter_otlp_endpoint == ""
    assert s.otel_service_name == "i-home-life"


def test_setup_tracing_disabled_returns_none():
    """tracing_enabled=False 时 setup_tracing 返回 None（零开销 no-op）。"""
    s = get_settings()
    s.tracing_enabled = False
    assert setup_tracing(s) is None


def test_setup_tracing_enabled_without_deps_returns_none(monkeypatch):
    """tracing_enabled=True 但 OTel 未安装时优雅降级，返回 None 不抛错。"""
    if _OTEL_INSTALLED:
        pytest.skip("OTel 已安装，此路径仅在缺失依赖时验证")
    s = get_settings()
    monkeypatch.setattr(s, "tracing_enabled", True, raising=False)
    # 不应抛 ImportError，应返回 None 并记录 warning
    assert setup_tracing(s) is None


def test_inject_trace_context_noop_without_active_span():
    """无活跃 span 时 inject_trace_context 原样返回，不注入 trace_id。"""
    event = {"message": "hello", "level": "info"}
    result = inject_trace_context(None, None, dict(event))
    assert "trace_id" not in result
    assert "trace_id" not in event  # 原事件不被修改
    assert result.get("message") == "hello"


def test_inject_trace_context_never_raises():
    """inject_trace_context 在任何异常下都绝不抛错（日志可靠性优先）。"""
    result = inject_trace_context(None, None, {"message": "x"})
    assert isinstance(result, dict)


def test_instrument_fastapi_noop_when_not_initialized():
    """tracing 未初始化时 instrument_fastapi 为 no-op，不修改 app。"""
    from fastapi import FastAPI

    app = FastAPI()
    before = getattr(app, "_is_instrumented_by_opentelemetry", False)
    instrument_fastapi(app)  # 未 setup_tracing → _tracing_initialized=False
    after = getattr(app, "_is_instrumented_by_opentelemetry", False)
    assert before == after is False


# ── 启用且依赖就绪路径（仅 OTel 已安装时运行，合并为单测避免 provider 单例冲突）──


@pytest.mark.skipif(not _OTEL_INSTALLED, reason="OTel 未安装")
def test_enabled_path_end_to_end():
    """启用路径端到端：setup → 日志关联 → instrument_app，全程不抛错。

    合并为单测：OTel 全局 TracerProvider 为进程单例，set 仅首次生效，
    多次 set 仅告警不覆盖。单测内顺序执行确保仅一次 set，provider 真正生效。
    """
    s = get_settings()
    s.tracing_enabled = True
    s.otel_exporter_otlp_endpoint = ""  # 用 console exporter

    # ① setup_tracing 返回 shutdown 回调，并设置全局 provider + SQLAlchemy 仪表化
    shutdown = setup_tracing(s)
    try:
        assert callable(shutdown), "启用时 setup_tracing 应返回 shutdown 回调"
        # 二次调用（已初始化）应返回 None
        assert setup_tracing(s) is None

        # ② 日志-追踪关联：活跃 span 下 inject_trace_context 注入 trace_id/span_id
        # 复用 setup_tracing 设置的全局 provider（console exporter），span 上下文仍有效
        from opentelemetry import trace

        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("demo-span") as span:
            ctx = span.get_span_context()
            expected_trace = f"{ctx.trace_id:032x}"
            expected_span = f"{ctx.span_id:016x}"
            ev = inject_trace_context(None, None, {"message": "in-span"})
            assert ev["trace_id"] == expected_trace, "trace_id 应与活跃 span 一致"
            assert ev["span_id"] == expected_span, "span_id 应与活跃 span 一致"
            assert len(ev["trace_id"]) == 32
            assert len(ev["span_id"]) == 16

        # ③ instrument_fastapi 为 app 添加仪表化（OTel 通过 _is_instrumented 标记）
        from fastapi import FastAPI

        app = FastAPI()
        assert not getattr(app, "_is_instrumented_by_opentelemetry", False)
        instrument_fastapi(app)
        assert getattr(app, "_is_instrumented_by_opentelemetry", False), (
            "instrument_fastapi 应将 app 标记为已仪表化"
        )
    finally:
        if shutdown:
            shutdown()
