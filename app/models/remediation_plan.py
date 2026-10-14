"""站点修复清单（v1.18.0，表 remediation_plans）

借鉴来源：数智前线《万小智，让AI从网站生成走向企业经营》（2026-09-24）——
「一份报告可能涉及几十项检查……找人明确问题、联系开发、落实修改，再检查改动
有没有生效，很容易卡在半道没有下文」。本表承载**诊断 → 清单 → 确认 → 执行 →
复检 → 回滚**的完整留痕，避免清单止步于「报告」。

纪律：
- `items` 为 JSON 清单（每条含 tier：auto / confirm / human_only）；
- `backups` 为执行前文件全文备份（JSON：相对路径 → {existed, content}），
  `rollback` 据此确定性还原，不留不可逆改动；
- `status` 与 `applied_at` / `verified_at` / `rolled_back_at` 一一对应，
  执行 ≠ 生效：须 `verified` 才算修复闭环（复检为重新审计的确定性比对）。
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# 单源：status 允许集（模型约束 / 迁移 / API 契约逐字一致）
REMEDIATION_PLAN_STATUSES: tuple[str, ...] = (
    "proposed",          # 已生成，待确认
    "applied",           # 已执行白名单条目，待复检
    "verified",          # 复检通过（修复生效）
    "partially_verified",  # 部分条目复检通过
    "rolled_back",       # 已回滚
)


class RemediationPlan(Base):
    """站点修复清单（诊断 → 执行 → 复检 → 回滚的留痕）"""

    __tablename__ = "remediation_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_type: Mapped[str] = mapped_column(String(40), nullable=False, default="site_ai_visibility")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="proposed")
    # 审计时的站点静态产物目录（复检时按同一目录重跑，保证可比）
    static_root: Mapped[str | None] = mapped_column(String(200), nullable=True)
    score_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_after: Mapped[int | None] = mapped_column(Integer, nullable=True)

    items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 执行前文件全文备份：{相对路径: {"existed": bool, "content": str|None}}
    backups: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('proposed', 'applied', 'verified', 'partially_verified', 'rolled_back')",
            name="chk_remediation_plan_status",
        ),
    )
