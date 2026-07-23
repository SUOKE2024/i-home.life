"""产品/服务模型 — 供应商发布产品，AI 辅助内容发布"""
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Text, Boolean, Float, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Product(Base):
    """供应商产品/服务"""
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    supplier_id: Mapped[str] = mapped_column(String(36), ForeignKey("suppliers.id"), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    # tile / flooring / cabinet / paint / lighting / appliance / curtain / custom_furniture / service / other
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 价格信息
    price_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="个")
    # 计价单位：㎡ / m / 个 / 套 / 台 / 次

    # 多媒体
    images: Mapped[str | None] = mapped_column(Text, nullable=True)   # JSON 数组
    cover_image: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # 标签和规格
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)     # JSON 数组
    specs: Mapped[str | None] = mapped_column(Text, nullable=True)    # JSON 对象

    # 库存状态
    stock_status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_stock")
    # in_stock / pre_order / out_of_stock

    # 发布状态
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # draft / published / archived

    # AI 辅助标记
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_description: Mapped[str | None] = mapped_column(Text, nullable=True)  # AI 生成的产品文案

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    __table_args__ = (
        CheckConstraint(
            "category IN ('tile', 'flooring', 'cabinet', 'paint', 'lighting', 'appliance', 'curtain', 'custom_furniture', 'service', 'other')",
            name="chk_product_category",
        ),
        CheckConstraint("stock_status IN ('in_stock', 'pre_order', 'out_of_stock')", name="chk_product_stock_status"),
        CheckConstraint("status IN ('draft', 'published', 'archived')", name="chk_product_status"),
        CheckConstraint("price_min IS NULL OR price_min >= 0", name="chk_product_price_min_positive"),
        CheckConstraint("price_max IS NULL OR price_max >= 0", name="chk_product_price_max_positive"),
    )
