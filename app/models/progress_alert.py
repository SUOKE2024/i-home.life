"""F37 进度预警模型 — 延期/风险/里程碑跟踪"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Integer, Float, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProgressAlert(Base):
    """进度预警记录"""

    __tablename__ = "progress_alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("construction_tasks.id"), nullable=True)
    phase: Mapped[str] = mapped_column(String(50), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(30), nullable=False, default="delay")
    # alert_type: delay(延期) / risk(风险) / milestone(里程碑) / reminder(提醒)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    # severity: low / medium / high / critical
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    planned_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actual_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delay_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    # status: active(活跃) / resolved(已解决) / ignored(已忽略)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
    task = relationship("ConstructionTask")


class MilestoneTracker(Base):
    """里程碑跟踪记录 — 与结算里程碑对齐"""

    __tablename__ = "milestone_trackers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    milestone_code: Mapped[str] = mapped_column(String(30), nullable=False)
    # milestone_code: delivery(交房) / mep(水电) / masonry(泥瓦) / completion(竣工) / warranty(保修)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    planned_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actual_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    planned_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    actual_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # status: pending / in_progress / completed / delayed
    payment_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 对应结算比例：交房30% / 水电20% / 泥瓦25% / 竣工20% / 保修5%
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
