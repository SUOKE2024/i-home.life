"""F38 质量管理 Pydantic 模型"""

from datetime import datetime
from pydantic import BaseModel, Field


class QualityIssueCreate(BaseModel):
    project_id: str
    task_id: str | None = None
    inspection_id: str | None = None
    phase: str
    category: str
    description: str
    severity: str = "medium"
    images: str | None = None
    detected_by: str = "manual"
    standard: str | None = None
    location: str | None = None


class QualityIssueUpdate(BaseModel):
    status: str | None = None
    resolution: str | None = None
    resolved_by: str | None = None
    verified_by: str | None = None


class QualityIssueResponse(BaseModel):
    id: str
    project_id: str
    task_id: str | None
    inspection_id: str | None
    phase: str
    category: str
    description: str
    severity: str
    status: str
    images: str | None
    detected_by: str
    standard: str | None
    location: str | None
    resolution: str | None
    resolved_at: datetime | None
    resolved_by: str | None
    verified_by: str | None
    verified_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RectificationOrderCreate(BaseModel):
    project_id: str
    title: str
    description: str | None = None
    phase: str
    issue_ids: list[str] | None = None
    responsible_party: str | None = None
    responsible_phone: str | None = None
    deadline: datetime | None = None
    priority: str = "medium"
    cost: float = 0.0
    notes: str | None = None


class RectificationOrderResponse(BaseModel):
    id: str
    project_id: str
    order_no: str
    title: str
    description: str | None
    phase: str
    issue_ids: str | None
    responsible_party: str | None
    responsible_phone: str | None
    deadline: datetime | None
    priority: str
    status: str
    cost: float
    notes: str | None
    completed_at: datetime | None
    verified_at: datetime | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QualityAssessmentCreate(BaseModel):
    project_id: str
    phase: str
    total_items: int = 0
    passed: int = 0
    failed: int = 0
    score: float = 0.0
    verdict: str = "pending"
    assessor: str | None = None
    summary: str | None = None
    issues_summary: str | None = None


class QualityAssessmentResponse(BaseModel):
    id: str
    project_id: str
    phase: str
    total_items: int
    passed: int
    failed: int
    score: float
    verdict: str
    assessor: str | None
    summary: str | None
    issues_summary: str | None
    assessed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QualityDetectRequest(BaseModel):
    """AI 质量问题检测请求"""

    project_id: str
    phase: str
    inspection_results: list[dict] = Field(default_factory=list, description="质检结果列表")
    task_id: str | None = None
    inspection_id: str | None = None
