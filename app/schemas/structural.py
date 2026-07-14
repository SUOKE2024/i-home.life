"""F8-F9 土建模块 Pydantic 模型"""

from datetime import datetime
from typing import Any
from pydantic import BaseModel


# ── 承重墙 ──

class LoadBearingWallCreate(BaseModel):
    project_id: str
    room_id: str | None = None
    wall_name: str
    is_load_bearing: bool = True
    thickness_mm: int = 240
    length_m: float = 0.0
    height_m: float = 2.8
    material: str | None = None
    notes: str | None = None


class LoadBearingWallResponse(BaseModel):
    id: str
    project_id: str
    room_id: str | None
    wall_name: str
    is_load_bearing: bool
    thickness_mm: int
    length_m: float
    height_m: float
    material: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── 梁 ──

class BeamCreate(BaseModel):
    project_id: str
    beam_name: str
    beam_type: str = "main_beam"
    width_mm: int = 200
    height_mm: int = 400
    length_m: float = 0.0
    material: str = "reinforced_concrete"
    concrete_grade: str | None = None
    position_desc: str | None = None
    notes: str | None = None


class BeamResponse(BaseModel):
    id: str
    project_id: str
    beam_name: str
    beam_type: str
    width_mm: int
    height_mm: int
    length_m: float
    material: str
    concrete_grade: str | None
    position_desc: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── 柱 ──

class ColumnCreate(BaseModel):
    project_id: str
    column_name: str
    column_type: str = "rectangular"
    width_mm: int = 300
    depth_mm: int = 300
    height_m: float = 2.8
    material: str = "reinforced_concrete"
    concrete_grade: str | None = None
    position_desc: str | None = None
    notes: str | None = None


class ColumnResponse(BaseModel):
    id: str
    project_id: str
    column_name: str
    column_type: str
    width_mm: int
    depth_mm: int
    height_m: float
    material: str
    concrete_grade: str | None
    position_desc: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── 楼板 ──

class FloorSlabCreate(BaseModel):
    project_id: str
    slab_name: str
    slab_type: str = "solid"
    thickness_mm: int = 120
    area_m2: float = 0.0
    concrete_grade: str | None = None
    rebar_diameter_mm: int | None = None
    rebar_spacing_mm: int | None = None
    notes: str | None = None


class FloorSlabResponse(BaseModel):
    id: str
    project_id: str
    slab_name: str
    slab_type: str
    thickness_mm: int
    area_m2: float
    concrete_grade: str | None
    rebar_diameter_mm: int | None
    rebar_spacing_mm: int | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── 基础类型 ──

class FoundationTypeCreate(BaseModel):
    project_id: str
    found_type: str
    bearing_capacity_kpa: float = 150.0
    embed_depth_m: float = 1.5
    foundation_width_m: float | None = None
    soil_type: str | None = None
    is_selected: bool = False
    notes: str | None = None


class FoundationTypeResponse(BaseModel):
    id: str
    project_id: str
    found_type: str
    bearing_capacity_kpa: float
    embed_depth_m: float
    foundation_width_m: float | None
    soil_type: str | None
    is_selected: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── 荷载估算 ──

class LoadEstimateCreate(BaseModel):
    project_id: str
    load_type: str
    load_value_kn_m2: float = 0.0
    area_m2: float = 0.0
    floor_level: int | None = None
    usage: str | None = None
    notes: str | None = None


class LoadEstimateResponse(BaseModel):
    id: str
    project_id: str
    load_type: str
    load_value_kn_m2: float
    area_m2: float
    total_load_kn: float
    floor_level: int | None
    usage: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LoadEstimateRequest(BaseModel):
    """荷载估算请求 — 用于自动计算典型荷载值"""

    usage: str = "住宅"
    # usage: 住宅 / 办公 / 商业 / 屋面
    area_m2: float = 0.0
    floor_level: int | None = None
    include_seismic: bool = False


# ── 合规检查 ──

class BayComplianceCreate(BaseModel):
    project_id: str
    room_name: str
    bay_width_m: float = 0.0
    depth_m: float = 0.0
    floor_height_m: float = 2.8
    notes: str | None = None


class BayComplianceResponse(BaseModel):
    id: str
    project_id: str
    room_name: str
    bay_width_m: float
    depth_m: float
    floor_height_m: float
    is_bay_compliant: bool
    is_depth_compliant: bool
    is_height_compliant: bool
    checks: list[dict[str, Any]] | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── 工程量计算 ──

class QuantityCalcCreate(BaseModel):
    project_id: str
    calc_name: str
    calc_type: str
    wall_volume_m3: float = 0.0
    brick_count: int = 0
    mortar_m3: float = 0.0
    concrete_m3: float = 0.0
    rebar_kg: float = 0.0
    formwork_m2: float = 0.0
    notes: str | None = None


class QuantityCalcResponse(BaseModel):
    id: str
    project_id: str
    calc_name: str
    calc_type: str
    wall_volume_m3: float
    brick_count: int
    mortar_m3: float
    concrete_m3: float
    rebar_kg: float
    formwork_m2: float
    total_cost: float
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QuantityLineItemCreate(BaseModel):
    calculation_id: str
    material_type: str
    material_name: str
    quantity: float = 0.0
    unit: str = "m³"
    unit_price: float = 0.0


class QuantityLineItemResponse(BaseModel):
    id: str
    calculation_id: str
    material_type: str
    material_name: str
    quantity: float
    unit: str
    unit_price: float
    total_price: float
    created_at: datetime

    model_config = {"from_attributes": True}


class AutoCalcRequest(BaseModel):
    """自动工程量计算请求"""

    calc_type: str = "brickwork"
    # calc_type: brickwork / concrete / formwork / total
    wall_length_m: float = 0.0
    wall_height_m: float = 2.8
    wall_thickness_m: float = 0.24
    slab_area_m2: float = 0.0
    slab_thickness_m: float = 0.12
    formwork_area_m2: float = 0.0
    concrete_grade: str = "C30"
