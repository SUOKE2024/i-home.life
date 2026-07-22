"""A2UI JSON Schema — Agent-to-UI 渲染协议定义

定义 Agent 输出 → 前端渲染卡片的 JSON 规范。
每种 card 类型对应一个 Agent 场景，前端（Flutter/Web）按 type 路由到对应渲染器。

协议版本: 1.0.0
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ── 协议常量 ──

PROTOCOL_VERSION = "1.0.0"


# ── 枚举 ──

class CardType(str, Enum):
    """A2UI 卡片类型枚举"""
    DESIGN_PLAN = "design_plan"
    BUDGET_BREAKDOWN = "budget_breakdown"
    CONSTRUCTION_PROGRESS = "construction_progress"
    PROCUREMENT_ORDER = "procurement_order"
    QA_REPORT = "qa_report"
    SETTLEMENT_SUMMARY = "settlement_summary"
    MATERIAL_CARD = "material_card"
    ALERT_CARD = "alert_card"


class AlertSeverity(str, Enum):
    """告警严重级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class PaymentStageStatus(str, Enum):
    """付款阶段状态"""
    PAID = "paid"
    PENDING = "pending"
    OVERDUE = "overdue"


class ConstructionPhaseStatus(str, Enum):
    """施工阶段状态"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DELAYED = "delayed"


class ProcurementStatus(str, Enum):
    """采购状态"""
    ORDERED = "ordered"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class QACheckpointResult(str, Enum):
    """质检检查点结果"""
    PASS = "pass"
    FAIL = "fail"
    PENDING = "pending"


class EcoLevel(str, Enum):
    """环保等级"""
    E0 = "E0"
    E1 = "E1"
    E2 = "E2"
    F4_STAR = "F4☆"
    CARB_P2 = "CARB P2"
    NAF = "NAF"


# ── 基础数据类 ──

@dataclass
class CardHeader:
    """所有 A2UI 卡片的公共头"""
    type: str
    version: str = PROTOCOL_VERSION
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ActionButton:
    """操作按钮"""
    label: str
    action: str  # 动作标识，如 "view_3d", "confirm_payment", "contact_supplier"
    url: str = ""
    icon: str = ""
    variant: str = "primary"  # primary | secondary | danger | outline


# ── 卡片数据定义 ──

@dataclass
class DesignPlanData:
    """设计方案的卡片数据"""
    project_name: str
    floor_layout: str  # 户型布局描述，如 "三室两厅两卫"
    total_area: float  # 总面积（㎡）
    rooms: list[dict[str, Any]] = field(default_factory=list)
    # 每个房间: {"name": "客厅", "area": 28.5, "orientation": "南"}
    style: str = ""
    preview_3d_url: str = ""
    preview_image_url: str = ""
    estimated_timeline: str = ""  # 预估工期，如 "90天"
    notes: str = ""

    def to_card(self) -> dict[str, Any]:
        """转换为 design_plan 卡片"""
        return make_card(CardType.DESIGN_PLAN, asdict(self))


@dataclass
class BudgetBreakdownData:
    """预算明细的卡片数据"""
    project_name: str
    items: list[dict[str, Any]] = field(default_factory=list)
    # 每项: {"category": "硬装", "name": "地板铺设", "quantity": 80, "unit": "㎡",
    #         "unit_price": 150, "amount": 12000}
    subtotal: float = 0.0
    tax_rate: float = 0.0
    tax_amount: float = 0.0
    total: float = 0.0
    warranty_months: int = 24
    warranty_scope: str = ""
    payment_stages: list[dict[str, Any]] = field(default_factory=list)
    # 每阶段: {"stage": "签约", "ratio": 0.3, "amount": 30000, "status": "paid"}

    def to_card(self) -> dict[str, Any]:
        """转换为 budget_breakdown 卡片"""
        return make_card(CardType.BUDGET_BREAKDOWN, asdict(self))


@dataclass
class ConstructionProgressData:
    """施工进度的卡片数据"""
    project_name: str
    overall_progress: float  # 0.0 ~ 1.0
    phases: list[dict[str, Any]] = field(default_factory=list)
    # 每阶段: {"name": "水电改造", "progress": 1.0, "status": "completed",
    #          "start_date": "2026-01-15", "end_date": "2026-01-28"}
    crew_info: dict[str, Any] = field(default_factory=dict)
    # {"leader": "王工", "team_size": 8, "specialties": ["水电", "瓦工"]}
    next_milestone: dict[str, Any] = field(default_factory=dict)
    # {"name": "木工进场", "date": "2026-02-05", "description": ""}
    updated_at: str = ""

    def to_card(self) -> dict[str, Any]:
        """转换为 construction_progress 卡片"""
        return make_card(CardType.CONSTRUCTION_PROGRESS, asdict(self))


@dataclass
class ProcurementOrderData:
    """采购订单的卡片数据"""
    order_id: str
    items: list[dict[str, Any]] = field(default_factory=list)
    # 每项: {"name": "东鹏瓷砖", "specs": "800×800mm", "quantity": 50, "unit": "箱", "unit_price": 120}
    supplier: dict[str, Any] = field(default_factory=dict)
    # {"name": "东鹏建材", "contact": "138xxxx", "rating": 4.8}
    total_amount: float = 0.0
    delivery_date: str = ""
    status: str = ProcurementStatus.ORDERED.value
    tracking_url: str = ""

    def to_card(self) -> dict[str, Any]:
        """转换为 procurement_order 卡片"""
        return make_card(CardType.PROCUREMENT_ORDER, asdict(self))


@dataclass
class QAReportData:
    """质检报告的卡片数据"""
    project_name: str
    checkpoints: list[dict[str, Any]] = field(default_factory=list)
    # 每项: {"name": "墙面平整度", "result": "pass", "standard": "偏差≤2mm",
    #         "actual": "1.2mm", "photo_url": "", "note": ""}
    overall_result: str = QACheckpointResult.PASS.value
    inspector: str = ""
    inspection_date: str = ""
    fix_deadline: str = ""
    failed_count: int = 0
    passed_count: int = 0

    def to_card(self) -> dict[str, Any]:
        """转换为 qa_report 卡片"""
        return make_card(CardType.QA_REPORT, asdict(self))


@dataclass
class SettlementSummaryData:
    """结算汇总的卡片数据"""
    project_name: str
    total_amount: float = 0.0
    paid_amount: float = 0.0
    balance_amount: float = 0.0
    payment_history: list[dict[str, Any]] = field(default_factory=list)
    # 每笔: {"date": "2026-01-10", "amount": 30000, "method": "银行转账", "status": "completed"}
    next_payment: dict[str, Any] = field(default_factory=dict)
    # {"amount": 20000, "due_date": "2026-03-15", "condition": "木工验收通过"}
    settlement_status: str = "in_progress"  # in_progress | settled | disputed

    def to_card(self) -> dict[str, Any]:
        """转换为 settlement_summary 卡片"""
        return make_card(CardType.SETTLEMENT_SUMMARY, asdict(self))


@dataclass
class MaterialCardData:
    """材料详情的卡片数据"""
    name: str
    category: str = ""  # 瓷砖、地板、涂料、五金等
    specs: str = ""  # 规格参数
    eco_level: str = EcoLevel.E1.value
    unit_price: float = 0.0
    unit: str = "㎡"
    supplier: str = ""
    stock_status: str = "in_stock"  # in_stock | low_stock | out_of_stock
    image_url: str = ""
    description: str = ""
    certifications: list[str] = field(default_factory=list)

    def to_card(self) -> dict[str, Any]:
        """转换为 material_card 卡片"""
        return make_card(CardType.MATERIAL_CARD, asdict(self))


@dataclass
class AlertCardData:
    """系统告警的卡片数据"""
    alert_type: str = ""  # budget_overrun | delay | quality_issue | payment_overdue | system
    severity: str = AlertSeverity.INFO.value
    title: str = ""
    message: str = ""
    actions: list[dict[str, Any]] = field(default_factory=list)
    # 每项: {"label": "查看详情", "action": "view_detail", "url": "", "variant": "primary"}
    source_agent: str = ""  # 触发告警的 Agent 标识
    dismissible: bool = True

    def to_card(self) -> dict[str, Any]:
        """转换为 alert_card 卡片"""
        return make_card(CardType.ALERT_CARD, asdict(self))


# ── 工厂函数 ──

def make_card(card_type: CardType, data: dict[str, Any]) -> dict[str, Any]:
    """统一构造 A2UI 卡片 JSON"""
    return {
        "type": card_type.value,
        "version": PROTOCOL_VERSION,
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }


def make_alert_card(
    title: str,
    message: str,
    severity: str = AlertSeverity.INFO.value,
    alert_type: str = "system",
    actions: list[dict[str, Any]] | None = None,
    source_agent: str = "",
) -> dict[str, Any]:
    """快捷创建告警卡片"""
    data = AlertCardData(
        alert_type=alert_type,
        severity=severity,
        title=title,
        message=message,
        actions=actions or [],
        source_agent=source_agent,
    )
    return data.to_card()


# ── 序列化工具 ──

def card_to_json(card: dict[str, Any], indent: int | None = None) -> str:
    """将 A2UI 卡片序列化为 JSON 字符串"""
    return json.dumps(card, ensure_ascii=False, indent=indent)


def encode_cards_to_wire(cards: list[dict[str, Any]]) -> str:
    """将多个 A2UI 卡片编码为传输格式（单行 JSON，适合 SSE streaming）"""
    return json.dumps({"version": PROTOCOL_VERSION, "cards": cards}, ensure_ascii=False)
