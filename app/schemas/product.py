"""产品/服务 Schema"""
from datetime import datetime
from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    """创建产品 — 支持 AI 辅助生成"""
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(default="other")
    description: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    unit: str = Field(default="个")
    images: list[str] | None = None
    cover_image: str | None = None
    tags: list[str] | None = None
    specs: dict | None = None
    stock_status: str = Field(default="in_stock")
    ai_assisted: bool = Field(default=False)  # 是否请求 AI 辅助


class ProductUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    description: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    unit: str | None = None
    images: list[str] | None = None
    cover_image: str | None = None
    tags: list[str] | None = None
    specs: dict | None = None
    stock_status: str | None = None
    status: str | None = None


class ProductResponse(BaseModel):
    id: str
    user_id: str
    supplier_id: str
    name: str
    category: str
    description: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    unit: str
    images: list[str] | None = None
    cover_image: str | None = None
    tags: list[str] | None = None
    specs: dict | None = None
    stock_status: str
    status: str
    ai_generated: bool = False
    ai_description: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductCardData(BaseModel):
    """聊天消息中的产品卡片数据"""
    product_id: str
    name: str
    category: str
    description: str | None = None
    price_range: str  # 如 "50元/㎡起"
    cover_image: str | None = None
    tags: list[str] | None = None
    action_buttons: list[dict] | None = None  # [{"label": "确认发布", "type": "publish"}, ...]
