"""smart_devices 补 state 列（P0 设备热点联动实时状态）

Revision ID: d1e2f3a4b5c6
Revises: f3a4b5c6d7e8
Create Date: 2026-08-12

背景：P0「漫游即控制」device-overlay / WS 事件需返回设备实时状态
（power/brightness 等）。smart_devices 原无状态字段，补可空 JSON 列。
数据纪律：仅生态桥真机执行成功（send_command 返回 ok）时写入，
无真机数据恒 NULL（诚实不伪造）。
列定义与 app/models/smart_home.py::SmartDevice.state 完全一致（可空 JSON）。
回滚：DROP COLUMN（幂等）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "f3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "smart_devices"
_COLUMN = "state"


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
    if not _has_table(_TABLE):
        # 表不存在（create_all 建表场景）：新模型已含列，跳过
        print(f"  skip: {_TABLE} not exists (create_all 建表)")
        return
    if _has_column(_TABLE, _COLUMN):
        print(f"  skip: {_TABLE}.{_COLUMN} already exists")
        return
    col = sa.Column(_COLUMN, sa.JSON(), nullable=True)
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.add_column(col)
    else:
        op.add_column(_TABLE, col)
    print(f"  added: {_TABLE}.{_COLUMN} (实时状态 JSON)")


def downgrade() -> None:
    if not _has_table(_TABLE):
        print(f"  skip: {_TABLE} not exists")
        return
    if not _has_column(_TABLE, _COLUMN):
        print(f"  skip: {_TABLE}.{_COLUMN} not exists")
        return
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.drop_column(_COLUMN)
    else:
        op.drop_column(_TABLE, _COLUMN)
    print(f"  dropped: {_TABLE}.{_COLUMN}")
