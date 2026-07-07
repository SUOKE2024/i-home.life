"""F16 厨房设计器 Pydantic 模型"""

from datetime import datetime
from pydantic import BaseModel


class KitchenDesignCreate(BaseModel):
    project_id: str
    room_name: str
    layout_type: str = "L"
    room_width: float = 3.0
    room_length: float = 3.0
    ceiling_height: float = 2.8
    counter_height: float = 850.0
    counter_depth: float = 600.0
    water_inlet_pos: str | None = None
    drain_pos: str | None = None
    gas_pos: str | None = None
    vent_pos: str | None = None
    status: str = "draft"


class KitchenDesignUpdate(BaseModel):
    layout_type: str | None = None
    room_width: float | None = None
    room_length: float | None = None
    ceiling_height: float | None = None
    counter_height: float | None = None
    counter_depth: float | None = None
    water_inlet_pos: str | None = None
    drain_pos: str | None = None
    gas_pos: str | None = None
    vent_pos: str | None = None
    status: str | None = None


class KitchenDesignResponse(BaseModel):
    id: str
    project_id: str
    room_name: str
    layout_type: str
    room_width: float
    room_length: float
    ceiling_height: float
    counter_height: float
    counter_depth: float
    water_inlet_pos: str | None
    drain_pos: str | None
    gas_pos: str | None
    vent_pos: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KitchenComponentCreate(BaseModel):
    design_id: str
    component_type: str
    brand: str | None = None
    model: str | None = None
    width: float = 600.0
    depth: float = 600.0
    height: float = 720.0
    position_x: float = 0.0
    position_y: float = 0.0
    position_z: float = 0.0
    rotation: float = 0.0
    material: str | None = None
    color: str | None = None
    price: float = 0.0
    notes: str | None = None


class KitchenComponentResponse(BaseModel):
    id: str
    design_id: str
    component_type: str
    brand: str | None
    model: str | None
    width: float
    depth: float
    height: float
    position_x: float
    position_y: float
    position_z: float
    rotation: float
    material: str | None
    color: str | None
    price: float
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
