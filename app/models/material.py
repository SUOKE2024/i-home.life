import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Float, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MaterialCategory(Base):
    __tablename__ = "material_categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    materials = relationship("Material", back_populates="category")


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    category_id: Mapped[str] = mapped_column(String(36), ForeignKey("material_categories.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="piece")
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    spec: Mapped[str | None] = mapped_column(String(300), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    category = relationship("MaterialCategory", back_populates="materials")
    bom_items = relationship("BOMItem", back_populates="material")

    __table_args__ = (
        CheckConstraint("unit_price >= 0", name="chk_material_unit_price_positive"),
    )


class BOMItem(Base):
    __tablename__ = "bom_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(String(36), ForeignKey("materials.id"), nullable=False, index=True)
    room_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("rooms.id"), nullable=True, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="bom_items")
    material = relationship("Material", back_populates="bom_items")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_bom_item_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="chk_bom_item_unit_price_positive"),
        CheckConstraint("total_price >= 0", name="chk_bom_item_total_price_positive"),
        CheckConstraint("status IN ('pending', 'ordered', 'delivered', 'installed', 'auto_generated')", name="chk_bom_item_status"),
    )
