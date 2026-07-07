"""F24/F25 软装搭配 + 收纳系统 Pydantic 模型"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── 方案 ──


class SoftFurnishingSchemeCreate(BaseModel):
    project_id: str
    room_name: str
    style: str = "modern"
    # style: modern / 北欧 / 新中式 / 美式 / 法式 / 工业 / 日式
    color_scheme: dict[str, Any] | None = None
    budget_total: float = 0.0
    budget_used: float = 0.0
    status: str = "draft"
    notes: str | None = None


class SoftFurnishingSchemeResponse(BaseModel):
    id: str
    project_id: str
    room_name: str
    style: str
    color_scheme: dict[str, Any] | None
    budget_total: float
    budget_used: float
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── 单品 ──


class SoftFurnishingItemCreate(BaseModel):
    item_type: str
    brand: str | None = None
    model: str | None = None
    name: str
    width: float | None = None
    depth: float | None = None
    height: float | None = None
    color: str | None = None
    material: str | None = None
    price: float = 0.0
    quantity: int = 1
    image_url: str | None = None
    position_x: float | None = None
    position_y: float | None = None
    position_z: float | None = None
    status: str = "planned"


class SoftFurnishingItemResponse(BaseModel):
    id: str
    scheme_id: str
    item_type: str
    brand: str | None
    model: str | None
    name: str
    width: float | None
    depth: float | None
    height: float | None
    color: str | None
    material: str | None
    price: float
    quantity: int
    image_url: str | None
    position_x: float | None
    position_y: float | None
    position_z: float | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SoftFurnishingItemStatusUpdate(BaseModel):
    status: str


# ── 收纳系统 ──


class StorageSystemCreate(BaseModel):
    room_name: str
    storage_type: str
    total_capacity_l: float = 0.0
    compartment_count: int = 0
    adjustable_shelves: bool = True
    smart_features: dict[str, Any] | None = None
    notes: str | None = None


class StorageSystemResponse(BaseModel):
    id: str
    scheme_id: str
    room_name: str
    storage_type: str
    total_capacity_l: float
    compartment_count: int
    adjustable_shelves: bool
    smart_features: dict[str, Any] | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── 计算结果 ──


class ColorHarmonyResult(BaseModel):
    """配色和谐度结果 (60-30-10 法则)"""

    score: float = Field(description="和谐度评分 0-100")
    primary_pct: float = Field(description="主色占比 %")
    secondary_pct: float = Field(description="辅色占比 %")
    accent_pct: float = Field(description="点缀色占比 %")
    suggestion: str | None = Field(default=None, description="调整建议")


class BudgetUsageResult(BaseModel):
    """预算使用情况"""

    budget_total: float
    budget_used: float
    budget_remaining: float
    usage_pct: float = Field(description="使用率 %")
    status: str = Field(description="预算状态: normal / warning / over")


class StorageRecommendResult(BaseModel):
    """收纳方案推荐"""

    room_name: str
    room_area: float
    family_size: int
    recommended_capacity_l: float = Field(description="推荐总容量(升)")
    suggestions: list[dict[str, Any]] = Field(default_factory=list, description="建议收纳清单")


class StorageCapacityResult(BaseModel):
    """收纳容量计算结果"""

    total_capacity_l: float
    utilization_rate: float = Field(description="利用率,默认 0.7")
    effective_capacity_l: float = Field(description="有效容量(升)")
