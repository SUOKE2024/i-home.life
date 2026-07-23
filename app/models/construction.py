import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Integer, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ConstructionTask(Base):
    __tablename__ = "construction_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phase: Mapped[str] = mapped_column(String(50), nullable=False, default="preparation")
    assigned_to: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_duration_days: Mapped[float | None] = mapped_column(nullable=True, default=None)  # 实际工期（天）
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # 任务依赖：前置任务 ID（子任务不能在前置任务完成之前开始）
    predecessor_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("construction_tasks.id"), nullable=True, index=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    logs = relationship("ConstructionLog", back_populates="task", cascade="all, delete-orphan")
    inspections = relationship("Inspection", back_populates="task", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "phase IN ('preparation', 'demolition', 'water_electricity', 'electrical', 'waterproof', 'masonry', 'mep', 'carpentry', 'painting', 'installation', 'completion', 'inspection')",
            name="chk_construction_task_phase",
        ),
        CheckConstraint("status IN ('pending', 'in_progress', 'ready', 'paused', 'completed', 'cancelled')", name="chk_construction_task_status"),
        CheckConstraint("priority >= 0", name="chk_construction_task_priority_positive"),
    )
    # 自引用关系：前置任务和后续任务
    predecessor = relationship("ConstructionTask", remote_side=[id], back_populates="successors", foreign_keys=[predecessor_id])
    successors = relationship("ConstructionTask", back_populates="predecessor", foreign_keys=[predecessor_id])


class ConstructionLog(Base):
    __tablename__ = "construction_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("construction_tasks.id"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(String(2000), nullable=False)
    log_type: Mapped[str] = mapped_column(String(20), nullable=False, default="daily")
    image_urls: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task = relationship("ConstructionTask", back_populates="logs")

    __table_args__ = (
        CheckConstraint("log_type IN ('daily', 'inspection', 'issue', 'change')", name="chk_construction_log_type"),
    )


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("construction_tasks.id"), nullable=False, index=True)
    inspector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    result: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    images: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    issues: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inspected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task = relationship("ConstructionTask", back_populates="inspections")

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'passed', 'failed')", name="chk_inspection_status"),
        CheckConstraint("score IS NULL OR (score >= 0 AND score <= 100)", name="chk_inspection_score_range"),
    )
