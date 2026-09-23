"""FDE 现场服务记录（v1.17.4，表 fde_field_visits）

政策依据：工信厅科函〔2026〕414号 任务四——「鼓励服务商搭建**前线部署工程师
（FDE）团队，扎根用户现场**，保障场景落地」。

补齐缺口 G3：`space_assets` 是资产台账（改造状态机维度），无法回答
「谁在现场、做了什么、耗时多少、解决与否」。本表按**现场服务记录**维度登记，
支撑资源池报送中「配套服务」类别的真实证据与后续服务量核算。

纪律：
- `capability_tags` 只声明**实际具备**的维度
  （business 懂业务 / model 通模型 / security 知安全 / delivery 能交付），
  不硬凑四维（与 `elderly_design` 同纪律）。
- 归属按 `owner_id` 隔离（非 admin 仅见自己的记录）；带 `project_id` 时由 API 层
  走 `verify_project_access` 项目归属校验。
- 记录的是**现场服务事实**，不构成交付验收结论（验收以质检/节点确认为准）。
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# ── 枚举（单源：schema/service 校验共用，改此处须知会 API 契约）──

FDE_SERVICE_TYPES: tuple[str, ...] = (
    "installation",         # 设备 / 系统安装
    "commissioning",        # 联调联试
    "training",             # 用户培训
    "maintenance",          # 运维保养
    "safety_walkthrough",   # 安全巡检
    "consulting",           # 现场咨询规划
)

# 对齐政策「现场驻守 + 远程专家支持」
FDE_MODES: tuple[str, ...] = (
    "on_site",         # 现场驻守
    "remote_support",  # 远程专家支持
)

# 政策 FDE 四维能力（只声明实际具备的维度，不硬凑四维）
FDE_CAPABILITY_TAGS: tuple[str, ...] = (
    "business",   # 懂业务
    "model",      # 通模型
    "security",   # 知安全
    "delivery",   # 能交付
)


class FdeFieldVisit(Base):
    """FDE 前线部署工程师现场服务记录（表 fde_field_visits）"""

    __tablename__ = "fde_field_visits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # 归属：记录人（现场工程师 / 项目经理），API 层按 owner_id 做越权校验
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=True, index=True
    )
    # 关联空间资产（康养/疗愈/旅居/文旅/适老），可选
    space_asset_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("space_assets.id"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # 现场工程师（谁在现场）；留空表示未登记执行人，不猜测
    engineer_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    service_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="installation", index=True
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="on_site")
    # JSON list[str]，子集 ∈ FDE_CAPABILITY_TAGS（空列表 = 未声明维度）
    capability_tags: Mapped[list | None] = mapped_column(JSON, nullable=True)

    service_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    duration_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 现场问题是否已闭环（记录服务事实，不构成交付验收结论）
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner = relationship("User")
    project = relationship("Project")
