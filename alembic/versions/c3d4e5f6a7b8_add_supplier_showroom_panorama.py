"""suppliers 补 showroom_panorama_id 列（M4 供应商实景展厅）

Revision ID: c3e5f6a7b8c9
Revises: b2d4e5f6a7b8
Create Date: 2026-08-12

背景：设计文档 4.2 供应商实景展厅（车间/样品间）→ 采购商线上漫游验厂。
suppliers 表加可空 FK 列关联 vr_panoramas.id（供应商实景展厅全景）。
数据纪律：无实景内容恒 NULL（诚实标注，未上传展厅的供应商前端隐藏/标注）。
列定义与 app/models/procurement.py::Supplier.showroom_panorama_id 完全一致。
回滚：DROP COLUMN（幂等）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3e5f6a7b8c9"
down_revision: Union[str, None] = "b2d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "suppliers"
_COLUMN = "showroom_panorama_id"


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
    col = sa.Column(
        _COLUMN,
        sa.String(36),
        sa.ForeignKey("vr_panoramas.id", name="fk_suppliers_showroom_panorama"),
        nullable=True,
    )
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.add_column(col)
    else:
        op.add_column(_TABLE, col)
    print(f"  added: {_TABLE}.{_COLUMN} (实景展厅全景 FK -> vr_panoramas)")


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
