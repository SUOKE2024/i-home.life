from datetime import datetime

from pydantic import BaseModel, Field


class ConstructionCrewCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    leader: str = Field(min_length=1, max_length=100)
    phone: str | None = None
    city: str | None = None
    district: str | None = None
    qualification: str = Field(default="B")
    specialties: list[str] = []
    rating: float = Field(default=4.0, ge=0, le=5)
    completed_projects: int = Field(default=0, ge=0)
    avg_duration: int = Field(default=60, ge=1)
    daily_rate: int = Field(default=800, ge=0)
    status: str = Field(default="available")
    introduction: str | None = None


class ConstructionCrewResponse(BaseModel):
    id: str
    name: str
    leader: str
    phone: str | None = None
    city: str | None = None
    district: str | None = None
    qualification: str
    specialties: list[str] = []
    rating: float
    completed_projects: int
    avg_duration: int
    daily_rate: int
    status: str
    introduction: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CrewMatchResponse(BaseModel):
    id: str
    project_id: str
    crew_id: str
    match_score: float
    score_breakdown: dict = {}
    recommendation: str | None = None
    status: str
    crew: ConstructionCrewResponse | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CrewMatchRequest(BaseModel):
    project_id: str
    city: str | None = None
    district: str | None = None
    required_specialties: list[str] = []
    budget_daily_rate_max: int | None = None
    expected_duration_days: int | None = None
    top_n: int = Field(default=5, ge=1, le=20)
