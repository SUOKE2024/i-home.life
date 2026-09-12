"""施工进度 3DGS 数字存档模型（评估报告 2026-09-12 P3）

施工节点（水电/瓦工/木工/油漆/竣工等）的 3DGS 实景快照，形成施工时间线，
支持竣工验收比对（qa_inspector / settlement 存证）与业主远程查看进度。
复用 P0 的 .spz/.ply 资产托管（FileAttachment），splat_url 指向下载端点。
"""
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ConstructionSnapshot(Base):
    """施工进度 3DGS 快照 — 某施工阶段对现场实景的一次 3D 扫描存档"""

    __tablename__ = "construction_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    task_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("construction_tasks.id"), nullable=True, index=True)
    # 施工阶段（复用 ConstructionTask.phase 值域）
    stage: Mapped[str] = mapped_column(String(50), nullable=False, default="preparation")
    room_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    splat_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project")

    __table_args__ = (
        CheckConstraint(
            "stage IN ('preparation', 'demolition', 'water_electricity', 'electrical', "
            "'waterproof', 'masonry', 'mep', 'carpentry', 'painting', 'installation', "
            "'completion', 'inspection')",
            name="chk_construction_snapshot_stage",
        ),
    )
