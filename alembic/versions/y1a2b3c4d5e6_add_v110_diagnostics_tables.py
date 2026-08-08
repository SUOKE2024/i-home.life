"""v1.10.x 全链路诊断系统 5 张新表建表迁移

Revision ID: y1a2b3c4d5e6
Revises: z8a9b0c1d2e3
Create Date: 2026-08-08

背景（2026-08-08 全链路诊断落地）：
v1.10.x 新增 5 张诊断表（diagnostic_metric_snapshots / diagnostic_traces /
diagnostic_alerts / diagnostic_recommendations / diagnostic_rum_events），
只有 ORM model 定义、由 create_all 建表，无 alembic 迁移。按项目双轨迁移
约定（新 model 必须同步 alembic 迁移链，否则空库 upgrade head 后缺失，
check_schema_drift 报 drift），本迁移补齐建表。

特性（与 z0e1f2a3b4c5 同策略）：
  - 幂等：_has_table 守卫，本地/生产已有表（create_all 建过）则 skip
  - 列/索引/唯一约束/CheckConstraint 与 app/models/diagnostics.py 对齐
  - 5 张表相互独立（无 FK 依赖），建表顺序任意
  - SQLite / PostgreSQL 通用；downgrade 整表删除（无索引回收问题）
"""
from typing import Sequence, Union

import logging

from alembic import op
import sqlalchemy as sa

# 复用 alembic 内置 logger 命名空间：随 alembic 命令输出，无需额外配置
logger = logging.getLogger("alembic.runtime.migration")


# revision identifiers, used by Alembic.
revision: str = "y1a2b3c4d5e6"
down_revision: Union[str, None] = "z8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        return table in inspector.get_table_names()
    except Exception:
        return False


def _create_if_missing(table_name: str, create_fn) -> None:
    """幂等建表：表已存在（本地/生产 create_all 建过）则 skip 并记录。"""
    if _has_table(table_name):
        logger.info("[%s] skip: table %s already exists", revision, table_name)
        return
    create_fn()
    logger.info("[%s] created: %s", revision, table_name)


