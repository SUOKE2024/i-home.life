"""变更管理模型 — F39 业主发起变更 → 设计评估 → 预算影响 → 业主确认 → 合同附项"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Float, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ChangeOrder(Base):
    """工程变更单"""
    __tablename__ = "change_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    change_type: Mapped[str] = mapped_column(String(30), nullable=False, default="owner_request")
    # owner_request / design_adjust / budget_optimization / construction_issue / force_majeure

    # 评估结果
    feasibility: Mapped[str | None] = mapped_column(String(20), nullable=True)  # feasible / infeasible / partial
    feasibility_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_impact: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    schedule_impact_days: Mapped[int] = mapped_column(default=0)
    design_impact: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 审批流
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # pending / reviewing / approved / rejected / cancelled / completed
    submitted_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="change_orders")
    items = relationship("ChangeOrderItem", back_populates="change_order", cascade="all, delete-orphan")


class ChangeOrderItem(Base):
    """变更明细项"""
    __tablename__ = "change_order_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    change_order_id: Mapped[str] = mapped_column(String(36), ForeignKey("change_orders.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # add / modify / remove
    target_type: Mapped[str] = mapped_column(String(30), nullable=False, default="room")
    # room / wall / material / task / budget_line
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    before_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    after_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    change_order = relationship("ChangeOrder", back_populates="items")
