from datetime import datetime

from pydantic import BaseModel, Field


class BudgetLineCreate(BaseModel):
    category: str
    name: str = Field(min_length=1, max_length=200)
    estimated_amount: float = Field(default=0.0, ge=0)
    unit: str = Field(default="项")
    quantity: float = Field(default=1.0, gt=0)
    unit_price: float = Field(default=0.0, ge=0)
    note: str | None = None


class BudgetLineResponse(BaseModel):
    id: str
    budget_id: str
    category: str
    name: str
    estimated_amount: float
    actual_amount: float
    unit: str
    quantity: float
    unit_price: float
    note: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BudgetCreate(BaseModel):
    project_id: str
    lines: list[BudgetLineCreate] = []


class BudgetResponse(BaseModel):
    id: str
    project_id: str
    total_estimated: float
    total_actual: float
    status: str
    lines: list[BudgetLineResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
