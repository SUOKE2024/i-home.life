"""F29/F30 灯光设计器 Pydantic 模型"""

from datetime import datetime
from pydantic import BaseModel


class LightingSchemeCreate(BaseModel):
    project_id: str
    room_name: str
    scheme_type: str = "main_light"
    room_area: float = 0.0
    ceiling_height: float = 2.8
    total_lumens: float | None = None
    total_power_w: float | None = None
    color_temp_k: int | None = None
    cri: float | None = None
    ugpr: float | None = None
    status: str = "draft"
    notes: str | None = None


class LightingSchemeUpdate(BaseModel):
    scheme_type: str | None = None
    room_area: float | None = None
    ceiling_height: float | None = None
    total_lumens: float | None = None
    total_power_w: float | None = None
    color_temp_k: int | None = None
    cri: float | None = None
    ugpr: float | None = None
    status: str | None = None
    notes: str | None = None


class LightingSchemeResponse(BaseModel):
    id: str
    project_id: str
    room_name: str
    scheme_type: str
    room_area: float
    ceiling_height: float
    total_lumens: float | None
    total_power_w: float | None
    color_temp_k: int | None
    cri: float | None
    ugpr: float | None
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LightingFixtureCreate(BaseModel):
    scheme_id: str
    fixture_type: str
    brand: str | None = None
    model: str | None = None
    wattage_w: float = 0.0
    lumens: float = 0.0
    color_temp_k: int | None = None
    beam_angle: float | None = None
    position_x: float | None = None
    position_y: float | None = None
    position_z: float | None = None
    quantity: int = 1
    dimmable: bool = False
    smart_control: bool = False


class LightingFixtureResponse(BaseModel):
    id: str
    scheme_id: str
    fixture_type: str
    brand: str | None
    model: str | None
    wattage_w: float
    lumens: float
    color_temp_k: int | None
    beam_angle: float | None
    position_x: float | None
    position_y: float | None
    position_z: float | None
    quantity: int
    dimmable: bool
    smart_control: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AIDesignRequest(BaseModel):
    """AI 灯光方案设计请求"""

    room_type: str = "living_room"
    # room_type: living_room(客厅) / kitchen(厨房) / bedroom(卧室) / study(书房)
    style: str = "modern"
    # style: modern(现代) / minimalist(极简) / warm(温馨) / luxury(轻奢)
