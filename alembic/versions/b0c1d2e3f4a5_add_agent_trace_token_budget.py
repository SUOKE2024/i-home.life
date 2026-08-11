"""v1.13.0 Agent 工具纪律: agent_traces.token_budget_hit 列（Agent loop 早停可观测性）

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-08-11

对齐 2026 生产级 Agent 可观测性（Agent loop 早停/预算控制）：
- token_budget_hit: Agent 单次执行因 token 预算触顶提前终止标记，
  供离线评估区分「正常完成 vs 预算早停」（早停率高说明工具结果上下文过大需优化）。

特性：
  - 幂等：has_column 检查（生产可安全重复执行）
  - NOT NULL 列带 server_default（存量行获得默认值，避免 ALTER 失败）
  - SQLite batch mode 兼容
  - 回滚：DROP COLUMN（幂等）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b0c1d2e3f4a5"
down_revision: Union[str, None] = "a9b0c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TRACE_TABLE = "agent_traces"
_COLUMN = "token_budget_hit"


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        return table_name in inspector.get_table_names()
    except Exception:
        return False


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        cols = [c["name"] for c in inspector.get_columns(table_name)]
    except Exception:
        return True
    return column_name in cols


def upgrade() -> None:
    if not _has_table(_TRACE_TABLE):
        # 表不存在（v1.12.x 起 agent_traces 经 create_all 建表，alembic 链无建表迁移）：
        # 空库场景直接跳过，真实库由 create_all 建表时列已在模型定义中。
        print(f"  skip: {_TRACE_TABLE} not exists (create_all 建表)")
        return
    if _has_column(_TRACE_TABLE, _COLUMN):
        print(f"  skip: {_TRACE_TABLE}.{_COLUMN} already exists")
        return
    bind = op.get_bind()
    col = sa.Column(
        _COLUMN, sa.Boolean(), nullable=False, server_default=sa.false(),
    )
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(_TRACE_TABLE) as batch_op:
            batch_op.add_column(col)
    else:
        op.add_column(_TRACE_TABLE, col)
    print(f"  added: {_TRACE_TABLE}.{_COLUMN}")


def downgrade() -> None:
    if not _has_table(_TRACE_TABLE):
        print(f"  skip: {_TRACE_TABLE} not exists")
        return
    if not _has_column(_TRACE_TABLE, _COLUMN):
        print(f"  skip: {_TRACE_TABLE}.{_COLUMN} not exists")
        return
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(_TRACE_TABLE) as batch_op:
            batch_op.drop_column(_COLUMN)
    else:
        op.drop_column(_TRACE_TABLE, _COLUMN)
    print(f"  dropped: {_TRACE_TABLE}.{_COLUMN}")
