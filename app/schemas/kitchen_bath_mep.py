"""F18 厨卫水电 Pydantic 模型"""

from datetime import datetime
from typing import Any
from pydantic import BaseModel


class KitchenBathMEPPlanCreate(BaseModel):
    project_id: str
    room_name: str
    room_type: str
    # room_type: kitchen / bathroom / laundry / balcony
    water_inlets: list[dict[str, Any]] | None = None
    drains: list[dict[str, Any]] | None = None
    gas_pipe_layout: list[dict[str, Any]] | None = None
    electrical_circuits: list[dict[str, Any]] | None = None
    equipotential_bonding: bool = False
    water_heater_type: str | None = None
    water_heater_capacity_l: int | None = None
    status: str = "draft"
    notes: str | None = None


class KitchenBathMEPPlanResponse(BaseModel):
    id: str
    project_id: str
    room_name: str
    room_type: str
    water_inlets: list[dict[str, Any]] | None
    drains: list[dict[str, Any]] | None
    gas_pipe_layout: list[dict[str, Any]] | None
    electrical_circuits: list[dict[str, Any]] | None
    equipotential_bonding: bool
    water_heater_type: str | None
    water_heater_capacity_l: int | None
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MEPPointCreate(BaseModel):
    plan_id: str
    point_type: str
    device: str | None = None
    position_x: float = 0.0
    position_y: float = 0.0
    position_z: float = 0.0
    spec: str | None = None
    voltage: str | None = None
    power_w: float | None = None
    notes: str | None = None


class MEPPointResponse(BaseModel):
    id: str
    plan_id: str
    point_type: str
    device: str | None
    position_x: float
    position_y: float
    position_z: float
    spec: str | None
    voltage: str | None
    power_w: float | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AutoGenerateRequest(BaseModel):
    """自动生成水电点位请求"""

    devices: list[str] = []
    # devices: ["热水器", "洗碗机", "净水器", "智能马桶", "洗衣机"]
