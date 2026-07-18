"""F32 场景编辑 Pydantic 模型"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


# ── 场景 ──


class SceneAutomationCreate(BaseModel):
    project_id: str
    scheme_id: str | None = None
    scene_name: str = Field(description="场景名称（如：回家模式）。也支持传 name 字段作为别名）")
    scene_type: str = "manual"
    # scene_type: manual / scheduled / triggered / geo
    trigger_condition: dict[str, Any] | None = None
    actions: list[dict[str, Any]] | None = None
    enabled: bool = True
    priority: int = 0

    @model_validator(mode="before")
    @classmethod
    def _accept_name_alias(cls, values: Any) -> Any:
        """允许前端传 name 作为 scene_name 的别名，提升 API 一致性"""
        if isinstance(values, dict) and "name" in values and "scene_name" not in values:
            values["scene_name"] = values.pop("name")
        return values


class SceneAutomationUpdate(BaseModel):
    scene_name: str | None = None
    scene_type: str | None = None
    trigger_condition: dict[str, Any] | None = None
    actions: list[dict[str, Any]] | None = None
    enabled: bool | None = None
    priority: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _accept_name_alias(cls, values: Any) -> Any:
        """允许前端传 name 作为 scene_name 的别名"""
        if isinstance(values, dict) and "name" in values and "scene_name" not in values:
            values["scene_name"] = values.pop("name")
        return values


class SceneAutomationResponse(BaseModel):
    id: str
    project_id: str
    scheme_id: str | None
    scene_name: str
    scene_type: str
    trigger_condition: dict[str, Any] | None
    actions: list[dict[str, Any]] | None
    enabled: bool
    priority: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── 生态对接 ──


class EcosystemIntegrationCreate(BaseModel):
    project_id: str
    ecosystem: str = Field(description="生态: homekit/mijia/harmonyos/alexa/google_home/tuya")
    auth_status: str = "disconnected"
    device_count: int = 0
    config: dict[str, Any] | None = None
    notes: str | None = None


class EcosystemIntegrationResponse(BaseModel):
    id: str
    project_id: str
    ecosystem: str
    auth_status: str
    device_count: int
    last_synced_at: datetime | None
    config: dict[str, Any] | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── 计算结果 ──


class SceneValidateResult(BaseModel):
    """场景校验结果"""

    valid: bool
    errors: list[str] = Field(default_factory=list, description="校验错误")


class SceneSimulateResult(BaseModel):
    """场景模拟执行结果"""

    scene_id: str
    scene_name: str
    would_execute: bool = Field(description="是否满足触发条件")
    actions_preview: list[dict[str, Any]] = Field(default_factory=list, description="预期执行动作")
    notes: list[str] = Field(default_factory=list, description="执行说明")


class SceneRecommendResult(BaseModel):
    """场景推荐结果"""

    room_type: str
    lifestyle: str
    recommended_scenes: list[dict[str, Any]] = Field(default_factory=list, description="推荐场景清单")


class SceneParseResult(BaseModel):
    """自然语言解析场景结果"""

    parsed: bool = Field(description="是否成功解析")
    scene_name: str | None = None
    scene_type: str | None = None
    trigger_condition: dict[str, Any] | None = None
    actions: list[dict[str, Any]] | None = None
    raw_text: str = Field(default="", description="原始文本")


class SceneSyncResult(BaseModel):
    """场景同步到生态结果"""

    scene_id: str
    ecosystem: str
    synced: bool = Field(description="是否同步成功")
    message: str = Field(default="", description="同步消息")
