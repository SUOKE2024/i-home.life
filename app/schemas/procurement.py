from datetime import datetime

from pydantic import BaseModel, Field


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    contact_name: str | None = None
    phone: str | None = None
    address: str | None = None
    category: str = Field(min_length=1, max_length=50)
    rating: float = Field(default=3.0, ge=0, le=5)


class SupplierResponse(BaseModel):
    id: str
    name: str
    contact_name: str | None = None
    phone: str | None = None
    address: str | None = None
    category: str
    rating: float
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class QuotationCreate(BaseModel):
    supplier_id: str
    material_id: str
    project_id: str
    quantity: float = Field(default=1.0, gt=0)
    unit_price: float = Field(default=0.0, ge=0)
    delivery_days: int = Field(default=7, ge=1)


class QuotationResponse(BaseModel):
    id: str
    supplier_id: str
    material_id: str
    project_id: str
    quantity: float
    unit_price: float
    total_price: float
    delivery_days: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderLineCreate(BaseModel):
    material_id: str
    quantity: float = Field(default=1.0, gt=0)
    unit_price: float = Field(default=0.0, ge=0)
    note: str | None = None


class OrderCreate(BaseModel):
    project_id: str
    supplier_id: str
    expected_delivery: datetime | None = None
    note: str | None = None
    lines: list[OrderLineCreate] = []


class OrderUpdate(BaseModel):
    expected_delivery: datetime | None = None
    note: str | None = None


class OrderStatusUpdate(BaseModel):
    status: str = Field(min_length=1, max_length=20)


class OrderLineResponse(BaseModel):
    id: str
    material_id: str
    quantity: float
    unit_price: float
    total_price: float
    note: str | None = None

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: str
    project_id: str
    supplier_id: str
    total_amount: float
    status: str
    expected_delivery: datetime | None = None
    note: str | None = None
    lines: list[OrderLineResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
