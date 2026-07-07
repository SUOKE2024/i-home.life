from datetime import datetime

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    project_id: str
    name: str = Field(min_length=1, max_length=200)
    phase: str = Field(default="preparation")
    assigned_to: str | None = None
    priority: int = Field(default=0, ge=0)
    start_date: datetime | None = None
    end_date: datetime | None = None
    description: str | None = None


class TaskResponse(BaseModel):
    id: str
    project_id: str
    name: str
    phase: str
    assigned_to: str | None = None
    status: str
    priority: int
    start_date: datetime | None = None
    end_date: datetime | None = None
    description: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LogCreate(BaseModel):
    task_id: str
    content: str = Field(min_length=1, max_length=2000)
    log_type: str = Field(default="daily")
    image_urls: str | None = None


class LogResponse(BaseModel):
    id: str
    task_id: str
    content: str
    log_type: str
    image_urls: str | None = None
    created_by: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class InspectionCreate(BaseModel):
    task_id: str
    inspector: str | None = None
    result: str | None = None
    images: str | None = None
    issues: str | None = None
    score: int | None = Field(None, ge=0, le=100)


class InspectionResponse(BaseModel):
    id: str
    task_id: str
    inspector: str | None = None
    status: str
    result: str | None = None
    images: str | None = None
    issues: str | None = None
    score: int | None = None
    inspected_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
