from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.procurement import Supplier, Quotation, ProcurementOrder, OrderLine
from app.models.material import BOMItem, Material, MaterialCategory
from app.models.construction import ConstructionTask

# 采购订单状态流转定义
ORDER_STATUS_FLOW: dict[str, set[str]] = {
    "draft": {"pending", "confirmed", "cancelled"},
    "pending": {"confirmed", "cancelled"},
    "confirmed": {"shipped", "cancelled"},
    "shipped": {"delivered", "cancelled"},
    "delivered": {"completed"},
    "completed": set(),
    "cancelled": set(),
}


def is_valid_status_transition(current: str, target: str) -> bool:
    """校验订单状态流转是否合法"""
    allowed = ORDER_STATUS_FLOW.get(current, set())
    return target in allowed


async def get_suppliers(db: AsyncSession, category: str | None = None) -> list[Supplier]:
    stmt = select(Supplier).where(Supplier.is_active.is_(True)).order_by(Supplier.rating.desc())
    if category:
        stmt = stmt.where(Supplier.category == category)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_supplier(db: AsyncSession, data: dict) -> Supplier:
    supplier = Supplier(**data)
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier


async def create_quotation(db: AsyncSession, data: dict) -> Quotation:
    total = data["quantity"] * data["unit_price"]
    quotation = Quotation(**data, total_price=total)
    db.add(quotation)
    await db.commit()
    await db.refresh(quotation)
    return quotation


async def get_quotations(db: AsyncSession, project_id: str) -> list[Quotation]:
    result = await db.execute(
        select(Quotation)
        .where(Quotation.project_id == project_id)
        .options(selectinload(Quotation.supplier), selectinload(Quotation.material))
        .order_by(Quotation.total_price.asc())
    )
    return list(result.scalars().all())


async def create_order(db: AsyncSession, data: dict) -> ProcurementOrder:
    lines_data = data.pop("lines", [])
    order = ProcurementOrder(**data)
    db.add(order)
    await db.flush()

    total = 0.0
    for line_data in lines_data:
        line_total = line_data["quantity"] * line_data["unit_price"]
        total += line_total
        ol = OrderLine(order_id=order.id, **line_data, total_price=line_total)
        db.add(ol)

    order.total_amount = total
    await db.commit()
    await db.refresh(order)
    return await get_order(db, order.id)


async def get_order(db: AsyncSession, order_id: str) -> ProcurementOrder | None:
    result = await db.execute(
        select(ProcurementOrder)
        .where(ProcurementOrder.id == order_id)
        .options(
            selectinload(ProcurementOrder.lines).selectinload(OrderLine.material),
            selectinload(ProcurementOrder.supplier),
        )
    )
    return result.scalar_one_or_none()


async def get_project_orders(db: AsyncSession, project_id: str) -> list[ProcurementOrder]:
    result = await db.execute(
        select(ProcurementOrder)
        .where(ProcurementOrder.project_id == project_id)
        .options(
            selectinload(ProcurementOrder.supplier),
            selectinload(ProcurementOrder.lines).selectinload(OrderLine.material),
        )
        .order_by(ProcurementOrder.created_at.desc())
    )
    return list(result.scalars().all())


