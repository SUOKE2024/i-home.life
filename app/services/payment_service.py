"""支付管理服务 — F15 发起 / 确认 / 退款 / 里程碑聚合 / 电子发票 / 分阶段支付节点 / 最终结算报告"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.models.settlement import Settlement


# ── 状态机定义 ──
# pending  → disputed (raise_dispute) | pending → paid (confirm) | pending → failed (mark_failed)
# disputed → paid (confirm, 争议解决)   | disputed → failed (mark_failed, 争议不成立)
# failed   → paid (confirm, 重试)       | failed → failed (mark_failed, 新原因)
# paid     → refunded (refund)          [终态前一步]
# refunded → 终态，不可再变
VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"paid", "failed", "disputed"},
    "disputed": {"paid", "failed"},
    "failed": {"paid", "failed"},
    "paid": {"refunded"},
    "refunded": set(),
}


class PaymentStateError(Exception):
    """支付状态机校验失败"""

    def __init__(self, current_status: str, action: str, allowed: set[str]):
        self.current_status = current_status
        self.action = action
        self.allowed = allowed
        super().__init__(
            f"支付状态「{current_status}」不支持操作「{action}」，"
            f"允许的目标状态: {sorted(allowed) or '无（终态）'}"
        )


def _assert_transition(payment: Payment, action: str, target: str) -> None:
    """校验状态机：当前状态是否允许转换到 target"""
    allowed = VALID_TRANSITIONS.get(payment.status, set())
    if target not in allowed:
        raise PaymentStateError(payment.status, action, allowed)


async def get_project_payments(db: AsyncSession, project_id: str) -> list[Payment]:
    result = await db.execute(
        select(Payment)
        .where(Payment.project_id == project_id)
        .order_by(Payment.stage_order.asc(), Payment.created_at.desc())
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
    """确认支付：pending/failed → paid"""
    payment = await get_payment(db, payment_id)
    if not payment:
        return None
    _assert_transition(payment, "confirm", "paid")
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
    """退款：paid → refunded"""
    payment = await get_payment(db, payment_id)
    if not payment:
        return None
    _assert_transition(payment, "refund", "refunded")
    refund_amount = data.get("refund_amount", payment.amount)
    payment.refund_amount = min(float(refund_amount), payment.amount)
    payment.refund_reason = data.get("refund_reason")
    payment.status = "refunded"
    payment.refunded_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(payment)
    return payment


async def mark_failed(db: AsyncSession, payment_id: str, reason: str | None = None) -> Payment | None:
    """标记失败：pending/disputed/failed → failed"""
    payment = await get_payment(db, payment_id)
    if not payment:
        return None
    _assert_transition(payment, "mark_failed", "failed")
    payment.status = "failed"
    if reason:
        payment.note = reason
    await db.commit()
    await db.refresh(payment)
    return payment


async def mark_disputed(db: AsyncSession, payment_id: str, reason: str | None = None) -> Payment | None:
    """标记争议：pending → disputed（资金类业务不可逆保护）"""
    payment = await get_payment(db, payment_id)
    if not payment:
        return None
    _assert_transition(payment, "raise_dispute", "disputed")
    payment.status = "disputed"
    if reason:
        payment.note = f"[争议] {reason}"
    await db.commit()
    await db.refresh(payment)
    return payment


async def generate_invoice(db: AsyncSession, payment_id: str, data: dict) -> Payment | None:
    """F15 电子发票开具：仅已支付的支付记录可开票

    生成发票号 INV-{YYYYMMDD}-{uuid6}，并记录发票 URL / 抬头 / 时间。
    """
    payment = await get_payment(db, payment_id)
    if not payment:
        return None
    if payment.status != "paid":
        raise PaymentStateError(payment.status, "generate_invoice", {"paid"})
    if payment.invoice_no:
        # 已开票，更新发票 URL / 抬头（允许补传文件）
        payment.invoice_url = data.get("invoice_url") or payment.invoice_url
        payment.payer = data.get("payer") or payment.payer
        payment.payee = data.get("payee") or payment.payee
        if data.get("note"):
            payment.note = data.get("note")
        await db.commit()
        await db.refresh(payment)
        return payment

    now = datetime.now(timezone.utc)
    invoice_no = f"INV-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    payment.invoice_no = invoice_no
    payment.invoice_url = data.get("invoice_url")
    payment.invoiced_at = now
    payment.payer = data.get("payer") or payment.payer
    payment.payee = data.get("payee") or payment.payee
    if data.get("note"):
        payment.note = data.get("note")
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
        elif row.status == "disputed":
            m.setdefault("disputed_amount", 0.0)
            m["disputed_amount"] += amt

    total_paid = sum(m["paid_amount"] for m in milestones.values())
    total_pending = sum(m["pending_amount"] for m in milestones.values())

    return {
        "project_id": project_id,
        "milestones": list(milestones.values()),
        "total_paid": round(total_paid, 2),
        "total_pending": round(total_pending, 2),
        "total_amount": round(total_paid + total_pending, 2),
    }


async def get_payment_schedule(db: AsyncSession, project_id: str) -> list[dict]:
    """F15 分阶段支付节点：按 stage_code 聚合，返回每个阶段的支付进度

    若项目无 stage_code（兼容旧数据），则按 milestone_code 聚合。
    """
    result = await db.execute(
        select(
            Payment.stage_code,
            Payment.milestone_code,
            func.min(Payment.stage_order).label("stage_order"),
            func.max(Payment.due_at).label("due_at"),
            func.count(Payment.id).label("payment_count"),
            func.sum(Payment.amount).label("total_amount"),
        )
        .where(Payment.project_id == project_id)
        .group_by(Payment.stage_code, Payment.milestone_code)
        .order_by(func.min(Payment.stage_order).asc())
    )
    rows = result.all()

    # 按状态聚合
    status_result = await db.execute(
        select(
            Payment.stage_code,
            Payment.milestone_code,
            Payment.status,
            func.sum(Payment.amount).label("amount"),
        )
        .where(Payment.project_id == project_id)
        .group_by(Payment.stage_code, Payment.milestone_code, Payment.status)
    )
    status_rows = status_result.all()

    # 构建节点索引
    nodes: dict[tuple, dict] = {}
    for row in rows:
        key = (row.stage_code, row.milestone_code)
        nodes[key] = {
            "stage_code": row.stage_code or row.milestone_code or "default",
            "stage_order": row.stage_order or 0,
            "milestone_code": row.milestone_code or "completion",
            "total_amount": float(row.total_amount or 0),
            "paid_amount": 0.0,
            "pending_amount": 0.0,
            "refunded_amount": 0.0,
            "failed_amount": 0.0,
            "payment_count": row.payment_count,
            "due_at": row.due_at,
            "status": "pending",
        }

    for row in status_rows:
        key = (row.stage_code, row.milestone_code)
        node = nodes.setdefault(key, {
            "stage_code": row.stage_code or row.milestone_code or "default",
            "stage_order": 0,
            "milestone_code": row.milestone_code or "completion",
            "total_amount": 0.0,
            "paid_amount": 0.0,
            "pending_amount": 0.0,
            "refunded_amount": 0.0,
            "failed_amount": 0.0,
            "payment_count": 0,
            "due_at": None,
            "status": "pending",
        })
        amt = float(row.amount or 0)
        if row.status == "paid":
            node["paid_amount"] += amt
        elif row.status == "pending":
            node["pending_amount"] += amt
        elif row.status == "refunded":
            node["refunded_amount"] += amt
        elif row.status == "failed":
            node["failed_amount"] += amt

    # 计算每个节点状态
    now = datetime.now(timezone.utc)
    schedule: list[dict] = []
    for node in nodes.values():
        total = node["total_amount"]
        paid = node["paid_amount"]
        if total > 0:
            if paid >= total:
                node["status"] = "paid"
            elif paid > 0:
                node["status"] = "partial"
            elif node["due_at"] and node["due_at"] < now:
                node["status"] = "overdue"
            else:
                node["status"] = "pending"
        else:
            node["status"] = "pending"
        schedule.append(node)

    schedule.sort(key=lambda n: (n["stage_order"], n["stage_code"]))
    return schedule


async def get_final_settlement_report(db: AsyncSession, project_id: str) -> dict:
    """F15 最终结算报告：聚合所有支付 + 发票 + 结算单数据

    返回:
        project_id, total_contract_amount, total_paid, total_pending,
        total_refunded, total_failed, paid_ratio, invoice_count,
        invoiced_amount, milestone_summary, payment_count, generated_at
    """
    # 拉取结算单（可能不存在）
    settlement_result = await db.execute(
        select(Settlement).where(Settlement.project_id == project_id)
    )
    settlement = settlement_result.scalar_one_or_none()
    contract_amount = float(settlement.contract_amount) if settlement else 0.0

    # 聚合支付数据
    result = await db.execute(
        select(
            Payment.status,
            func.count(Payment.id).label("count"),
            func.sum(Payment.amount).label("amount"),
        )
        .where(Payment.project_id == project_id)
        .group_by(Payment.status)
    )
    status_rows = result.all()

    total_paid = 0.0
    total_pending = 0.0
    total_refunded = 0.0
    total_failed = 0.0
    total_disputed = 0.0
    payment_count = 0
    for row in status_rows:
        amt = float(row.amount or 0)
        payment_count += int(row.count)
        if row.status == "paid":
            total_paid += amt
        elif row.status == "pending":
            total_pending += amt
        elif row.status == "refunded":
            total_refunded += amt
        elif row.status == "failed":
            total_failed += amt
        elif row.status == "disputed":
            total_disputed += amt

    # 发票聚合
    invoice_result = await db.execute(
        select(
            func.count(Payment.id).label("invoice_count"),
            func.sum(Payment.amount).label("invoiced_amount"),
        )
        .where(
            Payment.project_id == project_id,
            Payment.invoice_no.is_not(None),
        )
    )
    invoice_row = invoice_result.one()
    invoice_count = int(invoice_row.invoice_count or 0)
    invoiced_amount = float(invoice_row.invoiced_amount or 0)

    # 里程碑摘要
    milestone_data = await get_milestone_summary(db, project_id)

    # 已付比例
    total_amount = total_paid + total_pending
    paid_ratio = round(total_paid / total_amount, 4) if total_amount > 0 else 0.0

    return {
        "project_id": project_id,
        "total_contract_amount": round(contract_amount, 2),
        "total_paid": round(total_paid, 2),
        "total_pending": round(total_pending, 2),
        "total_refunded": round(total_refunded, 2),
        "total_failed": round(total_failed, 2),
        "total_disputed": round(total_disputed, 2),
        "paid_ratio": paid_ratio,
        "invoice_count": invoice_count,
        "invoiced_amount": round(invoiced_amount, 2),
        "milestone_summary": milestone_data.get("milestones", []),
        "payment_count": payment_count,
        "generated_at": datetime.now(timezone.utc),
    }
