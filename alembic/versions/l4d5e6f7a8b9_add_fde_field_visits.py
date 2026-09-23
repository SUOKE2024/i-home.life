"""新增 fde_field_visits 表 — FDE 现场服务记录（v1.17.4）

Revision ID: l4d5e6f7a8b9
Revises: k3c4d5e6f7a9
Create Date: 2026-09-23

政策依据：工信厅科函〔2026〕414号《关于开展人工智能应用服务商培育专项行动的
通知》任务四——「鼓励服务商搭建前线部署工程师（FDE）团队，扎根用户现场」。

补齐缺口 G3：`space_assets` 是资产台账（改造状态机维度），缺少
「谁在现场、做了什么、耗时多少、解决与否」的服务记录维度。

幂等：表已存在（create_all 建表场景）则跳过。
回滚：downgrade 直接 drop_table（无既有数据依赖；FDE 记录为本版本新增数据）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l4d5e6f7a8b9"
down_revision: Union[str, None] = "k3c4d5e6f7a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "fde_field_visits"


def _has_table(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
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
        sa.Column("space_asset_id", sa.String(36), sa.ForeignKey("space_assets.id"), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("engineer_name", sa.String(100), nullable=True),
        sa.Column("service_type", sa.String(30), nullable=False, server_default="installation"),
        sa.Column("mode", sa.String(20), nullable=False, server_default="on_site"),
        sa.Column("capability_tags", sa.JSON, nullable=True),
        sa.Column("service_date", sa.Date, nullable=True),
        sa.Column("duration_hours", sa.Float, nullable=False, server_default="0"),
        sa.Column("findings", sa.Text, nullable=True),
        sa.Column("resolved", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(f"ix_{_TABLE}_owner_id", _TABLE, ["owner_id"])
    op.create_index(f"ix_{_TABLE}_project_id", _TABLE, ["project_id"])
    op.create_index(f"ix_{_TABLE}_space_asset_id", _TABLE, ["space_asset_id"])
    op.create_index(f"ix_{_TABLE}_service_type", _TABLE, ["service_type"])
    op.create_index(f"ix_{_TABLE}_service_date", _TABLE, ["service_date"])
    print(f"  created: {_TABLE} (FDE 现场服务记录)")


def downgrade() -> None:
    if not _has_table(_TABLE):
        print(f"  skip: {_TABLE} not exists")
        return
    # 索引随表一并删除（SQLite/PostgreSQL 均无需显式 drop_index）
    op.drop_table(_TABLE)
    print(f"  dropped: {_TABLE}")
