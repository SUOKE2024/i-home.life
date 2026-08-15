"""窗帘智能展厅建表迁移（单店铺固定「官渡区帘享空间窗帘布艺经营部」）

Revision ID: c9d0e1f2a3b4
Revises: b1c2d3e4f5a6
Create Date: 2026-08-14

背景：把窗帘/布艺做成可 3D 交互的智能展厅（换装 / 时间灯光 / 安装方式 / 热点加 BOM）。
列定义与 app/models/curtain_showroom.py 完全一致。
回滚：DROP TABLE（幂等，按 FK 逆序删除）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
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
    # 1. 展厅锚点
    if not _has_table("curtain_showrooms"):
        op.create_table(
            "curtain_showrooms",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("description", sa.String(500), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        print("  created: curtain_showrooms")

    # 2. 系列
    if not _has_table("curtain_series"):
        op.create_table(
            "curtain_series",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("showroom_id", sa.String(36), sa.ForeignKey("curtain_showrooms.id"), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("description", sa.String(500), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_curtain_series_showroom_id", "curtain_series", ["showroom_id"])
        print("  created: curtain_series")

    # 3. 安装方式（无 FK，先建以便 areas 引用）
    if not _has_table("curtain_installations"):
        op.create_table(
            "curtain_installations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("code", sa.String(50), nullable=False, unique=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("render_type", sa.String(30), nullable=False),
            sa.Column("description", sa.String(500), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        print("  created: curtain_installations")

    # 4. 时间/灯光预设（无 FK）
    if not _has_table("curtain_lighting_presets"):
        op.create_table(
            "curtain_lighting_presets",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("code", sa.String(50), nullable=False, unique=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("time_of_day", sa.String(30), nullable=False),
            sa.Column("light_color", sa.String(20), nullable=False, server_default=sa.text("'#ffffff'")),
            sa.Column("ambient_intensity", sa.Float(), nullable=False, server_default=sa.text("1.0")),
            sa.Column("description", sa.String(500), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        print("  created: curtain_lighting_presets")

    # 5. 展品（依赖 showrooms + series + materials）
    if not _has_table("curtain_products"):
        op.create_table(
            "curtain_products",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("showroom_id", sa.String(36), sa.ForeignKey("curtain_showrooms.id"), nullable=False),
            sa.Column("series_id", sa.String(36), sa.ForeignKey("curtain_series.id"), nullable=False),
            sa.Column("material_id", sa.String(36), sa.ForeignKey("materials.id"), nullable=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("sku", sa.String(100), nullable=False, unique=True),
            sa.Column("brand", sa.String(100), nullable=True),
            sa.Column("fabric", sa.String(50), nullable=False),
            sa.Column("color", sa.String(50), nullable=True),
            sa.Column("texture_url", sa.String(1000), nullable=True),
            sa.Column("image_url", sa.String(500), nullable=True),
            sa.Column("unit", sa.String(20), nullable=False, server_default=sa.text("'米'")),
            sa.Column("unit_price", sa.Float(), nullable=False, server_default=sa.text("0.0")),
            sa.Column("description", sa.String(1000), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_curtain_products_showroom_id", "curtain_products", ["showroom_id"])
        op.create_index("ix_curtain_products_series_id", "curtain_products", ["series_id"])
        op.create_index("ix_curtain_products_material_id", "curtain_products", ["material_id"])
        print("  created: curtain_products")

    # 6. 展示区域（依赖 showrooms + installations + products）
    if not _has_table("curtain_showroom_areas"):
        op.create_table(
            "curtain_showroom_areas",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("showroom_id", sa.String(36), sa.ForeignKey("curtain_showrooms.id"), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("description", sa.String(500), nullable=True),
            sa.Column("installation_id", sa.String(36), sa.ForeignKey("curtain_installations.id"), nullable=False),
            sa.Column("default_product_id", sa.String(36), sa.ForeignKey("curtain_products.id"), nullable=True),
            sa.Column("position", sa.JSON(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_curtain_showroom_areas_showroom_id", "curtain_showroom_areas", ["showroom_id"])
        print("  created: curtain_showroom_areas")


def downgrade() -> None:
    # 按 FK 逆序删除
    for table in (
        "curtain_showroom_areas",
        "curtain_products",
        "curtain_lighting_presets",
        "curtain_installations",
        "curtain_series",
        "curtain_showrooms",
    ):
        if _has_table(table):
            op.drop_table(table)
            print(f"  dropped: {table}")
