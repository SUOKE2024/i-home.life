"""F37 进度管理 Pydantic 模型"""

from datetime import datetime
from pydantic import BaseModel, Field


class ProgressAlertCreate(BaseModel):
    project_id: str
    task_id: str | None = None
    phase: str
    alert_type: str = "delay"
    severity: str = "medium"
    message: str
    planned_date: datetime | None = None
    actual_date: datetime | None = None
    delay_days: int = 0
    progress_percent: float = 0.0
    suggestion: str | None = None


class ProgressAlertResponse(BaseModel):
    id: str
    project_id: str
    task_id: str | None
    phase: str
    alert_type: str
    severity: str
    message: str
    planned_date: datetime | None
    actual_date: datetime | None
    delay_days: int
    progress_percent: float
    suggestion: str | None
    status: str
    resolved_at: datetime | None
    resolved_by: str | None
    resolution_note: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MilestoneTrackerResponse(BaseModel):
    id: str
    project_id: str
    milestone_code: str
    name: str
    planned_date: datetime | None
    actual_date: datetime | None
    planned_percent: float
    actual_percent: float
    status: str
    payment_ratio: float
    note: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProgressAnalysisRequest(BaseModel):
    """进度分析请求 — 基于项目任务列表 + 当前日期"""

    project_id: str
    tasks: list[dict] = Field(default_factory=list, description="施工任务列表")
    current_date: datetime | None = Field(default=None, description="当前日期，缺省为系统当前时间")
    milestones: list[dict] | None = Field(default=None, description="里程碑列表（可选）")


class ProgressAnalysisResponse(BaseModel):
    """进度分析结果"""

    project_id: str
    current_date: datetime
    overall_progress: float
    expected_progress: float
    progress_deviation: float
    phase_status: list[dict]
    alerts: list[dict]
    milestones: list[dict]
    risk_level: str
    summary: str
    suggestions: list[str]
