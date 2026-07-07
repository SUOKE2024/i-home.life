"""F23 门窗/防水工程 Pydantic 模型"""

from datetime import datetime
from pydantic import BaseModel


class DoorWindowSpecCreate(BaseModel):
    project_id: str
    room_name: str
    location: str | None = None
    spec_type: str
    # spec_type: entry_door / interior_door / window / sliding_door / french_window
    material: str
    # material: solid_wood / wood_composite / aluminum / pvc / steel
    width: float = 800.0
    height: float = 2000.0
    thickness: float | None = None
    opening_direction: str = "inward"
    # opening_direction: inward / outward / sliding / folding
    glass_type: str | None = None
    brand: str | None = None
    model: str | None = None
    price: float = 0.0
    has_screen: bool = False
    has_lock: bool = False
    notes: str | None = None


class DoorWindowSpecResponse(BaseModel):
    id: str
    project_id: str
    room_name: str
    location: str | None
    spec_type: str
    material: str
    width: float
    height: float
    thickness: float | None
    opening_direction: str
    glass_type: str | None
    brand: str | None
    model: str | None
    price: float
    has_screen: bool
    has_lock: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DoorWindowRecommendRequest(BaseModel):
    """门窗推荐请求"""

    spec_type: str
    room_type: str | None = None
    opening_direction: str | None = None


class WaterproofPlanCreate(BaseModel):
    project_id: str
    room_name: str
    room_type: str
    # room_type: bathroom / kitchen / balcony / terrace / laundry
    wall_height_mm: int = 1800
    floor_area: float = 0.0
    wall_area: float = 0.0
    waterproof_material: str = "polyurethane"
    # waterproof_material: polyurethane / JS / cement_based / SBS
    coating_layers: int = 2
    thickness_mm: float = 1.5
    closure_test_hours: int = 24
    material_quantity: float = 0.0
    unit_price: float = 0.0
    total_price: float = 0.0
    status: str = "draft"
    notes: str | None = None


class WaterproofPlanResponse(BaseModel):
    id: str
    project_id: str
    room_name: str
    room_type: str
    wall_height_mm: int
    floor_area: float
    wall_area: float
    waterproof_material: str
    coating_layers: int
    thickness_mm: float
    closure_test_hours: int
    material_quantity: float
    unit_price: float
    total_price: float
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WaterproofAreaRequest(BaseModel):
    """防水面积计算请求"""

    room_width: float
    room_length: float
    wall_height_mm: int = 1800
