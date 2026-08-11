import json
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


def _parse_room_status(value) -> dict[str, str]:
    """将 room_status 的 JSON 字符串解析为 dict；非 dict 视为空。"""
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    if isinstance(value, dict):
        return value
    return {}


class FloorPlanCreate(BaseModel):
    project_id: str
    name: str = Field(default="未命名方案", max_length=200)
    data: str = Field(default="")                # 户型矢量数据 (JSON)，新建时可留空
    wall_height: float = Field(default=2.8, ge=2.0, le=5.0)
    total_area: float = Field(default=0.0, ge=0)
    room_count: int = Field(default=0, ge=0)
    room_status: dict[str, str] | None = None   # 逐房间状态 {"客厅": "in_progress", ...}


class FloorPlanResponse(BaseModel):
    id: str
    project_id: str
    name: str
    data: str
    wall_height: float
    total_area: float
    room_count: int
    room_status: dict[str, str] = {}
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("room_status", mode="before")
    @classmethod
    def _parse_room_status(cls, v):
        return _parse_room_status(v)

    model_config = {"from_attributes": True}


class FloorPlanUpdate(BaseModel):
    """户型方案部分更新 — 所有字段可选"""
    name: str | None = None
    data: str | None = None
    wall_height: float | None = None
    total_area: float | None = None
    room_count: int | None = None
    room_status: dict[str, str] | None = None
    is_active: bool | None = None


class FloorPlanListItem(BaseModel):
    id: str
    project_id: str
    name: str
    total_area: float
    room_count: int
    wall_height: float
    room_status: dict[str, str] = {}
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("room_status", mode="before")
    @classmethod
    def _parse_room_status(cls, v):
        return _parse_room_status(v)

    model_config = {"from_attributes": True}
