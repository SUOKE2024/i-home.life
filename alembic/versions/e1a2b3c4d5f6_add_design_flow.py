"""设计流程编排建表 + suppliers 补风格/价格档位列

Revision ID: e1a2b3c4d5f6
Revises: c9d0e1f2a3b4
Create Date: 2026-08-14

背景：设计流程编排（风格/预算选供应商 → VR 效果图 → 可行性分析）需要
1) suppliers 新增 styles（JSON 风格列表）+ price_tier（价格档位）两列；
2) 新增 design_flows（编排会话状态机）+ design_flow_feasibilities（可行性四维度）两张表。
列定义与 app/models/procurement.py::Supplier、app/models/design_flow.py 完全一致。
回滚：DROP TABLE（幂等）+ DROP COLUMN（幂等）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1a2b3c4d5f6"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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


def _add_supplier_columns() -> None:
    bind = op.get_bind()
    columns = [
        ("styles", sa.Column("styles", sa.Text(), nullable=False, server_default="[]")),
        ("price_tier", sa.Column("price_tier", sa.String(20), nullable=False, server_default="standard")),
    ]
    for name, col in columns:
        if _has_column("suppliers", name):
            print(f"  skip: suppliers.{name} already exists")
            continue
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("suppliers") as batch_op:
                batch_op.add_column(col)
        else:
            op.add_column("suppliers", col)
        print(f"  added: suppliers.{name}")


def upgrade() -> None:
    # 1. suppliers 补列（幂等）
    if _has_table("suppliers"):
        _add_supplier_columns()

    # 2. design_flows（编排会话状态机）
    if not _has_table("design_flows"):
        op.create_table(
            "design_flows",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("floorplan_id", sa.String(36), sa.ForeignKey("floor_plans.id"), nullable=False),
            sa.Column("style", sa.String(100), nullable=False),
            sa.Column("budget", sa.Float(), nullable=False, server_default=sa.text("0.0")),
            sa.Column("price_tier", sa.String(20), nullable=False, server_default=sa.text("'standard'")),
            sa.Column("supplier_selection_mode", sa.String(20), nullable=False, server_default=sa.text("'random'")),
            sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id"), nullable=True),
            sa.Column("scene_id", sa.String(36), sa.ForeignKey("vr_scenes.id"), nullable=True),
            sa.Column("stage", sa.String(30), nullable=False, server_default=sa.text("'init'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_design_flows_project_id", "design_flows", ["project_id"])
        op.create_index("ix_design_flows_floorplan_id", "design_flows", ["floorplan_id"])
        op.create_index("ix_design_flows_supplier_id", "design_flows", ["supplier_id"])
        op.create_index("ix_design_flows_scene_id", "design_flows", ["scene_id"])
        print("  created: design_flows")

    # 3. design_flow_feasibilities（可行性四维度 + 聚合）
    if not _has_table("design_flow_feasibilities"):
        op.create_table(
            "design_flow_feasibilities",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("flow_id", sa.String(36), sa.ForeignKey("design_flows.id"), nullable=False),
            sa.Column("duration_analysis", sa.Text(), nullable=True),
            sa.Column("budget_analysis", sa.Text(), nullable=True),
            sa.Column("material_analysis", sa.Text(), nullable=True),
            sa.Column("risk_analysis", sa.Text(), nullable=True),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_design_flow_feasibilities_flow_id", "design_flow_feasibilities", ["flow_id"], unique=True)
        print("  created: design_flow_feasibilities")


def downgrade() -> None:
    for table in ("design_flow_feasibilities", "design_flows"):
        if _has_table(table):
            op.drop_table(table)
            print(f"  dropped: {table}")

    # 列删除（幂等）
    bind = op.get_bind()
    for name in ("styles", "price_tier"):
        if _has_column("suppliers", name):
            if bind.dialect.name == "sqlite":
                with op.batch_alter_table("suppliers") as batch_op:
                    batch_op.drop_column(name)
            else:
                op.drop_column("suppliers", name)
            print(f"  dropped: suppliers.{name}")
