"""suppliers 补 is_verified 列（M4 供应商入驻认证状态）

Revision ID: b2d4e5f6a7b8
Revises: a1b2c3d4e5f7
Create Date: 2026-08-12

背景：设计文档 4.2 供应商实景展厅要求「入驻/认证状态（Supplier.is_verified）
在展厅标注，未认证展厅显示 pending 水印」。原 suppliers 表无认证字段。
数据纪律：认证状态由平台授予（admin 端点），非供应商自报，默认 False 诚实标注。
列定义与 app/models/procurement.py::Supplier.is_verified 完全一致（非空布尔，默认 False）。
回滚：DROP COLUMN（幂等）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2d4e5f6a7b8"
down_revision: Union[str, None] = "a1b2c3d4e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "suppliers"
_COLUMN = "is_verified"


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
    col = sa.Column(_COLUMN, sa.Boolean(), nullable=False, server_default=sa.false())
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.add_column(col)
    else:
        op.add_column(_TABLE, col)
    print(f"  added: {_TABLE}.{_COLUMN} (入驻认证状态，默认 False)")


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
