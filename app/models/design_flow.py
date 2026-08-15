"""设计流程编排模型 — 风格/预算选供应商 → VR 效果图 → 可行性分析

确定性编排 + 状态机（design_flows），LLM 意见走旁路建议端点。
可行性分析结果四维度落 design_flow_feasibilities，单维度独立降级。
"""

import json
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Float, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DesignFlow(Base):
    """设计流程编排会话 — 串联户型 → 供应商 → VR 渲染 → 可行性分析的状态机"""

    __tablename__ = "design_flows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    floorplan_id: Mapped[str] = mapped_column(String(36), ForeignKey("floor_plans.id"), nullable=False, index=True)
    style: Mapped[str] = mapped_column(String(100), nullable=False)
    budget: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 价格档位：economy / standard / premium（由 budget + floorplan 面积推导）
    price_tier: Mapped[str] = mapped_column(String(20), nullable=False, default="standard")
    # 供应商选择方式：random（随机）/ manual（自选）
    supplier_selection_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="random")
    supplier_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("suppliers.id"), nullable=True, index=True)
    scene_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("vr_scenes.id"), nullable=True, index=True)
    # 状态机阶段：init / supplier_matched / rendered / confirmed / feasibility_done / cancelled
    stage: Mapped[str] = mapped_column(String(30), nullable=False, default="init")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DesignFlowFeasibility(Base):
    """可行性分析结果 — 四维度（工期/预算/物料/风险）+ 聚合结论"""

    __tablename__ = "design_flow_feasibilities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    flow_id: Mapped[str] = mapped_column(String(36), ForeignKey("design_flows.id"), nullable=False, index=True, unique=True)
    # 四维度均为 JSON 字符串，单维度失败标 partial 不影响其它维度
    duration_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    budget_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    material_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # status: pending / partial / completed / failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def duration_dict(self) -> dict:
        return self._loads(self.duration_analysis)

    @property
    def budget_dict(self) -> dict:
        return self._loads(self.budget_analysis)

    @property
    def material_dict(self) -> dict:
        return self._loads(self.material_analysis)

    @property
    def risk_dict(self) -> dict:
        return self._loads(self.risk_analysis)

    @property
    def summary_dict(self) -> dict:
        return self._loads(self.summary)

    @staticmethod
    def _loads(raw: str | None) -> dict:
        try:
            return json.loads(raw or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}


class DesignFlowDrawing(Base):
    """设计环节图纸 — 施工图全套 + 水电图 + 灯图（渲染前生成）"""

    __tablename__ = "design_flow_drawings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    flow_id: Mapped[str] = mapped_column(String(36), ForeignKey("design_flows.id"), nullable=False, index=True, unique=True)
    # 施工图：平面布置图 SVG
    floor_plan_svg: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 施工图：立面图列表（JSON [{wall_name, svg}]）
    elevation_svgs: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 施工图：剖面图 SVG
    section_svg: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 水电图：给排水/电气叠加 SVG
    mep_overlay_svg: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 水电图：点位规划（JSON，复用 mep_service.generate_mep_plan）
    mep_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 灯图：逐房间灯光方案（JSON 列表，复用 lighting_service.generate_ai_scheme）
    lighting_schemes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # status: pending / completed / failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
