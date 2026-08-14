"""curtain_products 补法线/粗糙度贴图列（三件套 PBR 上传）

Revision ID: c9a8b7c6d5e4
Revises: f0a1b2c3d4e5
Create Date: 2026-08-14

背景：真实面料贴图三件套（albedo/normal/roughness）上传入口扩展。
在已有 texture_* 基础上补 normal_* 与 roughness_* 三组列。
列定义与 app/models/curtain_showroom.py::CurtainProduct 完全一致。
回滚：DROP COLUMN（幂等）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9a8b7c6d5e4"
down_revision: Union[str, None] = "f0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "curtain_products"
_COLUMNS = [
    ("normal_url", sa.String(1000)),
    ("normal_data", sa.LargeBinary()),
    ("normal_content_type", sa.String(100)),
    ("roughness_url", sa.String(1000)),
    ("roughness_data", sa.LargeBinary()),
    ("roughness_content_type", sa.String(100)),
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
    for name, col_type in _COLUMNS:
        if _has_column(_TABLE, name):
            print(f"  skip: {_TABLE}.{name} already exists")
            continue
        col = sa.Column(name, col_type, nullable=True)
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
    for name, _col_type in reversed(_COLUMNS):
        if not _has_column(_TABLE, name):
            print(f"  skip: {_TABLE}.{name} not exists")
            continue
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table(_TABLE) as batch_op:
                batch_op.drop_column(name)
        else:
            op.drop_column(_TABLE, name)
        print(f"  dropped: {_TABLE}.{name}")
