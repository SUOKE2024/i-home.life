from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.settlement import Settlement, SettlementLine
from app.models.budget import Budget


async def get_settlement(db: AsyncSession, project_id: str) -> Settlement | None:
    result = await db.execute(
        select(Settlement)
        .where(Settlement.project_id == project_id)
        .options(selectinload(Settlement.lines))
    )
    return result.scalar_one_or_none()


async def create_settlement(db: AsyncSession, data: dict) -> Settlement:
    lines_data = data.pop("lines", [])
    settlement = Settlement(project_id=data["project_id"], milestone=data.get("milestone", "completion"))
    db.add(settlement)
    await db.flush()

    total_contract = 0.0
    for line_data in lines_data:
        total_contract += line_data["contract_amount"] + line_data.get("change_amount", 0)
        sl = SettlementLine(settlement_id=settlement.id, **line_data)
        db.add(sl)

    settlement.contract_amount = total_contract
    await db.commit()
    return await get_settlement(db, data["project_id"])


async def generate_from_budget(db: AsyncSession, project_id: str) -> Settlement | None:
    result = await db.execute(
        select(Budget)
        .where(Budget.project_id == project_id)
        .options(selectinload(Budget.lines))
    )
    budget = result.scalar_one_or_none()
    if not budget:
        return None

    existing = await get_settlement(db, project_id)
    if existing:
        return existing

    settlement = Settlement(project_id=project_id, milestone="completion")
    db.add(settlement)
    await db.flush()

    total = 0.0
    for bl in budget.lines:
        sl = SettlementLine(
            settlement_id=settlement.id,
            category=bl.category,
            name=bl.name,
            contract_amount=bl.estimated_amount,
            actual_amount=bl.actual_amount,
            status="pending",
        )
        total += bl.estimated_amount
        db.add(sl)

    settlement.contract_amount = total
    settlement.actual_amount = budget.total_actual
    settlement.payable_amount = max(total, budget.total_actual)
    await db.commit()
    return await get_settlement(db, project_id)


async def confirm_settlement(db: AsyncSession, project_id: str) -> Settlement | None:
    settlement = await get_settlement(db, project_id)
    if not settlement:
        return None

    # F14：若存在严重异常且未复核，阻止确认
    if settlement.critical_anomaly_count > 0 and not settlement.reviewed_by:
        settlement.review_required = True
        await db.commit()
        await db.refresh(settlement)
        return settlement

    settlement.status = "confirmed"
    settlement.settled_at = datetime.now(timezone.utc)

    settlement.payable_amount = settlement.actual_amount or settlement.contract_amount

    await db.commit()
    await db.refresh(settlement)
    return settlement


# ── F14 异常费用标记到结算行 ──────────────────────────────────
async def attach_anomalies(
    db: AsyncSession,
    project_id: str,
    anomalies: list[dict],
    auto_mark_lines: bool = True,
) -> Settlement | None:
    """将 Agent 检测出的异常关联到结算单：
    - 汇总 anomaly_count / critical_anomaly_count / suggested_deduction
    - auto_mark_lines=True 时，按 name 模糊匹配把异常落到 SettlementLine
    - 若存在严重异常，自动置 review_required=True
    """
    settlement = await get_settlement(db, project_id)
    if not settlement:
        return None

    critical_count = sum(1 for a in anomalies if a.get("severity") == "critical")
    deduction = sum(a.get("amount", 0) for a in anomalies if a.get("severity") == "critical")

    settlement.anomaly_count = len(anomalies)
    settlement.critical_anomaly_count = critical_count
    settlement.suggested_deduction = round(deduction, 2)
    settlement.review_required = critical_count > 0

    if auto_mark_lines and settlement.lines:
        # 重置已有标记
        for line in settlement.lines:
            line.is_anomaly = False
            line.anomaly_type = None
            line.anomaly_severity = None
            line.anomaly_detail = None

        # 按名称模糊匹配
        for anomaly in anomalies:
            target_name = (
                anomaly.get("name")
                or anomaly.get("detail", "").split("：")[-1]
                or ""
            )
            for line in settlement.lines:
                if target_name and target_name in line.name:
                    line.is_anomaly = True
                    line.anomaly_type = anomaly.get("type", line.anomaly_type)
                    line.anomaly_severity = anomaly.get("severity", line.anomaly_severity)
                    line.anomaly_detail = anomaly.get("detail", line.anomaly_detail)
                    line.status = "flagged"
                    break

    await db.commit()
    return await get_settlement(db, project_id)


# ── F14 人工复核 ─────────────────────────────────────────────
async def request_review(
    db: AsyncSession,
    project_id: str,
    reason: str,
    reviewer_id: str | None = None,
) -> Settlement | None:
    """触发人工复核：标记 review_required，记录 reason 和 reviewer。"""
    settlement = await get_settlement(db, project_id)
    if not settlement:
        return None

    settlement.review_required = True
    settlement.review_reason = reason
    if reviewer_id:
        settlement.reviewed_by = reviewer_id
    settlement.status = "review"

    await db.commit()
    await db.refresh(settlement)
    return settlement


async def approve_review(
    db: AsyncSession,
    project_id: str,
    reviewer_id: str,
) -> Settlement | None:
    """人工复核通过：清除 review_required，标记 reviewer，可继续 confirm。"""
    settlement = await get_settlement(db, project_id)
    if not settlement:
        return None

    settlement.review_required = False
    settlement.reviewed_by = reviewer_id
    settlement.status = "draft"

    await db.commit()
    await db.refresh(settlement)
    return settlement


# ── F14 对账单导出（结构化数据，由前端/导出层渲染为 CSV/Excel） ──
async def export_reconciliation(db: AsyncSession, project_id: str) -> dict | None:
    settlement = await get_settlement(db, project_id)
    if not settlement:
        return None

    lines_payload = []
    for line in settlement.lines:
        lines_payload.append({
            "category": line.category,
            "name": line.name,
            "contract_amount": line.contract_amount,
            "change_amount": line.change_amount,
            "actual_amount": line.actual_amount,
            "variance": round(line.actual_amount - line.contract_amount - line.change_amount, 2),
            "status": line.status,
            "is_anomaly": line.is_anomaly,
            "anomaly_type": line.anomaly_type,
            "anomaly_detail": line.anomaly_detail,
        })

    return {
        "project_id": project_id,
        "settlement_id": settlement.id,
        "milestone": settlement.milestone,
        "contract_amount": settlement.contract_amount,
        "actual_amount": settlement.actual_amount,
        "payable_amount": settlement.payable_amount,
        "anomaly_count": settlement.anomaly_count,
        "critical_anomaly_count": settlement.critical_anomaly_count,
        "suggested_deduction": settlement.suggested_deduction,
        "status": settlement.status,
        "settled_at": settlement.settled_at.isoformat() if settlement.settled_at else None,
        "lines": lines_payload,
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }
