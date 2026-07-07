from datetime import datetime

from pydantic import BaseModel, Field


class FloorPlanCreate(BaseModel):
    project_id: str
    name: str = Field(default="未命名方案", max_length=200)
    data: str
    wall_height: float = Field(default=2.8, ge=2.0, le=5.0)
    total_area: float = Field(default=0.0, ge=0)
    room_count: int = Field(default=0, ge=0)


class FloorPlanResponse(BaseModel):
    id: str
    project_id: str
    name: str
    data: str
    wall_height: float
    total_area: float
    room_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FloorPlanListItem(BaseModel):
    id: str
    project_id: str
    name: str
    total_area: float
    room_count: int
    wall_height: float
    updated_at: datetime

    model_config = {"from_attributes": True}
