"""F35 服务者匹配 Pydantic 模型"""

from datetime import datetime
from pydantic import BaseModel, Field


class ServiceWorkerCreate(BaseModel):
    name: str
    phone: str | None = None
    avatar_url: str | None = None
    city: str | None = None
    district: str | None = None
    role: str  # designer / supervisor / estimator
    role_attributes: dict | None = None
    qualification: str = "B"
    rating: float = 4.0
    completed_projects: int = 0
    years_of_experience: int = 1
    hourly_rate: int = 200
    daily_rate: int = 800
    status: str = "available"
    introduction: str | None = None
    certifications: list[str] | None = None
    portfolio_urls: list[str] | None = None


class ServiceWorkerResponse(BaseModel):
    id: str
    name: str
    phone: str | None
    avatar_url: str | None
    city: str | None
    district: str | None
    role: str
    role_attributes: dict
    qualification: str
    rating: float
    completed_projects: int
    years_of_experience: int
    hourly_rate: int
    daily_rate: int
    status: str
    introduction: str | None
    certifications: list[str]
    portfolio_urls: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkerMatchRequest(BaseModel):
    """服务者匹配请求"""

    project_id: str
    role: str = Field(..., description="designer / supervisor / estimator")
    city: str | None = None
    district: str | None = None
    # 通用筛选
    required_styles: list[str] | None = Field(default=None, description="设计师：风格偏好")
    required_phases: list[str] | None = Field(default=None, description="监理：擅长阶段")
    required_budget_types: list[str] | None = Field(default=None, description="预算师：预算类型")
    budget_hourly_rate_max: int | None = None
    budget_daily_rate_max: int | None = None
    min_rating: float = 0.0
    min_experience: int = 0
    top_n: int = 5


class WorkerMatchResponse(BaseModel):
    id: str
    project_id: str
    worker_id: str
    role: str
    match_score: float
    score_breakdown: dict
    recommendation: str | None
    status: str
    worker: ServiceWorkerResponse | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
