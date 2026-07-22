"""A2UI Generator — Agent 输出 → A2UI JSON 转换器

将各 Agent 的结构化输出转换为符合 A2UI 协议的 JSON 卡片，
前端（Flutter/Web）可直接渲染。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.a2ui_schema import (
    AlertSeverity,
    AlertCardData,
    BudgetBreakdownData,
    CardType,
    ConstructionProgressData,
    DesignPlanData,
    MaterialCardData,
    ProcurementOrderData,
    QAReportData,
    QACheckpointResult,
    SettlementSummaryData,
    make_alert_card,
    make_card,
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    """安全转换为 float"""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_str(value: Any, default: str = "") -> str:
    """安全转换为 str"""
    if value is None:
        return default
    return str(value)


def _safe_list(value: Any) -> list[dict[str, Any]]:
    """安全转换为 dict list"""
    if isinstance(value, list):
        return [item if isinstance(item, dict) else {"value": str(item)} for item in value]
    return []


# ═══════════════════════════════════════════
# 专用转换器
# ═══════════════════════════════════════════

def design_to_card(agent_output: dict[str, Any]) -> dict[str, Any]:
    """将 DesignerAgent 输出转换为 design_plan 卡片

    agent_output 示例:
    {
        "project_name": "朝阳丽景 3-1201",
        "floor_layout": "三室两厅两卫",
        "total_area": 128.5,
        "rooms": [{"name": "客厅", "area": 28.5, "orientation": "南"}, ...],
        "style": "现代简约",
        "preview_3d_url": "https://...",
        ...
    }
    """
    data = DesignPlanData(
        project_name=_safe_str(agent_output.get("project_name")),
        floor_layout=_safe_str(agent_output.get("floor_layout")),
        total_area=_safe_float(agent_output.get("total_area")),
        rooms=_safe_list(agent_output.get("rooms")),
        style=_safe_str(agent_output.get("style")),
        preview_3d_url=_safe_str(agent_output.get("preview_3d_url")),
        preview_image_url=_safe_str(agent_output.get("preview_image_url")),
        estimated_timeline=_safe_str(agent_output.get("estimated_timeline")),
        notes=_safe_str(agent_output.get("notes")),
    )
    return data.to_card()


def budget_to_card(agent_output: dict[str, Any]) -> dict[str, Any]:
    """将 BudgetAgent 输出转换为 budget_breakdown 卡片

    agent_output 示例:
    {
        "project_name": "朝阳丽景 3-1201",
        "items": [{...}, ...],
        "subtotal": 100000,
        "tax_rate": 0.03,
        "total": 103000,
        "warranty_months": 24,
        "payment_stages": [{...}, ...],
    }
    """
    subtotal = _safe_float(agent_output.get("subtotal"))
    tax_rate = _safe_float(agent_output.get("tax_rate"))
    tax_amount = agent_output.get("tax_amount")
    if tax_amount is None:
        tax_amount = round(subtotal * tax_rate, 2)

    data = BudgetBreakdownData(
        project_name=_safe_str(agent_output.get("project_name")),
        items=_safe_list(agent_output.get("items")),
        subtotal=subtotal,
        tax_rate=tax_rate,
        tax_amount=_safe_float(tax_amount),
        total=_safe_float(agent_output.get("total", subtotal + _safe_float(tax_amount))),
        warranty_months=int(agent_output.get("warranty_months", 24)),
        warranty_scope=_safe_str(agent_output.get("warranty_scope")),
        payment_stages=_safe_list(agent_output.get("payment_stages")),
    )
    return data.to_card()


def construction_to_card(agent_output: dict[str, Any]) -> dict[str, Any]:
    """将 ConstructionAgent 输出转换为 construction_progress 卡片"""
    data = ConstructionProgressData(
        project_name=_safe_str(agent_output.get("project_name")),
        overall_progress=_safe_float(agent_output.get("overall_progress")),
        phases=_safe_list(agent_output.get("phases")),
        crew_info=agent_output.get("crew_info") if isinstance(agent_output.get("crew_info"), dict) else {},
        next_milestone=agent_output.get("next_milestone") if isinstance(agent_output.get("next_milestone"), dict) else {},
        updated_at=_safe_str(agent_output.get("updated_at", datetime.now(timezone.utc).isoformat())),
    )
    return data.to_card()


def procurement_to_card(agent_output: dict[str, Any]) -> dict[str, Any]:
    """将 ProcurementAgent 输出转换为 procurement_order 卡片"""
    data = ProcurementOrderData(
        order_id=_safe_str(agent_output.get("order_id", "")),
        items=_safe_list(agent_output.get("items")),
        supplier=agent_output.get("supplier") if isinstance(agent_output.get("supplier"), dict) else {},
        total_amount=_safe_float(agent_output.get("total_amount")),
        delivery_date=_safe_str(agent_output.get("delivery_date")),
        status=_safe_str(agent_output.get("status", "ordered")),
        tracking_url=_safe_str(agent_output.get("tracking_url")),
    )
    return data.to_card()


def qa_to_card(agent_output: dict[str, Any]) -> dict[str, Any]:
    """将 QAInspector 输出转换为 qa_report 卡片

    agent_output 示例:
    {
        "project_name": "朝阳丽景 3-1201",
        "checkpoints": [
            {"name": "墙面平整度", "result": "pass", "standard": "偏差≤2mm", "actual": "1.2mm"},
            ...
        ],
        "inspector": "李工",
        "fix_deadline": "2026-03-01",
    }
    """
    checkpoints = _safe_list(agent_output.get("checkpoints"))
    failed_count = sum(1 for c in checkpoints if c.get("result") == QACheckpointResult.FAIL.value)
    passed_count = sum(1 for c in checkpoints if c.get("result") == QACheckpointResult.PASS.value)

    # 整体结果
    has_failed = any(c.get("result") == QACheckpointResult.FAIL.value for c in checkpoints)
    has_pending = any(c.get("result") == QACheckpointResult.PENDING.value for c in checkpoints)
    if has_failed:
        overall_result = QACheckpointResult.FAIL.value
    elif has_pending:
        overall_result = QACheckpointResult.PENDING.value
    else:
        overall_result = QACheckpointResult.PASS.value

    data = QAReportData(
        project_name=_safe_str(agent_output.get("project_name")),
        checkpoints=checkpoints,
        overall_result=_safe_str(agent_output.get("overall_result", overall_result)),
        inspector=_safe_str(agent_output.get("inspector")),
        inspection_date=_safe_str(agent_output.get("inspection_date")),
        fix_deadline=_safe_str(agent_output.get("fix_deadline")),
        failed_count=failed_count,
        passed_count=passed_count,
    )
    return data.to_card()


def settlement_to_card(agent_output: dict[str, Any]) -> dict[str, Any]:
    """将 SettlementAgent 输出转换为 settlement_summary 卡片"""
    total = _safe_float(agent_output.get("total_amount"))
    paid = _safe_float(agent_output.get("paid_amount"))
    balance = agent_output.get("balance_amount")
    if balance is None:
        balance = round(total - paid, 2)

    data = SettlementSummaryData(
        project_name=_safe_str(agent_output.get("project_name")),
        total_amount=total,
        paid_amount=paid,
        balance_amount=_safe_float(balance),
        payment_history=_safe_list(agent_output.get("payment_history")),
        next_payment=agent_output.get("next_payment") if isinstance(agent_output.get("next_payment"), dict) else {},
        settlement_status=_safe_str(agent_output.get("settlement_status", "in_progress")),
    )
    return data.to_card()


def material_to_card(agent_output: dict[str, Any]) -> dict[str, Any]:
    """将 ProductsAgent 输出转换为 material_card 卡片"""
    data = MaterialCardData(
        name=_safe_str(agent_output.get("name")),
        category=_safe_str(agent_output.get("category")),
        specs=_safe_str(agent_output.get("specs")),
        eco_level=_safe_str(agent_output.get("eco_level", "E1")),
        unit_price=_safe_float(agent_output.get("unit_price")),
        unit=_safe_str(agent_output.get("unit", "㎡")),
        supplier=_safe_str(agent_output.get("supplier")),
        stock_status=_safe_str(agent_output.get("stock_status", "in_stock")),
        image_url=_safe_str(agent_output.get("image_url")),
        description=_safe_str(agent_output.get("description")),
        certifications=(
            agent_output.get("certifications")
            if isinstance(agent_output.get("certifications"), list)
            else []
        ),
    )
    return data.to_card()


# ═══════════════════════════════════════════
# 通用 / 回退转换器
# ═══════════════════════════════════════════

def generic_to_card(agent_type: str, text: str) -> dict[str, Any]:
    """将纯文本 Agent 输出转换为通用 A2UI 卡片（fallback）

    当 Agent 输出不是结构化 JSON 时使用，保留原始文本并包裹为卡片。
    """
    return make_card(
        CardType.ALERT_CARD,
        {
            "alert_type": "agent_message",
            "severity": AlertSeverity.INFO.value,
            "title": f"{agent_type} 响应",
            "message": text,
            "source_agent": agent_type,
            "actions": [],
            "dismissible": True,
        },
    )


# ═══════════════════════════════════════════
# 自动路由转换器
# ═══════════════════════════════════════════

# Agent key → 转换器函数 映射表
AGENT_CONVERTER_MAP: dict[str, Any] = {
    "design": design_to_card,
    "budget": budget_to_card,
    "construction": construction_to_card,
    "procurement": procurement_to_card,
    "quality": qa_to_card,
    "settlement": settlement_to_card,
    "products": material_to_card,
    "materials": material_to_card,
    "furniture": material_to_card,
}


def agent_output_to_card(agent_key: str, agent_output: dict[str, Any] | str) -> dict[str, Any]:
    """根据 Agent 标识自动选择转换器，将输出转为 A2UI 卡片

    Args:
        agent_key: Agent 标识符，如 "design", "budget", "construction" 等
        agent_output: Agent 输出，可以是结构化 dict 或纯文本 str

    Returns:
        A2UI 卡片 JSON (dict)
    """
    # 若已是纯文本，走通用 fallback
    if isinstance(agent_output, str):
        return generic_to_card(agent_key, agent_output)

    # 若输出本身已是 A2UI 卡片格式，直接返回
    if isinstance(agent_output, dict) and "type" in agent_output and "data" in agent_output:
        return agent_output

    # 路由到对应转换器
    converter = AGENT_CONVERTER_MAP.get(agent_key)
    if converter is not None:
        try:
            return converter(agent_output)
        except Exception:
            # 转换失败时回退到通用卡片
            pass

    # 最终 fallback
    return generic_to_card(agent_key, str(agent_output))


def batch_to_cards(
    agent_outputs: list[dict[str, Any]],
    agent_key: str | None = None,
) -> list[dict[str, Any]]:
    """批量转换 Agent 输出为 A2UI 卡片列表

    Args:
        agent_outputs: 多个 Agent 输出组成的列表，
                       每项可包含 "agent_key" 字段指定 Agent 类型
        agent_key: 默认 Agent 类型（当列表项未指定时使用）

    Returns:
        A2UI 卡片列表
    """
    cards: list[dict[str, Any]] = []
    for output in agent_outputs:
        key = str(output.get("agent_key", agent_key or "unknown"))
        card = agent_output_to_card(key, output)
        cards.append(card)
    return cards
