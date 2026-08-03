"""F43 资金托管深化服务层 — 银行存管/第三方监管账户 + 节点验收双向确认放款

现有担保支付 EscrowPayment 深化为托管存管账户：
- 对接银行存管 / 第三方监管账户（脱敏展示账号）
- 业主 + 施工方/供应商双向确认后放款
- 托管资金利息归属业主
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.escrow_trustee import EscrowTrusteeAccount
from app.models.procurement_enhanced import EscrowPayment

# 节点验收双向确认角色（owner=业主 / contractor=施工方/供应商）
ACCEPTANCE_ROLES = ("owner", "contractor")

# 存管账户状态机
STATUS_ACTIVE = "active"
STATUS_RELEASE_REQUESTED = "release_requested"
STATUS_RELEASED = "released"


async def create_account(
    db: AsyncSession,
    escrow_payment_id: str,
    trustee_type: str,
    account_no_masked: str,
    interest_to_owner: bool = True,
    release_rule: str = "node_based",
) -> EscrowTrusteeAccount:
    """为担保支付开通存管账户，同一担保支付仅允许一个存管账户"""
    payment = await db.get(EscrowPayment, escrow_payment_id)
    if not payment:
        raise ValueError("担保支付不存在")
    existing = await get_account_by_payment(db, escrow_payment_id)
    if existing:
        raise ValueError("该担保支付已开通存管账户")
    account = EscrowTrusteeAccount(
        escrow_payment_id=escrow_payment_id,
        trustee_type=trustee_type,
        account_no_masked=account_no_masked,
        interest_to_owner=interest_to_owner,
        release_rule=release_rule,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


async def get_account(db: AsyncSession, account_id: str) -> EscrowTrusteeAccount | None:
    """按 ID 查询存管账户"""
    return await db.get(EscrowTrusteeAccount, account_id)


async def get_account_by_payment(
    db: AsyncSession, escrow_payment_id: str,
) -> EscrowTrusteeAccount | None:
    """按担保支付 ID 查询存管账户"""
    result = await db.execute(
        select(EscrowTrusteeAccount).where(
            EscrowTrusteeAccount.escrow_payment_id == escrow_payment_id,
        )
    )
    return result.scalar_one_or_none()


async def list_accounts_by_project(
    db: AsyncSession, project_id: str,
) -> list[EscrowTrusteeAccount]:
    """按项目列出存管账户（JOIN EscrowPayment 过滤 project_id）"""
    result = await db.execute(
        select(EscrowTrusteeAccount)
        .join(EscrowPayment, EscrowPayment.id == EscrowTrusteeAccount.escrow_payment_id)
        .where(EscrowPayment.project_id == project_id)
        .order_by(EscrowTrusteeAccount.created_at.desc())
    )
    return list(result.scalars().all())


async def confirm_acceptance(
    db: AsyncSession, account_id: str, role: str,
) -> EscrowTrusteeAccount | None:
    """节点验收双向确认：双方都确认后账户进入放款请求状态"""
    account = await get_account(db, account_id)
    if not account:
        return None
    if role == "owner":
        account.owner_confirmed = True
    elif role == "contractor":
        account.contractor_confirmed = True
    else:
        raise ValueError("无效的确认角色，可选: owner/contractor")
    if account.owner_confirmed and account.contractor_confirmed:
        if account.status == STATUS_ACTIVE:
            account.status = STATUS_RELEASE_REQUESTED
    await db.commit()
    await db.refresh(account)
    return account


async def release_funds(db: AsyncSession, account_id: str) -> EscrowTrusteeAccount | None:
    """放款：需业主与施工方双方确认且担保支付已完成买家付款

    成功后存管账户 → released，并将资金释放给供应商
    （EscrowPayment.supplier_received=True, status → supplier_received）。
    """
    account = await get_account(db, account_id)
    if not account:
        return None
    if not (account.owner_confirmed and account.contractor_confirmed):
        raise ValueError("需业主与施工方双方确认后才能放款")
    if account.status == STATUS_RELEASED:
        raise ValueError("该存管账户已放款，请勿重复操作")
    payment = await db.get(EscrowPayment, account.escrow_payment_id)
    if not payment or not payment.buyer_paid:
        raise ValueError("担保支付未完成买家付款，无法放款")
    account.status = STATUS_RELEASED
    account.released_at = datetime.now(timezone.utc)
    payment.supplier_received = True
    payment.status = "supplier_received"
    await db.commit()
    await db.refresh(account)
    return account


async def delete_account(db: AsyncSession, account_id: str) -> bool:
    """删除存管账户（仅 active 状态可删除）"""
    account = await get_account(db, account_id)
    if not account:
        return False
    if account.status != STATUS_ACTIVE:
        raise ValueError("仅存管中(active)状态的账户可删除")
    await db.delete(account)
    await db.commit()
    return True


def get_interest_info(account: EscrowTrusteeAccount) -> dict:
    """托管资金利息归属说明"""
    if account.interest_to_owner:
        return {
            "interest_to_owner": True,
            "note": "托管资金利息归属业主，按约定周期结算至业主账户",
        }
    return {
        "interest_to_owner": False,
        "note": "托管资金利息归属平台，需与业主明确约定并提示合规风险",
    }
