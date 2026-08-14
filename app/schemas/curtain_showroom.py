"""窗帘智能展厅 Pydantic 模型"""

from pydantic import BaseModel, Field


class CurtainShowroomResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class CurtainSeriesResponse(BaseModel):
    id: str
    showroom_id: str
    name: str
    description: str | None = None
    sort_order: int

    model_config = {"from_attributes": True}


class CurtainProductResponse(BaseModel):
    id: str
    showroom_id: str
    series_id: str
    material_id: str | None = None
    name: str
    sku: str
    brand: str | None = None
    fabric: str
    color: str | None = None
    texture_url: str | None = None
    normal_url: str | None = None
    roughness_url: str | None = None
    image_url: str | None = None
    unit: str
    unit_price: float
    description: str | None = None
    sort_order: int
    is_active: bool

    model_config = {"from_attributes": True}


class CurtainInstallationResponse(BaseModel):
    id: str
    code: str
    name: str
    render_type: str
    description: str | None = None
    sort_order: int

    model_config = {"from_attributes": True}


class CurtainLightingPresetResponse(BaseModel):
    id: str
    code: str
    name: str
    time_of_day: str
    light_color: str
    ambient_intensity: float
    description: str | None = None
    sort_order: int

    model_config = {"from_attributes": True}


class CurtainShowroomAreaResponse(BaseModel):
    id: str
    showroom_id: str
    name: str
    description: str | None = None
    installation_id: str
    default_product_id: str | None = None
    position: dict | None = None
    sort_order: int
    installation: CurtainInstallationResponse | None = None
    default_product: CurtainProductResponse | None = None

    model_config = {"from_attributes": True}


class CurtainShowroomOverviewResponse(BaseModel):
    """展厅总览：店铺 + 系列 + 安装方式 + 灯光预设 + 展示区域"""

    showroom: CurtainShowroomResponse
    series: list[CurtainSeriesResponse] = Field(default_factory=list)
    installations: list[CurtainInstallationResponse] = Field(default_factory=list)
    lighting_presets: list[CurtainLightingPresetResponse] = Field(default_factory=list)
    areas: list[CurtainShowroomAreaResponse] = Field(default_factory=list)
