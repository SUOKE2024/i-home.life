"""F38 AI 质量管理模型 — 质量问题 + 整改单 + 质量评估"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Integer, Float, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class QualityIssue(Base):
    """质量问题记录"""

    __tablename__ = "quality_issues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("construction_tasks.id"), nullable=True)
    inspection_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("inspections.id"), nullable=True)
    phase: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    # category: 平整度/空鼓/防水/电路/安装/油漆 等
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    # severity: low / medium / high / critical
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    # status: open(待处理) / in_progress(整改中) / resolved(已整改) / verified(已验收) / closed(已关闭)
    images: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    detected_by: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    # detected_by: ai / manual / inspection
    standard: Mapped[str | None] = mapped_column(String(500), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
    task = relationship("ConstructionTask")
    inspection = relationship("Inspection")


class RectificationOrder(Base):
    """整改单"""

    __tablename__ = "rectification_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    order_no: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    phase: Mapped[str] = mapped_column(String(50), nullable=False)
    issue_ids: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # issue_ids: JSON 字符串，关联多个 QualityIssue
    responsible_party: Mapped[str | None] = mapped_column(String(100), nullable=True)
    responsible_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    # priority: low / medium / high / urgent
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # status: pending(待处理) / in_progress(整改中) / completed(已完成) / verified(已验收) / closed(已关闭)
    cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project")


class QualityAssessment(Base):
    """质量评估汇总"""

    __tablename__ = "quality_assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    phase: Mapped[str] = mapped_column(String(50), nullable=False)
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    verdict: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    # verdict: excellent / pass / conditional_pass / fail / pending
    assessor: Mapped[str | None] = mapped_column(String(100), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    issues_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
