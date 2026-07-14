from datetime import datetime

from pydantic import BaseModel, Field


class PaymentCreate(BaseModel):
    project_id: str
    settlement_id: str | None = None
    milestone_code: str = Field(default="completion")
    stage_code: str | None = None  # deposit / progress / final / warranty
    stage_order: int = Field(default=0, ge=0)
    due_at: datetime | None = None
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


class PaymentFail(BaseModel):
    reason: str | None = None
    note: str | None = None


class PaymentDispute(BaseModel):
    """发起支付争议"""
    reason: str


class PaymentInvoiceRequest(BaseModel):
    """F15 电子发票开具请求"""
    invoice_url: str | None = None  # 发票文件 URL（PDF/图片）
    payer: str | None = None  # 发票抬头（付款方）
    payee: str | None = None  # 销方名称（收款方）
    note: str | None = None


class PaymentResponse(BaseModel):
    id: str
    project_id: str
    settlement_id: str | None = None
    milestone_code: str
    stage_code: str | None = None
    stage_order: int = 0
    due_at: datetime | None = None
    amount: float
    payment_method: str
    status: str
    transaction_id: str | None = None
    payer: str | None = None
    payee: str | None = None
    evidence_url: str | None = None
    note: str | None = None
    invoice_no: str | None = None
    invoice_url: str | None = None
    invoiced_at: datetime | None = None
    paid_at: datetime | None = None
    refunded_at: datetime | None = None
    refund_amount: float = 0.0
    refund_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaymentScheduleNode(BaseModel):
    """F15 分阶段支付节点"""
    stage_code: str
    stage_order: int
    milestone_code: str
    total_amount: float
    paid_amount: float
    pending_amount: float
    refunded_amount: float
    failed_amount: float
    payment_count: int
    due_at: datetime | None = None
    status: str  # pending / partial / paid / overdue


class FinalSettlementReport(BaseModel):
    """F15 最终结算报告"""
    project_id: str
    total_contract_amount: float
    total_paid: float
    total_pending: float
    total_refunded: float
    total_failed: float
    total_disputed: float = 0.0  # v1.0.1 新增争议统计
    paid_ratio: float  # 已付比例 0-1
    invoice_count: int
    invoiced_amount: float
    milestone_summary: list[dict]
    payment_count: int
    generated_at: datetime
