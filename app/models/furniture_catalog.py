"""F26 家具品类库模型 — 家具库单品"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, func, Integer, Float, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FurnitureCatalogItem(Base):
    """家具库单品"""

    __tablename__ = "furniture_catalog_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    # category: living_room / dining_room / bedroom / study / kitchen / bathroom / outdoor
    subcategory: Mapped[str] = mapped_column(String(50), nullable=False)
    # subcategory: sofa / bed / dining_table / chair / coffee_table / wardrobe /
    #   bookshelf / desk / tv_cabinet / shoe_cabinet / nightstand
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    width: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 宽 mm
    depth: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 深 mm
    height: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 高 mm
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 重量 kg
    material: Mapped[str | None] = mapped_column(String(100), nullable=True)
    color: Mapped[str | None] = mapped_column(String(100), nullable=True)
    style: Mapped[str] = mapped_column(String(50), nullable=False, default="modern")
    # style: modern / nordic / chinese / american / french / industrial / japanese
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sale_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    model_3d_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 3D 模型 USDZ/GLB URL
    ar_preview_supported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    stock_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rating: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 评分 0-5
    sales_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 浏览量
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # 标签 JSON: ["热销", "新品", "环保"]
    specs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 详细规格 JSON: {"材质": "实木", "产地": "中国"}
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    # status: active(在售) / discontinued(停售)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
