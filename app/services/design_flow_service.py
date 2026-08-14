"""设计流程编排服务 — 确定性编排 + 状态机

串联「户型 → 风格/预算选供应商 → VR 效果图渲染 → 调整(循环) → 可行性分析」。
LLM 智能体意见作为旁路建议（suggest_adjustment），不阻塞主流程。

设计原则：
1. 供应商匹配、状态流转、渲染触发、可行性聚合全部确定性，可测。
2. 复用 ai_render / vr_panorama / procurement / predictive_maintenance 现有 service。
3. 可行性四维度单维度独立降级（失败标 partial，不影响其它维度）。
4. 诚实降级：mock 报价/占位图显式标注 source，不伪装真实数据。
"""

import json
import logging
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.design_flow import DesignFlow, DesignFlowFeasibility
from app.models.floorplan import FloorPlan
from app.models.material import BOMItem
from app.models.procurement import Supplier
from app.services.ai_render_service import ai_render_service
from app.services.material_service import get_current_bom_version
from app.services.predictive_maintenance_service import analyze_project_risks
from app.services.procurement_service import get_material_availability
from app.services import vr_panorama_service

logger = logging.getLogger(__name__)

# 状态机阶段
STAGE_INIT = "init"
STAGE_SUPPLIER_MATCHED = "supplier_matched"
STAGE_RENDERED = "rendered"
STAGE_CONFIRMED = "confirmed"
STAGE_FEASIBILITY_DONE = "feasibility_done"
STAGE_CANCELLED = "cancelled"

# 供应商选择方式
MODE_RANDOM = "random"
MODE_MANUAL = "manual"

# 预算档位映射（每平米预算，元/㎡，首版硬编码常量）
_PRICE_TIER_ECONOMY_MAX = 1500.0
_PRICE_TIER_STANDARD_MAX = 3000.0

# 施工阶段（确定性工期估算，天数为 100㎡ 基准，按面积系数缩放；对齐 b2b_delivery）
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
_AREA_BASE = 120.0
_BUFFER_RATIO = 0.1


# ── 预算档位与工期 ──


def _derive_price_tier(budget: float, area: float) -> str:
    """按每平米预算推导价格档位（economy / standard / premium）。"""
    if area <= 0:
        area = 1.0
    per_sqm = budget / area
    if per_sqm < _PRICE_TIER_ECONOMY_MAX:
        return "economy"
    if per_sqm <= _PRICE_TIER_STANDARD_MAX:
        return "standard"
    return "premium"


def _estimate_construction(area: float) -> dict:
    """确定性工期估算（含 ≥10% 缓冲）。"""
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


def _loads(raw: str | None) -> dict:
    try:
        return json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


# ── 会话创建与查询 ──


async def get_design_flow(db: AsyncSession, flow_id: str) -> DesignFlow | None:
    result = await db.execute(select(DesignFlow).where(DesignFlow.id == flow_id))
    return result.scalar_one_or_none()


async def _get_floorplan(db: AsyncSession, floorplan_id: str) -> FloorPlan | None:
    result = await db.execute(select(FloorPlan).where(FloorPlan.id == floorplan_id))
    return result.scalar_one_or_none()


async def start_design_flow(
    db: AsyncSession,
    project_id: str,
    floorplan_id: str,
    style: str,
    budget: float,
    supplier_selection_mode: str = MODE_RANDOM,
) -> DesignFlow:
    """创建编排会话，强校验 floorplan 就绪（is_active=True）。"""
    floorplan = await _get_floorplan(db, floorplan_id)
    if not floorplan or floorplan.project_id != project_id:
        raise ValueError("户型不存在或不属于该项目")
    if not floorplan.is_active:
        raise ValueError("户型未就绪（is_active=False）")

    price_tier = _derive_price_tier(budget, floorplan.total_area)
    flow = DesignFlow(
        project_id=project_id,
        floorplan_id=floorplan_id,
        style=style,
        budget=budget,
        price_tier=price_tier,
        supplier_selection_mode=supplier_selection_mode,
        stage=STAGE_INIT,
    )
    db.add(flow)
    await db.commit()
    await db.refresh(flow)
    return flow


# ── 供应商匹配与选择 ──


