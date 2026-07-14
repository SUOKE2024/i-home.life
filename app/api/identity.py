"""实名认证 API — 提交认证、查询状态、管理员审核"""
import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.auth import get_current_user
from app.rbac import allow_admin
from app.services import identity_service
from app.schemas.identity import (
    IdentitySubmitRequest,
    IdentityReviewRequest,
    IdentityVerificationResponse,
    IdentityStatusResponse,
)

router = APIRouter(prefix="/identity", tags=["身份认证"])


@router.post("/submit", response_model=IdentityVerificationResponse)
async def submit_verification(
    data: IdentitySubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """提交实名认证申请"""
    verification = await identity_service.submit_verification(
        db=db,
        user=current_user,
        real_name=data.real_name,
        id_card=data.id_card,
        id_card_front=data.id_card_front,
        id_card_back=data.id_card_back,
        selfie_with_id=data.selfie_with_id,
        role_attributes=data.role_attributes,
    )

    resp = IdentityVerificationResponse.model_validate(verification)
    # 解密身份证号显示（前端展示时脱敏）
    return resp


@router.get("/status", response_model=IdentityStatusResponse)
async def get_verification_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询当前用户的认证状态"""
    status_data = await identity_service.get_verification_status(db, current_user.id)
    return IdentityStatusResponse(**status_data)


@router.get("/pending", response_model=list[IdentityVerificationResponse])
async def list_pending_verifications(
    current_user: User = Depends(allow_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理员查看待审核列表"""
    verifications = await identity_service.list_pending_verifications(db)
    return [IdentityVerificationResponse.model_validate(v) for v in verifications]


@router.post("/{verification_id}/review", response_model=IdentityVerificationResponse)
async def review_verification(
    verification_id: str,
    data: IdentityReviewRequest,
    current_user: User = Depends(allow_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理员审核通过/拒绝认证"""
    verification = await identity_service.review_verification(
        db=db,
        verification_id=verification_id,
        status=data.status,
        reviewer_id=current_user.id,
        review_note=data.review_note,
    )
    if not verification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="认证记录不存在")

    return IdentityVerificationResponse.model_validate(verification)
