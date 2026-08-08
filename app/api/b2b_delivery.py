"""B2B 装企交付 API（v1.4.x，借鉴"卖结果不卖功能"的交付式产品）

面向装企/工作室：一次请求拿到「设计方案 + 报价 + 施工计划」整包交付，
而非零散功能 API。能力演进：
- 交付单订单化：整包快照落库，可追溯/可流转（状态机 + 用户强隔离）
- 对接真实项目：project_id 关联项目，报价档优先用项目真实 Budget/BudgetLine
- 异步生成：async_mode=true 时立即返回 generating，后台任务填充整包
- 各交付块诚实标注来源：
  - design: llm | fallback（复用 design_proposal_service）
  - budget: db（项目真实预算）| estimated（确定性分档估算）
  - construction: estimated（确定性工期估算，含 ≥10% 缓冲对齐 HC-004）
- feature flag: settings.b2b_delivery_enabled

用法::

    POST /api/b2b/delivery
    {
      "name": "三室两厅整装交付",
      "area": 120, "style": "modern", "budget": 250000,
      "project_id": "p1",              # 可选：关联真实项目（报价走真实预算）
      "async_mode": false,             # 可选：true=立即返回 generating 后台生成
      "requirements": "主卧带衣帽间", "rooms": "客厅,主卧,次卧,厨房,卫生间"
    }
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.delivery_order import DeliveryOrder, ALL_STATUSES
from app.models.user import User

router = APIRouter(prefix="/b2b", tags=["B2B 装企交付"])

settings = get_settings()
logger = logging.getLogger(__name__)

# 业务时区（平台业务时区为北京时间，对齐 agent_context_service._DEFAULT_TZ）
_BJ_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")

# 施工阶段（确定性工期估算，天数为 100㎡ 基准，按面积系数缩放）
_PHASE_PLAN = [
    ("preparation", "准备阶段", 3),
    ("demolition", "拆改阶段", 5),
    ("water_electricity", "水电阶段", 8),
    ("masonry", "泥瓦阶段", 12),
    ("carpentry", "木工阶段", 8),
    ("painting", "油漆阶段", 8),
    ("installation", "安装阶段", 5),
    ("inspection", "验收阶段", 3),
]
# 面积缩放系数（120㎡ = 1.0 基准）
_AREA_BASE = 120.0
# HC-004：工期须含 ≥10% 缓冲
_BUFFER_RATIO = 0.1


class DeliveryRequest(BaseModel):
    name: str = Field("整装交付", max_length=200)
    area: float = Field(..., gt=0, le=10000, description="建筑面积（平方米）")
    style: str = Field("modern", max_length=50, description="风格：modern/nordic/japanese/luxury/chinese")
    budget: float = Field(0, ge=0, description="业主预算（元），0=不限定")
    requirements: str = Field("", max_length=2000, description="设计需求补充")
    rooms: str = Field("客厅,卧室,厨房,卫生间", max_length=200, description="房间列表，逗号分隔")
    # v1.4.x 对接真实项目：关联后报价档走项目真实预算（source=db）
    project_id: str | None = Field(None, description="关联项目 ID（可选，需项目归属校验）")
    # v1.4.x 异步生成：立即返回 generating，后台任务填充整包
    async_mode: bool = Field(False, description="异步模式：true=立即返回，后台生成整包")


class DeliveryResponse(BaseModel):
    delivery_id: str
    delivery_order_id: str | None = None
    status: str = "draft"
    name: str
    summary: str
    proposals: list[dict]
    budget_estimate: dict
    construction_plan: dict
    sources: dict[str, str]
    generated_at: str


class DeliveryListItem(BaseModel):
    delivery_order_id: str
    name: str
    area: float
    style: str
    status: str
    summary: str | None
    created_at: str


class DeliveryStatusUpdate(BaseModel):
    status: str = Field(..., description=f"目标状态，合法值：{', '.join(ALL_STATUSES)}")


# 交付单状态机（QM"可还原"：交付进度可追踪、可回滚）
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "generating": {"draft", "cancelled"},  # 异步生成中 → 完成(草稿) / 失败(取消)
    "draft": {"quoted", "cancelled"},
    "quoted": {"accepted", "cancelled"},
    "accepted": {"in_construction", "cancelled"},
    "in_construction": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


def _order_to_dict(order: DeliveryOrder) -> dict:
    """序列化交付单（供列表/详情返回）。"""
    return {
        "delivery_order_id": order.id,
        "project_id": order.project_id,
        "name": order.name,
        "area": order.area,
        "style": order.style,
        "budget": order.budget,
        "requirements": order.requirements,
        "status": order.status,
        "summary": order.summary,
        "proposals": order.proposals,
        "budget_estimate": order.budget_estimate,
        "construction_plan": order.construction_plan,
        "sources": order.sources,
        "created_at": order.created_at.isoformat() if order.created_at else "",
        "updated_at": order.updated_at.isoformat() if order.updated_at else "",
    }


# ── 报价：项目真实预算优先，无则确定性估算（诚实降级）──


async def _estimate_budget(db: AsyncSession, data: DeliveryRequest) -> dict:
    """报价档：关联项目且有真实 Budget/BudgetLine → source=db；否则估算。"""
    if data.project_id:
        from app.models.budget import Budget, BudgetLine
        try:
            stmt = (
                select(Budget, BudgetLine)
                .join(BudgetLine, BudgetLine.budget_id == Budget.id, isouter=True)
                .where(Budget.project_id == data.project_id, Budget.deleted_at.is_(None))
            )
            rows = (await db.execute(stmt)).all()
            if rows and rows[0][0] is not None:
                budget = rows[0][0]
                lines = [r[1] for r in rows if r[1] is not None]
                by_category: dict[str, float] = {}
                for line in lines:
                    by_category[line.category] = by_category.get(line.category, 0.0) + line.estimated_amount
                return {
                    "source": "db",
                    "project_id": data.project_id,
                    "area": data.area,
                    "style": data.style,
                    "total_estimated": round(budget.total_estimated, 2),
                    "status": budget.status,
                    "line_count": len(lines),
                    "breakdown_by_category": {k: round(v, 2) for k, v in by_category.items()},
                }
        except Exception as e:
            logger.warning("b2b_delivery: 项目真实预算查询失败，降级估算: %s", e)
    return _estimate_budget_fallback(data.area, data.style, data.budget)


def _estimate_budget_fallback(area: float, style: str, budget_limit: float) -> dict:
    """确定性分档报价估算（source=estimated，与 _tool_get_budget 一致口径）"""
    total_by_tier: dict[str, int] = {
        "economy": round(area * 1000),
        "comfort": round(area * 1600),
        "quality": round(area * 2750),
        "luxury": round(area * 5000),
    }
    tiers = {
        "economy": {"label": "经济型", "price_per_sqm": "800-1200元/㎡", "total_estimate": total_by_tier["economy"]},
        "comfort": {"label": "舒适型", "price_per_sqm": "1200-2000元/㎡", "total_estimate": total_by_tier["comfort"]},
        "quality": {"label": "品质型", "price_per_sqm": "2000-3500元/㎡", "total_estimate": total_by_tier["quality"]},
        "luxury": {"label": "豪华型", "price_per_sqm": "3500元/㎡以上", "total_estimate": total_by_tier["luxury"]},
    }
    breakdown_ratio = {
        "硬装（水电+墙面+地面）": 0.42,
        "定制柜体": 0.18,
        "软装+家电": 0.30,
        "管理费+其他": 0.10,
    }
    best_tier = None
    if budget_limit > 0:
        for key, total in total_by_tier.items():
            if total <= budget_limit:
                best_tier = key
    return {
        "source": "estimated",
        "area": area,
        "style": style,
        "tiers": tiers,
        "breakdown_ratio": breakdown_ratio,
        "recommended_tier": best_tier or "comfort",
    }


# ── 施工计划（确定性估算，含 ≥10% 缓冲，对齐 HC-004）──


def _estimate_construction(area: float) -> dict:
    scale = max(0.6, min(1.5, area / _AREA_BASE))
    phases = []
    base_total = 0
    for code, name, days in _PHASE_PLAN:
        d = max(1, round(days * scale))
        base_total += d
        phases.append({"phase_code": code, "name": name, "days": d})
    buffer_days = round(base_total * _BUFFER_RATIO)
    return {
        "source": "estimated",
        "total_days": base_total + buffer_days,
        "buffer_days": buffer_days,
        "buffer_ratio": _BUFFER_RATIO,
        "phases": phases,
        "note": "工期为确定性估算，含 ≥10% 缓冲；实际以现场排期为准",
    }


def _build_summary(data: DeliveryRequest, design_source: str, budget_estimate: dict, total_days: int) -> str:
    """整包摘要：报价描述随来源变化（真实预算 / 推荐档位），诚实区分。"""
    rooms = data.rooms or "全屋"
    if budget_estimate.get("source") == "db":
        budget_desc = (
            f"基于项目真实预算 ¥{budget_estimate['total_estimated']:,.0f}"
            f"（{budget_estimate['line_count']} 项明细）"
        )
    else:
        tier_label = budget_estimate["tiers"][budget_estimate["recommended_tier"]]["label"]
        budget_desc = f"推荐 {tier_label} 报价档"
    return (
        f"「{data.name}」交付方案已生成：{data.area}㎡（{rooms}），{data.style} 风格。"
        f"共 {design_source} 套设计备选，{budget_desc}，"
        f"预计工期 {total_days} 天（含缓冲）。装企可直接将本方案作为交付初稿推进。"
    )


# ── 整包生成（同步路径与异步后台任务共用）──


async def _generate_package_payload(
    db: AsyncSession, user_id: str, data: DeliveryRequest,
) -> tuple[str, list[dict], dict, dict, dict]:
    """生成整包交付内容（设计方案 + 报价 + 施工计划），各块诚实标注来源。"""
    from app.services.design_proposal_service import generate_proposals

    requirement = data.requirements or f"设计 {data.area}㎡ {data.style} 风格装修方案"
    session_id = f"b2b_{user_id}"
    proposal_set = await generate_proposals(requirement, session_id)
    proposals = [p.model_dump() for p in proposal_set.proposals]
    design_source = "llm" if any(p.get("source") == "llm" for p in proposals) else "fallback"

    budget_estimate = await _estimate_budget(db, data)
    construction_plan = _estimate_construction(data.area)
    summary = _build_summary(data, design_source, budget_estimate, construction_plan["total_days"])
    sources = {
        "design": design_source,
        "budget": budget_estimate["source"],
        "construction": construction_plan["source"],
    }
    return summary, proposals, budget_estimate, construction_plan, sources


async def _run_async_generate(order_id: str, data: DeliveryRequest) -> None:
    """异步后台任务：生成整包并更新交付单。

    v1.4.x 借鉴 voice_task_registry 的进程内后台任务模式（模块化单体单实例假设，
    阿里云 FC 单实例下可用；多实例扩展时应迁移到 Redis 队列）。请求结束后自建
    DB session，避免使用已关闭的请求 session。
    """
    import asyncio
    # 先让出事件循环：待请求响应发送、依赖 teardown 释放请求 session，
    # 避免 SQLite StaticPool 单连接被并发占用（生产 PG 连接池无此问题）。
    await asyncio.sleep(0.05)

    from app.database import async_session

    async with async_session() as db:
        order = await db.get(DeliveryOrder, order_id)
        if order is None:
            return
        try:
            summary, proposals, budget_estimate, construction_plan, sources = (
                await _generate_package_payload(db, order.user_id, data)
            )
            order.summary = summary
            order.proposals = proposals
            order.budget_estimate = budget_estimate
            order.construction_plan = construction_plan
            order.sources = sources
            order.status = "draft"  # generating → draft，随后由用户流转
            await db.commit()
            logger.info("b2b_delivery_async_done: order=%s", order_id)
        except Exception as e:  # noqa: BLE001 — 后台任务必须兜底，不泄漏到事件循环
            logger.warning("b2b_delivery_async_failed: order=%s error=%s", order_id, e)
            order.status = "cancelled"
            await db.commit()


# ── 端点 ──


@router.post("/delivery", response_model=DeliveryResponse)
async def create_delivery(
    data: DeliveryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """生成整包交付：设计方案 + 报价 + 施工计划。

    - 关联 project_id 时校验项目归属（owner/admin），报价档走真实预算
    - async_mode=true 立即返回 generating，后台任务填充整包（GET 详情轮询）
    """
    if not settings.b2b_delivery_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="B2B 交付功能未启用",
        )

    # 项目归属校验（若指定 project_id）
    if data.project_id:
        from app.models.project import Project
        result = await db.execute(select(Project).where(Project.id == data.project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        if current_user.role != "admin" and project.owner_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")

    # 异步模式：立即落库返回 generating，后台生成整包
    if data.async_mode:
        import asyncio
        order = DeliveryOrder(
            user_id=current_user.id,
            project_id=data.project_id,
            name=data.name,
            area=data.area,
            style=data.style,
            budget=data.budget,
            requirements=data.requirements,
            status="generating",
        )
        db.add(order)
        await db.commit()
        await db.refresh(order)
        asyncio.create_task(_run_async_generate(order.id, data))
        return DeliveryResponse(
            delivery_id=order.id,
            delivery_order_id=order.id,
            status=order.status,
            name=data.name,
            summary="",
            proposals=[],
            budget_estimate={},
            construction_plan={},
            sources={},
            generated_at=datetime.now(_BJ_TZ).isoformat(),
        )

    # 同步模式：生成整包并落库
    summary, proposals, budget_estimate, construction_plan, sources = (
        await _generate_package_payload(db, current_user.id, data)
    )
    order = DeliveryOrder(
        user_id=current_user.id,
        project_id=data.project_id,
        name=data.name,
        area=data.area,
        style=data.style,
        budget=data.budget,
        requirements=data.requirements,
        status="draft",
        summary=summary,
        proposals=proposals,
        budget_estimate=budget_estimate,
        construction_plan=construction_plan,
        sources=sources,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    return DeliveryResponse(
        delivery_id=order.id,
        delivery_order_id=order.id,
        status=order.status,
        name=data.name,
        summary=summary,
        proposals=proposals,
        budget_estimate=budget_estimate,
        construction_plan=construction_plan,
        sources=sources,
        generated_at=datetime.now(_BJ_TZ).isoformat(),
    )


async def _get_owned_order(db: AsyncSession, order_id: str, user_id: str) -> DeliveryOrder:
    """按 ID + 归属加载交付单（强隔离 user_id），不存在或非本人 → 404。"""
    result = await db.execute(
        select(DeliveryOrder).where(
            DeliveryOrder.id == order_id,
            DeliveryOrder.user_id == user_id,
        )
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="交付单不存在")
    return order


@router.get("/delivery", response_model=list[DeliveryListItem])
async def list_deliveries(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户的交付单（按创建时间倒序，用户强隔离）。"""
    result = await db.execute(
        select(DeliveryOrder)
        .where(DeliveryOrder.user_id == current_user.id)
        .order_by(DeliveryOrder.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    orders = result.scalars().all()
    return [
        DeliveryListItem(
            delivery_order_id=o.id,
            name=o.name,
            area=o.area,
            style=o.style,
            status=o.status,
            summary=o.summary,
            created_at=o.created_at.isoformat() if o.created_at else "",
        )
        for o in orders
    ]


@router.get("/delivery/{order_id}")
async def get_delivery(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取交付单详情（整包内容快照；异步生成中返回 status=generating）。"""
    order = await _get_owned_order(db, order_id, current_user.id)
    return _order_to_dict(order)


@router.put("/delivery/{order_id}/status")
async def update_delivery_status(
    order_id: str,
    data: DeliveryStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """流转交付单状态（generating→draft→quoted→accepted→in_construction→completed）。

    非法流转返回 422，保证交付进度可追踪、可回滚（QM"可还原"）。
    """
    order = await _get_owned_order(db, order_id, current_user.id)
    target = data.status
    allowed = _ALLOWED_TRANSITIONS.get(order.status, set())
    if target not in ALL_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"非法状态: {target}，合法值: {', '.join(ALL_STATUSES)}",
        )
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"非法状态流转: {order.status} → {target}，允许: {', '.join(sorted(allowed)) or '无'}",
        )
    order.status = target
    await db.commit()
    await db.refresh(order)
    return _order_to_dict(order)
