"""FDE 现场服务记录 Pydantic 模型（v1.17.4）

枚举单源：`app/models/fde_field_service.py`（FDE_SERVICE_TYPES / FDE_MODES /
FDE_CAPABILITY_TAGS）。政策依据：工信厅科函〔2026〕414号 任务四（FDE 扎根现场）。
诚实纪律：capability_tags 只声明实际具备的维度，不硬凑四维。
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

FdeServiceType = Literal[
    "installation", "commissioning", "training",
    "maintenance", "safety_walkthrough", "consulting",
]
FdeMode = Literal["on_site", "remote_support"]
FdeCapabilityTag = Literal["business", "model", "security", "delivery"]


class FdeFieldVisitCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200, description="现场服务事由")
    engineer_name: str | None = Field(default=None, max_length=100, description="现场工程师")
    service_type: FdeServiceType = "installation"
    mode: FdeMode = "on_site"
    capability_tags: list[FdeCapabilityTag] | None = Field(
        default=None,
        description="实际具备的 FDE 能力维度（business/model/security/delivery），"
                    "允许为空——不硬凑四维",
    )
    service_date: date | None = None
    duration_hours: float = Field(default=0.0, ge=0, description="现场服务工时（小时）")
    findings: str | None = Field(default=None, description="现场发现与处理记录")
    resolved: bool = Field(default=False, description="现场问题是否闭环（非交付验收结论）")

    project_id: str | None = None
    space_asset_id: str | None = None


class FdeFieldVisitUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    engineer_name: str | None = Field(default=None, max_length=100)
    service_type: FdeServiceType | None = None
    mode: FdeMode | None = None
    capability_tags: list[FdeCapabilityTag] | None = None
    service_date: date | None = None
    duration_hours: float | None = Field(default=None, ge=0)
    findings: str | None = None
    resolved: bool | None = None
    project_id: str | None = None
    space_asset_id: str | None = None


class FdeFieldVisitResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    owner_id: str
    project_id: str | None
    space_asset_id: str | None
    title: str
    engineer_name: str | None
    service_type: str
    mode: str
    capability_tags: list[str] | None
    service_date: date | None
    duration_hours: float
    findings: str | None
    resolved: bool
    created_at: datetime | None
    updated_at: datetime | None
