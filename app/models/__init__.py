import logging

from app.database import Base as _Base  # 注册自检用（见文件末尾）

from app.models.user import User
from app.models.project import Project, Floor, Room
from app.models.material import MaterialCategory, Material, BOMItem
from app.models.budget import Budget, BudgetLine
from app.models.procurement import Supplier, Quotation, ProcurementOrder, OrderLine
from app.models.construction import ConstructionTask, ConstructionLog, Inspection
from app.models.settlement import Settlement, SettlementLine
from app.models.floorplan import FloorPlan
from app.models.file_attachment import FileAttachment
from app.models.survey import Survey
from app.models.change_order import ChangeOrder, ChangeOrderItem
from app.models.payment import Payment
from app.models.chat import ChatMessage, ChatRoom
from app.models.construction_crew import ConstructionCrew, CrewBenefit, CrewMatch
from app.models.progress_alert import ProgressAlert, MilestoneTracker
from app.models.quality import QualityIssue, RectificationOrder, QualityAssessment
from app.models.service_worker import ServiceWorker, ServiceWorkerMatch
from app.models.ar_scan import ScanSession, WallFeature, MeasurementPoint
from app.models.lighting import LightingScheme, LightingFixture
from app.models.kitchen import KitchenDesign, KitchenComponent
from app.models.bathroom import BathroomDesign, BathroomFixture
from app.models.custom_furniture import CustomFurnitureDesign, FurnitureModule, FurnitureBOM
from app.models.soft_furnishing import SoftFurnishingScheme, SoftFurnishingItem, StorageSystem
from app.models.vr_panorama import VRPanorama, VRScene
from app.models.ai_image import AIImageJob, AIImagePreset
from app.models.kitchen_bath_mep import KitchenBathMEPPlan, MEPPoint
from app.models.hard_decoration import HardDecorationScheme, HardDecorationFloor, WallFinish, CeilingDesign
from app.models.door_window_waterproof import DoorWindowSpec, WaterproofPlan
from app.models.furniture_catalog import FurnitureCatalogItem
from app.models.curtain_showroom import (
    CurtainShowroom,
    CurtainSeries,
    CurtainProduct,
    CurtainInstallation,
    CurtainLightingPreset,
    CurtainShowroomArea,
)
from app.models.smart_home import SmartHomeScheme, SmartDevice
from app.models.matter_device import MatterDevice
from app.models.agent_feedback import AgentFeedback
from app.models.agent_session import AgentSession, AgentMessage
from app.models.agent_memory import AgentMemory
from app.models.scene_automation import SceneAutomation, EcosystemIntegration
from app.models.scene_behavior import SceneBehaviorLog, PredictedScene
from app.models.procurement_enhanced import (
    PriceComparison, PriceComparisonItem, EscrowPayment, LogisticsTracking, SampleRequest,
)

# A6 施工预测性维护
from app.models.predictive_maintenance import RiskPrediction

# F19-F20 电器品类库 + 电器点位规划
from app.models.appliance import ApplianceCategory, Appliance, AppliancePoint, ApplianceLoadCalc

# F8-F9 土建模块 — 结构属性 + 工程量计算
from app.models.structural import (
    LoadBearingWall, Beam, Column, FloorSlab, FoundationType,
    StructureLoadEstimate, BayCompliance, QuantityCalculation, QuantityLineItem,
)

# 新增：身份认证、积分、产品、任务协调
from app.models.identity_verification import IdentityVerification
from app.models.product import Product
from app.models.points import (
    PointsAccount, PointsTransaction, PointsRule,
    PointsMallItem, PointsRedemption, PointsRanking,
)
from app.models.orchestrator_task import OrchestratorTask, TaskCandidate
from app.models.a2a_task import A2ATask
from app.models.delivery_order import DeliveryOrder
from app.models.webauthn_credential import WebAuthnCredential
from app.models.device_token import DeviceToken
from app.models.permission import Permission, RolePermission
from app.models.audit_log import AuditLog

