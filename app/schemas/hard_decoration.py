"""F21 硬装模块 Pydantic 模型"""

from datetime import datetime
from typing import Any
from pydantic import BaseModel


class HardDecorationSchemeCreate(BaseModel):
    project_id: str
    room_name: str
    scheme_type: str = "floor"
    # scheme_type: floor / wall / ceiling
    floor_area: float = 0.0
    wall_area: float = 0.0
    ceiling_area: float = 0.0
    total_budget: float = 0.0
    status: str = "draft"
    notes: str | None = None


class HardDecorationSchemeResponse(BaseModel):
    id: str
    project_id: str
    room_name: str
    scheme_type: str
    floor_area: float
    wall_area: float
    ceiling_area: float
    total_budget: float
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FloorPlanCreate(BaseModel):
    scheme_id: str
    material_type: str
    material_spec: str | None = None
    tile_width: float | None = None
    tile_length: float | None = None
    pattern: str = "直铺"
    coverage_area: float = 0.0
    waste_percent: float = 5.0
    total_material: float = 0.0
    unit_price: float = 0.0
    total_price: float = 0.0


class FloorPlanResponse(BaseModel):
    id: str
    scheme_id: str
    material_type: str
    material_spec: str | None
    tile_width: float | None
    tile_length: float | None
    pattern: str
    coverage_area: float
    waste_percent: float
    total_material: float
    unit_price: float
    total_price: float
    created_at: datetime

    model_config = {"from_attributes": True}


class WallFinishCreate(BaseModel):
    scheme_id: str
    finish_type: str
    color_code: str | None = None
    color_name: str | None = None
    coverage_area: float = 0.0
    coats: int = 2
    waste_percent: float = 5.0
    total_material: float = 0.0
    unit_price: float = 0.0
    total_price: float = 0.0


class WallFinishResponse(BaseModel):
    id: str
    scheme_id: str
    finish_type: str
    color_code: str | None
    color_name: str | None
    coverage_area: float
    coats: int
    waste_percent: float
    total_material: float
    unit_price: float
    total_price: float
    created_at: datetime

    model_config = {"from_attributes": True}


class CeilingDesignCreate(BaseModel):
    scheme_id: str
    ceiling_type: str = "flat"
    height_drop_mm: int = 0
    light_strip: bool = False
    light_positions: list[dict[str, Any]] | None = None
    material: str | None = None
    total_area: float = 0.0
    unit_price: float = 0.0
    total_price: float = 0.0


class CeilingDesignResponse(BaseModel):
    id: str
    scheme_id: str
    ceiling_type: str
    height_drop_mm: int
    light_strip: bool
    light_positions: list[dict[str, Any]] | None
    material: str | None
    total_area: float
    unit_price: float
    total_price: float
    created_at: datetime

    model_config = {"from_attributes": True}


class TileLayoutRequest(BaseModel):
    """瓷砖排版请求"""

    room_width: float
    room_length: float
    tile_width: float
    tile_length: float
    pattern: str = "直铺"


class PaintUsageRequest(BaseModel):
    """涂料用量计算请求"""

    wall_area: float
    coats: int = 2
    coverage_per_l: float = 9.0
    # 每升单遍涂刷面积 (8-10㎡)


class CeilingDesignRequest(BaseModel):
    """吊顶设计请求"""

    room_type: str
    height: float = 2.8
