"""任务协调 Schema"""
from datetime import datetime
from pydantic import BaseModel, Field


class TaskCreateRequest(BaseModel):
    project_id: str
    task_type: str
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    assigned_agent: str
    priority: int = Field(default=5, ge=1, le=10)
    parent_task_id: str | None = None
    dependencies: list[str] | None = None
    claimable: bool = True
    claim_deadline: datetime | None = None
    claim_role: str | None = None


class TaskClaimRequest(BaseModel):
    task_id: str


class TaskAssignRequest(BaseModel):
    task_id: str
    user_id: str


class TaskCandidateResponse(BaseModel):
    id: str
    task_id: str
    user_id: str
    user_name: str | None = None
    user_avatar: str | None = None
    points_score: float
    experience_score: float
    rating_score: float
    composite_score: float
    score_breakdown: dict | None = None
    status: str

    model_config = {"from_attributes": True}


class TaskResponse(BaseModel):
    id: str
    project_id: str
    task_type: str
    title: str
    description: str | None = None
    assigned_agent: str
    assigned_user_id: str | None = None
    assigned_user_name: str | None = None
    priority: int
    status: str
    parent_task_id: str | None = None
    dependencies: list[str] | None = None
    claimable: bool
    claim_deadline: datetime | None = None
    claim_role: str | None = None
    result: dict | None = None
    created_by: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    candidates: list[TaskCandidateResponse] | None = None

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
    total: int