# v1.8.0 Agent 工具批准 + Skill 资产化（同 energy_monitor 补注册先例：
# model 文件已存在且 service 直接引用，但未在 __init__ 注册会致 Base.metadata 缺表、
# create_all / autogenerate / check_schema_drift 漏管）
from app.models.agent_approval import AgentApproval
from app.models.agent_skill import AgentSkill
from app.models.agent_case import AgentCase

# A1/A2 智能家居能耗 + 健康监测（model 文件已存在且 service 引用，但此前未在 __init__ 注册，
# 致 Base.metadata 不含这些表、alembic autogenerate 检测不到、check_schema_drift 误报为多余表。
# 补注册后 create_all 与 autogenerate 均能正确管理这些表）
from app.models.energy_monitor import EnergyMonitor, EnergySavingTip
from app.models.health_monitor import HealthMonitor, AirQualityRecord

# v1.5.0 需求补充落地（PRD v3.1 F41-F47）— 存量焕新 + 信任合规
from app.models.elderly_adaptation import ElderlyAdaptationScheme
from app.models.partial_renovation import PartialRenovationPlan
from app.models.escrow_trustee import EscrowTrusteeAccount
from app.models.eco_material import MaterialEcoCert, MaterialBoardTrace

# v1.10.x 全链路诊断系统 — 指标快照 / 全链路 Trace / 告警 / 建议 / RUM
from app.models.diagnostics import (
    DiagnosticMetricSnapshot,
    DiagnosticTrace,
    DiagnosticAlert,
    DiagnosticRecommendation,
    DiagnosticRumEvent,
)

# v1.12.x 智能体系统性打磨 — Agent 执行轨迹持久化（可观测性 + 离线评估 + 漂移检测）
from app.models.agent_trace import AgentTraceRecord

# v1.13.6 质量评估体系 — 评估快照持久化（历史趋势对比 + 迭代闭环）
from app.models.eval_snapshot import EvalSnapshotRecord

# 设备链路全量诊断修复 — 传感器快照落库（Flutter SensorService 上报真实读数）
from app.models.sensor_snapshot import SensorSnapshot

# 设计流程编排 — 风格/预算选供应商 → VR 效果图 → 可行性分析
from app.models.design_flow import DesignFlow, DesignFlowFeasibility, DesignFlowDrawing

