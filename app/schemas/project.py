from datetime import datetime

from pydantic import BaseModel, Field
from typing import Literal

# 项目类型枚举（与 console PROJECT_TYPE_LABELS / 模型注释对齐）
PROJECT_TYPE_VALUES = Literal[
    "full_renovation", "hard_decoration", "soft_furnishing",
    "curtain", "kitchen", "bathroom", "electrical", "carpentry",
    "painting", "plumbing", "masonry", "installation",
]


class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    room_type: str = Field(default="bedroom")
    area: float | None = None
    width: float | None = None
    height: float | None = None
    length: float | None = None


class RoomResponse(BaseModel):
    id: str
    floor_id: str
    name: str
    room_type: str
    area: float | None = None
    width: float | None = None
    height: float | None = None
    length: float | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FloorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    floor_number: int = Field(default=1, ge=1)
    area: float | None = None
    rooms: list[RoomCreate] = []


class FloorResponse(BaseModel):
    id: str
    project_id: str
    name: str
    floor_number: int
    area: float | None = None
    rooms: list[RoomResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: str | None = None
    total_area: float | None = None
    project_type: PROJECT_TYPE_VALUES = "full_renovation"
    source: Literal["manual", "ar_measure"] = "manual"
    description: str | None = Field(default=None, max_length=500)
    # 创建时收集的可选信息（户型/定位/联系方式），落库持久化
    house_type: str | None = Field(default=None, max_length=50)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    contact_name: str | None = Field(default=None, max_length=100)
    contact_phone: str | None = Field(default=None, max_length=30)
    floors: list[FloorCreate] = []


class ProjectUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    total_area: float | None = None
    project_type: PROJECT_TYPE_VALUES | None = None
    status: str | None = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    address: str | None = None
    total_area: float | None = None
    status: str
    project_type: str = "full_renovation"
    house_type: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    owner_id: str
    floors: list[FloorResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    address: str | None = None
    total_area: float | None = None
    status: str
    project_type: str = "full_renovation"
    house_type: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    owner_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
