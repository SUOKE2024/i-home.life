"""F35 服务者匹配 Pydantic 模型"""

from datetime import datetime
from pydantic import BaseModel, Field


class ServiceWorkerCreate(BaseModel):
    name: str
    phone: str | None = None
    avatar_url: str | None = None
    city: str | None = None
    district: str | None = None
    role: str = Field(
        ...,
        description="角色：designer / supervisor / estimator / carpenter / plumber_electrician / curtain_installer",
    )
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
    role: str = Field(
        ...,
        description="designer / supervisor / estimator / carpenter / plumber_electrician / curtain_installer",
    )
    city: str | None = None
    district: str | None = None
    # 设计师筛选
    required_styles: list[str] | None = Field(default=None, description="设计师：风格偏好")
    # 监理筛选
    required_phases: list[str] | None = Field(default=None, description="监理：擅长阶段")
    # 预算师筛选
    required_budget_types: list[str] | None = Field(default=None, description="预算师：预算类型")
    # 木工筛选
    required_skills: list[str] | None = Field(
        default=None,
        description="木工：技能类型（furniture/door_window/cabinet/flooring/ceiling）",
    )
    # 水电安装工筛选
    required_specialties: list[str] | None = Field(
        default=None,
        description="水电安装工：专业领域（water_supply/drainage/electrical/gas/heating）",
    )
    # 窗帘安装工筛选
    required_curtain_types: list[str] | None = Field(
        default=None,
        description="窗帘安装工：窗帘类型（roller/roman/motorized/fabric/sheer）",
    )
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