async def update_order_status(db: AsyncSession, order_id: str, status: str) -> ProcurementOrder | None:
    result = await db.execute(select(ProcurementOrder).where(ProcurementOrder.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        return None
    if not is_valid_status_transition(order.status, status):
        raise ValueError(f"非法状态流转: {order.status} → {status}")
    order.status = status
    await db.commit()
    await db.refresh(order)
    return order


async def update_order(db: AsyncSession, order_id: str, data: dict) -> ProcurementOrder | None:
    result = await db.execute(select(ProcurementOrder).where(ProcurementOrder.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        return None
    for key, value in data.items():
        setattr(order, key, value)
    await db.commit()
    return await get_order(db, order_id)


async def delete_order(db: AsyncSession, order_id: str) -> bool:
    result = await db.execute(select(ProcurementOrder).where(ProcurementOrder.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        return False
    await db.delete(order)
    await db.commit()
    return True


# ── BOM 自动生成采购订单 ──


async def generate_from_bom(db: AsyncSession, project_id: str) -> dict:
    """从 BOM 物料清单自动生成采购订单

    按物料分类分组 BOM 项，为每个供应商（同品类）创建 draft 状态的采购订单。
    """
    # 查询项目所有 BOM 项（含物料及分类信息）
    bom_result = await db.execute(
        select(BOMItem)
        .where(BOMItem.project_id == project_id)
        .options(
            selectinload(BOMItem.material).selectinload(Material.category),
        )
        .order_by(BOMItem.created_at.asc())
    )
    bom_items = list(bom_result.scalars().all())
    if not bom_items:
        raise ValueError(f"项目 {project_id} 没有 BOM 物料清单，请先生成 BOM")

    # 按物料分类分组
    category_groups: dict[str, list[BOMItem]] = {}
    for item in bom_items:
        cat_name = item.material.category.name if item.material and item.material.category else "未分类"
        if cat_name not in category_groups:
            category_groups[cat_name] = []
        category_groups[cat_name].append(item)

    created_orders: list[ProcurementOrder] = []

    for cat_name, items in category_groups.items():
        # 找该品类下评分最高的活跃供应商
        supplier_result = await db.execute(
            select(Supplier)
            .where(Supplier.category == cat_name, Supplier.is_active.is_(True))
            .order_by(Supplier.rating.desc())
            .limit(1)
        )
        supplier = supplier_result.scalar_one_or_none()
        if not supplier:
            # 如果没有同品类供应商，找任意活跃供应商
            fallback_result = await db.execute(
                select(Supplier)
                .where(Supplier.is_active.is_(True))
                .order_by(Supplier.rating.desc())
                .limit(1)
            )
            supplier = fallback_result.scalar_one_or_none()
            if not supplier:
                continue

        # 创建采购订单（draft 状态）
        order = ProcurementOrder(
            project_id=project_id,
            supplier_id=supplier.id,
            status="draft",
            note=f"BOM 自动生成 — {cat_name}",
        )
        db.add(order)
        await db.flush()

        total = 0.0
        for item in items:
            mat = item.material
            line_total = round(item.quantity * item.unit_price, 2)
            total += line_total
            ol = OrderLine(
                order_id=order.id,
                material_id=item.material_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total_price=line_total,
                note=item.note,
            )
            db.add(ol)

        order.total_amount = round(total, 2)
        created_orders.append(order)

    await db.commit()

    # 重新加载带关联的订单
    order_ids = [o.id for o in created_orders]
    final_result = await db.execute(
        select(ProcurementOrder)
        .where(ProcurementOrder.id.in_(order_ids))
        .options(
            selectinload(ProcurementOrder.supplier),
            selectinload(ProcurementOrder.lines).selectinload(OrderLine.material),
        )
    )
    orders = list(final_result.scalars().all())

    return {
        "project_id": project_id,
        "total_bom_items": len(bom_items),
        "total_categories": len(category_groups),
        "generated_orders": len(orders),
        "orders": [
            {
                "order_id": o.id,
                "supplier_name": o.supplier.name if o.supplier else None,
                "status": o.status,
                "total_amount": o.total_amount,
                "line_count": len(o.lines),
                "lines": [
                    {
                        "material_name": line.material.name if line.material else None,
                        "sku": line.material.sku if line.material else None,
                        "quantity": line.quantity,
                        "unit_price": line.unit_price,
                        "total_price": line.total_price,
                    }
                    for line in o.lines
                ],
            }
            for o in orders
        ],
    }


# ── 供应商比价 ──


async def compare_suppliers(db: AsyncSession, material_id: str, quantity: float) -> dict:
    """多供应商比价

    获取同一物料的所有供应商报价，按总价排序。
    包含供应商评分、交货天数和总成本。
    """
    # 校验物料存在
    mat_result = await db.execute(
        select(Material).where(Material.id == material_id).options(selectinload(Material.category))
    )
    material = mat_result.scalar_one_or_none()
    if not material:
        raise ValueError(f"物料不存在: {material_id}")

    # 查询所有活跃供应商对此物料的报价
    quotations_result = await db.execute(
        select(Quotation)
        .where(Quotation.material_id == material_id)
        .options(selectinload(Quotation.supplier))
        .order_by(Quotation.unit_price.asc())
    )
    quotations = list(quotations_result.scalars().all())

    comparisons: list[dict] = []
    for q in quotations:
        total_cost = round(quantity * q.unit_price, 2)
        comparisons.append({
            "supplier_id": q.supplier_id,
            "supplier_name": q.supplier.name if q.supplier else "未知",
            "supplier_rating": q.supplier.rating if q.supplier else 0.0,
            "unit_price": q.unit_price,
            "quantity": quantity,
            "total_cost": total_cost,
            "delivery_days": q.delivery_days,
            "quotation_id": q.id,
            "quotation_status": q.status,
        })

    # 按 total_cost 排序
    comparisons.sort(key=lambda x: x["total_cost"])

    # 如果没有已有报价，查询所有供应商的基础信息
    if not comparisons:
        suppliers_result = await db.execute(
            select(Supplier)
            .where(Supplier.is_active.is_(True))
            .order_by(Supplier.rating.desc())
        )
        suppliers = list(suppliers_result.scalars().all())
        for s in suppliers:
            comparisons.append({
                "supplier_id": s.id,
                "supplier_name": s.name,
                "supplier_rating": s.rating,
                "unit_price": 0.0,
                "quantity": quantity,
                "total_cost": 0.0,
                "delivery_days": 7,  # 默认 7 天
                "quotation_id": None,
                "quotation_status": "no_quotation",
                "note": "暂无报价",
            })

    return {
        "material_id": material_id,
        "material_name": material.name,
        "material_sku": material.sku,
        "material_unit": material.unit,
        "requested_quantity": quantity,
        "total_suppliers": len(comparisons),
        "comparisons": comparisons,
    }


# ── 到货核验 ──


async def verify_delivery(db: AsyncSession, order_id: str) -> dict:
    """到货核验：对比实际到货与订单明细

    遍历每个 OrderLine，检查 delivered_quantity 是否匹配 ordered quantity。
    记录核验时间。返回差异清单。
    """
    order_result = await db.execute(
        select(ProcurementOrder)
        .where(ProcurementOrder.id == order_id)
        .options(
            selectinload(ProcurementOrder.lines).selectinload(OrderLine.material),
            selectinload(ProcurementOrder.supplier),
        )
    )
    order = order_result.scalar_one_or_none()
    if not order:
        raise ValueError(f"采购订单不存在: {order_id}")

    discrepancies: list[dict] = []
    all_matched = True

    for line in order.lines:
        ordered = line.quantity
        delivered = line.delivered_quantity
        diff = round(ordered - delivered, 2)

        line_status = "matched"
        if abs(diff) > 0.001:
            all_matched = False
            line_status = "short" if diff > 0 else "over"

        discrepancies.append({
            "line_id": line.id,
            "material_name": line.material.name if line.material else None,
            "sku": line.material.sku if line.material else None,
            "ordered_quantity": ordered,
            "delivered_quantity": delivered,
            "difference": diff,
            "status": line_status,
            "note": (
                f"缺少 {diff} {getattr(line.material, 'unit', '件')}" if diff > 0
                else (f"超出 {abs(diff)} {getattr(line.material, 'unit', '件')}" if diff < 0
                else "数量匹配")
            ),
        })

    # 记录核验时间
    verified_at = datetime.now(timezone.utc)
    order.delivery_notes = (
        (order.delivery_notes or "")
        + f"\n[核验 {verified_at.isoformat()}] "
        + ("全部匹配" if all_matched else f"发现 {sum(1 for d in discrepancies if d['status'] != 'matched')} 项差异")
    ).strip()

    await db.commit()

    return {
        "order_id": order_id,
        "supplier_name": order.supplier.name if order.supplier else None,
        "verified_at": verified_at.isoformat(),
        "all_matched": all_matched,
        "total_lines": len(order.lines),
        "discrepancy_count": sum(1 for d in discrepancies if d["status"] != "matched"),
        "discrepancies": discrepancies,
    }


# ── 采购-施工联动 ──


async def link_to_construction(db: AsyncSession, order_id: str, task_id: str) -> dict:
    """将采购订单关联到施工任务

    当订单标记为 delivered 时，自动更新关联的施工任务状态为 ready（如果它因等待材料而阻塞）。
    记录 material_delivered_at 时间戳。
    """
    # 获取订单
    order_result = await db.execute(
        select(ProcurementOrder)
        .where(ProcurementOrder.id == order_id)
        .options(selectinload(ProcurementOrder.lines))
    )
    order = order_result.scalar_one_or_none()
    if not order:
        raise ValueError(f"采购订单不存在: {order_id}")

    # 获取施工任务
    task_result = await db.execute(
        select(ConstructionTask).where(ConstructionTask.id == task_id)
    )
    task = task_result.scalar_one_or_none()
    if not task:
        raise ValueError(f"施工任务不存在: {task_id}")

    # 校验项目一致
    if order.project_id != task.project_id:
        raise ValueError(
            f"订单项目 ({order.project_id}) 与任务项目 ({task.project_id}) 不一致"
        )

    # 关联
    order.construction_task_id = task_id

    # 如果订单已交付，更新任务状态并记录物料到达时间
    if order.status == "delivered" and task.status == "pending":
        task.status = "ready"
        order.material_delivered_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(order)
    await db.refresh(task)

    return {
        "order_id": order.id,
        "order_status": order.status,
        "task_id": task.id,
        "task_name": task.name,
        "task_status": task.status,
        "material_delivered_at": order.material_delivered_at.isoformat()
            if order.material_delivered_at else None,
        "linked_at": datetime.now(timezone.utc).isoformat(),
    }


# ── 物料库存查询 ──


async def get_material_availability(db: AsyncSession, material_id: str) -> dict:
    """查询物料在各供应商的库存/可供应情况

    返回各供应商的可用数量、交货周期和下次交货日期。
    """
    mat_result = await db.execute(
        select(Material).where(Material.id == material_id).options(selectinload(Material.category))
    )
    material = mat_result.scalar_one_or_none()
    if not material:
        raise ValueError(f"物料不存在: {material_id}")

    # 查询所有有此物料报价的活跃供应商
    quotations_result = await db.execute(
        select(Quotation)
        .where(Quotation.material_id == material_id)
        .options(selectinload(Quotation.supplier))
        .order_by(Quotation.unit_price.asc())
    )
    quotations = list(quotations_result.scalars().all())

    suppliers_availability: list[dict] = []
    total_available = 0.0

    for q in quotations:
        supplier = q.supplier
        if not supplier or not supplier.is_active:
            continue

        # 基于该供应商对此物料的在途/已下订单量估算可用库存
        # 查询该供应商已确认但未交付的订单中此物料的总量
        in_transit_result = await db.execute(
            select(func.coalesce(func.sum(OrderLine.quantity), 0))
            .select_from(OrderLine)
            .join(ProcurementOrder, ProcurementOrder.id == OrderLine.order_id)
            .where(
                OrderLine.material_id == material_id,
                ProcurementOrder.supplier_id == supplier.id,
                ProcurementOrder.status.in_(["confirmed", "shipped"]),
            )
        )
        in_transit_quantity = float(in_transit_result.scalar() or 0)

        # 从报价中推算基础可用库存（unit_price 作为参考，数量使用报价 quantity）
        base_stock = q.quantity * 10  # 简化估算
        available = max(0, base_stock - in_transit_quantity)

        suppliers_availability.append({
            "supplier_id": supplier.id,
            "supplier_name": supplier.name,
            "supplier_rating": supplier.rating,
            "available_quantity": round(available, 2),
            "lead_time_days": q.delivery_days,
            "unit_price": q.unit_price,
            "next_delivery_date": None,  # 从报价中无法直接推断，需要额外数据源
            "in_transit_quantity": round(in_transit_quantity, 2),
        })
        total_available += available

    return {
        "material_id": material_id,
        "material_name": material.name,
        "material_sku": material.sku,
        "material_unit": material.unit,
        "category": material.category.name if material.category else None,
        "total_available": round(total_available, 2),
        "supplier_count": len(suppliers_availability),
        "suppliers": suppliers_availability,
    }
