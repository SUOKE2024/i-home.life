"""F31 智能家居方案设计器模型 — 方案 + 设备"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Integer, Float, Text, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SmartHomeScheme(Base):
    """智能家居方案"""

    __tablename__ = "smart_home_schemes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    room_name: Mapped[str] = mapped_column(String(100), nullable=False)
    room_type: Mapped[str] = mapped_column(String(50), nullable=False, default="living_room")
    # room_type: living_room / bedroom / kitchen / bathroom / entrance / study
    protocol: Mapped[str] = mapped_column(String(50), nullable=False, default="zigbee")
    # protocol: zigbee / wifi / bluetooth / matter / homekit
    hub_brand: Mapped[str] = mapped_column(String(50), nullable=False, default="xiaomi")
    # hub_brand: xiaomi / huawei / apple / tuya / alexa
    device_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # status: draft(草稿) / planned(已规划) / installing(安装中) / completed(已完成)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
    devices = relationship(
        "SmartDevice",
        back_populates="scheme",
        cascade="all, delete-orphan",
        order_by="SmartDevice.created_at",
    )


class SmartDevice(Base):
    """智能设备"""

    __tablename__ = "smart_devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scheme_id: Mapped[str] = mapped_column(String(36), ForeignKey("smart_home_schemes.id"), nullable=False)
    device_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # device_type: light / switch / socket / sensor / camera / lock / curtain /
    #   speaker / thermostat / air_purifier / robot_vacuum
    device_name: Mapped[str] = mapped_column(String(200), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    position_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_z: Mapped[float | None] = mapped_column(Float, nullable=True)
    room_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    protocol: Mapped[str] = mapped_column(String(50), nullable=False, default="zigbee")
    control_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    # control_mode: manual / voice / app / automation
    power_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 功率 W
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    wiring_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    wiring_spec: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 布线规格 JSON: {"零火线": true, "网线": false, "电源预留": true}
    features: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 功能特性 JSON: {"调光": true, "色温": true}
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    # status: planned(已规划) / installed(已安装) / online(在线) / offline(离线)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    scheme = relationship("SmartHomeScheme", back_populates="devices")
