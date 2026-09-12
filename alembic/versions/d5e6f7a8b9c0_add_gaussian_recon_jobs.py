"""新增 gaussian_recon_jobs 表（3DGS 云端重建任务，评估报告 2026-09-12 P1）

Revision ID: d5e6f7a8b9c0
Revises: c2d3e4f5a6b7
Create Date: 2026-09-12

背景：P1 落地「云端重建」骨架——采集照片/视频提交外部重建后端（如 XGRIDS
LCC Cloud）生成 .spz/.ply。平台不自建 GPU、不做 2D→3D 重建（诚实降级红线），
本表仅记录重建任务生命周期（queued → processing → completed/failed）。
列定义与 app/models/gaussian_recon.py::GaussianReconstructionJob 完全一致。
回滚：DROP TABLE（幂等）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "gaussian_recon_jobs"


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
        sa.Column("room_name", sa.String(100), nullable=False),
        sa.Column("floorplan_id", sa.String(36), sa.ForeignKey("floor_plans.id"), nullable=True),
        sa.Column("scan_session_id", sa.String(36), sa.ForeignKey("ar_scan_sessions.id"), nullable=True),
        sa.Column("source_type", sa.String(20), nullable=False, server_default="photos"),
        sa.Column("source_files", sa.Text(), nullable=True),
        sa.Column("backend_job_id", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("splat_url", sa.String(1000), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "source_type IN ('photos', 'video', 'ar_scan')",
            name="chk_gaussian_recon_source_type",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed')",
            name="chk_gaussian_recon_status",
        ),
    )
    op.create_index(f"ix_{_TABLE}_project_id", _TABLE, ["project_id"])
    op.create_index(f"ix_{_TABLE}_floorplan_id", _TABLE, ["floorplan_id"])
    op.create_index(f"ix_{_TABLE}_scan_session_id", _TABLE, ["scan_session_id"])
    print(f"  created: {_TABLE} (3DGS 云端重建任务)")


def downgrade() -> None:
    if not _has_table(_TABLE):
        print(f"  skip: {_TABLE} not exists")
        return
    op.drop_table(_TABLE)
    print(f"  dropped: {_TABLE}")
