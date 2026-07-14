"""积分系统 Schema"""
from datetime import datetime
from pydantic import BaseModel, Field


class PointsAccountResponse(BaseModel):
    id: str
    user_id: str
    account_type: str
    balance: int
    total_earned: int
    total_spent: int
    level: str
    year_earned: int
    year_spent: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PointsTransactionResponse(BaseModel):
    id: str
    user_id: str
    amount: int
    transaction_type: str
    source: str
    description: str
    balance_after: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PointsRuleResponse(BaseModel):
    id: str
    action: str
    role: str
    points: int
    limit_daily: int | None = None
    limit_weekly: int | None = None
    description: str
    is_active: bool

    model_config = {"from_attributes": True}


class PointsMallItemResponse(BaseModel):
    id: str
    name: str
    category: str
    description: str | None = None
    image_url: str | None = None
    points_required: int
    stock: int
    discount_type: str | None = None
    discount_value: float | None = None
    discount_max: float | None = None
    validity_days: int
    is_active: bool
    sort_order: int

    model_config = {"from_attributes": True}


class RedemptionRequest(BaseModel):
    item_id: str


class RedemptionResponse(BaseModel):
    id: str
    user_id: str
    item_id: str
    item_name: str
    points_spent: int
    discount_code: str | None = None
    discount_type: str | None = None
    discount_value: float | None = None
    discount_max: float | None = None
    expires_at: datetime | None = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RankingResponse(BaseModel):
    user_id: str
    user_name: str | None = None
    role: str
    year_earned: int
    rank: int
    level: str | None = None

    model_config = {"from_attributes": True}


class PointsEarnRequest(BaseModel):
    """积分变动请求（内部调用）"""
    user_id: str
    source: str
    amount: int | None = None  # 不传则从规则读取
    reference_id: str | None = None
    description: str | None = None
