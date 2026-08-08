"""全链路诊断系统模型 — 性能指标快照 / 全链路 Trace / 异常告警 / 优化建议 / RUM

v1.10.x 落地（对齐 2026 行业前沿 MELT+P 可观测性）：
- DiagnosticMetricSnapshot：指标滚动快照（FC 无持久 Prometheus，落库支撑历史趋势图）
- DiagnosticTrace：全链路追踪记录（HTTP→DB→LLM/Agent span 关联，spans 存 JSON）
- DiagnosticAlert：异常检测告警（规则 + z-score 统计），状态机 open/ack/resolved
- DiagnosticRecommendation：规则引擎生成的性能优化建议
- DiagnosticRumEvent：前端 RUM（Core Web Vitals：LCP/CLS/INP/FCP/TTFB）

采集路径全部受 settings.diagnostics_enabled 门控，关闭时零开销。
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Float, Integer, JSON, CheckConstraint, func, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DiagnosticMetricSnapshot(Base):
    """指标滚动快照（表 diagnostic_metric_snapshots）

    每个采样窗口每个 metric_key 一条：聚合该窗口内端点/系统指标的
    count / error_count / avg / p50 / p95 / p99 / max 及 extra 明细
    （如 LLM token、缓存命中次数）。
    """

    __tablename__ = "diagnostic_metric_snapshots"
    __table_args__ = (
        Index("ix_diag_snapshot_key_window", "category", "metric_key", "window_start"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    category: Mapped[str] = mapped_column(
        String(30), nullable=False, default="endpoint",
    )  # endpoint / system / llm / cache / rum
    metric_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)

    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    p50_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    p95_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    p99_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    extra: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DiagnosticTrace(Base):
    """全链路追踪记录（表 diagnostic_traces）

    一条记录 = 一次被采样的 HTTP 请求。spans 字段存储子 span 明细：
    LLM 调用（provider/latency/status/agent/fallback）、慢查询 SQL 片段等。
    对齐 OTel GenAI 语义约定：agent span（agent_name）+ model span（llm spans）。
    """

    __tablename__ = "diagnostic_traces"
    __table_args__ = (
        Index("ix_diag_trace_time", "started_at"),
        Index("ix_diag_trace_endpoint_time", "endpoint", "started_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
    )  # trace_id（与 HTTP 请求 X-Request-ID 一致）
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    has_error: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)  # status >= 400

    db_query_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    db_query_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    llm_call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    llm_fallback_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    agent_names: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # 子 span 明细（LLM 调用 / 慢查询等），最多保留 20 条防膨胀
    spans: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )


class DiagnosticAlert(Base):
    """系统异常告警（表 diagnostic_alerts）

    由诊断分析引擎（规则 + z-score）生成。状态机：
    open → ack（已确认）→ resolved（已解决）。同 metric_key 已有 open/ack
    告警时不重复创建（去重）。
    """

    __tablename__ = "diagnostic_alerts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'ack', 'resolved')",
            name="chk_diag_alert_status",
        ),
        Index("ix_diag_alert_status_time", "status", "detected_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    alert_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
    )  # error_rate_spike / latency_p95_high / slow_query_burst / llm_fallback_spike / db_query_storm / rum_lcp_poor / zscore_deviation
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="warning",
    )  # info / warning / critical
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metric_key: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DiagnosticRecommendation(Base):
    """性能优化建议（表 diagnostic_recommendations）

    由规则引擎从快照/全链路 trace 证据生成可执行建议
    （缓存、索引、N+1 优化、LLM 路由、降级路径等）。
    """

    __tablename__ = "diagnostic_recommendations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    category: Mapped[str] = mapped_column(
        String(30), nullable=False,
    )  # cache / db_index / n_plus_one / llm_routing / error_handling / general
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="info",
    )  # info / warning / critical
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DiagnosticRumEvent(Base):
    """前端 RUM 性能事件（表 diagnostic_rum_events）

    由 webapp PerformanceObserver 采集（LCP/CLS/INP/FCP/TTFB），
    经 /api/analytics/collect 上报，受 settings.diagnostics_rum_enabled 门控。
    对齐 Core Web Vitals 指标定义。
    """

    __tablename__ = "diagnostic_rum_events"
    __table_args__ = (
        Index("ix_diag_rum_metric_time", "metric", "recorded_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    page: Mapped[str | None] = mapped_column(String(200), nullable=True)
    metric: Mapped[str] = mapped_column(
        String(30), nullable=False,
    )  # lcp / cls / inp / fcp / ttfb
    value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    extra: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )
