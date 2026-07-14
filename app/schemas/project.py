from datetime import datetime

from pydantic import BaseModel, Field


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
    project_type: str = Field(default="full_renovation")
    # full_renovation(整装) / hard_decoration(硬装) / soft_furnishing(软装) /
    # curtain(窗帘定制) / kitchen(厨房改造) / bathroom(卫浴改造) /
    # electrical(电路改造) / carpentry(木工制作) / painting(油漆涂刷) /
    # plumbing(水管改造) / masonry(泥瓦铺贴) / installation(设备安装)
    source: str = Field(default="manual")
    # manual / ar_measure
    floors: list[FloorCreate] = []


class ProjectUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    total_area: float | None = None
    project_type: str | None = None
    status: str | None = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    address: str | None = None
    total_area: float | None = None
    status: str
    project_type: str = "full_renovation"
    owner_id: str
    floors: list[FloorResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    id: str
    name: str
    address: str | None = None
    total_area: float | None = None
    status: str
    project_type: str = "full_renovation"
    owner_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
