"""可观测性子包 — OpenTelemetry 分布式追踪。

v1.2.2 F4：补齐 logs/metrics/traces 三支柱中的 tracing。
"""
from app.observability.tracing import (
    inject_trace_context,
    instrument_fastapi,
    setup_tracing,
)

__all__ = ["setup_tracing", "instrument_fastapi", "inject_trace_context"]
