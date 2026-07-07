"""F33/F34 增强服务层 — AI 比价 + 担保支付 + 物流追踪 + 样品索要"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.material import BOMItem, Material, MaterialCategory
from app.models.procurement import Supplier, Quotation, ProcurementOrder
from app.models.procurement_enhanced import (
    PriceComparison,
    PriceComparisonItem,
    EscrowPayment,
    LogisticsTracking,
    SampleRequest,
)


# ── 通用工具 ──

async def _gen_no(prefix: str) -> str:
    """生成业务单号: PREFIX-YYYYMMDD-XXXXXXXX"""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    short = uuid.uuid4().hex[:8].upper()
    return f"{prefix}-{today}-{short}"


# ── F33 比价报告 ──

# 评分权重: 价格 40% + 交期 25% + 库存 15% + 评分 20%
WEIGHT_PRICE = 0.40
WEIGHT_DELIVERY = 0.25
WEIGHT_STOCK = 0.15
WEIGHT_RATING = 0.20


def rank_quotations(quotations: list[dict]) -> list[dict]:
    """报价排名（综合评分）。

    输入: [{supplier_id, supplier_name, price, delivery_days, in_stock, rating}]
    输出: 按综合分降序排列，并补充 score 字段。
    """
    if not quotations:
        return []

    prices = [q["price"] for q in quotations if q.get("price", 0) > 0]
    if not prices:
        return quotations

    max_price = max(prices)
    min_delivery = min((q.get("delivery_days", 7) for q in quotations), default=7)
    max_delivery = max((q.get("delivery_days", 7) for q in quotations), default=7)

    rated = []
    for q in quotations:
        price = q.get("price", 0.0)
        delivery = q.get("delivery_days", 7)
        in_stock = bool(q.get("in_stock", True))
        rating = float(q.get("rating", 3.0))

        # 价格分: 越低越高 (与最高价比)
        price_score = (1 - (price / max_price)) if max_price > 0 else 0.0
        # 交期分: 越短越高
        if max_delivery > min_delivery:
            delivery_score = 1 - (delivery - min_delivery) / (max_delivery - min_delivery)
        else:
            delivery_score = 1.0
        # 库存分
        stock_score = 1.0 if in_stock else 0.0
        # 评分 (rating 0-5 → 0-1)
        rating_score = rating / 5.0

        total = (
            WEIGHT_PRICE * price_score
            + WEIGHT_DELIVERY * delivery_score
            + WEIGHT_STOCK * stock_score
            + WEIGHT_RATING * rating_score
        )
        new_q = dict(q)
        new_q["score"] = round(total * 100, 2)
        rated.append(new_q)

    rated.sort(key=lambda x: x["score"], reverse=True)
    return rated


def compute_savings(comparison_items: list) -> float:
    """计算节省金额（对比每个 item 的最高报价 vs 推荐报价）。"""
    total = 0.0
    for item in comparison_items:
        quotes = getattr(item, "quotations", None) or []
        if not quotes:
            continue
        prices = [q.get("price", 0.0) for q in quotes if q.get("price", 0) > 0]
        if not prices:
            continue
        max_price = max(prices)
        recommended = getattr(item, "recommended_price", 0.0) or 0.0
        quantity = getattr(item, "quantity", 1.0) or 1.0
        if max_price > 0 and recommended > 0:
            total += (max_price - recommended) * quantity
    return round(total, 2)


async def ai_match_suppliers(
    db: AsyncSession,
    bom_item: BOMItem,
    location: str | None = None,
) -> dict:
    """AI 供应商匹配。

    基于：物料类型/规格/数量 + 供应商专长(category) + 历史评分 + 库存状态。
    返回: {material_name, matched_suppliers: [...], recommended_supplier_id, reason}
    """
    # 取出物料信息
    mat_result = await db.execute(
        select(Material).where(Material.id == bom_item.material_id)
    )
    material = mat_result.scalar_one_or_none()
    if not material:
        return {
            "material_name": "未知物料",
            "matched_suppliers": [],
            "recommended_supplier_id": None,
            "reason": "物料不存在",
        }

    # 取出物料品类
    cat_result = await db.execute(
        select(MaterialCategory).where(MaterialCategory.id == material.category_id)
    )
    category = cat_result.scalar_one_or_none()
    category_code = category.code if category else "unknown"

    # 匹配同品类、激活状态的供应商
    sup_stmt = select(Supplier).where(
        Supplier.is_active == True,
        Supplier.category == category_code,
    ).order_by(Supplier.rating.desc())
    sup_result = await db.execute(sup_stmt)
    suppliers = list(sup_result.scalars().all())

    # 若同品类无供应商，则放宽到全部活跃供应商
    if not suppliers:
        all_result = await db.execute(
            select(Supplier).where(Supplier.is_active == True).order_by(Supplier.rating.desc())
        )
        suppliers = list(all_result.scalars().all())

    # 构造候选报价（基于物料基准价上下浮动，模拟市场报价）
    base_price = material.unit_price or 100.0
    candidates = []
    for idx, sup in enumerate(suppliers):
        # 不同供应商给出不同折扣 (5%~15%)
        discount = 0.95 - (idx % 4) * 0.03
        price = round(base_price * discount, 2)
        # 交期 3-10 天，按供应商评分倒序越短
        delivery = max(3, 10 - int(sup.rating))
        # 库存状态：评分高的供应商更可能有库存
        in_stock = sup.rating >= 4.0
        candidates.append({
            "supplier_id": sup.id,
            "supplier_name": sup.name,
            "price": price,
            "delivery_days": delivery,
            "in_stock": in_stock,
            "rating": sup.rating,
        })

    # 综合评分排名
    ranked = rank_quotations(candidates)

    # 地域偏好（如指定 location，则匹配 address 含该关键字的优先）
    if location and ranked:
        loc_lower = location.lower()
        for r in ranked:
            addr = ""
            sup_match = next((s for s in suppliers if s.id == r["supplier_id"]), None)
            if sup_match and sup_match.address:
                addr = sup_match.address.lower()
            r["location_match"] = int(bool(loc_lower) and loc_lower in addr)

    recommended_id = ranked[0]["supplier_id"] if ranked else None
    reason = None
    if ranked:
        top = ranked[0]
        reason = (
            f"综合评分最高({top['score']}): 价格 ¥{top['price']}、交期 {top['delivery_days']} 天、"
            f"{'有库存' if top.get('in_stock') else '无库存'}、评分 {top.get('rating', 0)}"
        )

    return {
        "material_name": material.name,
        "matched_suppliers": ranked,
        "recommended_supplier_id": recommended_id,
        "reason": reason,
    }


async def generate_comparison_from_bom(
    db: AsyncSession,
    project_id: str,
    bom_id: str | None = None,
) -> PriceComparison:
    """从 BOM 生成比价报告。

    - 遍历 BOM 物料，匹配供应商、收集报价
    - 评分算法: 价格 40% + 交期 25% + 库存 15% + 评分 20%
    - 推荐最优供应商组合（可能跨供应商）
    """
    # 查询 BOM 物料列表
    bom_stmt = (
        select(BOMItem)
        .where(BOMItem.project_id == project_id)
        .options(selectinload(BOMItem.material))
    )
    if bom_id:
        # 如果指定 bom_id, 当前模型 BOMItem 没有 bom_id 字段，使用 id 限定
        bom_stmt = bom_stmt.where(BOMItem.id == bom_id)
    bom_result = await db.execute(bom_stmt)
    bom_items = list(bom_result.scalars().all())

    if not bom_items:
        raise ValueError("BOM 物料为空，无法生成比价报告")

    # 创建比价报告
    report_no = await _gen_no("PC")
    comparison = PriceComparison(
        project_id=project_id,
        bom_id=bom_id,
        report_no=report_no,
        item_count=len(bom_items),
        status="draft",
    )
    db.add(comparison)
    await db.flush()

    supplier_set: set[str] = set()
    total_quotes = 0

    for bom_item in bom_items:
        match_result = await ai_match_suppliers(db, bom_item)
        ranked = match_result["matched_suppliers"]

        # 推荐排名第一的供应商
        recommended_id = match_result.get("recommended_supplier_id")
        recommended_price = ranked[0]["price"] if ranked else 0.0
        max_price = max((q["price"] for q in ranked), default=0.0)
        savings = 0.0
        if max_price > 0 and recommended_price > 0:
            savings = round((max_price - recommended_price) * bom_item.quantity, 2)

        if recommended_id:
            supplier_set.add(recommended_id)
        total_quotes += len(ranked)

        item = PriceComparisonItem(
            comparison_id=comparison.id,
            bom_item_id=bom_item.id,
            material_name=bom_item.material.name if bom_item.material else "未知物料",
            spec=bom_item.material.spec if bom_item.material else None,
            quantity=bom_item.quantity,
            unit=bom_item.material.unit if bom_item.material else "piece",
            quotations=ranked,
            recommended_supplier_id=recommended_id,
            recommended_price=recommended_price,
            savings_per_item=savings,
        )
        db.add(item)

    # 统计节省金额
    items_result = await db.execute(
        select(PriceComparisonItem).where(PriceComparisonItem.comparison_id == comparison.id)
    )
    items_list = list(items_result.scalars().all())
    total_savings = compute_savings(items_list)

    # 推荐供应商：被推荐次数最多的供应商
    recommended_supplier_id = None
    if items_list:
        rec_counts: dict[str, int] = {}
        for it in items_list:
            if it.recommended_supplier_id:
                rec_counts[it.recommended_supplier_id] = rec_counts.get(it.recommended_supplier_id, 0) + 1
        if rec_counts:
            recommended_supplier_id = max(rec_counts, key=rec_counts.get)

    comparison.supplier_count = len(supplier_set)
    comparison.total_quotes = total_quotes
    comparison.total_savings = total_savings
    comparison.recommended_supplier_id = recommended_supplier_id
    comparison.status = "completed"

    await db.commit()
    await db.refresh(comparison)
    return comparison


async def get_comparison(db: AsyncSession, comparison_id: str) -> PriceComparison | None:
    result = await db.execute(
        select(PriceComparison)
        .where(PriceComparison.id == comparison_id)
        .options(selectinload(PriceComparison.items))
    )
    return result.scalar_one_or_none()


async def list_project_comparisons(db: AsyncSession, project_id: str) -> list[PriceComparison]:
    result = await db.execute(
        select(PriceComparison)
        .where(PriceComparison.project_id == project_id)
        .order_by(PriceComparison.created_at.desc())
    )
    return list(result.scalars().all())


async def list_comparison_items(db: AsyncSession, comparison_id: str) -> list[PriceComparisonItem]:
    result = await db.execute(
        select(PriceComparisonItem)
        .where(PriceComparisonItem.comparison_id == comparison_id)
        .order_by(PriceComparisonItem.created_at.asc())
    )
    return list(result.scalars().all())


async def delete_comparison(db: AsyncSession, comparison_id: str) -> bool:
    result = await db.execute(select(PriceComparison).where(PriceComparison.id == comparison_id))
    comparison = result.scalar_one_or_none()
    if not comparison:
        return False
    await db.delete(comparison)
    await db.commit()
    return True


# ── F34 担保支付 ──

ESCROW_FEE_RATE = 0.005  # 担保手续费 0.5%


async def create_escrow_payment(db: AsyncSession, order_id: str) -> EscrowPayment:
    """创建担保支付（基于订单金额）。"""
    order_result = await db.execute(
        select(ProcurementOrder).where(ProcurementOrder.id == order_id)
    )
    order = order_result.scalar_one_or_none()
    if not order:
        raise ValueError("订单不存在")

    escrow_no = await _gen_no("ES")
    total_amount = order.total_amount or 0.0
    fee = round(total_amount * ESCROW_FEE_RATE, 2)

    payment = EscrowPayment(
        order_id=order_id,
        project_id=order.project_id,
        escrow_no=escrow_no,
        total_amount=total_amount,
        escrow_fee=fee,
        status="pending",
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return payment


async def get_escrow(db: AsyncSession, escrow_id: str) -> EscrowPayment | None:
    result = await db.execute(select(EscrowPayment).where(EscrowPayment.id == escrow_id))
    return result.scalar_one_or_none()


async def buyer_pay(db: AsyncSession, escrow_id: str) -> EscrowPayment | None:
    """买家付款（资金进入平台担保账户）。"""
    payment = await get_escrow(db, escrow_id)
    if not payment:
        return None
    if payment.status not in ("pending",):
        raise ValueError(f"当前状态 {payment.status} 不允许付款")
    payment.buyer_paid = True
    payment.buyer_paid_at = datetime.now(timezone.utc)
    payment.status = "buyer_paid"
    await db.commit()
    await db.refresh(payment)
    return payment


async def release_to_supplier(db: AsyncSession, escrow_id: str) -> EscrowPayment | None:
    """确认收货后释放资金给供应商。"""
    payment = await get_escrow(db, escrow_id)
    if not payment:
        return None
    if payment.status != "buyer_paid":
        raise ValueError(f"当前状态 {payment.status} 不允许释放资金，需先买家付款")
    payment.supplier_received = True
    payment.supplier_received_at = datetime.now(timezone.utc)
    payment.status = "supplier_received"
    await db.commit()
    await db.refresh(payment)
    return payment


async def request_refund(db: AsyncSession, escrow_id: str, reason: str) -> EscrowPayment | None:
    """申请退款。允许 buyer_paid → refunded 或 disputed → refunded。"""
    payment = await get_escrow(db, escrow_id)
    if not payment:
        return None
    if payment.status not in ("buyer_paid", "disputed"):
        # 已释放或已退款的不能退款
        raise ValueError(f"当前状态 {payment.status} 不允许退款")
    payment.status = "refunded"
    payment.dispute_reason = reason
    await db.commit()
    await db.refresh(payment)
    return payment


async def request_dispute(db: AsyncSession, escrow_id: str, reason: str) -> EscrowPayment | None:
    """发起争议。buyer_paid → disputed。"""
    payment = await get_escrow(db, escrow_id)
    if not payment:
        return None
    if payment.status != "buyer_paid":
        raise ValueError(f"当前状态 {payment.status} 不允许发起争议")
    payment.status = "disputed"
    payment.dispute_reason = reason
    await db.commit()
    await db.refresh(payment)
    return payment


async def resolve_dispute(db: AsyncSession, escrow_id: str, resolution: str) -> EscrowPayment | None:
    """解决争议。disputed → refunded 或 disputed → supplier_received。"""
    payment = await get_escrow(db, escrow_id)
    if not payment:
        return None
    if payment.status != "disputed":
        raise ValueError(f"当前状态 {payment.status} 不允许解决争议")
    if resolution == "refunded":
        payment.status = "refunded"
    elif resolution == "supplier_received":
        payment.status = "supplier_received"
        payment.supplier_received = True
        payment.supplier_received_at = datetime.now(timezone.utc)
    else:
        raise ValueError("resolution 必须为 refunded 或 supplier_received")
    await db.commit()
    await db.refresh(payment)
    return payment


# ── F34 物流追踪 ──

# 承运商平均时效 (天数)
CARRIER_BASE_DAYS = {
    "sf_express": 2,
    "yt_express": 3,
    "zto": 3,
    "sto": 3,
    "jd_logistics": 2,
    "debon": 4,
    "self_delivery": 1,
}


def compute_eta(tracking: LogisticsTracking) -> datetime | None:
    """计算预计到达时间（基于承运商和起止地）。"""
    base_days = CARRIER_BASE_DAYS.get(tracking.carrier, 5)
    # 起止地不同省份额外加 1 天
    extra = 0
    if tracking.ship_from and tracking.ship_to:
        if tracking.ship_from[:2] != tracking.ship_to[:2]:
            extra = 1
    return datetime.now(timezone.utc) + timedelta(days=base_days + extra)


async def create_logistics(
    db: AsyncSession,
    order_id: str,
    carrier: str,
    ship_from: str | None = None,
    ship_to: str | None = None,
) -> LogisticsTracking:
    """创建物流单。"""
    order_result = await db.execute(
        select(ProcurementOrder).where(ProcurementOrder.id == order_id)
    )
    order = order_result.scalar_one_or_none()
    if not order:
        raise ValueError("订单不存在")

    tracking_no = await _gen_no("LG")
    tracking = LogisticsTracking(
        order_id=order_id,
        project_id=order.project_id,
        tracking_no=tracking_no,
        carrier=carrier,
        ship_from=ship_from,
        ship_to=ship_to,
        status="pending",
        tracking_history=[],
    )
    tracking.estimated_arrival = compute_eta(tracking)
    db.add(tracking)
    await db.commit()
    await db.refresh(tracking)
    return tracking


async def get_logistics(db: AsyncSession, tracking_id: str) -> LogisticsTracking | None:
    result = await db.execute(select(LogisticsTracking).where(LogisticsTracking.id == tracking_id))
    return result.scalar_one_or_none()


async def get_order_logistics(db: AsyncSession, order_id: str) -> list[LogisticsTracking]:
    result = await db.execute(
        select(LogisticsTracking)
        .where(LogisticsTracking.order_id == order_id)
        .order_by(LogisticsTracking.created_at.desc())
    )
    return list(result.scalars().all())


async def update_tracking(
    db: AsyncSession,
    tracking_id: str,
    status: str | None = None,
    location: str | None = None,
    description: str | None = None,
) -> LogisticsTracking | None:
    """更新物流轨迹。"""
    tracking = await get_logistics(db, tracking_id)
    if not tracking:
        return None

    now = datetime.now(timezone.utc)
    # 创建新列表以确保 SQLAlchemy 检测到 JSON 字段变更
    history = list(tracking.tracking_history or [])
    history.append({
        "timestamp": now.isoformat(),
        "location": location or "",
        "status": status or tracking.status,
        "description": description or "",
    })
    tracking.tracking_history = history

    if status:
        tracking.status = status
        if status == "delivered":
            tracking.actual_arrival = now

    await db.commit()
    await db.refresh(tracking)
    return tracking


# ── F34 样品索要 ──

async def request_sample(
    db: AsyncSession,
    project_id: str,
    supplier_id: str,
    material_id: str | None = None,
    sample_type: str = "实物",
    notes: str | None = None,
) -> SampleRequest:
    """样品索要。"""
    sample = SampleRequest(
        project_id=project_id,
        supplier_id=supplier_id,
        material_id=material_id,
        sample_type=sample_type,
        status="requested",
        notes=notes,
    )
    db.add(sample)
    await db.commit()
    await db.refresh(sample)
    return sample


async def get_sample(db: AsyncSession, sample_id: str) -> SampleRequest | None:
    result = await db.execute(select(SampleRequest).where(SampleRequest.id == sample_id))
    return result.scalar_one_or_none()


async def list_project_samples(db: AsyncSession, project_id: str) -> list[SampleRequest]:
    result = await db.execute(
        select(SampleRequest)
        .where(SampleRequest.project_id == project_id)
        .order_by(SampleRequest.created_at.desc())
    )
    return list(result.scalars().all())


async def update_sample_status(
    db: AsyncSession,
    sample_id: str,
    new_status: str,
    notes: str | None = None,
) -> SampleRequest | None:
    """更新样品状态。"""
    sample = await get_sample(db, sample_id)
    if not sample:
        return None
    sample.status = new_status
    if notes is not None:
        sample.notes = notes
    if new_status == "shipped":
        sample.shipped_at = datetime.now(timezone.utc)
    elif new_status == "received":
        sample.received_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(sample)
    return sample
