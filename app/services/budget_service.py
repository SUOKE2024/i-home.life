from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.budget import Budget, BudgetLine
from app.models.material import BOMItem, Material
from app.models.procurement import ProcurementOrder


# ── F12 物料品类 code → 预算科目名（与 generate_budget_from_bom 保持一致）──
BUDGET_CATEGORY_BY_CODE: dict[str, str] = {
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


async def generate_budget_from_bom(
    db: AsyncSession, project_id: str, tier: str = "comfort",
) -> Budget | None:
    """从 BOM 生成预算

    v1.1.31 FP-6（S5）：受 ``settings.quota_library_enabled`` 控制
    - True：estimated = BOM量 × 定额单价（app.standards.quota_library 按
      category_code × tier 查询），定额缺失时回退到 BOMItem.total_price
    - False：直接用 BOMItem.total_price（原行为）

    Args:
        db: 异步数据库会话
        project_id: 项目 ID
        tier: 档次（economy/comfort/premium/luxury），定额查询用，默认 comfort
    """
    from app.config import get_settings
    from app.standards.quota_library import get_quota_price

    settings = get_settings()

    result = await db.execute(
        select(BOMItem)
        .where(BOMItem.project_id == project_id)
        .options(selectinload(BOMItem.material).selectinload(Material.category))
    )
    bom_items = result.scalars().all()

    if not bom_items:
        return None

    # 复用已有空预算（如 lifecycle_orchestration 项目创建时自动建的占位预算），
    # 避免重复插入触发 project_id 唯一约束冲突；非空预算由调用方在 409 检查拦截。
    existing = await get_budget(db, project_id)
    if existing:
        # 清空旧预算行（delete-orphan cascade 负责删除），再写入 BOM 派生行
        existing.lines.clear()
        budget = existing
    else:
        budget = Budget(project_id=project_id)
        db.add(budget)
        await db.flush()

    category_names = BUDGET_CATEGORY_BY_CODE

    total = 0.0
    for item in bom_items:
        cat_code = item.material.category.code if item.material and item.material.category else "other"
        label = category_names.get(cat_code, "其他工程")

        # v1.1.31 FP-6: 定额优先，回退到 BOM 采购价
        estimated = item.total_price
        applied_unit_price = item.unit_price
        pricing_source = "bom_price"
        if settings.quota_library_enabled:
            quota_price, quota_unit = get_quota_price(cat_code, tier)
            if quota_price is not None:
                # 定额按标准计量单位计价；BOM 量与定额单位一致时直接乘
                # （mep/custom_furniture 按 ㎡，doors_windows 按 樘，soft_decor 按 项）
                estimated = round(item.quantity * quota_price, 2)
                applied_unit_price = quota_price
                pricing_source = "quota"

        bl = BudgetLine(
            budget_id=budget.id,
            category=label,
            name=item.material.name if item.material else f"物料-{item.material_id[:8]}",
            estimated_amount=estimated,
            unit=item.material.unit if item.material else "项",
            quantity=item.quantity,
            unit_price=applied_unit_price,
            # note 记录定价来源（定额 vs 采购价），便于成本对比
            note=f"pricing_source={pricing_source}; tier={tier}" if settings.quota_library_enabled else None,
        )
        total += estimated
        if existing:
            # 已有预算的 lines 已通过 selectinload 加载，走关系集合避免 delete-orphan 误删
            existing.lines.append(bl)
        else:
            # 新建预算 lines 未加载（懒加载在 async 下会 MissingGreenlet），直接 db.add
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


# ── F12 采购订单 → 预算科目自动扣减联动 ──


async def deduct_budget_for_purchase(
    db: AsyncSession,
    project_id: str,
    order_id: str,
    amount: float,
    category_hint: str | None = None,
) -> dict:
    """F12 采购订单 → 预算科目自动扣减联动

    将订单金额累加到对应预算科目（BudgetLine.actual_amount），重算预算
    total_actual 并返回扣减后偏差状态。无预算 / 无科目时不抛错，返回
    ``deducted=False`` 与原因，供采购主流程 try/except 包裹——预算联动
    失败不阻塞采购下单（见 procurement_service.create_order）。

    BudgetLine 模型含 actual_amount 字段：扣减即累加 actual_amount。
    联动记录写入 BudgetLine.note（linked_order={order_id}），供
    get_linked_purchases 查询。

    Args:
        db: 异步数据库会话
        project_id: 项目 ID
        order_id: 采购订单 ID
        amount: 扣减金额（订单总额）
        category_hint: 预算科目名（如「地面工程」）；无提示/未匹配时，
            取估算额最大的科目，仍无科目则自动创建采购支出行
    Returns:
        dict: deducted / budget_line_id / category / total_estimated /
              total_actual / variance / variance_pct 或 reason
    """
    result: dict = {
        "project_id": project_id,
        "order_id": order_id,
        "amount": round(float(amount or 0.0), 2),
        "deducted": False,
        "reason": None,
    }

    budget = await get_budget(db, project_id)
    if not budget:
        result["reason"] = "NO_BUDGET"
        return result

    line = None
    if category_hint:
        line = next((ln for ln in budget.lines if ln.category == category_hint), None)
    if line is None and budget.lines:
        # 无科目提示或未匹配时，落到估算额最大的科目，保证联动可追踪
        line = max(budget.lines, key=lambda ln: ln.estimated_amount or 0.0)

    if line is None:
        # 预算存在但无明细行：自动创建采购支出科目行（记账该笔采购）
        category = category_hint or "采购支出"
        line = BudgetLine(
            budget_id=budget.id,
            category=category,
            name=f"采购订单-{order_id[:8]}",
            estimated_amount=round(float(amount or 0.0), 2),
            actual_amount=round(float(amount or 0.0), 2),
            unit="项",
            quantity=1.0,
            unit_price=round(float(amount or 0.0), 2),
            note=f"linked_order={order_id};auto_created",
        )
        db.add(line)
        budget.lines.append(line)
    else:
        line.actual_amount = round((line.actual_amount or 0.0) + float(amount or 0.0), 2)
        line.note = f"{line.note or ''} linked_order={order_id}".strip()

    budget.total_actual = round(sum(ln.actual_amount or 0.0 for ln in budget.lines), 2)
    await db.commit()

    refreshed = await get_budget(db, project_id)
    total_estimated = refreshed.total_estimated if refreshed else budget.total_estimated
    total_actual = refreshed.total_actual if refreshed else budget.total_actual
    result.update({
        "deducted": True,
        "budget_line_id": line.id,
        "category": line.category,
        "total_estimated": round(total_estimated, 2),
        "total_actual": round(total_actual, 2),
        "variance": round(total_actual - total_estimated, 2),
        "variance_pct": round((total_actual - total_estimated) / total_estimated * 100, 2)
        if total_estimated
        else 0.0,
    })
    return result


async def get_linked_purchases(db: AsyncSession, project_id: str) -> dict:
    """F12 联动记录：返回该预算下已联动（自动扣减）的采购订单清单

    联动记录持久化在 BudgetLine.note（linked_order={order_id}），此处
    解析并关联订单详情（金额/状态/供应商），供前端「采购订单与预算科目
    联动记录」查询。
    """
    budget = await get_budget(db, project_id)
    links: list[dict] = []
    order_ids: list[str] = []
    if budget:
        for line in budget.lines:
            if not line.note:
                continue
            for token in line.note.replace(";", " ").split():
                if token.startswith("linked_order="):
                    order_id = token.split("=", 1)[1]
                    links.append({
                        "order_id": order_id,
                        "budget_line_id": line.id,
                        "category": line.category,
                        "line_name": line.name,
                        "line_actual_amount": round(line.actual_amount or 0.0, 2),
                    })
                    order_ids.append(order_id)
                    break

    orders_info: dict[str, dict] = {}
    if order_ids:
        result = await db.execute(
            select(ProcurementOrder)
            .where(ProcurementOrder.id.in_(order_ids))
            .options(selectinload(ProcurementOrder.supplier))
        )
        for order in result.scalars().all():
            orders_info[order.id] = {
                "order_id": order.id,
                "total_amount": round(order.total_amount or 0.0, 2),
                "status": order.status,
                "supplier_name": order.supplier.name if order.supplier else None,
                "created_at": order.created_at.isoformat() if order.created_at else None,
            }
    for link in links:
        link.update(orders_info.get(link["order_id"], {}))

    return {
        "project_id": project_id,
        "has_budget": budget is not None,
        "linked_count": len(links),
        "linked_purchases": links,
    }
