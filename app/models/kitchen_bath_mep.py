"""F18 厨卫水电模型 — 厨卫水电方案 + 水电点位"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Integer, Float, Text, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class KitchenBathMEPPlan(Base):
    """厨卫水电方案"""

    __tablename__ = "kitchen_bath_mep_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    room_name: Mapped[str] = mapped_column(String(100), nullable=False)
    room_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # room_type: kitchen(厨房) / bathroom(卫生间) / laundry(洗衣房) / balcony(阳台)
    water_inlets: Mapped[str | None] = mapped_column(JSON, nullable=True)
    # 给水点位列表 (JSON)
    drains: Mapped[str | None] = mapped_column(JSON, nullable=True)
    # 排水点位列表 (JSON)
    gas_pipe_layout: Mapped[str | None] = mapped_column(JSON, nullable=True)
    # 燃气管道路径 (JSON)
    electrical_circuits: Mapped[str | None] = mapped_column(JSON, nullable=True)
    # 电路回路列表 (JSON)
    equipotential_bonding: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 等电位连接 (卫生间强制要求)
    water_heater_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # water_heater_type: gas(燃气) / electric(电) / solar(太阳能) / air_source(空气能)
    water_heater_capacity_l: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 热水器容量 (升)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # status: draft / completed
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
    points = relationship("MEPPoint", back_populates="plan", cascade="all, delete-orphan")


class MEPPoint(Base):
    """水电点位"""

    __tablename__ = "mep_points"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("kitchen_bath_mep_plans.id"), nullable=False, index=True)
    point_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # point_type: water_inlet(给水) / drain(排水) / gas(燃气) / socket(插座) / switch(开关) / vent(通风)
    device: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # device: 洗碗机/净水器/智能马桶/热水器/洗衣机/油烟机 等
    position_x: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    position_y: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    position_z: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    spec: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # spec: 1/2" / 3/4" / 4分管 等
    voltage: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # voltage: 220V / 380V
    power_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 功率 (W)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    plan = relationship("KitchenBathMEPPlan", back_populates="points")
