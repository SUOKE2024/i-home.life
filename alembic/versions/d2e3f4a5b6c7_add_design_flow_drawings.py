"""设计流程编排补设计图纸表（施工图/水电图/灯图）

Revision ID: d2e3f4a5b6c7
Revises: c9a8b7c6d5e4
Create Date: 2026-08-14

背景：设计流程编排（design-flow）在渲染效果图之前新增「设计图纸」环节，
需要落库施工图全套（平面/立面/剖面）+ 水电图 + 灯图。
列定义与 app/models/design_flow.py::DesignFlowDrawing 完全一致。
回滚：DROP TABLE（幂等）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, None] = "c9a8b7c6d5e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        return table_name in inspector.get_table_names()
    except Exception:
        return False


def upgrade() -> None:
    if not _has_table("design_flow_drawings"):
        op.create_table(
            "design_flow_drawings",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("flow_id", sa.String(36), sa.ForeignKey("design_flows.id"), nullable=False),
            sa.Column("floor_plan_svg", sa.Text(), nullable=True),
            sa.Column("elevation_svgs", sa.Text(), nullable=True),
            sa.Column("section_svg", sa.Text(), nullable=True),
            sa.Column("mep_overlay_svg", sa.Text(), nullable=True),
            sa.Column("mep_plan", sa.Text(), nullable=True),
            sa.Column("lighting_schemes", sa.Text(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_design_flow_drawings_flow_id", "design_flow_drawings", ["flow_id"], unique=True)
        print("  created: design_flow_drawings")


def downgrade() -> None:
    if _has_table("design_flow_drawings"):
        op.drop_table("design_flow_drawings")
        print("  dropped: design_flow_drawings")
