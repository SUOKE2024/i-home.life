"""v1.15.5 失败学习 + 协议信任层列：agent_cases.failure_type + a2a_tasks.trace_id/evidence

Revision ID: v1c2d3e4f5a6
Revises: f8e7d6c5b4a3
Create Date: 2026-08-17

背景（2026 前沿借鉴 EdgeBench「从真实环境失败中学习」+ AAIF「可验证证据
在协议边界」）：
1. agent_cases.failure_type：此前失败轨迹（harness FAILED/FALLBACK）不沉淀
   Case，失败信号被丢弃。本列记录确定性失败分类（timeout/empty_reply/fallback/
   llm_error/tool_loop），供反模式 Skill 蒸馏按 (agent_name, failure_type) 聚类
   （借鉴 HarnessBank 病理键）。
2. a2a_tasks.trace_id/evidence：A2A 任务执行证据链持久化——trace_id 关联
   harness 轨迹可回放溯源，evidence 存 JSON（agent_name/workflow_id/duration_ms/
   degraded/status），客户端可核验执行真实性而非信任裸文案。

设计：
  - 幂等：_has_column 守卫，已存在 skip
  - 可空（历史数据无这些列值），无默认值变更语义
  - downgrade 删除各列（SQLite 用 batch_alter_table）
"""
from typing import Sequence, Union

import logging

from alembic import op
import sqlalchemy as sa

logger = logging.getLogger("alembic.runtime.migration")


# revision identifiers, used by Alembic.
revision: str = "v1c2d3e4f5a6"
down_revision: Union[str, None] = "f8e7d6c5b4a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(conn, table: str, column: str) -> bool:
    from sqlalchemy import inspect as sa_inspect
    cols = [c["name"] for c in sa_inspect(conn).get_columns(table)]
    return column in cols


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, "agent_cases", "failure_type"):
        op.add_column(
            "agent_cases",
            sa.Column("failure_type", sa.String(30), nullable=True),
        )
        op.create_index(
            "ix_agent_cases_failure_type", "agent_cases", ["failure_type"],
        )
    else:
        logger.info("agent_cases.failure_type 已存在，跳过")
    if not _has_column(bind, "a2a_tasks", "trace_id"):
        op.add_column(
            "a2a_tasks",
            sa.Column("trace_id", sa.String(12), nullable=True),
        )
        op.create_index("ix_a2a_tasks_trace_id", "a2a_tasks", ["trace_id"])
    else:
        logger.info("a2a_tasks.trace_id 已存在，跳过")
    if not _has_column(bind, "a2a_tasks", "evidence"):
        op.add_column(
            "a2a_tasks",
            sa.Column("evidence", sa.Text, nullable=True),
        )
    else:
        logger.info("a2a_tasks.evidence 已存在，跳过")


def downgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, "a2a_tasks", "evidence"):
        op.drop_column("a2a_tasks", "evidence")
    if _has_column(bind, "a2a_tasks", "trace_id"):
        op.drop_index("ix_a2a_tasks_trace_id", table_name="a2a_tasks")
        op.drop_column("a2a_tasks", "trace_id")
    if _has_column(bind, "agent_cases", "failure_type"):
        op.drop_index("ix_agent_cases_failure_type", table_name="agent_cases")
        op.drop_column("agent_cases", "failure_type")
