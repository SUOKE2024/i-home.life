"""F29/F30 灯光设计器模型 — 灯光方案 + 灯具"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Integer, Float, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LightingScheme(Base):
    """灯光方案"""

    __tablename__ = "lighting_schemes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    room_name: Mapped[str] = mapped_column(String(100), nullable=False)
    scheme_type: Mapped[str] = mapped_column(String(30), nullable=False, default="main_light")
    # scheme_type: main_light(主灯)/none_main(无主灯)/mixed(混合)/scene(场景)
    room_area: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ceiling_height: Mapped[float] = mapped_column(Float, nullable=False, default=2.8)
    total_lumens: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_power_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    color_temp_k: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cri: Mapped[float | None] = mapped_column(Float, nullable=True)
    # cri: 显色指数 (0-100)
    ugpr: Mapped[float | None] = mapped_column(Float, nullable=True)
    # ugpr: 统一眩光指数
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # status: draft(草稿) / completed(已完成)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
    fixtures = relationship("LightingFixture", back_populates="scheme", cascade="all, delete-orphan")


class LightingFixture(Base):
    """灯具"""

    __tablename__ = "lighting_fixtures"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scheme_id: Mapped[str] = mapped_column(String(36), ForeignKey("lighting_schemes.id"), nullable=False)
    fixture_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # fixture_type: ceiling(吸顶)/pendant(吊灯)/spot(射灯)/strip(灯带)/track(轨道)/wall(壁灯)/panel(面板灯)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    wattage_w: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    lumens: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    color_temp_k: Mapped[int | None] = mapped_column(Integer, nullable=True)
    beam_angle: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_z: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    dimmable: Mapped[bool] = mapped_column(default=False)
    smart_control: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    scheme = relationship("LightingScheme", back_populates="fixtures")
