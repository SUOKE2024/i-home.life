"""空间资产台账 Pydantic 模型（Phase 3，2026-09-13）

业态 / 类别 / 持有方类型枚举与 app/models/space_asset.py 单源对齐。
轻资产约束：platform_role 为只读输出，不接受写入。
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.space_asset import (
    ASSET_CATEGORIES,
    BUSINESS_FORMATS,
    HOLDER_TYPES,
    RENOVATION_STATUSES,
)

AssetCategory = Literal[
    "kangyang", "healing", "travel_residence", "cultural_tourism", "elderly_housing"
]
BusinessFormat = Literal[
    "herb_food_courtyard", "forest_herbal_bath", "kangyang_study", "seasonal_stay",
    "wellness_resort", "cultural_site", "elderly_home", "other"
]
HolderType = Literal["private", "enterprise", "collective", "government"]
RenovationStatus = Literal[
    "pending_assessment", "assessed", "in_renovation", "delivered", "operating", "suspended"
]
ComplianceStatus = Literal["pass", "warning", "fail", "unknown"]


class SpaceAssetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    asset_holder: str = Field(
        min_length=1, max_length=200,
        description="资产持有方（业主/运营方/集体/政府）；不得为平台自身",
    )
    province: str = Field(default="云南省", max_length=50)
    city: str = Field(default="昆明市", max_length=50)
    district: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=300)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    building_area_sqm: float | None = Field(default=None, gt=0)
    room_count: int | None = Field(default=None, ge=0)
    floor_info: str | None = Field(default=None, max_length=100)
    built_year: int | None = Field(default=None, ge=1800, le=2200)
    structure_type: str | None = Field(default=None, max_length=50)

    asset_category: AssetCategory = "kangyang"
    business_format: BusinessFormat = "other"
    holder_type: HolderType = "private"

    project_id: str | None = None
    renovation_scope: list[dict[str, Any]] | None = None
    retrofit_package_code: str | None = Field(default=None, max_length=40)
    elderly_scheme_id: str | None = None

    matter_device_count: int = Field(default=0, ge=0)
    sensor_count: int = Field(default=0, ge=0)
    scene_automation_count: int = Field(default=0, ge=0)
    fire_safety_status: ComplianceStatus = "unknown"
    accessibility_status: ComplianceStatus = "unknown"

    operation_metrics: dict[str, Any] | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _reject_platform_holder(self) -> "SpaceAssetCreate":
        """轻资产约束：持有方不得为平台自身（与 service 层双重校验）。"""
        for kw in ("索克家居", "i-home.life", "索克生活", "索克（昆明）"):
            if kw in self.asset_holder:
                raise ValueError(
                    f"asset_holder 不得为平台自身（命中「{kw}」）——"
                    "本平台为轻资产改造服务商，不持有房产"
                )
        return self


class SpaceAssetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    asset_holder: str | None = Field(default=None, min_length=1, max_length=200)
    district: str | None = None
    address: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    building_area_sqm: float | None = Field(default=None, gt=0)
    room_count: int | None = Field(default=None, ge=0)
    floor_info: str | None = None
    built_year: int | None = Field(default=None, ge=1800, le=2200)
    structure_type: str | None = None
    asset_category: AssetCategory | None = None
    business_format: BusinessFormat | None = None
    holder_type: HolderType | None = None
    project_id: str | None = None
    renovation_scope: list[dict[str, Any]] | None = None
    retrofit_package_code: str | None = None
    elderly_scheme_id: str | None = None
    matter_device_count: int | None = Field(default=None, ge=0)
    sensor_count: int | None = Field(default=None, ge=0)
    scene_automation_count: int | None = Field(default=None, ge=0)
    fire_safety_status: ComplianceStatus | None = None
    accessibility_status: ComplianceStatus | None = None
    operation_metrics: dict[str, Any] | None = None
    notes: str | None = None


class SpaceAssetResponse(BaseModel):
    id: str
    owner_id: str
    project_id: str | None
    name: str
    province: str
    city: str
    district: str | None
    address: str | None
    latitude: float | None
    longitude: float | None
    building_area_sqm: float | None
    room_count: int | None
    floor_info: str | None
    built_year: int | None
    structure_type: str | None
    asset_category: str
    business_format: str
    asset_holder: str
    holder_type: str
    platform_role: str
    renovation_status: str
    renovation_scope: list | None
    retrofit_package_code: str | None
    elderly_scheme_id: str | None
    smart_ready: bool
    smart_readiness_score: float
    matter_device_count: int
    sensor_count: int
    scene_automation_count: int
    fire_safety_status: str
    accessibility_status: str
    operation_metrics: dict | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StatusTransitionRequest(BaseModel):
    new_status: RenovationStatus

    @field_validator("new_status")
    @classmethod
    def _check_known(cls, v: str) -> str:
        if v not in RENOVATION_STATUSES:
            raise ValueError(f"new_status 非法，可选: {', '.join(RENOVATION_STATUSES)}")
        return v


class ReadinessBreakdownResponse(BaseModel):
    asset_id: str
    score: float
    smart_ready: bool
    breakdown: dict[str, Any]


class PortfolioSummaryResponse(BaseModel):
    total_assets: int
    by_category: dict[str, int]
    by_status: dict[str, int]
    by_city: dict[str, int]
    avg_smart_readiness: float
    smart_ready_count: int
    total_area_sqm: float
    platform_role: str | None = None
    note: str | None = None


class EnumsResponse(BaseModel):
    asset_categories: list[str]
    business_formats: list[str]
    holder_types: list[str]
    renovation_statuses: list[str]
    platform_role: str


__all__ = [
    "ASSET_CATEGORIES", "BUSINESS_FORMATS", "HOLDER_TYPES", "RENOVATION_STATUSES",
    "SpaceAssetCreate", "SpaceAssetUpdate", "SpaceAssetResponse",
    "StatusTransitionRequest", "ReadinessBreakdownResponse",
    "PortfolioSummaryResponse", "EnumsResponse",
]
