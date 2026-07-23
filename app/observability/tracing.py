"""OpenTelemetry 分布式追踪 — 补齐 logs/metrics/traces 可观测三支柱。

设计要点
--------
1. **完全 feature-flag 门控**：``tracing_enabled=False``（默认）时 ``setup_tracing``
   立即返回，不导入 OTel 仪表化包、不创建 span，运行时零开销。生产可灰度开启。
2. **依赖缺失优雅降级**：OTel 包未安装时 ``setup_tracing`` 记 warning 并返回 ``None``，
   应用照常运行（追踪为可选增强，非硬依赖）。
3. **FastAPI 仪表化**：``instrument_fastapi(app)`` 为每个 HTTP 请求生成 server span，
   必须在 app 创建且路由注册后、服务启动前调用（项目在 lifespan startup 调用）。
4. **SQLAlchemy 仪表化**：``enable()`` 全局补丁方言，为 DB 查询生成 client span。
5. **日志-追踪关联**：``inject_trace_context`` structlog 处理器将活跃 span 的
   ``trace_id``/``span_id`` 注入日志事件，便于在 Jaeger/Tempo 中按 trace 检索日志。

导出端点
--------
- ``otel_exporter_otlp_endpoint`` 非空 → ``OTLPSpanExporter``（HTTP）导出到 collector
- 为空 → ``ConsoleSpanExporter``（仅本地调试，span 打到 stdout）

安全
----
- 追踪不应记录 PII。OTel FastAPI 仪表化默认捕获 method/url/status，不记录 body/headers
  （除非显式配置 ``capture_headers``，本项目不开启）。
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

logger = logging.getLogger("ihome.tracing")

# 模块级状态：避免重复初始化（lifespan 可能多次进入，测试也会调用）
_tracing_initialized: bool = False


# ════════════════════════════════════════════════════════════════
# 日志-追踪关联处理器
# ════════════════════════════════════════════════════════════════


def inject_trace_context(_logger, _method_name, event_dict: dict) -> dict:
    """structlog 处理器：将活跃 OTel span 的 trace_id/span_id 注入日志事件。

    OTel 未安装或当前无活跃 span 时原样返回（零开销 no-op），因此可安全加入
    始终生效的 ``_shared_processors`` 链——无论 tracing_enabled 与否都不影响日志。

    注入字段：
    - ``trace_id``：32 hex（128-bit W3C trace id）
    - ``span_id``：16 hex（64-bit span id）
    """
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context() if span is not None else None
        if ctx is not None and ctx.is_valid:
            event_dict["trace_id"] = f"{ctx.trace_id:032x}"
            event_dict["span_id"] = f"{ctx.span_id:016x}"
    except Exception:
        # OTel 未安装 / 无活跃 span：静默 no-op，绝不影响日志输出
        pass
    return event_dict


# ════════════════════════════════════════════════════════════════
# SDK 初始化 + 仪表化
# ════════════════════════════════════════════════════════════════


def setup_tracing(settings) -> Optional[Callable[[], None]]:
    """初始化 OTel SDK（TracerProvider + SpanProcessor）并启用 SQLAlchemy 仪表化。

    Args:
        settings: 应用配置对象（Settings 实例）。

    Returns:
        shutdown 回调：调用以刷新并关闭 tracer provider（在 lifespan teardown 使用）；
        ``tracing_enabled=False`` 或 OTel 依赖缺失时返回 ``None``（无追踪）。
    """
    global _tracing_initialized

    if _tracing_initialized:
        logger.debug("tracing: already initialized, skip")
        return None

    if not getattr(settings, "tracing_enabled", False):
        # 默认路径：追踪关闭，零开销
        return None

    # ── 延迟导入：仅在 tracing_enabled=True 时才加载 OTel 包 ──
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning(
            "tracing_enabled=True 但 opentelemetry-sdk 未安装，追踪已禁用。"
            "安装：pip install opentelemetry-sdk opentelemetry-exporter-otlp "
            "opentelemetry-instrumentation-fastapi "
            "opentelemetry-instrumentation-sqlalchemy"
        )
        return None

    service_name = getattr(settings, "otel_service_name", "") or "i-home-life"
    endpoint = getattr(settings, "otel_exporter_otlp_endpoint", "") or ""

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": getattr(settings, "app_version", "unknown"),
            # 部署环境标记，便于在 Tempo/Jaeger 中按环境筛选
            "deployment.environment": "dev" if getattr(settings, "debug", False) else "prod",
        }
    )
    provider = TracerProvider(resource=resource)

    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
            )
            logger.info("tracing: enabled, exporting to OTLP endpoint=%s", endpoint)
        except ImportError:
            # 有 SDK 但缺 OTLP exporter：退回 console，保证追踪不静默丢失
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter

            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
            logger.warning(
                "tracing: otel_exporter_otlp_endpoint 已配置但 "
                "opentelemetry-exporter-otlp 未安装，退回 console exporter"
            )
    else:
        # 无 endpoint：console exporter 便于本地调试观察 span
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter

        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        logger.info("tracing: enabled, no OTLP endpoint, using console exporter")

    trace.set_tracer_provider(provider)

    # ── SQLAlchemy 仪表化：DB 查询 client span ──
    # 全局补丁方言（不传 engine），对已创建的 engine 也生效；
    # enable_commenter=False 避免向 SQL 注入注释（部分 SQLite 边界场景对尾部注释敏感）。
    # 注：OTel 0.40+ 将 enable() 改名为 instrument()，这里用 instrument。
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().instrument(enable_commenter=False)
        logger.info("tracing: SQLAlchemy instrumentation enabled")
    except ImportError:
        logger.warning(
            "tracing: opentelemetry-instrumentation-sqlalchemy 未安装，跳过 DB 仪表化"
        )
    except Exception as exc:  # noqa: BLE001 — 仪表化失败不应阻断启动
        logger.warning("tracing: SQLAlchemy 仪表化失败: %s", exc)

    _tracing_initialized = True

    def shutdown() -> None:
        """刷新未导出的 span 并关闭 provider（lifespan teardown 调用）。"""
        try:
            provider.force_flush(timeout_millis=5000)
            provider.shutdown()
        except Exception as exc:  # noqa: BLE001
            logger.warning("tracing: provider shutdown error: %s", exc)

    return shutdown


def instrument_fastapi(app) -> None:
    """对已创建的 FastAPI app 执行 HTTP 仪表化（server span）。

    必须在 app 创建且路由注册后、服务启动前调用。tracing 未启用
    （``_tracing_initialized=False``）时为 no-op。
    """
    if not _tracing_initialized:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        logger.info("tracing: FastAPI instrumentation enabled")
    except ImportError:
        logger.warning(
            "tracing: opentelemetry-instrumentation-fastapi 未安装，跳过 HTTP 仪表化"
        )
    except Exception as exc:  # noqa: BLE001 — 仪表化失败不应阻断请求处理
        logger.warning("tracing: FastAPI 仪表化失败: %s", exc)


def reset_tracing_state_for_tests() -> None:
    """重置模块级初始化状态（仅测试用，确保隔离）。"""
    global _tracing_initialized
    _tracing_initialized = False


__all__ = [
    "setup_tracing",
    "instrument_fastapi",
    "inject_trace_context",
    "reset_tracing_state_for_tests",
]
