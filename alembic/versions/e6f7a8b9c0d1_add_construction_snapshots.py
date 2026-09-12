"""新增 construction_snapshots 表（施工进度 3DGS 数字存档，评估报告 2026-09-12 P3）

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-09-12

背景：P3 落地「施工存档」——施工节点现场 3DGS 实景快照，形成施工时间线
（竣工验收比对 + 业主远程查看 + settlement 存证）。splat_url 复用 P0 的
FileAttachment 托管（.spz/.ply）。
列定义与 app/models/construction_snapshot.py::ConstructionSnapshot 完全一致。
回滚：DROP TABLE（幂等）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "construction_snapshots"


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
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("construction_tasks.id"), nullable=True),
        sa.Column("stage", sa.String(50), nullable=False, server_default="preparation"),
        sa.Column("room_name", sa.String(100), nullable=True),
        sa.Column("splat_url", sa.String(1000), nullable=False),
        sa.Column("thumbnail_url", sa.String(1000), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "stage IN ('preparation', 'demolition', 'water_electricity', 'electrical', "
            "'waterproof', 'masonry', 'mep', 'carpentry', 'painting', 'installation', "
            "'completion', 'inspection')",
            name="chk_construction_snapshot_stage",
        ),
    )
    op.create_index(f"ix_{_TABLE}_project_id", _TABLE, ["project_id"])
    op.create_index(f"ix_{_TABLE}_task_id", _TABLE, ["task_id"])
    print(f"  created: {_TABLE} (施工进度 3DGS 存档)")


def downgrade() -> None:
    if not _has_table(_TABLE):
        print(f"  skip: {_TABLE} not exists")
        return
    op.drop_table(_TABLE)
    print(f"  dropped: {_TABLE}")
