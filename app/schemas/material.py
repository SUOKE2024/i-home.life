from datetime import datetime

from pydantic import BaseModel, Field


class MaterialCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=50)
    description: str | None = None


class MaterialCategoryResponse(BaseModel):
    id: str
    name: str
    code: str
    description: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MaterialCreate(BaseModel):
    category_id: str
    name: str = Field(min_length=1, max_length=200)
    sku: str = Field(min_length=1, max_length=100)
    unit: str = Field(default="piece")
    unit_price: float = Field(default=0.0, ge=0)
    brand: str | None = None
    spec: str | None = None
    image_url: str | None = None
    description: str | None = None


class MaterialResponse(BaseModel):
    id: str
    category_id: str
    name: str
    sku: str
    unit: str
    unit_price: float
    brand: str | None = None
    spec: str | None = None
    image_url: str | None = None
    description: str | None = None
    is_active: bool
    category: MaterialCategoryResponse | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BOMItemCreate(BaseModel):
    project_id: str
    material_id: str
    room_id: str | None = None
    quantity: float = Field(default=1.0, gt=0)
    unit_price: float = Field(default=0.0, ge=0)
    note: str | None = None


class BOMItemResponse(BaseModel):
    id: str
    project_id: str
    material_id: str
    room_id: str | None = None
    quantity: float
    unit_price: float
    total_price: float
    note: str | None = None
    status: str
    material: MaterialResponse | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
