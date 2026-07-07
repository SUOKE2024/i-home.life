"""F24/F25 软装搭配 + 收纳系统模型 — 方案 + 单品 + 收纳"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Integer, Float, Text, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SoftFurnishingScheme(Base):
    """软装方案"""

    __tablename__ = "soft_furnishing_schemes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    room_name: Mapped[str] = mapped_column(String(100), nullable=False)
    style: Mapped[str] = mapped_column(String(50), nullable=False, default="modern")
    # style: modern / 北欧 / 新中式 / 美式 / 法式 / 工业 / 日式
    color_scheme: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 配色方案 JSON: {"primary": "...", "secondary": "...", "accent": "..."}
    budget_total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    budget_used: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # status: draft(草稿) / planned(已规划) / purchasing(采购中) / delivered(已交付) / installed(已安装)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
    items = relationship(
        "SoftFurnishingItem",
        back_populates="scheme",
        cascade="all, delete-orphan",
        order_by="SoftFurnishingItem.created_at",
    )
    storages = relationship(
        "StorageSystem",
        back_populates="scheme",
        cascade="all, delete-orphan",
        order_by="StorageSystem.created_at",
    )


class SoftFurnishingItem(Base):
    """软装单品"""

    __tablename__ = "soft_furnishing_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scheme_id: Mapped[str] = mapped_column(String(36), ForeignKey("soft_furnishing_schemes.id"), nullable=False)
    item_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # item_type: sofa(沙发) / bed(床) / dining_table(餐桌) / chair(椅子) / coffee_table(茶几) / rug(地毯) / curtain(窗帘) / artwork(装饰画) / plant(绿植) / lamp(灯具) / pillow(抱枕) / decorative(摆件)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    width: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 宽 mm
    depth: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 深 mm
    height: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 高 mm
    color: Mapped[str | None] = mapped_column(String(100), nullable=True)
    material: Mapped[str | None] = mapped_column(String(100), nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    position_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_z: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    # status: planned(已规划) / purchased(已采购) / delivered(已发货) / installed(已安装)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    scheme = relationship("SoftFurnishingScheme", back_populates="items")


class StorageSystem(Base):
    """收纳系统 — 关联软装方案"""

    __tablename__ = "storage_systems"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scheme_id: Mapped[str] = mapped_column(String(36), ForeignKey("soft_furnishing_schemes.id"), nullable=False)
    room_name: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # storage_type: 衣柜 / 厨柜 / 书柜 / 鞋柜 / 储物间 / 吊柜 / 地柜
    total_capacity_l: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 总容量(升)
    compartment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 格数
    adjustable_shelves: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # 是否可调节层板
    smart_features: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 智能功能 JSON: {"smart_lock": true, "dehumidify": false, "auto_light": true}
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    scheme = relationship("SoftFurnishingScheme", back_populates="storages")
