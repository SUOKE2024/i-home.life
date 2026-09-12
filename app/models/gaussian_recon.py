"""3DGS 云端重建任务模型 — 采集照片/视频提交云端重建为 .spz/.ply（评估报告 2026-09-12 P1）

复用 ar_scan 会话状态机语义（queued → processing → completed/failed），
但职责独立：ar_scan 是「空间测量」，本表是「照片/视频 → 3DGS 场景重建」。
平台不自建 GPU，重建由外部云端后端完成（gaussian_recon_backend_url），
未配置时诚实 503（见 gaussian_reconstruction_service.submit_reconstruction）。
"""
import json
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class GaussianReconstructionJob(Base):
    """3DGS 云端重建任务 — 一次「源数据 → 高斯场景」的重建请求"""

    __tablename__ = "gaussian_recon_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    room_name: Mapped[str] = mapped_column(String(100), nullable=False)
    floorplan_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("floor_plans.id"), nullable=True, index=True)
    # 桥接 ar_scan 会话：从 AR 测量扫描的原始数据（raw_data_url）发起重建
    scan_session_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ar_scan_sessions.id"), nullable=True, index=True)
    # 源数据类型与文件（照片集 / 视频 / AR 扫描原始数据）
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="photos")
    source_files: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 云端后端任务 ID（提交后回填）
    backend_job_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    splat_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project")

    __table_args__ = (
        CheckConstraint(
            "source_type IN ('photos', 'video', 'ar_scan')",
            name="chk_gaussian_recon_source_type",
        ),
        CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed')",
            name="chk_gaussian_recon_status",
        ),
    )

    @property
    def source_file_list(self) -> list[str]:
        try:
            return json.loads(self.source_files or "[]")
        except (json.JSONDecodeError, TypeError):
            return []

    @source_file_list.setter
    def source_file_list(self, value: list[str]):
        self.source_files = json.dumps(value, ensure_ascii=False)
