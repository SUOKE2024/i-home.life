"""服务商付费展厅商业闭环（M4）：crews 加 owner/featured + crew_benefits 表 + mall benefit_type

Revision ID: e5a7b8c9d0e1
Revises: d4f6a7b8c9d0
Create Date: 2026-08-12

背景：设计文档 4.3 服务商智能展厅商业模式——「服务商付费展厅（作品集置顶/VR 实拍权益
+ content_publish/points 体系）」。工程队/装企可用积分兑换展厅权益：
1. construction_crews 加 owner_id（权益归属用户，平台授予展示）+ featured（置顶标志，
   由权益生效驱动，非自报）。
2. 新表 crew_benefits（权益兑换记录，与 points_redemptions 解耦：记录权益类型/到期时间）。
3. points_mall_items 加 benefit_type（vip 类商品细分为 showroom_featured / vr_photo）。

数据纪律：平台授予非自报——featured 仅由权益兑换/管理员置位，无权益恒 False。
列定义与 app/models/construction_crew.py / app/models/points.py 完全一致。
回滚：删表 + DROP COLUMN（幂等）。
"""
from typing import Sequence, Union

import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision: str = "e5a7b8c9d0e1"
down_revision: Union[str, None] = "d4f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CREWS = "construction_crews"
_MALL = "points_mall_items"
_BENEFITS = "crew_benefits"


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


def _add_column(table: str, column: sa.Column) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(column)
    else:
        op.add_column(table, column)


def _drop_column(table: str, column: str) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column(column)
    else:
        op.drop_column(table, column)


def upgrade() -> None:
    # 1) construction_crews.owner_id（权益归属用户）
    if _has_table(_CREWS) and not _has_column(_CREWS, "owner_id"):
        _add_column(
            _CREWS,
            sa.Column(
                "owner_id",
                sa.String(36),
                sa.ForeignKey("users.id", name="fk_construction_crews_owner"),
                nullable=True,
            ),
        )
        print(f"  added: {_CREWS}.owner_id (权益归属用户)")
    # 2) construction_crews.featured（平台授予置顶标志）
    if _has_table(_CREWS) and not _has_column(_CREWS, "featured"):
        _add_column(_CREWS, sa.Column("featured", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        print(f"  added: {_CREWS}.featured (置顶标志，平台授予)")
    # 3) points_mall_items.benefit_type（vip 类商品细分权益类型）
    if _has_table(_MALL) and not _has_column(_MALL, "benefit_type"):
        _add_column(_MALL, sa.Column("benefit_type", sa.String(30), nullable=True))
        print(f"  added: {_MALL}.benefit_type (权益类型: showroom_featured / vr_photo)")
    # 4) 新表 crew_benefits（权益兑换记录）
    if not _has_table(_BENEFITS):
        op.create_table(
            _BENEFITS,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("crew_id", sa.String(36), sa.ForeignKey("construction_crews.id"), nullable=False, index=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("benefit_type", sa.String(30), nullable=False),
            # showroom_featured(作品集置顶) / vr_photo(VR 实拍权益)
            sa.Column("points_spent", sa.Integer(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'active'")),
            # active / expired / refunded
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        print(f"  created: {_BENEFITS} (服务商展厅权益兑换记录)")
    # 5) seed 展厅权益商品（幂等：按名称查重，不重复插入）
    _seed_benefit_items()


def _seed_benefit_items() -> None:
    """积分商城预置 vip 类展厅权益商品（设计 4.3 付费展厅）。

    幂等：已存在同名商品则跳过。benefit_type 驱动权益应用（showroom_featured 置顶 / vr_photo VR 实拍）。
    """
    if not _has_table(_MALL):
        return
    bind = op.get_bind()
    items = [
        {
            "name": "作品集置顶 · 30 天",
            "category": "vip",
            "description": "服务商智能展厅权益：工程队作品集在服务商列表中置顶展示 30 天（平台授予，非自报）。",
            "points_required": 2000,
            "stock": -1,
            "validity_days": 30,
            "benefit_type": "showroom_featured",
            "sort_order": 100,
        },
        {
            "name": "VR 实拍权益 · 3 套",
            "category": "vip",
            "description": "服务商智能展厅权益：平台上门拍摄 3 套完工实景，生成 VR 全景加入作品集展厅。",
            "points_required": 5000,
            "stock": -1,
            "validity_days": 90,
            "benefit_type": "vr_photo",
            "sort_order": 110,
        },
    ]
    for item in items:
        exists = bind.execute(
            sa.text("SELECT 1 FROM points_mall_items WHERE name = :n LIMIT 1"),
            {"n": item["name"]},
        ).fetchone()
        if exists:
            print(f"  skip seed: 商品「{item['name']}」已存在")
            continue
        bind.execute(
            sa.text(
                "INSERT INTO points_mall_items "
                "(id, name, category, description, image_url, points_required, stock, discount_type, "
                " discount_value, discount_max, benefit_type, validity_days, is_active, sort_order, created_at) "
                "VALUES (:id, :name, :category, :description, NULL, :points_required, :stock, NULL, "
                " NULL, NULL, :benefit_type, :validity_days, 1, :sort_order, :created_at)"
            ),
            {
                "id": str(uuid.uuid4()),
                "name": item["name"],
                "category": item["category"],
                "description": item["description"],
                "points_required": item["points_required"],
                "stock": item["stock"],
                "benefit_type": item["benefit_type"],
                "validity_days": item["validity_days"],
                "sort_order": item["sort_order"],
                "created_at": datetime.now(timezone.utc),
            },
        )
        print(f"  seeded: 商品「{item['name']}」({item['benefit_type']})")


def downgrade() -> None:
    if _has_table(_BENEFITS):
        op.drop_table(_BENEFITS)
        print(f"  dropped: {_BENEFITS}")
    if _has_table(_MALL) and _has_column(_MALL, "benefit_type"):
        _drop_column(_MALL, "benefit_type")
        print(f"  dropped: {_MALL}.benefit_type")
    if _has_table(_CREWS) and _has_column(_CREWS, "featured"):
        _drop_column(_CREWS, "featured")
        print(f"  dropped: {_CREWS}.featured")
    if _has_table(_CREWS) and _has_column(_CREWS, "owner_id"):
        _drop_column(_CREWS, "owner_id")
        print(f"  dropped: {_CREWS}.owner_id")
