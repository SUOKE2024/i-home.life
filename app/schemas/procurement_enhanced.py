"""F33/F34 增强 Pydantic 模型"""

from datetime import datetime
from pydantic import BaseModel, Field


# ── F33 比价报告 ──

class ComparisonCreateRequest(BaseModel):
    """从 BOM 生成比价报告"""
    project_id: str
    bom_id: str | None = None


class QuotationSummary(BaseModel):
    supplier_id: str
    supplier_name: str
    price: float = Field(ge=0)
    delivery_days: int = Field(ge=0)
    in_stock: bool = True
    score: float = Field(default=0.0, ge=0, le=100)


class PriceComparisonItemResponse(BaseModel):
    id: str
    comparison_id: str
    bom_item_id: str | None = None
    material_name: str
    spec: str | None = None
    quantity: float
    unit: str
    quotations: list[dict] | None = None
    recommended_supplier_id: str | None = None
    recommended_price: float
    savings_per_item: float
    created_at: datetime

    model_config = {"from_attributes": True}


class PriceComparisonResponse(BaseModel):
    id: str
    project_id: str
    bom_id: str | None = None
    report_no: str
    item_count: int
    supplier_count: int
    total_quotes: int
    recommended_supplier_id: str | None = None
    total_savings: float
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PriceComparisonDetailResponse(PriceComparisonResponse):
    items: list[PriceComparisonItemResponse] = []


class AiMatchRequest(BaseModel):
    """AI 供应商匹配"""
    bom_item_id: str
    location: str | None = None


class AiMatchResult(BaseModel):
    bom_item_id: str
    material_name: str
    matched_suppliers: list[dict] = []
    recommended_supplier_id: str | None = None
    reason: str | None = None


# ── F34 担保支付 ──

class EscrowCreateRequest(BaseModel):
    order_id: str


class EscrowRefundRequest(BaseModel):
    reason: str


class EscrowPaymentResponse(BaseModel):
    id: str
    order_id: str
    project_id: str
    escrow_no: str
    total_amount: float
    buyer_paid: bool
    buyer_paid_at: datetime | None = None
    supplier_received: bool
    supplier_received_at: datetime | None = None
    status: str
    escrow_fee: float
    dispute_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── F34 物流追踪 ──

class LogisticsCreateRequest(BaseModel):
    order_id: str
    carrier: str
    ship_from: str | None = None
    ship_to: str | None = None


class LogisticsUpdateRequest(BaseModel):
    status: str | None = None
    location: str | None = None
    description: str | None = None


class LogisticsTrackingResponse(BaseModel):
    id: str
    order_id: str
    project_id: str
    tracking_no: str
    carrier: str
    ship_from: str | None = None
    ship_to: str | None = None
    estimated_arrival: datetime | None = None
    actual_arrival: datetime | None = None
    status: str
    tracking_history: list[dict] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── F34 样品索要 ──

class SampleCreateRequest(BaseModel):
    project_id: str
    supplier_id: str
    material_id: str | None = None
    sample_type: str = "实物"


class SampleUpdateRequest(BaseModel):
    status: str
    notes: str | None = None


class SampleRequestResponse(BaseModel):
    id: str
    project_id: str
    supplier_id: str
    material_id: str | None = None
    sample_type: str
    status: str
    shipped_at: datetime | None = None
    received_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
