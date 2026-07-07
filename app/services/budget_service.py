from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.budget import Budget, BudgetLine
from app.models.material import BOMItem, Material


async def get_budget(db: AsyncSession, project_id: str) -> Budget | None:
    result = await db.execute(
        select(Budget)
        .where(Budget.project_id == project_id)
        .options(selectinload(Budget.lines))
    )
    return result.scalar_one_or_none()


async def create_budget(db: AsyncSession, data: dict) -> Budget:
    lines_data = data.pop("lines", [])

    budget = Budget(project_id=data["project_id"])
    db.add(budget)
    await db.flush()

    total = 0.0
    for line_data in lines_data:
        estimated = line_data.get("estimated_amount", 0)
        if not estimated:
            estimated = line_data.get("quantity", 1) * line_data.get("unit_price", 0)
            line_data["estimated_amount"] = estimated
        total += estimated
        bl = BudgetLine(budget_id=budget.id, **line_data)
        db.add(bl)

    budget.total_estimated = total
    await db.commit()
    return await get_budget(db, data["project_id"])


async def generate_budget_from_bom(db: AsyncSession, project_id: str) -> Budget | None:
    result = await db.execute(
        select(BOMItem)
        .where(BOMItem.project_id == project_id)
        .options(selectinload(BOMItem.material).selectinload(Material.category))
    )
    bom_items = result.scalars().all()

    if not bom_items:
        return None

    budget = Budget(project_id=project_id)
    db.add(budget)
    await db.flush()

    category_names = {
        "flooring": "地面工程",
        "wall": "墙面工程",
        "ceiling": "顶面工程",
        "kitchen_bath": "厨卫工程",
        "doors_windows": "门窗工程",
        "mep": "水电工程",
        "custom_furniture": "定制家具",
        "soft_decor": "软装工程",
        "appliances": "家电设备",
    }

    total = 0.0
    for item in bom_items:
        cat_code = item.material.category.code if item.material and item.material.category else "other"
        label = category_names.get(cat_code, "其他工程")

        bl = BudgetLine(
            budget_id=budget.id,
            category=label,
            name=item.material.name if item.material else f"物料-{item.material_id[:8]}",
            estimated_amount=item.total_price,
            unit=item.material.unit if item.material else "项",
            quantity=item.quantity,
            unit_price=item.unit_price,
        )
        total += item.total_price
        db.add(bl)

    budget.total_estimated = total
    await db.commit()
    return await get_budget(db, project_id)


async def update_budget_line(db: AsyncSession, line_id: str, data: dict) -> BudgetLine | None:
    result = await db.execute(select(BudgetLine).where(BudgetLine.id == line_id))
    bl = result.scalar_one_or_none()
    if not bl:
        return None

    for key, value in data.items():
        if hasattr(bl, key):
            setattr(bl, key, value)

    await db.commit()
    await db.refresh(bl)

    budget = await get_budget(db, bl.budget_id)
    if budget:
        budget.total_estimated = sum(line.estimated_amount for line in budget.lines)
        budget.total_actual = sum(line.actual_amount for line in budget.lines)
        await db.commit()

    return bl