async def match_suppliers(db: AsyncSession, style: str, price_tier: str) -> list[dict]:
    """按「风格 + 价格档位」硬过滤活跃供应商，按评分降序返回候选。"""
    result = await db.execute(
        select(Supplier)
        .where(Supplier.is_active.is_(True), Supplier.price_tier == price_tier)
        .order_by(Supplier.rating.desc())
    )
    suppliers = list(result.scalars().all())
    matched = [s for s in suppliers if style in s.styles_list]
    return [
        {
            "supplier_id": s.id,
            "name": s.name,
            "category": s.category,
            "rating": s.rating,
            "styles": s.styles_list,
            "price_tier": s.price_tier,
            "address": s.address,
        }
        for s in matched
    ]


async def select_supplier(
    db: AsyncSession,
    flow: DesignFlow,
    mode: str,
    supplier_id: str | None = None,
) -> DesignFlow:
    """随机/自选供应商，写入 flow 并推进 stage。"""
    candidates = await match_suppliers(db, flow.style, flow.price_tier)
    if not candidates:
        raise ValueError("无匹配供应商，请调整风格或预算")

    if mode == MODE_RANDOM:
        chosen = secrets.choice(candidates)
    else:
        chosen = next((c for c in candidates if c["supplier_id"] == supplier_id), None)
        if not chosen:
            raise ValueError("供应商不在匹配候选中")

    flow.supplier_id = chosen["supplier_id"]
    flow.supplier_selection_mode = mode
    flow.stage = STAGE_SUPPLIER_MATCHED
    await db.commit()
    await db.refresh(flow)
    return flow


# ── 渲染与全屋漫游 ──


async def _render_and_set_scene(db: AsyncSession, flow: DesignFlow, user_id: str) -> None:
    """逐房间渲染 2D 效果图 → 落 VRPanorama(content_source=effect) → 组合 VRScene。"""
    floorplan = await _get_floorplan(db, flow.floorplan_id)
    if not floorplan:
        raise ValueError("户型不存在")

    floorplan_dict = _loads(floorplan.data)
    rooms = floorplan_dict.get("rooms", []) or []
    if not rooms:
        raise ValueError("户型无房间数据，无法渲染效果图")

    panorama_ids: list[str] = []
    for room in rooms:
        if not isinstance(room, dict):
            continue
        room_name = room.get("name") or room.get("type") or "房间"
        layout_json = {
            "room": room_name,
            "room_type": room.get("type", ""),
            "area": room.get("area", 0),
            "floorplan": floorplan_dict,
        }
        render_result = await ai_render_service.render_2d(
            layout_json=layout_json,
            style=flow.style,
            user_id=user_id,
            db=db,
            require_real=False,
        )
        image_url = render_result.get("image_url") or render_result.get("placeholder_image_url")
        if not image_url:
            logger.warning("design_flow render 无 image_url room=%s", room_name)
            continue
        panorama = await vr_panorama_service.publish_effect_render(
            db,
            project_id=flow.project_id,
            room_name=room_name,
            image_url=image_url,
        )
        panorama_ids.append(panorama.id)

    if not panorama_ids:
        raise ValueError("渲染未产生任何效果图")

    scene = await vr_panorama_service.create_scene(db, {
        "project_id": flow.project_id,
        "name": f"{flow.style} 全屋漫游",
        "panorama_ids": panorama_ids,
        "transition_type": "fade",
    })
    flow.scene_id = scene.id
    flow.stage = STAGE_RENDERED


async def trigger_render(db: AsyncSession, flow: DesignFlow, user_id: str) -> DesignFlow:
    """触发渲染（stage: supplier_matched → rendered）。"""
    if flow.stage != STAGE_SUPPLIER_MATCHED:
        raise ValueError("当前阶段不可渲染，请先选择供应商")
    await _render_and_set_scene(db, flow, user_id)
    await db.commit()
    await db.refresh(flow)
    return flow


