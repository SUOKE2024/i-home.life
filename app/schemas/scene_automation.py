"""F32 场景编辑 Pydantic 模型"""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, Field, model_validator

# 有桥接实现的生态白名单（与 app/services/ecosystem_bridge.py BridgeFactory._bridges 逐字一致，
# 由 tests/test_smart_home_ecosystem_chain.py 断言防漂移）。
# 2026-09-23：此前为自由字符串且文档列出 alexa/google_home，但两者根本没有桥 → 创建成功却永远
# 无法同步（假能力）。现收窄到有桥生态；传入值统一小写（保持此前 BridgeFactory 大小写不敏感行为）。
EcosystemName = Annotated[
    Literal["mijia", "harmonyos", "homekit", "tuya", "matter"],
    BeforeValidator(lambda v: v.lower() if isinstance(v, str) else v),
]


# ── 场景 ──


class SceneAutomationCreate(BaseModel):
    project_id: str
    scheme_id: str | None = None
    scene_name: str = Field(description="场景名称（如：回家模式）。也支持传 name 字段作为别名）")
    scene_type: str = "manual"
    # scene_type: manual / scheduled / triggered / geo
    trigger_condition: dict[str, Any] | None = None
    actions: list[dict[str, Any]] | None = None
    ecosystem: EcosystemName | None = Field(
        default=None,
        description="执行动作所用生态桥: mijia/homekit/harmonyos/tuya/matter；不传则按项目已配置凭据的生态解析",
    )
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
    ecosystem: EcosystemName | None = None
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
    ecosystem: str | None = None
    enabled: bool
    priority: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── 生态对接 ──


class EcosystemIntegrationCreate(BaseModel):
    project_id: str
    ecosystem: EcosystemName = Field(
        description="生态: mijia/harmonyos/homekit/tuya/matter（仅接受有桥接实现的生态，无桥生态 422 而非假能力）"
    )
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
    # v1.2.2：暴露失败原因（not_implemented/invalid_credentials/bridge_error），
    # 便于前端按原因差异化提示，亦方便排障。成功时为 None。
    reason: str | None = Field(default=None, description="失败原因（成功时为 None）")


# ── 场景执行（P0 3D 场景/语音触发入口，2026-08-12）──


class SceneExecuteRequest(BaseModel):
    """场景执行请求"""

    trigger_source: str = Field(default="vr_overlay", description="触发来源: vr_overlay/voice/app")
    # 2026-08-27 P2 遗留修复：异步执行模式（请求立即返回，后台执行 + WS 推送结果）
    execute_async: bool = Field(default=False, description="true=后台异步执行，结果经 WebSocket 推送")


class SceneActionResult(BaseModel):
    """场景动作执行结果 — action_status 诚实标注"""

    device_id: str | None = None
    device_name: str | None = None
    action: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    action_status: str = Field(description="pending/success/failed/skipped/rejected")
    note: str | None = None


class SceneExecuteResult(BaseModel):
    """场景执行结果"""

    scene_id: str
    scene_name: str
    executed: bool
    actions: list[SceneActionResult] = Field(default_factory=list)
    triggered_at: str
    async_queued: bool = Field(default=False, description="是否为异步执行模式（结果经 WS 推送）")
