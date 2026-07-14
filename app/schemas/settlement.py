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
    is_anomaly: bool = False
    anomaly_type: str | None = None
    anomaly_severity: str | None = None
    anomaly_detail: str | None = None
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
    anomaly_count: int = 0
    critical_anomaly_count: int = 0
    suggested_deduction: float = 0.0
    review_required: bool = False
    review_reason: str | None = None
    reviewed_by: str | None = None
    lines: list[SettlementLineResponse] = []
    settled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SettlementConfirm(BaseModel):
    milestone: str | None = None


class ReviewRequest(BaseModel):
    """F14 人工复核请求"""
    reason: str = Field(min_length=1, max_length=500)
    reviewer_id: str | None = None


class AnomalyAttachRequest(BaseModel):
    """F14 异常标记附加请求 — 把 Agent 检测出的异常关联到结算行"""
    anomalies: list[dict] = Field(default_factory=list)
    auto_mark_lines: bool = True
