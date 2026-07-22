"""A6 施工预测性维护 — Pydantic schemas"""

from datetime import datetime

from pydantic import BaseModel, Field


class RiskPredictionResponse(BaseModel):
    id: str
    project_id: str
    risk_type: str
    risk_score: float
    probability: float
    impact_level: str
    trigger_factors: list | None = None
    affected_tasks: list | None = None
    mitigation_actions: list | None = None
    status: str
    predicted_at: datetime
    resolved_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PredictiveAnalysisResult(BaseModel):
    project_id: str
    analysis_time: datetime
    risks_created: int
    risks_active: int
    risks_list: list[RiskPredictionResponse] = []
    summary: str


class RiskMitigateRequest(BaseModel):
    note: str | None = None


class RiskResolveRequest(BaseModel):
    note: str | None = None


class ConstructionDashboardResponse(BaseModel):
    project_id: str
    project_name: str | None = None
    active_risks: list[RiskPredictionResponse] = []
    total_risks: int = 0
    active_count: int = 0
    mitigated_count: int = 0
    resolved_count: int = 0
    health_score: float = 100.0  # 施工健康度评分 0-100
    risk_breakdown: dict = {}  # 按 risk_type 分组的风险统计
    summary: str
