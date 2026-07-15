"""F19 电器品类库 + F20 电器点位规划 Pydantic 模型"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── 电器品类 ──


class ApplianceCategoryCreate(BaseModel):
    name: str
    code: str
    description: str | None = None


class ApplianceCategoryUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    description: str | None = None


class ApplianceCategoryResponse(BaseModel):
    id: str
    name: str
    code: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── 电器实例 ──


class ApplianceCreate(BaseModel):
    category_id: str
    name: str
    brand: str | None = None
    model: str | None = None
    subcategory: str = Field(
        description="子类型: air_conditioner/refrigerator/washing_machine/"
                    "water_heater/tv/range_hood/cooktop/dishwasher/steam_oven/"
                    "microwave/water_purifier/garbage_disposal/robot_vacuum/"
                    "vacuum_cleaner/dehumidifier/fresh_air_system"
    )
    spec: str | None = None
    power_rating: float | None = None
    energy_label: str | None = None
    price: float = 0.0
    install_requirements: dict[str, Any] | None = None
    dimensions: dict[str, Any] | None = None
    weight_kg: float | None = None
    image_url: str | None = None
    tags: list[str] | None = None
    status: str = "active"


class ApplianceUpdate(BaseModel):
    category_id: str | None = None
    name: str | None = None
    brand: str | None = None
    model: str | None = None
    subcategory: str | None = None
    spec: str | None = None
    power_rating: float | None = None
    energy_label: str | None = None
    price: float | None = None
    install_requirements: dict[str, Any] | None = None
    dimensions: dict[str, Any] | None = None
    weight_kg: float | None = None
    image_url: str | None = None
    tags: list[str] | None = None
    status: str | None = None


class ApplianceResponse(BaseModel):
    id: str
    category_id: str
    name: str
    brand: str | None
    model: str | None
    subcategory: str
    spec: str | None
    power_rating: float | None
    energy_label: str | None
    price: float
    install_requirements: dict[str, Any] | None
    dimensions: dict[str, Any] | None
    weight_kg: float | None
    image_url: str | None
    tags: list[str] | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApplianceSpecResponse(BaseModel):
    """电器详细规格"""
    id: str
    name: str
    brand: str | None
    model: str | None
    subcategory: str
    spec: str | None
    power_rating: float | None
    energy_label: str | None
    price: float
    install_requirements: dict[str, Any] | None
    dimensions: dict[str, Any] | None
    weight_kg: float | None
    tags: list[str] | None

    model_config = {"from_attributes": True}


# ── 电器点位 ──


class AppliancePointCreate(BaseModel):
    project_id: str
    room_id: str | None = None
    appliance_id: str | None = None
    name: str
    location: str | None = None
    outlet_type: str | None = None
    circuit: str | None = None
    water_supply: bool = False
    drainage: bool = False
    gas_supply: bool = False
    wall_hole: str | None = None
    embedding_notes: str | None = None
    power_w: float | None = None
    status: str = "planned"


class AppliancePointUpdate(BaseModel):
    room_id: str | None = None
    appliance_id: str | None = None
    name: str | None = None
    location: str | None = None
    outlet_type: str | None = None
    circuit: str | None = None
    water_supply: bool | None = None
    drainage: bool | None = None
    gas_supply: bool | None = None
    wall_hole: str | None = None
    embedding_notes: str | None = None
    power_w: float | None = None
    status: str | None = None


class AppliancePointResponse(BaseModel):
    id: str
    project_id: str
    room_id: str | None
    appliance_id: str | None
    name: str
    location: str | None
    outlet_type: str | None
    circuit: str | None
    water_supply: bool
    drainage: bool
    gas_supply: bool
    wall_hole: str | None
    embedding_notes: str | None
    power_w: float | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── 负载计算 ──


class ApplianceLoadCalcResponse(BaseModel):
    id: str
    project_id: str
    circuit_name: str
    total_power: float
    voltage: float
    max_current: float
    wire_gauge: str | None
    breaker_rating: str | None
    is_compliant: bool
    warning_msg: str | None
    appliance_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LoadCalcResult(BaseModel):
    """全屋负载计算结果"""
    project_id: str
    total_power: float = Field(description="全屋总功率 W")
    total_current: float = Field(description="全屋总电流 A")
    circuits: list[dict[str, Any]] = Field(default_factory=list, description="各回路详情")
    main_breaker_advice: str | None = Field(default=None, description="总闸建议")
    is_overall_compliant: bool = Field(default=True, description="整体是否合规")
    warnings: list[str] = Field(default_factory=list, description="整体警告")


# ── 嵌入式电器匹配 ──


class CabinetMatchRequest(BaseModel):
    appliance_id: str
    cabinet_width: float = Field(description="柜体内部宽度 mm")
    cabinet_depth: float = Field(description="柜体内部深度 mm")
    cabinet_height: float = Field(description="柜体内部高度 mm")


class CabinetMatchResult(BaseModel):
    """嵌入式电器尺寸匹配结果"""
    appliance_id: str
    appliance_name: str
    appliance_dimensions: dict[str, Any] | None = Field(default=None, description="电器尺寸")
    cabinet_dimensions: dict[str, float] = Field(description="柜体内部尺寸")
    fits: bool = Field(description="是否匹配")
    clearance: dict[str, Any] | None = Field(default=None, description="间隙详情")
    issues: list[str] = Field(default_factory=list, description="匹配问题")
    suggestions: list[str] = Field(default_factory=list, description="调整建议")


# ── 预埋规划 ──


class EmbeddingPlanResult(BaseModel):
    """预埋规划结果"""
    project_id: str
    items: list[dict[str, Any]] = Field(default_factory=list, description="预埋项清单")
    summary: str | None = Field(default=None, description="预埋总结")


# ── 房间推荐 ──


class RoomApplianceRecommendResult(BaseModel):
    """房间电器推荐结果"""
    room_id: str
    room_type: str
    room_name: str | None
    recommended: list[dict[str, Any]] = Field(default_factory=list, description="推荐电器清单")
    total_power: float = Field(default=0.0, description="预估总功率 W")
    total_price: float = Field(default=0.0, description="预估总价")
    notes: list[str] = Field(default_factory=list, description="注意事项")
