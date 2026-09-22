"""新增 space_assets 空间资产台账表（Phase 3 存量空间资产化，2026-09-13）

Revision ID: f1a2b3c4d5e6
Revises: e6f7a8b9c0d1
Create Date: 2026-09-13

背景：项目定位收口为「空间健康资产运营商」后，需要统一台账承载云南区域存量
空间资源（康养/疗愈/旅居/文旅/适老住宅）的资产评估 → AI 智能化改造 → 交付 →
运营指标全生命周期。业态枚举与索克生活 lodge_manager_registration `_lodgeTypes`
对齐，避免生态两侧口径分叉。

轻资产约束：platform_role 默认 'service_provider'，asset_holder 必须为外部主体，
平台不持有房产（CLAUDE.md 商业模式红线）。

幂等：表已存在则跳过（create_all 建表场景）。
回滚：op.drop_table（整表删除不走 batch_alter_table，BatchOperations 无 drop_table）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "space_assets"


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        return table_name in inspector.get_table_names()
    except Exception:
        return False


def upgrade() -> None:
    if _has_table(_TABLE):
        print(f"  skip: {_TABLE} already exists")
        return

    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("province", sa.String(50), nullable=False, server_default="云南省"),
        sa.Column("city", sa.String(50), nullable=False, server_default="昆明市"),
        sa.Column("district", sa.String(50), nullable=True),
        sa.Column("address", sa.String(300), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("building_area_sqm", sa.Float(), nullable=True),
        sa.Column("room_count", sa.Integer(), nullable=True),
        sa.Column("floor_info", sa.String(100), nullable=True),
        sa.Column("built_year", sa.Integer(), nullable=True),
        sa.Column("structure_type", sa.String(50), nullable=True),
        sa.Column("asset_category", sa.String(30), nullable=False, server_default="kangyang"),
        sa.Column("business_format", sa.String(40), nullable=False, server_default="other"),
        sa.Column("asset_holder", sa.String(200), nullable=False),
        sa.Column("holder_type", sa.String(20), nullable=False, server_default="private"),
        sa.Column("platform_role", sa.String(30), nullable=False, server_default="service_provider"),
        sa.Column("renovation_status", sa.String(30), nullable=False,
                  server_default="pending_assessment"),
        sa.Column("renovation_scope", sa.JSON(), nullable=True),
        sa.Column("retrofit_package_code", sa.String(40), nullable=True),
        sa.Column("elderly_scheme_id", sa.String(36), nullable=True),
        sa.Column("smart_ready", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("smart_readiness_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("matter_device_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sensor_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scene_automation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fire_safety_status", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("accessibility_status", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("operation_metrics", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_space_assets_owner_id", _TABLE, ["owner_id"])
    op.create_index("ix_space_assets_project_id", _TABLE, ["project_id"])
    op.create_index("ix_space_assets_renovation_status", _TABLE, ["renovation_status"])
    print(f"  created: {_TABLE}（空间资产台账）+ 3 索引")


def downgrade() -> None:
    if not _has_table(_TABLE):
        print(f"  skip: {_TABLE} not exists")
        return
    # 整表删除直接 op.drop_table（BatchOperations 无 drop_table 方法）
    op.drop_index("ix_space_assets_renovation_status", table_name=_TABLE)
    op.drop_index("ix_space_assets_project_id", table_name=_TABLE)
    op.drop_index("ix_space_assets_owner_id", table_name=_TABLE)
    op.drop_table(_TABLE)
    print(f"  dropped: {_TABLE}")
