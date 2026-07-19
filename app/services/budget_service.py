from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.budget import Budget, BudgetLine
from app.models.material import BOMItem, Material


# ── 状态机定义 ──
# draft    → submitted (提交) | closed (关闭)
# submitted → approved (批准) | closed (关闭)
# approved  → executed (执行) | closed (关闭)
# executed  → closed (关闭)
# closed    → 终态，不可再变
VALID_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"submitted", "closed"},
    "submitted": {"approved", "closed"},
    "approved": {"executed", "closed"},
    "executed": {"closed"},
    "closed": set(),
}


class BudgetStateError(Exception):
    """预算状态机校验失败"""

    def __init__(self, current_status: str, action: str, allowed: set[str]):
        self.current_status = current_status
        self.action = action
        self.allowed = allowed
        super().__init__(
            f"预算状态「{current_status}」不支持操作「{action}」，"
            f"允许的目标状态: {sorted(allowed) or '无（终态）'}"
        )


def _assert_transition(budget: Budget, action: str, target: str) -> None:
    """校验状态机：当前状态是否允许转换到 target"""
    allowed = VALID_TRANSITIONS.get(budget.status, set())
    if target not in allowed:
        raise BudgetStateError(budget.status, action, allowed)


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

    # 注意：get_budget 按 project_id 查询，这里需要按 budget_id 查询以重算总额
    budget_result = await db.execute(
        select(Budget).where(Budget.id == bl.budget_id).options(selectinload(Budget.lines))
    )
    budget = budget_result.scalar_one_or_none()
    if budget:
        budget.total_estimated = sum(line.estimated_amount for line in budget.lines)
        budget.total_actual = sum(line.actual_amount for line in budget.lines)
        await db.commit()

    return bl


# ── 预算审批流状态变更 ──

async def submit_budget(db: AsyncSession, budget_id: str) -> Budget | None:
    """提交预算：draft → submitted"""
    result = await db.execute(
        select(Budget).where(Budget.id == budget_id).options(selectinload(Budget.lines))
    )
    budget = result.scalar_one_or_none()
    if not budget:
        return None
    _assert_transition(budget, "submit", "submitted")
    budget.status = "submitted"
    await db.commit()
    await db.refresh(budget)
    return budget


async def approve_budget(db: AsyncSession, budget_id: str) -> Budget | None:
    """批准预算：submitted → approved"""
    result = await db.execute(
        select(Budget).where(Budget.id == budget_id).options(selectinload(Budget.lines))
    )
    budget = result.scalar_one_or_none()
    if not budget:
        return None
    _assert_transition(budget, "approve", "approved")
    budget.status = "approved"
    await db.commit()
    await db.refresh(budget)
    return budget


async def execute_budget(db: AsyncSession, budget_id: str) -> Budget | None:
    """执行预算：approved → executed"""
    result = await db.execute(
        select(Budget).where(Budget.id == budget_id).options(selectinload(Budget.lines))
    )
    budget = result.scalar_one_or_none()
    if not budget:
        return None
    _assert_transition(budget, "execute", "executed")
    budget.status = "executed"
    await db.commit()
    await db.refresh(budget)
    return budget


async def close_budget(db: AsyncSession, budget_id: str) -> Budget | None:
    """关闭预算：任意非终态 → closed"""
    result = await db.execute(
        select(Budget).where(Budget.id == budget_id).options(selectinload(Budget.lines))
    )
    budget = result.scalar_one_or_none()
    if not budget:
        return None
    _assert_transition(budget, "close", "closed")
    budget.status = "closed"
    await db.commit()
    await db.refresh(budget)
    return budget
