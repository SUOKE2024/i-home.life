"""v1.13.2 全链路进度评估: agent_traces 建表迁移（此前依赖运行时 create_all）

Revision ID: c0d1e2f3a4b5
Revises: b0c1d2e3f4a5
Create Date: 2026-08-11

背景：agent_traces 自 v1.12.x 起由 app/database.py 运行时 create_all 建表，
alembic 迁移链无建表迁移（b0c1d2e3f4a5 仅在表已存在时补 token_budget_hit 列）。
全量评估发现空库/未跑 create_all 的库缺 agent_traces 表 → 补幂等建表迁移，
对齐 F40 迁移链补齐模式（_has_table 幂等，空库 upgrade head 后表完整）。

列定义与 app/models/agent_trace.py::AgentTraceRecord 完全一致。
回滚：DROP TABLE（幂等）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c0d1e2f3a4b5"
down_revision: Union[str, None] = "b0c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TRACE_TABLE = "agent_traces"


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        return table_name in inspector.get_table_names()
    except Exception:
        return False


def upgrade() -> None:
    if _has_table(_TRACE_TABLE):
        print(f"  skip: {_TRACE_TABLE} already exists")
        return
    op.create_table(
        _TRACE_TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workflow_id", sa.String(36), nullable=True),
        sa.Column("agent_name", sa.String(60), nullable=False),
        sa.Column("agent_version", sa.String(30), nullable=True),
        sa.Column("provider", sa.String(30), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("project_id", sa.String(36), nullable=True),
        sa.Column("scope", sa.String(20), nullable=True),
        sa.Column("context_source", sa.String(20), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("first_token_latency_ms", sa.Float(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("tool_call_count", sa.Integer(), nullable=False),
        sa.Column("tool_call_rounds", sa.Integer(), nullable=False),
        sa.Column("token_budget_hit", sa.Boolean(), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column("fallback_reason", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("error_type", sa.String(60), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("prompt_preview", sa.Text(), nullable=True),
        sa.Column("response_preview", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Index("ix_agent_trace_agent_time", "agent_name", "created_at"),
        sa.Index("ix_agent_trace_workflow_time", "workflow_id", "created_at"),
        sa.Index("ix_agent_traces_workflow_id", "workflow_id"),
        sa.Index("ix_agent_traces_agent_name", "agent_name"),
        sa.Index("ix_agent_traces_user_id", "user_id"),
    )
    print(f"  created: {_TRACE_TABLE}")


def downgrade() -> None:
    if not _has_table(_TRACE_TABLE):
        print(f"  skip: {_TRACE_TABLE} not exists")
        return
    op.drop_table(_TRACE_TABLE)
    print(f"  dropped: {_TRACE_TABLE}")