def upgrade() -> None:
    bind = op.get_bind()
    logger.info("[%s] upgrade start: dialect=%s", revision, bind.dialect.name)

    # 1) diagnostic_metric_snapshots — 指标滚动快照（端点/系统/LLM/缓存）
    def _create_snapshots() -> None:
        op.create_table(
            "diagnostic_metric_snapshots",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("category", sa.String(30), nullable=False,
                      server_default="endpoint"),
            sa.Column("metric_key", sa.String(200), nullable=False),
            sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("avg_ms", sa.Float(), nullable=False, server_default="0"),
            sa.Column("p50_ms", sa.Float(), nullable=False, server_default="0"),
            sa.Column("p95_ms", sa.Float(), nullable=False, server_default="0"),
            sa.Column("p99_ms", sa.Float(), nullable=False, server_default="0"),
            sa.Column("max_ms", sa.Float(), nullable=False, server_default="0"),
            sa.Column("extra", sa.JSON(), nullable=False),
            sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "ix_diag_snapshot_key_window",
            "diagnostic_metric_snapshots", ["category", "metric_key", "window_start"],
        )
        op.create_index(
            "ix_diagnostic_metric_snapshots_metric_key",
            "diagnostic_metric_snapshots", ["metric_key"],
        )

    _create_if_missing("diagnostic_metric_snapshots", _create_snapshots)

    # 2) diagnostic_traces — 全链路追踪（HTTP 根 span + DB/LLM/Agent 子 span）
    def _create_traces() -> None:
        op.create_table(
            "diagnostic_traces",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), nullable=True),
            sa.Column("method", sa.String(10), nullable=False),
            sa.Column("endpoint", sa.String(200), nullable=False),
            sa.Column("status_code", sa.Integer(), nullable=False),
            sa.Column("duration_ms", sa.Float(), nullable=False, server_default="0"),
            sa.Column("has_error", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("db_query_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("db_query_ms", sa.Float(), nullable=False, server_default="0"),
            sa.Column("llm_call_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("llm_ms", sa.Float(), nullable=False, server_default="0"),
            sa.Column("llm_fallback_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("agent_names", sa.String(200), nullable=True),
            sa.Column("spans", sa.JSON(), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index(
            "ix_diag_trace_time", "diagnostic_traces", ["started_at"],
        )
        op.create_index(
            "ix_diag_trace_endpoint_time", "diagnostic_traces", ["endpoint", "started_at"],
        )
        op.create_index(
            "ix_diagnostic_traces_user_id", "diagnostic_traces", ["user_id"],
        )
        op.create_index(
            "ix_diagnostic_traces_endpoint", "diagnostic_traces", ["endpoint"],
        )

    _create_if_missing("diagnostic_traces", _create_traces)

    # 3) diagnostic_alerts — 异常告警（open/ack/resolved 状态机）
    def _create_alerts() -> None:
        op.create_table(
            "diagnostic_alerts",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("alert_type", sa.String(50), nullable=False),
            sa.Column("severity", sa.String(20), nullable=False,
                      server_default="warning"),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("metric_key", sa.String(200), nullable=True),
            sa.Column("value", sa.Float(), nullable=False, server_default="0"),
            sa.Column("threshold", sa.Float(), nullable=False, server_default="0"),
            sa.Column("evidence", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="open"),
            sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint(
                "status IN ('open', 'ack', 'resolved')",
                name="chk_diag_alert_status",
            ),
        )
        op.create_index(
            "ix_diag_alert_status_time", "diagnostic_alerts", ["status", "detected_at"],
        )
        op.create_index(
            "ix_diagnostic_alerts_metric_key", "diagnostic_alerts", ["metric_key"],
        )
        op.create_index(
            "ix_diagnostic_alerts_status", "diagnostic_alerts", ["status"],
        )

    _create_if_missing("diagnostic_alerts", _create_alerts)

    # 4) diagnostic_recommendations — 性能优化建议
    def _create_recommendations() -> None:
        op.create_table(
            "diagnostic_recommendations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("category", sa.String(30), nullable=False),
            sa.Column("severity", sa.String(20), nullable=False,
                      server_default="info"),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("evidence", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="open"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            "ix_diagnostic_recommendations_status",
            "diagnostic_recommendations", ["status"],
        )

    _create_if_missing("diagnostic_recommendations", _create_recommendations)

    # 5) diagnostic_rum_events — 前端 RUM（Core Web Vitals）
    def _create_rum() -> None:
        op.create_table(
            "diagnostic_rum_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("session_id", sa.String(64), nullable=True),
            sa.Column("page", sa.String(200), nullable=True),
            sa.Column("metric", sa.String(30), nullable=False),
            sa.Column("value", sa.Float(), nullable=False, server_default="0"),
            sa.Column("user_agent", sa.String(300), nullable=True),
            sa.Column("extra", sa.JSON(), nullable=False),
            sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index(
            "ix_diag_rum_metric_time", "diagnostic_rum_events", ["metric", "recorded_at"],
        )
        op.create_index(
            "ix_diagnostic_rum_events_session_id", "diagnostic_rum_events", ["session_id"],
        )

    _create_if_missing("diagnostic_rum_events", _create_rum)

    logger.info("[%s] upgrade done", revision)


def downgrade() -> None:
    bind = op.get_bind()
    logger.info("[%s] downgrade start: dialect=%s", revision, bind.dialect.name)

    # 整表删除：表之间无 FK 依赖，直接 op.drop_table（SQLite/PG 通用）
    for table_name in (
        "diagnostic_rum_events",
        "diagnostic_recommendations",
        "diagnostic_alerts",
        "diagnostic_traces",
        "diagnostic_metric_snapshots",
    ):
        if not _has_table(table_name):
            logger.info("[%s] skip: table %s not exists", revision, table_name)
            continue
        op.drop_table(table_name)
        logger.info("[%s] dropped: %s", revision, table_name)
    logger.info("[%s] downgrade done", revision)