__all__ = [
    "User",
    "Project",
    "Floor",
    "Room",
    "MaterialCategory",
    "Material",
    "BOMItem",
    "Budget",
    "BudgetLine",
    "Supplier",
    "Quotation",
    "ProcurementOrder",
    "OrderLine",
    "ConstructionTask",
    "ConstructionLog",
    "Inspection",
    "Settlement",
    "SettlementLine",
    "FloorPlan",
    "FileAttachment",
    "Survey",
    "ChangeOrder",
    "ChangeOrderItem",
    "Payment",
    "ChatMessage",
    "ChatRoom",
    "ConstructionCrew",
    "CrewBenefit",
    "CrewMatch",
    "ProgressAlert",
    "MilestoneTracker",
    "QualityIssue",
    "RectificationOrder",
    "QualityAssessment",
    "ServiceWorker",
    "ServiceWorkerMatch",
    "ScanSession",
    "WallFeature",
    "MeasurementPoint",
    "LightingScheme",
    "LightingFixture",
    "KitchenDesign",
    "KitchenComponent",
    "BathroomDesign",
    "BathroomFixture",
    "CustomFurnitureDesign",
    "FurnitureModule",
    "FurnitureBOM",
    "SoftFurnishingScheme",
    "SoftFurnishingItem",
    "StorageSystem",
    "VRPanorama",
    "VRScene",
    "AIImageJob",
    "AIImagePreset",
    "KitchenBathMEPPlan",
    "MEPPoint",
    "HardDecorationScheme",
    "HardDecorationFloor",
    "WallFinish",
    "CeilingDesign",
    "DoorWindowSpec",
    "WaterproofPlan",
    "FurnitureCatalogItem",
    "CurtainShowroom",
    "CurtainSeries",
    "CurtainProduct",
    "CurtainInstallation",
    "CurtainLightingPreset",
    "CurtainShowroomArea",
    "SmartHomeScheme",
    "SmartDevice",
    "MatterDevice",
    "SceneAutomation",
    "EcosystemIntegration",
    "SceneBehaviorLog",
    "PredictedScene",
    "PriceComparison",
    "PriceComparisonItem",
    "EscrowPayment",
    "LogisticsTracking",
    "SampleRequest",
    # A6 施工预测性维护
    "RiskPrediction",
    # F19-F20 电器
    "ApplianceCategory",
    "Appliance",
    "AppliancePoint",
    "ApplianceLoadCalc",
    # F8-F9 土建/结构
    "LoadBearingWall",
    "Beam",
    "Column",
    "FloorSlab",
    "FoundationType",
    "StructureLoadEstimate",
    "BayCompliance",
    "QuantityCalculation",
    "QuantityLineItem",
    # 新增
    "IdentityVerification",
    "Product",
    "PointsAccount",
    "PointsTransaction",
    "PointsRule",
    "PointsMallItem",
    "PointsRedemption",
    "PointsRanking",
    "OrchestratorTask",
    "TaskCandidate",
    "A2ATask",
    "DeliveryOrder",
    "WebAuthnCredential",
    "DeviceToken",
    "Permission",
    "RolePermission",
    "AgentFeedback",
    "AgentSession",
    "AgentMessage",
    "AgentMemory",
    "AuditLog",
    # v1.8.0 Agent 工具批准 + Skill 资产化
    "AgentApproval",
    "AgentSkill",
    # v1.10.1 自进化管线 — Agent Case（借鉴 EverMind EverOS Agent Memory）
    "AgentCase",
    # A1/A2 智能家居能耗 + 健康监测
    "EnergyMonitor",
    "EnergySavingTip",
    "HealthMonitor",
    "AirQualityRecord",
    # v1.5.0 需求补充落地（PRD v3.1 F41-F47）
    "ElderlyAdaptationScheme",
    "PartialRenovationPlan",
    "EscrowTrusteeAccount",
    "MaterialEcoCert",
    "MaterialBoardTrace",
    # v1.10.x 全链路诊断系统
    "DiagnosticMetricSnapshot",
    "DiagnosticTrace",
    "DiagnosticAlert",
    "DiagnosticRecommendation",
    "DiagnosticRumEvent",
    # v1.12.x Agent 执行轨迹持久化
    "AgentTraceRecord",
    # v1.13.6 质量评估体系 — 评估快照持久化
    "EvalSnapshotRecord",
    # 设备链路全量诊断修复 — 传感器快照落库
    "SensorSnapshot",
    # 设计流程编排
    "DesignFlow",
    "DesignFlowFeasibility",
    "DesignFlowDrawing",
]


# ── 模型注册自检（2026-08-06 全景诊断落地）──
# 背景：agent_approval / agent_skill 曾只被 service 直接 import、未在本文件注册，
# 致 Base.metadata 缺表、create_all / alembic autogenerate / check_schema_drift 漏管。
# import 期一次性自检：关键表缺失即 warning，零运行时成本。
_logger = logging.getLogger(__name__)

_REGISTRATION_CRITICAL_TABLES = ("agent_approvals", "agent_skills")
_registered_tables = set(_Base.metadata.tables.keys())
_missing_tables = [t for t in _REGISTRATION_CRITICAL_TABLES if t not in _registered_tables]
if _missing_tables:
    _logger.warning(
        "models 注册自检失败: 关键表未注册到 Base.metadata: %s —— create_all/autogenerate 将漏管",
        _missing_tables,
    )
_logger.debug("models 注册自检通过: Base.metadata 共 %d 张表", len(_registered_tables))
