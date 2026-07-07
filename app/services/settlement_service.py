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

    settlement.status = "confirmed"
    settlement.settled_at = datetime.now(timezone.utc)

    settlement.payable_amount = settlement.actual_amount or settlement.contract_amount

    await db.commit()
    await db.refresh(settlement)
    return settlement
