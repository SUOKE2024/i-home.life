"""变更管理 Schema — F39"""

from datetime import datetime

from pydantic import BaseModel, Field


class ChangeOrderItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    action: str = Field(default="add")  # add / modify / remove
    target_type: str = Field(default="room")
    target_id: str | None = None
    before_data: str | None = None
    after_data: str | None = None
    quantity: float = Field(default=1.0, gt=0)
    unit_price: float = Field(default=0.0, ge=0)
    amount: float = Field(default=0.0, ge=0)


class ChangeOrderItemResponse(BaseModel):
    id: str
    change_order_id: str
    name: str
    action: str
    target_type: str
    target_id: str | None = None
    before_data: str | None = None
    after_data: str | None = None
    quantity: float
    unit_price: float
    amount: float

    model_config = {"from_attributes": True}


class ChangeOrderCreate(BaseModel):
    project_id: str
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    change_type: str = Field(default="owner_request")
    items: list[ChangeOrderItemCreate] = []


class ChangeOrderReview(BaseModel):
    feasibility: str = Field(default="feasible")  # feasible / infeasible / partial
    feasibility_note: str | None = None
    cost_impact: float = Field(default=0.0)
    schedule_impact_days: int = Field(default=0)
    design_impact: str | None = None


class ChangeOrderResponse(BaseModel):
    id: str
    project_id: str
    title: str
    description: str
    change_type: str
    feasibility: str | None = None
    feasibility_note: str | None = None
    cost_impact: float
    schedule_impact_days: int
    design_impact: str | None = None
    status: str
    submitted_by: str | None = None
    reviewed_by: str | None = None
    approved_by: str | None = None
    submitted_at: datetime
    reviewed_at: datetime | None = None
    approved_at: datetime | None = None
    items: list[ChangeOrderItemResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
