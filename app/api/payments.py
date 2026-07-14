"""支付管理路由 — F15 发起支付 / 确认 / 退款 / 标记失败 / 里程碑聚合
F15 扩展：电子发票 / 分阶段支付节点 / 最终结算报告

v1.0.1: 全部端点补充 verify_project_access 项目归属校验，修复越权漏洞
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.schemas.payment import (
    FinalSettlementReport,
    PaymentConfirm,
    PaymentCreate,
    PaymentFail,
    PaymentDispute,
    PaymentInvoiceRequest,
    PaymentRefund,
    PaymentResponse,
    PaymentScheduleNode,
)
from app.auth import get_current_user
from app.services import payment_service
from app.services.payment_service import PaymentStateError
from app.ws import ws_manager

router = APIRouter(prefix="/payments", tags=["支付管理"])


def _handle_state_error(e: PaymentStateError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(e),
    )


def _verify_owner(project: Project | None, current_user: User) -> None:
    """校验项目归属（统一定义，避免内联重复）"""
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if current_user.role != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")


@router.get("/project/{project_id}", response_model=list[PaymentResponse])
async def list_project_payments(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    result = await db.execute(select(Project).where(Project.id == project_id))
    _verify_owner(result.scalar_one_or_none(), current_user)
    rows = await payment_service.get_project_payments(db, project_id)
    return [PaymentResponse.model_validate(r) for r in rows]


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    data: PaymentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    result = await db.execute(select(Project).where(Project.id == data.project_id))
    _verify_owner(result.scalar_one_or_none(), current_user)
    payment = await payment_service.create_payment(db, data.model_dump())
    resp = PaymentResponse.model_validate(payment)
    await ws_manager.broadcast_to_project(data.project_id, "payment.created", resp.model_dump())
    return resp


@router.get("/milestones/{project_id}")
async def milestone_summary(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    result = await db.execute(select(Project).where(Project.id == project_id))
    _verify_owner(result.scalar_one_or_none(), current_user)
    return await payment_service.get_milestone_summary(db, project_id)


@router.get("/schedule/{project_id}", response_model=list[PaymentScheduleNode])
async def payment_schedule(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """F15 分阶段支付节点：返回每个支付阶段的进度"""
    from sqlalchemy import select
    result = await db.execute(select(Project).where(Project.id == project_id))
    _verify_owner(result.scalar_one_or_none(), current_user)
    return await payment_service.get_payment_schedule(db, project_id)


@router.get("/final-settlement/{project_id}", response_model=FinalSettlementReport)
async def final_settlement_report(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """F15 最终结算报告：聚合支付 / 发票 / 结算单"""
    from sqlalchemy import select
    result = await db.execute(select(Project).where(Project.id == project_id))
    _verify_owner(result.scalar_one_or_none(), current_user)
    return await payment_service.get_final_settlement_report(db, project_id)


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    payment = await payment_service.get_payment(db, payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="支付记录不存在")
    result = await db.execute(select(Project).where(Project.id == payment.project_id))
    _verify_owner(result.scalar_one_or_none(), current_user)
    return PaymentResponse.model_validate(payment)


@router.post("/{payment_id}/confirm", response_model=PaymentResponse)
async def confirm_payment(
    payment_id: str,
    data: PaymentConfirm,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    # 先获取 payment 以校验项目归属
    payment = await payment_service.get_payment(db, payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="支付记录不存在")
    result = await db.execute(select(Project).where(Project.id == payment.project_id))
    _verify_owner(result.scalar_one_or_none(), current_user)
    try:
        payment = await payment_service.confirm_payment(db, payment_id, data.model_dump())
    except PaymentStateError as e:
        raise _handle_state_error(e) from e
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
    from sqlalchemy import select
    payment = await payment_service.get_payment(db, payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="支付记录不存在")
    result = await db.execute(select(Project).where(Project.id == payment.project_id))
    _verify_owner(result.scalar_one_or_none(), current_user)
    try:
        payment = await payment_service.refund_payment(db, payment_id, data.model_dump())
    except PaymentStateError as e:
        raise _handle_state_error(e) from e
    resp = PaymentResponse.model_validate(payment)
    await ws_manager.broadcast_to_project(payment.project_id, "payment.refunded", resp.model_dump())
    return resp


@router.post("/{payment_id}/fail", response_model=PaymentResponse)
async def fail_payment(
    payment_id: str,
    data: PaymentFail,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    payment = await payment_service.get_payment(db, payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="支付记录不存在")
    result = await db.execute(select(Project).where(Project.id == payment.project_id))
    _verify_owner(result.scalar_one_or_none(), current_user)
    try:
        payment = await payment_service.mark_failed(db, payment_id, data.reason or data.note or "手动标记失败")
    except PaymentStateError as e:
        raise _handle_state_error(e) from e
    resp = PaymentResponse.model_validate(payment)
    await ws_manager.broadcast_to_project(payment.project_id, "payment.failed", resp.model_dump())
    return resp


@router.post("/{payment_id}/dispute", response_model=PaymentResponse)
async def dispute_payment(
    payment_id: str,
    data: PaymentDispute,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记支付争议：pending → disputed（资金类业务不可逆保护）"""
    from sqlalchemy import select
    payment = await payment_service.get_payment(db, payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="支付记录不存在")
    result = await db.execute(select(Project).where(Project.id == payment.project_id))
    _verify_owner(result.scalar_one_or_none(), current_user)
    try:
        payment = await payment_service.mark_disputed(db, payment_id, data.reason)
    except PaymentStateError as e:
        raise _handle_state_error(e) from e
    resp = PaymentResponse.model_validate(payment)
    await ws_manager.broadcast_to_project(payment.project_id, "payment.disputed", resp.model_dump())
    return resp


@router.post("/{payment_id}/invoice", response_model=PaymentResponse)
async def generate_invoice(
    payment_id: str,
    data: PaymentInvoiceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """F15 电子发票开具：仅已支付记录可开票"""
    from sqlalchemy import select
    payment = await payment_service.get_payment(db, payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="支付记录不存在")
    result = await db.execute(select(Project).where(Project.id == payment.project_id))
    _verify_owner(result.scalar_one_or_none(), current_user)
    try:
        payment = await payment_service.generate_invoice(db, payment_id, data.model_dump())
    except PaymentStateError as e:
        raise _handle_state_error(e) from e
    resp = PaymentResponse.model_validate(payment)
    await ws_manager.broadcast_to_project(payment.project_id, "payment.invoiced", resp.model_dump())
    return resp
