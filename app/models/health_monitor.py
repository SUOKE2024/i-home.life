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
    device_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    # 外部设备标识（BLE MAC / 第三方设备号）。2026-09-24 交叉验证 A-2 修复：
    # 此前为 ForeignKey("smart_devices.id")，而穿戴 BLE 链路传的正是 BLE MAC
    # （flutter_app/lib/pages/wearable_devices_page.dart 传 _ble.device?.remoteId.str，
    # CLAUDE.md 亦明确「device_id=BLE MAC」）→ 三处口径互斥，生产实测恒 422
    # （health_monitors_device_id_fkey），适老/穿戴心率真实上报不可用。
    # 现放开外键（迁移 c6d7e8f9a0b1），仅作标识；需关联平台设备时用 smart_device_id。
    smart_device_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("smart_devices.id"), nullable=True, index=True
    )
    # 平台内 smart_devices 的可选关联（保留外键约束；与 device_id 互不强制）
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project")
    scheme = relationship("SmartHomeScheme")
    # 关系显式绑定 smart_device_id（device_id 已去外键、不再是可推断的 join 依据）
    device = relationship("SmartDevice", foreign_keys=[smart_device_id])


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
