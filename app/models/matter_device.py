"""Matter 认证设备模型 — A7 Matter 协议桥接

Matter 2.0 是 CSA 推出的跨生态智能家居标准, 支持 IP 通信 (Thread/Wi-Fi/Ethernet)。
本模型存储 Matter 设备从配网 (commissioning) 到日常控制的全生命周期数据。
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MatterDevice(Base):
    """Matter 认证设备。

    记录 Matter 设备的基本属性 (vendor_id / product_id / device_type_id)、
    配网状态 (commissioning_state / fabric_index / node_id)、
    能力声明 (clusters / endpoints) 和网络凭据 (thread_credentials / wifi_credentials)。
    """

    __tablename__ = "matter_devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False, index=True,
    )

    # ── Matter 标识 ──
    matter_unique_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # 格式: "vendor_id:product_id:serial_number" 或 CSA 分配的 Unique ID

    device_type_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # Matter DeviceType ID: 0x0100 (On/Off Light) ~ 0x0126 (Refrigerator)
    # 完整列表见 MatterBridge.MATTER_DEVICE_TYPES

    vendor_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # CSA 分配的 Vendor ID (16-bit)

    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # 厂商自定义 Product ID (16-bit)

    # ── 版本信息 ──
    software_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")
    hardware_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")

    # ── 配网状态 ──
    commissioning_state: Mapped[str] = mapped_column(
        String(30), nullable=False, default="not_commissioned",
    )
    # not_commissioned / commissioning / commissioned / failed

    fabric_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Matter Fabric 索引 (配网成功后由 Commissioner 分配)

    node_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Matter Node ID (配网成功后由 Fabric 分配, 64-bit)

    # ── 能力声明 ──
    clusters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 支持的 Matter Clusters 列表, 如:
    # {"server": ["OnOff", "LevelControl", "ColorControl"], "client": []}

    endpoints: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 端点配置, 如:
    # [{"endpoint_id": 0, "device_types": [{"id": 22, "revision": 1}]}]

    # ── 网络凭据 ──
    thread_credentials: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Thread 网络凭据 (仅在 Thread 设备时需要)
    # {"network_name": "xxx", "pan_id": 0x1234, "master_key": "hex", "channel": 15}

    wifi_credentials: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # WiFi 网络凭据 (仅在 WiFi 设备时需要)
    # {"ssid": "xxx", "password": "xxx", "security": "WPA2"}

    # ── 时间戳 ──
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    # ── 关系 ──
    project = relationship("Project")
