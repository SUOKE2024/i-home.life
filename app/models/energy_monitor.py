"""A1 智能家居能耗监测系统模型 — 能耗记录 + 节能建议"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Float, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EnergyMonitor(Base):
    """能耗监测记录"""

    __tablename__ = "energy_monitor_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    scheme_id: Mapped[str] = mapped_column(String(36), ForeignKey("smart_home_schemes.id"), nullable=False, index=True)

    # 统计周期
    period: Mapped[str] = mapped_column(String(10), nullable=False)
    # period: daily / weekly / monthly

    # 能耗指标
    total_consumption_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    device_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # {"light": 12.5, "ac": 45.2, "tv": 5.0, ...}
    peak_power_w: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_power_w: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    standby_consumption_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    estimated_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    carbon_footprint_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project")
    scheme = relationship("SmartHomeScheme")


class EnergySavingTip(Base):
    """节能建议"""

    __tablename__ = "energy_saving_tips"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scheme_id: Mapped[str] = mapped_column(String(36), ForeignKey("smart_home_schemes.id"), nullable=False, index=True)

    tip_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # tip_type: bill_optimization / device_replacement / schedule_optimization / standby_reduction
    device_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    device_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    current_consumption: Mapped[float | None] = mapped_column(Float, nullable=True)
    potential_saving_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    suggestion: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    # priority: high / medium / low
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active")
    # status: active / dismissed / applied
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scheme = relationship("SmartHomeScheme")
