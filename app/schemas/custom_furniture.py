"""F27 定制家具设计器 Pydantic 模型"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── 设计 ──


class CustomFurnitureDesignCreate(BaseModel):
    project_id: str
    room_name: str
    furniture_type: str
    total_width: float = 0.0
    total_height: float = 0.0
    total_depth: float = 0.0
    panel_material: str = "颗粒板"
    panel_thickness: float = 18.0
    edge_banding: str = "PVC"
    hardware_brand: str = "海蒂诗"
    color: str | None = None
    style: str = "modern"
    total_price: float = 0.0
    status: str = "draft"
    notes: str | None = None


class CustomFurnitureDesignResponse(BaseModel):
    id: str
    project_id: str
    room_name: str
    furniture_type: str
    total_width: float
    total_height: float
    total_depth: float
    panel_material: str
    panel_thickness: float
    edge_banding: str
    hardware_brand: str
    color: str | None
    style: str
    total_price: float
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── 模块 ──


class FurnitureModuleCreate(BaseModel):
    module_type: str
    position_index: int = 0
    width: float = 0.0
    height: float = 0.0
    depth: float = 0.0
    quantity: int = 1
    material: str | None = None
    color: str | None = None
    hardware_specs: dict[str, Any] | None = None
    price: float = 0.0


class FurnitureModuleResponse(BaseModel):
    id: str
    design_id: str
    module_type: str
    position_index: int
    width: float
    height: float
    depth: float
    quantity: int
    material: str | None
    color: str | None
    hardware_specs: dict[str, Any] | None
    price: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── BOM ──


class FurnitureBOMResponse(BaseModel):
    id: str
    design_id: str
    item_name: str
    item_type: str
    spec: str | None
    material: str | None
    quantity: float
    unit: str
    unit_price: float
    total_price: float
    supplier: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── 计算结果 ──


class PanelComputeResult(BaseModel):
    """板材计算结果"""

    total_panel_area_m2: float = Field(description="总展开面积(㎡)")
    panel_sheets: float = Field(description="板材用量(张)")
    hardware_list: list[dict[str, Any]] = Field(default_factory=list, description="五金件清单")


class PriceEstimateResult(BaseModel):
    """价格估算结果"""

    panel_cost: float = Field(description="板材费用")
    hardware_cost: float = Field(description="五金费用")
    door_cost: float = Field(description="门板费用")
    process_cost: float = Field(description="加工费")
    total_price: float = Field(description="总价")


class ValidationResult(BaseModel):
    """规格校验结果"""

    valid: bool
    issues: list[dict[str, Any]] = Field(default_factory=list)
