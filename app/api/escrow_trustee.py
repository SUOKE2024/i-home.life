"""F43 资金托管深化 API 端点"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.escrow_trustee import EscrowTrusteeAccount
from app.models.procurement_enhanced import EscrowPayment
from app.models.user import User
from app.rbac import verify_project_access
from app.services import escrow_trustee_service

router = APIRouter(prefix="/escrow", tags=["资金托管深化"])

ACCEPTANCE_ROLES = ("owner", "contractor")


class TrusteeAccountCreate(BaseModel):
    """开通存管账户请求"""
    escrow_payment_id: str
    trustee_type: str = "bank"
    account_no_masked: str
    interest_to_owner: bool = True
    release_rule: str = "node_based"


class AcceptanceRequest(BaseModel):
    """节点验收双向确认请求"""
    role: str


def _check_escrow_enabled() -> None:
    """校验 F43 feature flag"""
    settings = get_settings()
    if not settings.escrow_trustee_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该功能未启用")


def _account_dict(account: EscrowTrusteeAccount) -> dict:
    """存管账户详情序列化"""
    return {
        "id": account.id,
        "escrow_payment_id": account.escrow_payment_id,
        "trustee_type": account.trustee_type,
        "account_no_masked": account.account_no_masked,
        "interest_to_owner": account.interest_to_owner,
        "owner_confirmed": account.owner_confirmed,
        "contractor_confirmed": account.contractor_confirmed,
        "status": account.status,
        "release_rule": account.release_rule,
        "released_at": account.released_at,
        "created_at": account.created_at,
        "updated_at": account.updated_at,
    }


async def _get_account_with_access(
    db: AsyncSession, account_id: str, current_user: User,
) -> EscrowTrusteeAccount:
    """查询存管账户并通过其担保支付所属项目校验访问权限"""
    account = await escrow_trustee_service.get_account(db, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="存管账户不存在")
    payment = await db.get(EscrowPayment, account.escrow_payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="担保支付不存在")
    await verify_project_access(project_id=payment.project_id, current_user=current_user, db=db)
    return account


@router.post(
    "/trustee-accounts",
    status_code=status.HTTP_201_CREATED,
    summary="开通存管账户",
    description="为担保支付开通银行存管/第三方监管账户，同一担保支付仅允许一个存管账户。",
)
async def create_trustee_account(
    data: TrusteeAccountCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """开通担保支付的存管账户"""
    _check_escrow_enabled()
    payment = await db.get(EscrowPayment, data.escrow_payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="担保支付不存在")
    await verify_project_access(project_id=payment.project_id, current_user=current_user, db=db)
    try:
        account = await escrow_trustee_service.create_account(
            db,
            escrow_payment_id=data.escrow_payment_id,
            trustee_type=data.trustee_type,
            account_no_masked=data.account_no_masked,
            interest_to_owner=data.interest_to_owner,
            release_rule=data.release_rule,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return _account_dict(account)


@router.get("/trustee-accounts/{account_id}", summary="存管账户详情")
async def get_trustee_account(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """存管账户详情"""
    _check_escrow_enabled()
    account = await _get_account_with_access(db, account_id, current_user)
    return _account_dict(account)


@router.get("/escrow-payments/{payment_id}/trustee", summary="按担保支付查询存管账户")
async def get_trustee_by_payment(
    payment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """按担保支付查询存管账户"""
    _check_escrow_enabled()
    payment = await db.get(EscrowPayment, payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="担保支付不存在")
    await verify_project_access(project_id=payment.project_id, current_user=current_user, db=db)
    account = await escrow_trustee_service.get_account_by_payment(db, payment_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该担保支付未开通存管账户")
    return _account_dict(account)


@router.get("/project/{project_id}/trustee-accounts", summary="项目存管账户列表")
async def list_project_trustee_accounts(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """按项目列出存管账户"""
    _check_escrow_enabled()
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    accounts = await escrow_trustee_service.list_accounts_by_project(db, project_id)
    return [_account_dict(acc) for acc in accounts]


@router.post("/trustee-accounts/{account_id}/acceptance", summary="节点验收双向确认")
async def confirm_acceptance(
    account_id: str,
    data: AcceptanceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """节点验收双向确认（owner=业主 / contractor=施工方），双方确认后进入放款请求状态"""
    _check_escrow_enabled()
    if data.role not in ACCEPTANCE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="无效的确认角色，可选: owner/contractor",
        )
    await _get_account_with_access(db, account_id, current_user)
    try:
        updated = await escrow_trustee_service.confirm_acceptance(db, account_id, data.role)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="存管账户不存在")
    return _account_dict(updated)


@router.post("/trustee-accounts/{account_id}/release", summary="放款")
async def release_funds(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """放款：需业主与施工方双方确认且担保支付已完成买家付款"""
    _check_escrow_enabled()
    await _get_account_with_access(db, account_id, current_user)
    try:
        updated = await escrow_trustee_service.release_funds(db, account_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="存管账户不存在")
    return _account_dict(updated)


@router.get("/trustee-accounts/{account_id}/interest", summary="托管资金利息信息")
async def get_interest_info(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """托管资金利息归属说明"""
    _check_escrow_enabled()
    account = await _get_account_with_access(db, account_id, current_user)
    return escrow_trustee_service.get_interest_info(account)


@router.delete(
    "/trustee-accounts/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除存管账户",
)
async def delete_trustee_account(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除存管账户（仅 active 状态可删除）"""
    _check_escrow_enabled()
    await _get_account_with_access(db, account_id, current_user)
    try:
        await escrow_trustee_service.delete_account(db, account_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return None
