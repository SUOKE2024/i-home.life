"""支付管理服务 — F15 发起 / 确认 / 退款 / 里程碑聚合"""

from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment


async def get_project_payments(db: AsyncSession, project_id: str) -> list[Payment]:
    result = await db.execute(
        select(Payment)
        .where(Payment.project_id == project_id)
        .order_by(Payment.created_at.desc())
    )
    return list(result.scalars().all())


async def get_payment(db: AsyncSession, payment_id: str) -> Payment | None:
    result = await db.execute(
        select(Payment).where(Payment.id == payment_id)
    )
    return result.scalar_one_or_none()


async def create_payment(db: AsyncSession, data: dict) -> Payment:
    payment = Payment(**data)
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return payment


async def confirm_payment(db: AsyncSession, payment_id: str, data: dict) -> Payment | None:
    payment = await get_payment(db, payment_id)
    if not payment:
        return None
    if payment.status not in ("pending", "failed"):
        return payment  # 已支付或已退款不重复确认
    payment.transaction_id = data.get("transaction_id") or payment.transaction_id
    payment.evidence_url = data.get("evidence_url") or payment.evidence_url
    payment.payer = data.get("payer") or payment.payer
    payment.payee = data.get("payee") or payment.payee
    payment.note = data.get("note") or payment.note
    payment.status = "paid"
    payment.paid_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(payment)
    return payment


async def refund_payment(db: AsyncSession, payment_id: str, data: dict) -> Payment | None:
    payment = await get_payment(db, payment_id)
    if not payment:
        return None
    if payment.status != "paid":
        return payment  # 未支付不支持退款
    refund_amount = data.get("refund_amount", payment.amount)
    payment.refund_amount = min(refund_amount, payment.amount)
    payment.refund_reason = data.get("refund_reason")
    payment.status = "refunded"
    payment.refunded_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(payment)
    return payment


async def mark_failed(db: AsyncSession, payment_id: str, reason: str | None = None) -> Payment | None:
    payment = await get_payment(db, payment_id)
    if not payment:
        return None
    payment.status = "failed"
    if reason:
        payment.note = reason
    await db.commit()
    await db.refresh(payment)
    return payment


async def get_milestone_summary(db: AsyncSession, project_id: str) -> dict:
    """按里程碑聚合支付状态"""
    result = await db.execute(
        select(
            Payment.milestone_code,
            func.count(Payment.id).label("count"),
            func.sum(Payment.amount).label("total_amount"),
        )
        .where(Payment.project_id == project_id)
        .group_by(Payment.milestone_code)
    )
    rows = result.all()

    # 按状态再分组
    status_result = await db.execute(
        select(
            Payment.milestone_code,
            Payment.status,
            func.sum(Payment.amount).label("amount"),
        )
        .where(Payment.project_id == project_id)
        .group_by(Payment.milestone_code, Payment.status)
    )
    status_rows = status_result.all()

    milestones: dict[str, dict] = {}
    for row in rows:
        milestones[row.milestone_code] = {
            "milestone_code": row.milestone_code,
            "total_payments": row.count,
            "total_amount": float(row.total_amount or 0),
            "paid_amount": 0.0,
            "pending_amount": 0.0,
            "refunded_amount": 0.0,
            "failed_amount": 0.0,
        }
    for row in status_rows:
        m = milestones.setdefault(row.milestone_code, {
            "milestone_code": row.milestone_code,
            "total_payments": 0,
            "total_amount": 0.0,
            "paid_amount": 0.0,
            "pending_amount": 0.0,
            "refunded_amount": 0.0,
            "failed_amount": 0.0,
        })
        amt = float(row.amount or 0)
        if row.status == "paid":
            m["paid_amount"] += amt
        elif row.status == "pending":
            m["pending_amount"] += amt
        elif row.status == "refunded":
            m["refunded_amount"] += amt
        elif row.status == "failed":
            m["failed_amount"] += amt

    total_paid = sum(m["paid_amount"] for m in milestones.values())
    total_pending = sum(m["pending_amount"] for m in milestones.values())

    return {
        "project_id": project_id,
        "milestones": list(milestones.values()),
        "total_paid": round(total_paid, 2),
        "total_pending": round(total_pending, 2),
        "total_amount": round(total_paid + total_pending, 2),
    }
