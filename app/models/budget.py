import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Float, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False, unique=True, index=True
    )
    total_estimated: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_actual: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    lines = relationship("BudgetLine", back_populates="budget", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("status IN ('draft', 'approved', 'active', 'completed')", name="chk_budget_status"),
        CheckConstraint("total_estimated >= 0", name="chk_budget_total_estimated_positive"),
        CheckConstraint("total_actual >= 0", name="chk_budget_total_actual_positive"),
    )


class BudgetLine(Base):
    __tablename__ = "budget_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    budget_id: Mapped[str] = mapped_column(String(36), ForeignKey("budgets.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    estimated_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    actual_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="项")
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    budget = relationship("Budget", back_populates="lines")

    __table_args__ = (
        CheckConstraint("estimated_amount >= 0", name="chk_budget_line_estimated_amount_positive"),
        CheckConstraint("actual_amount >= 0", name="chk_budget_line_actual_amount_positive"),
        CheckConstraint("quantity > 0", name="chk_budget_line_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="chk_budget_line_unit_price_positive"),
    )
