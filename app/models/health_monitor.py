"""A2 智能家居健康监测系统模型 — 健康监测记录 + 空气质量记录"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Integer, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class HealthMonitor(Base):
    """健康监测记录"""

    __tablename__ = "health_monitors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    scheme_id: Mapped[str] = mapped_column(String(36), ForeignKey("smart_home_schemes.id"), nullable=False, index=True)
    monitor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # monitor_type: sleep_quality / air_quality / fall_detection / activity_tracking / heart_rate / spo2
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
    # value 示例: {"sleep_score": 85, "deep_sleep_hours": 3.2}
    alert_level: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    # alert_level: normal / warning / critical
    alert_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("smart_devices.id"), nullable=True, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project")
    scheme = relationship("SmartHomeScheme")
    device = relationship("SmartDevice")


class AirQualityRecord(Base):
    """空气质量记录"""

    __tablename__ = "air_quality_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    scheme_id: Mapped[str] = mapped_column(String(36), ForeignKey("smart_home_schemes.id"), nullable=False, index=True)
    room_name: Mapped[str] = mapped_column(String(100), nullable=False)
    pm25: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # PM2.5 浓度，单位 μg/m³
    pm10: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    co2: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # CO2 浓度，单位 ppm
    tvoc: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 总挥发性有机物，单位 ppb
    formaldehyde: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 甲醛浓度，单位 mg/m³
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    humidity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    aqi_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 综合 AQI 指数
    aqi_level: Mapped[str] = mapped_column(String(30), nullable=False, default="good")
    # aqi_level: good / moderate / unhealthy_sensitive / unhealthy / very_unhealthy / hazardous
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project")
    scheme = relationship("SmartHomeScheme")