async def adjust(
    db: AsyncSession,
    flow: DesignFlow,
    changes: dict,
    user_id: str,
) -> DesignFlow:
    """调整（任意环节调整均触发重渲染）。"""
    floorplan = await _get_floorplan(db, flow.floorplan_id)
    area = floorplan.total_area if floorplan else 0.0

    style_changed = bool(changes.get("style")) and changes["style"] != flow.style
    budget_changed = bool(changes.get("budget")) and changes["budget"] != flow.budget

    if changes.get("style"):
        flow.style = changes["style"]
    if changes.get("budget"):
        flow.budget = changes["budget"]
        flow.price_tier = _derive_price_tier(flow.budget, area)
    if changes.get("supplier_id"):
        flow.supplier_id = changes["supplier_id"]

    # 风格/预算变化且随机模式 → 重新随机匹配供应商
    if (style_changed or budget_changed) and flow.supplier_selection_mode == MODE_RANDOM:
        candidates = await match_suppliers(db, flow.style, flow.price_tier)
        if not candidates:
            raise ValueError("无匹配供应商，请调整风格或预算")
        flow.supplier_id = secrets.choice(candidates)["supplier_id"]

    await _render_and_set_scene(db, flow, user_id)
    await db.commit()
    await db.refresh(flow)
    return flow


async def confirm(db: AsyncSession, flow: DesignFlow) -> DesignFlow:
    """确认 → 触发可行性分析。"""
    if flow.stage != STAGE_RENDERED:
        raise ValueError("当前阶段不可确认，请先渲染效果图")
    flow.stage = STAGE_CONFIRMED
    await db.commit()
    await db.refresh(flow)
    await analyze_feasibility(db, flow)
    await db.refresh(flow)
    return flow


# ── 可行性分析 ──


async def analyze_feasibility(db: AsyncSession, flow: DesignFlow) -> DesignFlowFeasibility:
    """四维度聚合（工期/预算/物料/风险），单维度独立降级。"""
    existing = await db.execute(
        select(DesignFlowFeasibility).where(DesignFlowFeasibility.flow_id == flow.id)
    )
    feasibility = existing.scalar_one_or_none()
    if not feasibility:
        feasibility = DesignFlowFeasibility(flow_id=flow.id)
        db.add(feasibility)

    failed_dims: list[str] = []

    # 1. 工期
    try:
        floorplan = await _get_floorplan(db, flow.floorplan_id)
        area = floorplan.total_area if floorplan else 0.0
        duration = _estimate_construction(area)
        feasibility.duration_analysis = json.dumps(duration, ensure_ascii=False)
    except Exception as e:  # pragma: no cover - 防御
        logger.warning("design_flow duration analysis failed: %s", e)
        failed_dims.append("duration")

    # 2. 预算（BOM 汇总 vs 用户预算，诚实标注估算来源）
    try:
        current_version = await get_current_bom_version(db, flow.project_id)
        bom_result = await db.execute(
            select(BOMItem).where(
                BOMItem.project_id == flow.project_id,
                BOMItem.version == current_version,
            )
        )
        bom_items = list(bom_result.scalars().all())
        bom_total = round(sum(i.quantity * i.unit_price for i in bom_items), 2)
        budget = {
            "user_budget": flow.budget,
            "bom_total": bom_total,
            "gap": round(flow.budget - bom_total, 2),
            "over_budget": bom_total > flow.budget,
            "bom_item_count": len(bom_items),
            "source": "bom_estimated",
            "note": "预算基于项目 BOM 估算，未含供应商真实询价",
        }
        feasibility.budget_analysis = json.dumps(budget, ensure_ascii=False)
    except Exception as e:  # pragma: no cover - 防御
        logger.warning("design_flow budget analysis failed: %s", e)
        failed_dims.append("budget")

    # 3. 物料可供应性（选定供应商）
    try:
        current_version = await get_current_bom_version(db, flow.project_id)
        bom_result = await db.execute(
            select(BOMItem).where(
                BOMItem.project_id == flow.project_id,
                BOMItem.version == current_version,
            )
        )
        bom_items = list(bom_result.scalars().all())
        material_summary = []
        for item in bom_items:
            avail = await get_material_availability(db, item.material_id)
            sup = next(
                (s for s in avail.get("suppliers", []) if s.get("supplier_id") == flow.supplier_id),
                None,
            )
            material_summary.append({
                "material_id": item.material_id,
                "quantity": item.quantity,
                "supplier_id": flow.supplier_id,
                "available_quantity": sup.get("available_quantity") if sup else None,
                "lead_time_days": sup.get("lead_time_days") if sup else None,
                "in_stock": bool(sup and sup.get("available_quantity", 0) >= item.quantity),
            })
        material = {
            "total_materials": len(material_summary),
            "shortage_count": sum(1 for m in material_summary if not m["in_stock"]),
            "items": material_summary,
            "source": "availability_estimated",
        }
        feasibility.material_analysis = json.dumps(material, ensure_ascii=False)
    except Exception as e:  # pragma: no cover - 防御
        logger.warning("design_flow material analysis failed: %s", e)
        failed_dims.append("material")

    # 4. 施工条件/风险
    try:
        risks = await analyze_project_risks(flow.project_id, db)
        risk_list = []
        for r in risks.get("risks", []):
            risk_list.append({
                "risk_type": getattr(r, "risk_type", None),
                "risk_score": getattr(r, "risk_score", None),
                "probability": getattr(r, "probability", None),
                "impact_level": getattr(r, "impact_level", None),
                "status": getattr(r, "status", None),
            })
        risk_analysis = {
            "risks_created": risks.get("risks_created", 0),
            "risks": risk_list,
        }
        feasibility.risk_analysis = json.dumps(risk_analysis, ensure_ascii=False)
    except Exception as e:  # pragma: no cover - 防御
        logger.warning("design_flow risk analysis failed: %s", e)
        failed_dims.append("risk")

    # 聚合结论 + 可推进信号
    signal = "no_go" if failed_dims else "go"
    if failed_dims and len(failed_dims) < 4:
        signal = "go_with_conditions"
    summary = {
        "signal": signal,
        "failed_dimensions": failed_dims,
        "note": "可行性分析四维度确定性聚合；预算/物料为估算，非真实询价",
    }
    feasibility.summary = json.dumps(summary, ensure_ascii=False)
    feasibility.status = "failed" if len(failed_dims) == 4 else ("partial" if failed_dims else "completed")

    await db.commit()
    await db.refresh(feasibility)

    if flow.stage == STAGE_CONFIRMED and len(failed_dims) == 0:
        flow.stage = STAGE_FEASIBILITY_DONE
        await db.commit()
        await db.refresh(flow)

    return feasibility


