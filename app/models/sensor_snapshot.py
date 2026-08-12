"""传感器快照模型 — Flutter SensorService.getSnapshot() 上报的真实数据落库

设计约束（诚实降级红线）：
- 仅存储客户端真实采集到的读数（加速度计 / 陀螺仪 / 磁力计 / GPS）。
- 不推断、不伪造环境量（温度 / 湿度 / 光照 / 占用率）——手机传感器无法提供，
  禁止硬编码假数据伪装真实能力（v1.1.31 教训）。
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SensorSnapshot(Base):
    """传感器快照记录"""

    __tablename__ = "sensor_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    device_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    # 设备推送令牌 ID（可选）
    platform: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    # platform: ios / android / harmonyos / web

    # ── 加速度计 ──
    accelerometer_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    accelerometer_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    accelerometer_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    accelerometer_z: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── 陀螺仪 ──
    gyroscope_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    gyroscope_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    gyroscope_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    gyroscope_z: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── 磁力计 ──
    magnetometer_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    magnetometer_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    magnetometer_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    magnetometer_z: Mapped[float | None] = mapped_column(Float, nullable=True)
    magnetometer_heading_deg: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── GPS ──
    gps_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    gps_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_altitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── 环境量（环境传感器/生态桥接真实上报，非手机传感器，禁止伪造）──
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 温度 °C
    humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 湿度 %
    light_lux: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 光照度 lux

    # 客户端采样时间（ISO8601）
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
