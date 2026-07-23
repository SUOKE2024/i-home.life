import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Float, Text, Boolean, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    rating: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    is_active: Mapped[bool] = mapped_column(default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    quotations = relationship("Quotation", back_populates="supplier")
    orders = relationship("ProcurementOrder", back_populates="supplier")

    __table_args__ = (
        CheckConstraint("rating >= 0 AND rating <= 5", name="chk_supplier_rating_range"),
    )


class Quotation(Base):
    __tablename__ = "quotations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    supplier_id: Mapped[str] = mapped_column(String(36), ForeignKey("suppliers.id"), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(String(36), ForeignKey("materials.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    delivery_days: Mapped[int] = mapped_column(default=7)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    supplier = relationship("Supplier", back_populates="quotations")
    material = relationship("Material")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_quotation_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="chk_quotation_unit_price_positive"),
        CheckConstraint("total_price >= 0", name="chk_quotation_total_price_positive"),
        CheckConstraint("delivery_days > 0", name="chk_quotation_delivery_days_positive"),
        CheckConstraint("status IN ('pending', 'accepted', 'rejected', 'expired')", name="chk_quotation_status"),
    )


class ProcurementOrder(Base):
    __tablename__ = "procurement_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    supplier_id: Mapped[str] = mapped_column(String(36), ForeignKey("suppliers.id"), nullable=False, index=True)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    expected_delivery: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # A5 采购交付透明度
    delivery_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    # delivery_status: pending/shipping/in_transit/delivered/delayed/cancelled
    tracking_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    carrier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    estimated_delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    assembly_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    assembly_difficulty: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # assembly_difficulty: easy/medium/hard/professional_required
    delivery_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 关联施工任务
    construction_task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("construction_tasks.id"), nullable=True, index=True
    )
    material_delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    supplier = relationship("Supplier", back_populates="orders")
    lines = relationship("OrderLine", back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="chk_procurement_order_total_amount_positive"),
        CheckConstraint("status IN ('draft', 'pending', 'confirmed', 'shipped', 'delivered', 'cancelled')", name="chk_procurement_order_status"),
        CheckConstraint(
            "delivery_status IN ('pending', 'shipping', 'in_transit', 'delivered', 'delayed', 'cancelled')",
            name="chk_procurement_order_delivery_status",
        ),
        CheckConstraint(
            "assembly_difficulty IS NULL OR assembly_difficulty IN ('easy', 'medium', 'hard', 'professional_required')",
            name="chk_procurement_order_assembly_difficulty",
        ),
    )


class OrderLine(Base):
    __tablename__ = "order_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("procurement_orders.id"), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(String(36), ForeignKey("materials.id"), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    delivered_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order = relationship("ProcurementOrder", back_populates="lines")
    material = relationship("Material")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_order_line_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="chk_order_line_unit_price_positive"),
        CheckConstraint("total_price >= 0", name="chk_order_line_total_price_positive"),
        CheckConstraint("delivered_quantity >= 0", name="chk_order_line_delivered_qty_positive"),
    )
