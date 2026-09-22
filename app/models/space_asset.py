"""空间资产台账 — Phase 3 存量空间资产化（2026-09-13）

项目定位收口为「空间健康资产运营商」后的核心领域模型：面向云南区域**存量**
空间资源（康养 / 疗愈 / 旅居 / 文旅 / 适老住宅）建立统一资产台账，串联
「资产评估 → AI 智能化改造 → 交付 → 长期运营指标」。

轻资产约束（CLAUDE.md 商业模式红线）：
- 平台**不持有**房产，`asset_holder` 必须为业主 / 运营方 / 集体 / 政府等外部主体
- 平台角色恒为 `service_provider`（改造交付 + 智能运营 + 数据服务）
- 不做物业运营、不做房地产经纪

业态枚举（business_format）与索克生活
`lib/screens/suoke/lodge_manager_registration_screen.dart` `_lodgeTypes` 对齐，
避免生态两侧另造一套口径。
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ── 业态 / 类别 / 状态枚举（与索克生活侧对齐）──

ASSET_CATEGORIES: tuple[str, ...] = (
    "kangyang",            # 康养
    "healing",             # 疗愈
    "travel_residence",    # 旅居
    "cultural_tourism",    # 文旅
    "elderly_housing",     # 适老住宅
)

# 业态对齐索克生活 _lodgeTypes（药膳小院/森林药浴/康养研学/节气旅居）
BUSINESS_FORMATS: tuple[str, ...] = (
    "herb_food_courtyard",  # 药膳小院
    "forest_herbal_bath",   # 森林药浴
    "kangyang_study",       # 康养研学
    "seasonal_stay",        # 节气旅居
    "wellness_resort",      # 疗愈度假
    "cultural_site",        # 文旅点位
    "elderly_home",         # 适老住宅
    "other",
)

HOLDER_TYPES: tuple[str, ...] = (
    "private",       # 个人业主
    "enterprise",    # 企业
    "collective",    # 集体（村集体/合作社）
    "government",    # 政府/平台公司
)

RENOVATION_STATUSES: tuple[str, ...] = (
    "pending_assessment",  # 待评估
    "assessed",            # 已评估
    "in_renovation",       # 改造中
    "delivered",           # 已交付
    "operating",           # 运营中
    "suspended",           # 暂停/退出
)

# 平台角色恒为服务商（轻资产约束，不可配置为持有方）
PLATFORM_ROLE = "service_provider"


class SpaceAsset(Base):
    """空间资产台账（表 space_assets）"""

    __tablename__ = "space_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # 归属：录入人（业主/运营方对接人），API 层按 owner_id 做越权校验
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    # 关联装修/改造项目（可空：资产可先入台账，改造项目后建）
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("projects.id"), nullable=True, index=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # 区域（云南优先）：省 / 市 / 区县 / 详细地址
    province: Mapped[str] = mapped_column(String(50), nullable=False, default="云南省")
    city: Mapped[str] = mapped_column(String(50), nullable=False, default="昆明市")
    district: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 物理属性
    building_area_sqm: Mapped[float | None] = mapped_column(Float, nullable=True)
    room_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    floor_info: Mapped[str | None] = mapped_column(String(100), nullable=True)
    built_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    structure_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 分类与业态
    asset_category: Mapped[str] = mapped_column(String(30), nullable=False, default="kangyang")
    business_format: Mapped[str] = mapped_column(String(40), nullable=False, default="other")

    # 持有方（轻资产约束：不得为平台自身）
    asset_holder: Mapped[str] = mapped_column(String(200), nullable=False)
    holder_type: Mapped[str] = mapped_column(String(20), nullable=False, default="private")
    platform_role: Mapped[str] = mapped_column(String(30), nullable=False, default=PLATFORM_ROLE)

    # 改造状态机
    renovation_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending_assessment", index=True
    )
    # renovation_scope: JSON [{area, scope_type, package_code, budget}]
    renovation_scope: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # 关联 F42 快装套餐编码（PKG-48H-KITCHEN 等）
    retrofit_package_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # 关联 F41 适老改造方案
    elderly_scheme_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # 智能化就绪度
    smart_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    smart_readiness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    matter_device_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sensor_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scene_automation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 合规状态
    fire_safety_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    # 无障碍合规（GB 50763-2012）：pass / warning / fail / unknown
    accessibility_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")

    # 运营指标（JSON）：occupancy_rate / avg_daily_rate / health_alert_count /
    # energy_kwh_monthly / guest_satisfaction / revenue_monthly
    operation_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner = relationship("User")
    project = relationship("Project")
