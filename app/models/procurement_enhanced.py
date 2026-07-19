"""F33/F34 增强模型 — 比价报告 + 担保支付 + 物流追踪 + 样品索要"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Float, Integer, Text, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ── F33 AI 智能匹配与比价 ──

class PriceComparison(Base):
    """比价报告"""

    __tablename__ = "price_comparisons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    bom_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    report_no: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    supplier_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_quotes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recommended_supplier_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("suppliers.id"), nullable=True, index=True)
    total_savings: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # total_savings: 相对最高报价的累计节省金额
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # status: draft(草稿) / completed(已完成) / expired(已失效)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
    items = relationship("PriceComparisonItem", back_populates="comparison", cascade="all, delete-orphan")


class PriceComparisonItem(Base):
    """比价项（按 BOM 物料维度）"""

    __tablename__ = "price_comparison_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    comparison_id: Mapped[str] = mapped_column(String(36), ForeignKey("price_comparisons.id"), nullable=False, index=True)
    bom_item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    material_name: Mapped[str] = mapped_column(String(200), nullable=False)
    spec: Mapped[str | None] = mapped_column(String(300), nullable=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="piece")
    # quotations: JSON 数组 [{supplier_id, supplier_name, price, delivery_days, in_stock, score}]
    quotations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    recommended_supplier_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    recommended_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    savings_per_item: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    comparison = relationship("PriceComparison", back_populates="items")


# ── F34 担保支付 ──

class EscrowPayment(Base):
    """担保支付（资金进入平台担保账户，确认收货后释放给供应商）"""

    __tablename__ = "escrow_payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("procurement_orders.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    escrow_no: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    buyer_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    buyer_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    supplier_received: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supplier_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # status: pending(待付款) / buyer_paid(买家已付款) / supplier_received(供应商已收款) / refunded(已退款) / disputed(争议中)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    escrow_fee: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    dispute_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project")


# ── F34 物流追踪 ──

class LogisticsTracking(Base):
    """物流追踪"""

    __tablename__ = "logistics_trackings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("procurement_orders.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    tracking_no: Mapped[str] = mapped_column(String(50), nullable=False)
    # carrier: sf_express / yt_express / zto / sto / jd_logistics / debon / self_delivery
    carrier: Mapped[str] = mapped_column(String(30), nullable=False)
    ship_from: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ship_to: Mapped[str | None] = mapped_column(String(200), nullable=True)
    estimated_arrival: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_arrival: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # status: pending(待发货) / shipped(已发货) / in_transit(运输中) / delivered(已签收) / exception(异常)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # tracking_history: JSON 数组 [{timestamp, location, status, description}]
    tracking_history: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project")


# ── F34 样品索要 ──

class SampleRequest(Base):
    """样品索要"""

    __tablename__ = "sample_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    supplier_id: Mapped[str] = mapped_column(String(36), ForeignKey("suppliers.id"), nullable=False, index=True)
    material_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("materials.id"), nullable=True, index=True)
    # sample_type: 实物 / 色卡 / 小样
    sample_type: Mapped[str] = mapped_column(String(20), nullable=False, default="实物")
    # status: requested(已申请) / shipped(已寄出) / received(已收到) / rejected(已拒绝)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="requested")
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
    supplier = relationship("Supplier")
