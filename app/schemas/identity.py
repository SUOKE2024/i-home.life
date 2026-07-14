"""实名认证 Schema"""
from datetime import datetime
from pydantic import BaseModel, Field


class IdentitySubmitRequest(BaseModel):
    """提交实名认证请求"""
    real_name: str = Field(min_length=1, max_length=100)
    id_card: str = Field(min_length=15, max_length=18)
    id_card_front: str | None = None
    id_card_back: str | None = None
    selfie_with_id: str | None = None
    role_attributes: dict | None = None  # 角色特定属性


class IdentityReviewRequest(BaseModel):
    """审核认证请求"""
    status: str = Field(pattern=r"^(approved|rejected)$")
    review_note: str | None = None


class IdentityVerificationResponse(BaseModel):
    id: str
    user_id: str
    role: str
    real_name: str
    id_card: str
    # 支持第三方核验
    third_party_verified: bool = False
    third_party_provider: str | None = None
    status: str
    role_attributes: dict | None = None
    review_note: str | None = None
    verified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IdentityStatusResponse(BaseModel):
    """认证状态"""
    is_verified: bool
    status: str  # pending / approved / rejected / not_submitted
    role: str | None = None
    submitted_at: datetime | None = None
