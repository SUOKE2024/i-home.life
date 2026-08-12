"""vr_panoramas 补 content_source 列（设计 4.1 效果图漫游：actual 实景 / effect 效果图）

Revision ID: f6a7b8c9d0e2
Revises: e5a7b8c9d0e1
Create Date: 2026-08-12

背景：设计文档 4.1「效果图漫游体验（先看后装）」——把 AI 效果图从静态图升级为可漫游空间。
当前 AI 渲染（ai_render 2D 图）与 VR 漫游（equirectangular 全景）是两条独立链路无桥接；
本迁移新增内容来源字段 content_source（actual 实景 / effect AI 效果图），
使效果图可作为 VRPanorama 落库并在漫游页展示。

诚实降级纪律：effect 全景图为 2D 平面效果图（非 360° 等距柱状），前端对 effect
全景采用 2D 平面预览并标注「效果图预览 · 非实景」，不伪造 360° 沉浸感；
2D→3D（.spz）内容管线仍待 GPU 立项（M3 余项）。

列定义与 app/models/vr_panorama.py::VRPanorama.content_source 完全一致。
回滚：DROP COLUMN（幂等）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d0e2"
down_revision: Union[str, None] = "e5a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "vr_panoramas"
_COLUMN = "content_source"


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
        sa.String(20),
        nullable=False,
        server_default=sa.text("'actual'"),
    )
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.add_column(col)
    else:
        op.add_column(_TABLE, col)
    print(f"  added: {_TABLE}.{_COLUMN} (actual 实景 / effect AI 效果图，默认 actual)")


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
