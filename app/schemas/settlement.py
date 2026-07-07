from datetime import datetime

from pydantic import BaseModel, Field


class SettlementLineCreate(BaseModel):
    category: str
    name: str = Field(min_length=1, max_length=200)
    contract_amount: float = Field(default=0.0, ge=0)
    change_amount: float = Field(default=0.0)
    note: str | None = None


class SettlementLineResponse(BaseModel):
    id: str
    category: str
    name: str
    contract_amount: float
    change_amount: float
    actual_amount: float
    status: str
    note: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SettlementCreate(BaseModel):
    project_id: str
    milestone: str = Field(default="completion")
    lines: list[SettlementLineCreate] = []


class SettlementResponse(BaseModel):
    id: str
    project_id: str
    milestone: str
    contract_amount: float
    actual_amount: float
    payable_amount: float
    status: str
    lines: list[SettlementLineResponse] = []
    settled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SettlementConfirm(BaseModel):
    milestone: str | None = None
