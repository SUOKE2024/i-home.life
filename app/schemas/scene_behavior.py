"""A4 预测式智能场景推荐 Pydantic schema"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── 行为日志 ──


class SceneBehaviorLogCreate(BaseModel):
    """记录用户场景行为"""

    project_id: str
    action_type: str = Field(
        description="scene_activate / scene_deactivate / scene_create / scene_modify / "
        "manual_trigger / time_trigger / sensor_trigger"
    )
    scene_id: str | None = None
    room_type: str | None = None
    time_of_day: int | None = Field(default=None, ge=0, le=23)
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    duration_seconds: int | None = None
    device_states_before: dict[str, Any] | None = None
    device_states_after: dict[str, Any] | None = None
    ambient_data: dict[str, Any] | None = None


class SceneBehaviorLogResponse(BaseModel):
    id: str
    project_id: str
    user_id: str
    action_type: str
    scene_id: str | None
    room_type: str | None
    time_of_day: int | None
    day_of_week: int | None
    duration_seconds: int | None
    device_states_before: dict[str, Any] | None
    device_states_after: dict[str, Any] | None
    ambient_data: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── 预测场景 ──


class PredictedSceneResponse(BaseModel):
    id: str
    project_id: str
    user_id: str
    scene_name: str
    room_type: str | None
    trigger_time_hint: str | None
    trigger_condition: dict[str, Any] | None
    actions: list[dict[str, Any]] | None
    confidence: float
    based_on_count: int
    status: str
    explanation: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PredictedSceneAcceptResult(BaseModel):
    """接受预测并创建为真实场景的结果"""

    prediction_id: str
    scene_id: str
    scene_name: str
    message: str
