"""v1.13.8 Agent 轨迹可回放化: agent_traces.tool_calls 列（借鉴 DeepSeek Harness）

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
Create Date: 2026-08-14

对齐 DeepSeek Harness「Every run is traceable」：此前 agent_traces 仅有
tool_call_count（计数），无法还原「每次工具调用的入参/出参」。新增 tool_calls
列（Text 存 JSON 字符串），落库前截断（arguments 200 / result 300 字符，整体 4000），
防 PII 扩散 + 体积爆炸。nullable=True（无工具调用时存 NULL，与 count=0 一致）。

特性：
  - 幂等：has_column 检查（生产可安全重复执行）
  - SQLite batch mode 兼容
  - 回滚：DROP COLUMN（幂等）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TRACE_TABLE = "agent_traces"
_COLUMN = "tool_calls"


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
        print(f"  skip: {_TRACE_TABLE} not exists (create_all 建表)")
        return
    if _has_column(_TRACE_TABLE, _COLUMN):
        print(f"  skip: {_TRACE_TABLE}.{_COLUMN} already exists")
        return
    bind = op.get_bind()
    col = sa.Column(_COLUMN, sa.Text(), nullable=True)
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
