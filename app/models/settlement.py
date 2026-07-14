import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Settlement(Base):
    __tablename__ = "settlements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, unique=True)
    milestone: Mapped[str] = mapped_column(String(50), nullable=False, default="completion")
    contract_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    actual_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    payable_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # F14 异常检测与人工复核字段
    anomaly_count: Mapped[int] = mapped_column(default=0, nullable=False)
    critical_anomaly_count: Mapped[int] = mapped_column(default=0, nullable=False)
    suggested_deduction: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    review_required: Mapped[bool] = mapped_column(default=False, nullable=False)
    review_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    lines = relationship("SettlementLine", back_populates="settlement", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="settlement")
    project = relationship("Project")


class SettlementLine(Base):
    __tablename__ = "settlement_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    settlement_id: Mapped[str] = mapped_column(String(36), ForeignKey("settlements.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    contract_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    change_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    actual_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # F14 异常标记字段
    is_anomaly: Mapped[bool] = mapped_column(default=False, nullable=False)
    anomaly_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    anomaly_severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    anomaly_detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    settlement = relationship("Settlement", back_populates="lines")
