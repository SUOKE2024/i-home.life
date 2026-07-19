"""F21 硬装模块模型 — 硬装方案 + 地面 + 墙面 + 吊顶"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Integer, Float, Text, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class HardDecorationScheme(Base):
    """硬装方案"""

    __tablename__ = "hard_decoration_schemes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    room_name: Mapped[str] = mapped_column(String(100), nullable=False)
    scheme_type: Mapped[str] = mapped_column(String(30), nullable=False, default="floor")
    # scheme_type: floor(地面) / wall(墙面) / ceiling(吊顶)
    floor_area: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    wall_area: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ceiling_area: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_budget: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # status: draft / completed
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
    floors = relationship("HardDecorationFloor", back_populates="scheme", cascade="all, delete-orphan")
    walls = relationship("WallFinish", back_populates="scheme", cascade="all, delete-orphan")
    ceilings = relationship("CeilingDesign", back_populates="scheme", cascade="all, delete-orphan")


class HardDecorationFloor(Base):
    """地面方案"""

    __tablename__ = "hard_decoration_floor_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scheme_id: Mapped[str] = mapped_column(String(36), ForeignKey("hard_decoration_schemes.id"), nullable=False, index=True)
    material_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # material_type: tile(瓷砖) / wood(木地板) / laminate(强化) / vinyl(塑胶) / stone(石材) / carpet(地毯)
    material_spec: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tile_width: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 砖宽 (mm)
    tile_length: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 砖长 (mm)
    pattern: Mapped[str] = mapped_column(String(30), nullable=False, default="直铺")
    # pattern: 直铺 / 人字拼 / 鱼骨拼 / 工字铺 / 菱形
    coverage_area: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 铺设面积 (m²)
    waste_percent: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    # 损耗率 (默认 5%)
    total_material: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 材料总量 (m²)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scheme = relationship("HardDecorationScheme", back_populates="floors")


class WallFinish(Base):
    """墙面方案"""

    __tablename__ = "wall_finishes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scheme_id: Mapped[str] = mapped_column(String(36), ForeignKey("hard_decoration_schemes.id"), nullable=False, index=True)
    finish_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # finish_type: paint(涂料) / wallpaper(墙纸) / tile(瓷砖) / panel(护墙板) / stone(石材) / wainscoting(墙裙)
    color_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    color_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    coverage_area: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 涂刷/铺贴面积 (m²)
    coats: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    # 涂料遍数 (默认 2)
    waste_percent: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    total_material: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 材料总量 (L 或 m²)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scheme = relationship("HardDecorationScheme", back_populates="walls")


class CeilingDesign(Base):
    """吊顶方案"""

    __tablename__ = "ceiling_designs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scheme_id: Mapped[str] = mapped_column(String(36), ForeignKey("hard_decoration_schemes.id"), nullable=False, index=True)
    ceiling_type: Mapped[str] = mapped_column(String(30), nullable=False, default="flat")
    # ceiling_type: flat(平顶) / suspended(吊顶) / gypsum_perimeter(石膏线周边) / coffered(井格) / curve(弧形)
    height_drop_mm: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 下吊高度 (mm)
    light_strip: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 灯带预留
    light_positions: Mapped[str | None] = mapped_column(JSON, nullable=True)
    # 灯位坐标 (JSON)
    material: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_area: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scheme = relationship("HardDecorationScheme", back_populates="ceilings")
