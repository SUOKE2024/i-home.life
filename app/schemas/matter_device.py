"""Matter 设备 Pydantic 模型 — A7 Matter 协议桥接"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Matter 设备 ──


class MatterDeviceCreate(BaseModel):
    """创建 Matter 设备"""

    project_id: str
    matter_unique_id: str = Field(description="Matter 唯一标识 (vendor_id:product_id:serial)")
    device_type_id: int = Field(description="Matter DeviceType ID (0x0100-0x0126)")
    vendor_id: int = Field(description="CSA Vendor ID (16-bit)")
    product_id: int = Field(description="Product ID (16-bit)")
    software_version: str = "1.0.0"
    hardware_version: str = "1.0"
    commissioning_state: str = "not_commissioned"
    fabric_index: int | None = None
    node_id: int | None = None
    clusters: dict[str, Any] | None = None
    endpoints: dict[str, Any] | None = None
    thread_credentials: dict[str, Any] | None = None
    wifi_credentials: dict[str, Any] | None = None
    last_seen_at: datetime | None = None


class MatterDeviceResponse(BaseModel):
    """Matter 设备响应"""

    id: str
    project_id: str
    matter_unique_id: str
    device_type_id: int
    vendor_id: int
    product_id: int
    software_version: str
    hardware_version: str
    commissioning_state: str
    fabric_index: int | None
    node_id: int | None
    clusters: dict[str, Any] | None
    endpoints: dict[str, Any] | None
    thread_credentials: dict[str, Any] | None
    wifi_credentials: dict[str, Any] | None
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MatterDeviceUpdate(BaseModel):
    """更新 Matter 设备"""

    commissioning_state: str | None = None
    fabric_index: int | None = None
    node_id: int | None = None
    clusters: dict[str, Any] | None = None
    endpoints: dict[str, Any] | None = None
    thread_credentials: dict[str, Any] | None = None
    wifi_credentials: dict[str, Any] | None = None
    software_version: str | None = None
    hardware_version: str | None = None
    last_seen_at: datetime | None = None


# ── Matter Commissioning ──


class MatterCommissionRequest(BaseModel):
    """Matter 设备配网请求"""

    project_id: str = Field(description="项目 ID")
    passcode: int = Field(description="Manual Pairing Code (11 位数字)")
    discriminator: int = Field(description="设备识别码 (12-bit, 0-4095)")
    thread_credentials: dict[str, Any] | None = Field(
        default=None, description="Thread 网络凭据 (network_name, pan_id, master_key)"
    )
    wifi_credentials: dict[str, Any] | None = Field(
        default=None, description="WiFi 网络凭据 (ssid, password)"
    )
    device_type_id: int | None = Field(
        default=None, description="Matter DeviceType ID (可选, 配网后自动获取)"
    )
    vendor_id: int | None = Field(
        default=None, description="Vendor ID (可选, 配网后自动获取)"
    )
    product_id: int | None = Field(
        default=None, description="Product ID (可选, 配网后自动获取)"
    )


class MatterCommissionResponse(BaseModel):
    """Matter 设备配网响应"""

    device_id: str | None = Field(default=None, description="配网成功后创建的设备 ID")
    matter_unique_id: str | None = Field(default=None)
    node_id: int | None = Field(default=None)
    fabric_index: int | None = Field(default=None)
    commissioning_state: str = Field(default="failed")
    message: str = Field(default="")


class MatterPlacementPlanResponse(BaseModel):
    """Matter 设备点位规划响应"""

    project_id: str
    project_name: str
    estimated_area: float
    protocol: str
    rooms: list[dict[str, Any]] = Field(default_factory=list)
    total_device_count: int = 0
    estimated_power_w: int = 0
    commissioning_guide: str = ""
    commissioned_devices: list[dict[str, Any]] = Field(
        default_factory=list, description="已配对的 Matter 设备列表"
    )