async def get_feasibility(db: AsyncSession, flow_id: str) -> DesignFlowFeasibility | None:
    result = await db.execute(
        select(DesignFlowFeasibility).where(DesignFlowFeasibility.flow_id == flow_id)
    )
    return result.scalar_one_or_none()


# ── LLM 智能体建议（旁路） ──


async def suggest_adjustment(db: AsyncSession, flow: DesignFlow, user_id: str) -> dict:
    """基于当前快照生成 LLM 调整建议（只读，不改变状态）。"""
    try:
        from app.agents.base import BaseAgent

        floorplan = await _get_floorplan(db, flow.floorplan_id)
        area = floorplan.total_area if floorplan else 0.0
        agent = BaseAgent()
        try:
            prompt = (
                f"你是装修设计顾问。当前设计流程：风格={flow.style}，预算={flow.budget} 元，"
                f"面积={area} ㎡，价格档位={flow.price_tier}。"
                "请给出 1-3 条可执行的调整建议（换风格/调预算/换供应商等），"
                "输出 JSON 数组：[{\"type\": \"style|budget|supplier\", \"suggestion\": \"...\"}]"
            )
            reply = await agent._chat([
                {"role": "system", "content": "你是家装设计顾问，输出严格 JSON。"},
                {"role": "user", "content": prompt},
            ])
            if isinstance(reply, str) and reply.startswith("[mock]"):
                return {"suggestions": [], "source": "unavailable"}
            suggestions = _parse_suggestions(reply if isinstance(reply, str) else json.dumps(reply, ensure_ascii=False))
        finally:
            await agent.close()
        return {"suggestions": suggestions, "source": "llm"}
    except Exception as e:  # pragma: no cover - LLM 不可用诚实降级
        logger.warning("design_flow suggest_adjustment unavailable: %s", e)
        return {"suggestions": [], "source": "unavailable"}


def _parse_suggestions(reply: str) -> list[dict]:
    """解析 LLM 建议 JSON，失败返回空列表。"""
    try:
        text = reply.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
        if isinstance(data, list):
            return [s for s in data if isinstance(s, dict)]
        if isinstance(data, dict) and isinstance(data.get("suggestions"), list):
            return [s for s in data["suggestions"] if isinstance(s, dict)]
        return []
    except (json.JSONDecodeError, TypeError):
        return []
