"""F26 家具品类库 Pydantic 模型"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FurnitureCatalogItemCreate(BaseModel):
    category: str = Field(description="品类: living_room/dining_room/bedroom/study/kitchen/bathroom/outdoor")
    subcategory: str = Field(
        description="子品类: sofa/bed/dining_table/chair/coffee_table/"
                    "wardrobe/bookshelf/desk/tv_cabinet/shoe_cabinet/nightstand"
    )
    name: str
    brand: str | None = None
    model: str | None = None
    width: float | None = None
    depth: float | None = None
    height: float | None = None
    weight_kg: float | None = None
    material: str | None = None
    color: str | None = None
    style: str = "modern"
    price: float = 0.0
    sale_price: float | None = None
    image_url: str | None = None
    model_3d_url: str | None = None
    ar_preview_supported: bool = False
    stock_count: int = 0
    rating: float = 0.0
    sales_count: int = 0
    tags: list[str] | None = None
    specs: dict[str, Any] | None = None
    status: str = "active"


class FurnitureCatalogItemUpdate(BaseModel):
    name: str | None = None
    brand: str | None = None
    model: str | None = None
    width: float | None = None
    depth: float | None = None
    height: float | None = None
    weight_kg: float | None = None
    material: str | None = None
    color: str | None = None
    style: str | None = None
    price: float | None = None
    sale_price: float | None = None
    image_url: str | None = None
    model_3d_url: str | None = None
    ar_preview_supported: bool | None = None
    stock_count: int | None = None
    rating: float | None = None
    sales_count: int | None = None
    tags: list[str] | None = None
    specs: dict[str, Any] | None = None
    status: str | None = None


class FurnitureCatalogItemResponse(BaseModel):
    id: str
    category: str
    subcategory: str
    name: str
    brand: str | None
    model: str | None
    width: float | None
    depth: float | None
    height: float | None
    weight_kg: float | None
    material: str | None
    color: str | None
    style: str
    price: float
    sale_price: float | None
    image_url: str | None
    model_3d_url: str | None
    ar_preview_supported: bool
    stock_count: int
    rating: float
    sales_count: int
    view_count: int
    tags: list[str] | None
    specs: dict[str, Any] | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ARPlacementResult(BaseModel):
    """AR 摆放预览计算结果"""

    item_id: str
    item_name: str
    item_dimensions: dict[str, float | None] = Field(description="家具尺寸 width/depth/height(mm)")
    scale: float = Field(default=1.0, description="缩放比例,1:1 比例下为 1.0")
    recommended_position: dict[str, float] = Field(description="推荐位置坐标 x/y/z(mm)")
    room_dimensions: dict[str, float] = Field(description="房间尺寸 width/length/height(mm)")
    fit_warning: str | None = Field(default=None, description="摆放适配警告(尺寸过大等)")


class RoomRecommendResult(BaseModel):
    """按房间推荐家具组合结果"""

    room_type: str
    room_area: float
    style: str
    budget: float
    combos: list[dict[str, Any]] = Field(default_factory=list, description="推荐家具组合")
    total_estimate: float = Field(default=0.0, description="组合总价估算")
    within_budget: bool = Field(default=True, description="是否在预算内")
