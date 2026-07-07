"""F17 卫生间设计器模型 — 卫生间设计 + 卫浴设备"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Integer, Float, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BathroomDesign(Base):
    """卫生间设计"""

    __tablename__ = "bathroom_designs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    room_name: Mapped[str] = mapped_column(String(100), nullable=False)
    layout_type: Mapped[str] = mapped_column(String(30), nullable=False, default="dry_wet_separation")
    # layout_type: dry_wet_separation(干湿分离) / three_separation(三分离) / traditional(传统)
    room_width: Mapped[float] = mapped_column(Float, nullable=False, default=2.0)
    room_length: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    ceiling_height: Mapped[float] = mapped_column(Float, nullable=False, default=2.6)
    dry_area: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 干区面积 (m²)
    wet_area: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 湿区面积 (m²)
    floor_drain_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    waterproof_height_mm: Mapped[int] = mapped_column(Integer, nullable=False, default=1800)
    # 防水高度，默认 1800mm
    drain_slope_percent: Mapped[float] = mapped_column(Float, nullable=False, default=1.5)
    # 地漏坡度，默认 1.5%
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # status: draft / completed
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
    fixtures = relationship("BathroomFixture", back_populates="design", cascade="all, delete-orphan")


class BathroomFixture(Base):
    """卫浴设备"""

    __tablename__ = "bathroom_fixtures"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    design_id: Mapped[str] = mapped_column(String(36), ForeignKey("bathroom_designs.id"), nullable=False)
    fixture_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # fixture_type: toilet(马桶) / basin(洗手盆) / bathtub(浴缸) / shower(淋浴) /
    #   urinal(小便器) / bidet(妇洗器) / mirror(镜子) / cabinet(浴室柜) /
    #   towel_rack(毛巾架) / vent_fan(换气扇) / heater(暖风机)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    width: Mapped[float] = mapped_column(Float, nullable=False, default=600.0)
    depth: Mapped[float] = mapped_column(Float, nullable=False, default=500.0)
    height: Mapped[float] = mapped_column(Float, nullable=False, default=800.0)
    position_x: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    position_y: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    position_z: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    material: Mapped[str | None] = mapped_column(String(100), nullable=True)
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    design = relationship("BathroomDesign", back_populates="fixtures")
