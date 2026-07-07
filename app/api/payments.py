"""支付管理路由 — F15 发起支付 / 确认 / 退款 / 里程碑聚合"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.payment import (
    PaymentConfirm,
    PaymentCreate,
    PaymentRefund,
    PaymentResponse,
)
from app.auth import get_current_user
from app.services import payment_service
from app.ws import ws_manager

router = APIRouter(prefix="/payments", tags=["支付管理"])


@router.get("/project/{project_id}", response_model=list[PaymentResponse])
async def list_project_payments(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await payment_service.get_project_payments(db, project_id)
    return [PaymentResponse.model_validate(r) for r in rows]


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    data: PaymentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    payment = await payment_service.create_payment(db, data.model_dump())
    resp = PaymentResponse.model_validate(payment)
    await ws_manager.broadcast_to_project(data.project_id, "payment.created", resp.model_dump())
    return resp


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    payment = await payment_service.get_payment(db, payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="支付记录不存在")
    return PaymentResponse.model_validate(payment)


@router.post("/{payment_id}/confirm", response_model=PaymentResponse)
async def confirm_payment(
    payment_id: str,
    data: PaymentConfirm,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    payment = await payment_service.confirm_payment(db, payment_id, data.model_dump())
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="支付记录不存在")
    resp = PaymentResponse.model_validate(payment)
    await ws_manager.broadcast_to_project(payment.project_id, "payment.confirmed", resp.model_dump())
    return resp


@router.post("/{payment_id}/refund", response_model=PaymentResponse)
async def refund_payment(
    payment_id: str,
    data: PaymentRefund,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    payment = await payment_service.refund_payment(db, payment_id, data.model_dump())
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="支付记录不存在")
    if payment.status != "refunded":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"当前状态 {payment.status} 不支持退款")
    resp = PaymentResponse.model_validate(payment)
    await ws_manager.broadcast_to_project(payment.project_id, "payment.refunded", resp.model_dump())
    return resp


@router.get("/milestones/{project_id}")
async def milestone_summary(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await payment_service.get_milestone_summary(db, project_id)
