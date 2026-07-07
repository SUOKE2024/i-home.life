from datetime import datetime

from pydantic import BaseModel, Field


class PaymentCreate(BaseModel):
    project_id: str
    settlement_id: str | None = None
    milestone_code: str = Field(default="completion")
    amount: float = Field(ge=0)
    payment_method: str = Field(default="bank_transfer")
    payer: str | None = None
    payee: str | None = None
    evidence_url: str | None = None
    note: str | None = None


class PaymentConfirm(BaseModel):
    transaction_id: str | None = None
    evidence_url: str | None = None
    payer: str | None = None
    payee: str | None = None
    note: str | None = None


class PaymentRefund(BaseModel):
    refund_amount: float = Field(ge=0)
    refund_reason: str | None = None


class PaymentResponse(BaseModel):
    id: str
    project_id: str
    settlement_id: str | None = None
    milestone_code: str
    amount: float
    payment_method: str
    status: str
    transaction_id: str | None = None
    payer: str | None = None
    payee: str | None = None
    evidence_url: str | None = None
    note: str | None = None
    paid_at: datetime | None = None
    refunded_at: datetime | None = None
    refund_amount: float = 0.0
    refund_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
