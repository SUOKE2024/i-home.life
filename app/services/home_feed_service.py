"""首页 Feed 服务 — 将项目现有数据组合为 A2UI 卡片流

「空间即导航」×「时间叙事」落地：首页「管家主动卡片」feed 的 A2UI 数据源。
卡片全部来自现有业务表（诚实标注：UI 明示「按现有数据生成」，不伪造）：

| A2UI 卡片类型       | 数据来源                     |
|---------------------|------------------------------|
| alert_card          | progress_alerts（未解决）     |
| design_plan         | 当前激活户型方案             |
| construction_progress | 里程碑跟踪记录             |
| budget_breakdown    | 预算 + 预算明细              |
| procurement_order   | 最近采购订单                 |
| qa_report           | 最近质检评估汇总             |
| settlement_summary  | 结算记录                     |
| material_card       | 在库材料                     |
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.budget import Budget, BudgetLine
from app.models.floorplan import FloorPlan
from app.models.material import Material, MaterialCategory
from app.models.procurement import ProcurementOrder
from app.models.progress_alert import MilestoneTracker, ProgressAlert
from app.models.project import Project
from app.models.quality import QualityAssessment
from app.models.settlement import Settlement
from app.services.a2ui_schema import (
    AlertCardData,
    BudgetBreakdownData,
    ConstructionProgressData,
    DesignPlanData,
    MaterialCardData,
    ProcurementOrderData,
    QAReportData,
    SettlementSummaryData,
)

# 业务时区（北京时间，对齐 a2ui_schema._BJ_TZ）
_BJ_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")

# 默认 feed 卡片数量上限（每种类型各取最新 1 张 + 未解决预警取前 N）
_MAX_ALERT_CARDS = 3


def _safe_float(value, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _date_str(value: datetime | None) -> str:
    if not value:
        return ""
    return value.astimezone(_BJ_TZ).strftime("%Y-%m-%d")


# ═══════════════════════════════════════════
# 各类型卡片组合
# ═══════════════════════════════════════════

def _alert_card(alert: ProgressAlert) -> dict:
    data = AlertCardData(
        alert_type=alert.alert_type or "delay",
        severity=alert.severity or "medium",
        title=f"进度预警 · {alert.phase or '施工'}",
        message=alert.message or "",
        source_agent="health_os",
        actions=[{"label": "问管家", "action": "ask_agent", "variant": "primary"}],
    )
    return data.to_card()


def _design_card(project_name: str, plan: FloorPlan) -> dict:
    rooms: list[dict] = []
    try:
        parsed = json.loads(plan.data or "{}")
    except (json.JSONDecodeError, TypeError):
        parsed = {}
    if isinstance(parsed, dict):
        raw_rooms = parsed.get("rooms")
        if isinstance(raw_rooms, list):
            for r in raw_rooms:
                if not isinstance(r, dict):
                    continue
                rooms.append({
                    "name": r.get("name") or r.get("room_type") or "",
                    "area": round(_safe_float(r.get("area")), 1),
                    "type": r.get("room_type") or r.get("type") or "",
                })
    data = DesignPlanData(
        project_name=project_name,
        floor_layout=plan.name or "未命名方案",
        total_area=_safe_float(plan.total_area),
        rooms=rooms,
        notes="户型数据来自当前户型方案（按现有数据生成）",
    )
    return data.to_card()


def _progress_card(project_name: str, milestones: list[MilestoneTracker]) -> dict:
    phases = []
    done = 0
    for m in milestones:
        completed = m.actual_date is not None or m.status == "completed"
        if completed:
            done += 1
        phases.append({
            "name": m.name or m.milestone_code or "",
            "progress": _safe_float(m.actual_percent, 1.0 if completed else 0.0),
            "status": "completed" if completed else (m.status or "in_progress"),
        })
    overall = (done / len(milestones)) if milestones else 0.0
    data = ConstructionProgressData(
        project_name=project_name,
        overall_progress=round(overall, 3),
        phases=phases,
        updated_at=datetime.now(_BJ_TZ).isoformat(),
    )
    return data.to_card()


def _budget_card(project_name: str, budget: Budget, lines: list[BudgetLine]) -> dict:
    items = [
        {
            "category": line.category or "",
            "name": line.name or "",
            "quantity": line.quantity,
            "unit": line.unit or "项",
            "unit_price": line.unit_price,
            "amount": round(line.actual_amount or line.estimated_amount, 2),
        }
        for line in lines
    ]
    data = BudgetBreakdownData(
        project_name=project_name,
        items=items,
        subtotal=_safe_float(budget.total_estimated),
        tax_rate=0.0,
        tax_amount=0.0,
        total=_safe_float(budget.total_actual) or _safe_float(budget.total_estimated),
        warranty_months=24,
        payment_stages=[],
    )
    return data.to_card()


def _procurement_card(order: ProcurementOrder) -> dict:
    status = order.delivery_status or order.status or "ordered"
    data = ProcurementOrderData(
        order_id=order.id,
        items=[],
        supplier={},
        total_amount=_safe_float(order.total_amount),
        delivery_date=_date_str(order.expected_delivery),
        status=status,
    )
    return data.to_card()


def _qa_card(project_name: str, qa: QualityAssessment) -> dict:
    result_map = {"pass": "pass", "fail": "fail"}
    overall = "pending"
    if qa.verdict in ("excellent", "pass", "conditional_pass"):
        overall = "pass"
    elif qa.verdict == "fail":
        overall = "fail"
    checkpoints = [{
        "name": qa.phase or "质检汇总",
        "result": result_map.get(qa.verdict, "pending"),
        "standard": f"共 {qa.total_items} 项检查",
        "actual": f"通过 {qa.passed} / 未通过 {qa.failed}",
    }]
    data = QAReportData(
        project_name=project_name,
        checkpoints=checkpoints,
        overall_result=overall,
        inspector=qa.assessor or "",
        failed_count=qa.failed,
        passed_count=qa.passed,
    )
    return data.to_card()


def _settlement_card(project_name: str, settlement: Settlement) -> dict:
    data = SettlementSummaryData(
        project_name=project_name,
        total_amount=_safe_float(settlement.contract_amount),
        paid_amount=_safe_float(settlement.actual_amount),
        balance_amount=_safe_float(settlement.payable_amount),
        payment_history=[],
        next_payment={},
        settlement_status=settlement.status or "in_progress",
    )
    return data.to_card()


def _material_card(material: Material, category_name: str) -> dict:
    data = MaterialCardData(
        name=material.name or "",
        category=category_name,
        specs=material.spec or "",
        unit_price=_safe_float(material.unit_price),
        unit=material.unit or "件",
        supplier=material.brand or "",
        stock_status="in_stock",
        image_url=material.image_url or "",
        description=material.description or "",
    )
    return data.to_card()


# ═══════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════

async def build_feed_cards(db: AsyncSession, project_id: str) -> list[dict]:
    """将项目现有数据组合为 A2UI 卡片流（诚实标注：全部来自真实业务表）。

    Returns:
        A2UI 卡片列表（每种类型至多 1 张，预警最多 _MAX_ALERT_CARDS 张）
    """
    project = await db.get(Project, project_id)
    project_name = project.name if project else ""

    cards: list[dict] = []

    # 1) alert_card ← 未解决进度预警
    alert_result = await db.execute(
        select(ProgressAlert)
        .where(
            ProgressAlert.project_id == project_id,
            ProgressAlert.status != "resolved",
        )
        .order_by(ProgressAlert.updated_at.desc())
        .limit(_MAX_ALERT_CARDS)
    )
    alerts = list(alert_result.scalars().all())
    cards.extend(_alert_card(a) for a in alerts)

    # 2) design_plan ← 当前激活户型方案
    plan_result = await db.execute(
        select(FloorPlan)
        .where(FloorPlan.project_id == project_id, FloorPlan.is_active.is_(True))
        .order_by(FloorPlan.updated_at.desc())
        .limit(1)
    )
    plan = plan_result.scalar_one_or_none()
    if plan is not None:
        cards.append(_design_card(project_name, plan))

    # 3) construction_progress ← 里程碑跟踪
    ms_result = await db.execute(
        select(MilestoneTracker)
        .where(MilestoneTracker.project_id == project_id)
        .order_by(MilestoneTracker.planned_date.asc())
    )
    milestones = list(ms_result.scalars().all())
    if milestones:
        cards.append(_progress_card(project_name, milestones))

    # 4) budget_breakdown ← 预算 + 明细
    budget_result = await db.execute(
        select(Budget).where(Budget.project_id == project_id)
    )
    budget = budget_result.scalar_one_or_none()
    if budget is not None:
        lines_result = await db.execute(
            select(BudgetLine).where(BudgetLine.budget_id == budget.id)
        )
        cards.append(_budget_card(project_name, budget, list(lines_result.scalars().all())))

    # 5) procurement_order ← 最近采购订单
    order_result = await db.execute(
        select(ProcurementOrder)
        .where(ProcurementOrder.project_id == project_id)
        .order_by(ProcurementOrder.updated_at.desc())
        .limit(1)
    )
    order = order_result.scalar_one_or_none()
    if order is not None:
        cards.append(_procurement_card(order))

    # 6) qa_report ← 最近质检评估
    qa_result = await db.execute(
        select(QualityAssessment)
        .where(QualityAssessment.project_id == project_id)
        .order_by(QualityAssessment.created_at.desc())
        .limit(1)
    )
    qa = qa_result.scalar_one_or_none()
    if qa is not None:
        cards.append(_qa_card(project_name, qa))

    # 7) settlement_summary ← 结算记录（取 contract_amount 最大的）
    st_result = await db.execute(
        select(Settlement).where(Settlement.project_id == project_id)
    )
    settlements = list(st_result.scalars().all())
    if settlements:
        latest = max(settlements, key=lambda s: _safe_float(s.contract_amount))
        cards.append(_settlement_card(project_name, latest))

    # 8) material_card ← 首个在库材料
    mat_result = await db.execute(
        select(Material)
        .where(Material.is_active.is_(True), Material.deleted_at.is_(None))
        .order_by(Material.created_at.asc())
        .limit(1)
    )
    material = mat_result.scalar_one_or_none()
    if material is not None:
        category_name = ""
        cat = await db.get(MaterialCategory, material.category_id)
        if cat is not None:
            category_name = cat.name or ""
        cards.append(_material_card(material, category_name))

    return cards
