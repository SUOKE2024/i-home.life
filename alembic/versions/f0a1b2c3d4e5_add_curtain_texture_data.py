"""curtain_products 补 texture_data / texture_content_type 列（真实面料贴图上传）

Revision ID: f0a1b2c3d4e5
Revises: e1a2b3c4d5f6
Create Date: 2026-08-14

背景：窗帘展厅「真实面料贴图上传入口」——展品除程序化纹理外，支持上传真实面料
贴图（albedo 原始字节），存 DB 而非外链（单店铺固定展厅，量小）。
列定义与 app/models/curtain_showroom.py::CurtainProduct 完全一致。
回滚：DROP COLUMN（幂等）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f0a1b2c3d4e5"
down_revision: Union[str, None] = "e1a2b3c4d5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "curtain_products"
_COLUMNS = [
    ("texture_data", sa.LargeBinary(), True),
    ("texture_content_type", sa.String(100), True),
]


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
        return column_name in [c["name"] for c in inspector.get_columns(table_name)]
    except Exception:
        return True


def upgrade() -> None:
    if not _has_table(_TABLE):
        print(f"  skip: {_TABLE} not exists (create_all 建表)")
        return
    bind = op.get_bind()
    for name, col, nullable in _COLUMNS:
        if _has_column(_TABLE, name):
            print(f"  skip: {_TABLE}.{name} already exists")
            continue
        col.nullable = nullable
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table(_TABLE) as batch_op:
                batch_op.add_column(col)
        else:
            op.add_column(_TABLE, col)
        print(f"  added: {_TABLE}.{name}")


def downgrade() -> None:
    if not _has_table(_TABLE):
        print(f"  skip: {_TABLE} not exists")
        return
    bind = op.get_bind()
    for name, _col, _nullable in reversed(_COLUMNS):
        if not _has_column(_TABLE, name):
            print(f"  skip: {_TABLE}.{name} not exists")
            continue
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table(_TABLE) as batch_op:
                batch_op.drop_column(name)
        else:
            op.drop_column(_TABLE, name)
        print(f"  dropped: {_TABLE}.{name}")
