"""设计流程编排 Pydantic 验证模型"""

import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class DesignFlowCreate(BaseModel):
    """创建设计流程编排会话"""

    project_id: str
    floorplan_id: str
    style: str = Field(..., min_length=1, max_length=100)
    budget: float = Field(..., gt=0)
    supplier_selection_mode: Literal["random", "manual"] = Field(default="random")


class DesignFlowResponse(BaseModel):
    """设计流程编排会话详情"""

    id: str
    project_id: str
    floorplan_id: str
    style: str
    budget: float
    price_tier: str
    supplier_selection_mode: str
    supplier_id: str | None = None
    scene_id: str | None = None
    stage: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SupplierCandidate(BaseModel):
    """匹配到的供应商候选（风格 + 价格档位硬过滤）"""

    supplier_id: str
    name: str
    category: str
    rating: float
    styles: list[str] = Field(default_factory=list)
    price_tier: str = "standard"
    address: str | None = None
    # 供应商实景展厅（车间/样品间 360°），无实景内容恒 None，前端诚实标注
    showroom_panorama_id: str | None = None


class SupplierSelectRequest(BaseModel):
    """选择供应商（随机/自选）"""

    mode: Literal["random", "manual"] = Field(default="random")
    supplier_id: str | None = None


class DesignFlowAdjustRequest(BaseModel):
    """调整（任意环节调整均触发重渲染）"""

    style: str | None = Field(default=None, max_length=100)
    budget: float | None = Field(default=None, gt=0)
    supplier_id: str | None = None
    effect_tweak: dict[str, Any] | None = None


class DesignFlowSuggestResponse(BaseModel):
    """LLM 智能体调整建议（旁路，只读）"""

    suggestions: list[dict[str, Any]] = Field(default_factory=list)
    source: str = "unavailable"  # llm / unavailable


class DesignFlowFeasibilityResponse(BaseModel):
    """可行性分析结果（四维度 + 聚合）"""

    id: str
    flow_id: str
    status: str
    duration_analysis: dict[str, Any] = Field(default_factory=dict)
    budget_analysis: dict[str, Any] = Field(default_factory=dict)
    material_analysis: dict[str, Any] = Field(default_factory=dict)
    risk_analysis: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator(
        "duration_analysis", "budget_analysis", "material_analysis",
        "risk_analysis", "summary", mode="before",
    )
    @classmethod
    def _parse_json_field(cls, v):
        if v is None:
            return {}
        if isinstance(v, str):
            try:
                return json.loads(v or "{}")
            except (json.JSONDecodeError, TypeError):
                return {}
        return v


class DesignFlowDrawingResponse(BaseModel):
    """设计环节图纸（施工图全套 + 水电图 + 灯图）"""

    id: str
    flow_id: str
    floor_plan_svg: str | None = None
    elevation_svgs: list[dict[str, Any]] = Field(default_factory=list)
    section_svg: str | None = None
    mep_overlay_svg: str | None = None
    mep_plan: dict[str, Any] = Field(default_factory=dict)
    lighting_schemes: list[dict[str, Any]] = Field(default_factory=list)
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("elevation_svgs", mode="before")
    @classmethod
    def _parse_elevations(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            try:
                return json.loads(v or "[]")
            except (json.JSONDecodeError, TypeError):
                return []
        return v

    @field_validator("mep_plan", mode="before")
    @classmethod
    def _parse_mep_plan(cls, v):
        if v is None:
            return {}
        if isinstance(v, str):
            try:
                return json.loads(v or "{}")
            except (json.JSONDecodeError, TypeError):
                return {}
        return v

    @field_validator("lighting_schemes", mode="before")
    @classmethod
    def _parse_lighting(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            try:
                return json.loads(v or "[]")
            except (json.JSONDecodeError, TypeError):
                return []
        return v
