"""F31 智能家居方案设计器 Pydantic 模型"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── 方案 ──


class SmartHomeSchemeCreate(BaseModel):
    project_id: str
    room_name: str
    room_type: str = "living_room"
    protocol: str = "zigbee"
    hub_brand: str = "xiaomi"
    notes: str | None = None


class SmartHomeSchemeResponse(BaseModel):
    id: str
    project_id: str
    room_name: str
    room_type: str
    protocol: str
    hub_brand: str
    device_count: int
    total_price: float
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── 设备 ──


class SmartDeviceCreate(BaseModel):
    device_type: str = Field(description="设备类型: light/switch/socket/sensor/camera/lock/curtain/speaker/thermostat/air_purifier/robot_vacuum")
    device_name: str
    brand: str | None = None
    model: str | None = None
    position_x: float | None = None
    position_y: float | None = None
    position_z: float | None = None
    room_name: str | None = None
    protocol: str = "zigbee"
    control_mode: str = "manual"
    power_w: float | None = None
    price: float = 0.0
    wiring_required: bool = False
    wiring_spec: dict[str, Any] | None = None
    features: dict[str, Any] | None = None
    status: str = "planned"


class SmartDeviceResponse(BaseModel):
    id: str
    scheme_id: str
    device_type: str
    device_name: str
    brand: str | None
    model: str | None
    position_x: float | None
    position_y: float | None
    position_z: float | None
    room_name: str | None
    protocol: str
    control_mode: str
    power_w: float | None
    price: float
    wiring_required: bool
    wiring_spec: dict[str, Any] | None
    features: dict[str, Any] | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── 计算结果 ──


class AutoRecommendResult(BaseModel):
    """自动推荐设备结果"""

    room_type: str
    room_area: float
    protocol: str
    hub_brand: str
    recommended_devices: list[dict[str, Any]] = Field(default_factory=list, description="推荐设备清单")
    total_estimate: float = Field(default=0.0, description="设备总价估算")


class WiringPlanResult(BaseModel):
    """布线规划结果"""

    scheme_id: str
    wiring_items: list[dict[str, Any]] = Field(default_factory=list, description="布线项清单")
    notes: list[str] = Field(default_factory=list, description="布线注意事项")


class ProtocolAdviceResult(BaseModel):
    """协议选型建议结果"""

    hub_brand: str
    recommended_protocol: str = Field(description="推荐主协议")
    alternative_protocols: list[str] = Field(default_factory=list, description="备选协议")
    compatibility: list[str] = Field(default_factory=list, description="兼容性说明")
    notes: str | None = Field(default=None, description="补充说明")


class PriceComputeResult(BaseModel):
    """方案总价计算结果"""

    scheme_id: str
    device_count: int
    device_total: float = Field(description="设备总价")
    hub_estimate: float = Field(default=0.0, description="网关估价")
    total_price: float = Field(description="方案总价")
