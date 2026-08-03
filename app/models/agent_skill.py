"""Agent Skill 资产模型 — scope-owned 可授权共享的 Agent 能力资产

借鉴 YC QM（2026-07-31 开源）的 Skill 设计：
- scope-owned：每个 Skill 归属 personal/project/team/org 作用域
- share by grant：可授权给指定用户/团队
- admin gated promotion：提升到 org 级需 admin 审核
- 版本化 + 回退：每次更新 version+1，可回退到历史版本
- skill_pack 导入：从 git URL 导入外部 Skill 包

字段对齐：
- BaseAgent 类属性（agent_name/system_prompt/provider/tools/cost_tier）
- KnowledgeEntry 资产模式（scope/version/status/created_by/reviewed_by）

设计约束（对齐 CLAUDE.md）：
- owner_scope/owner_id 强隔离，非 owner 仅在 share_grants 含其 id 或 share_scope=org 时可见
- 软删除（deleted_at），不物理删除
- 版本链通过 parent_version_id 串联（仅直接 parent，不递归）
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    String, Text, DateTime, Integer, ForeignKey, UniqueConstraint,
    CheckConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# 作用域常量（对齐 agent_memory_service._ALL_SCOPES）
SCOPE_PERSONAL = "personal"
SCOPE_PROJECT = "project"
SCOPE_TEAM = "team"
SCOPE_ORG = "org"
_ALL_SCOPES = (SCOPE_PERSONAL, SCOPE_PROJECT, SCOPE_TEAM, SCOPE_ORG)

# 状态常量（对齐 KnowledgeEntry）
STATUS_DRAFT = "draft"
STATUS_ACTIVE = "active"
STATUS_ARCHIVED = "archived"
_ALL_STATUSES = (STATUS_DRAFT, STATUS_ACTIVE, STATUS_ARCHIVED)

# 共享范围
SHARE_NONE = "none"      # 不共享
SHARE_GRANT = "grant"    # 按授权共享（share_grants 列表）
SHARE_ORG = "org"        # 全组织可见
_ALL_SHARE_SCOPES = (SHARE_NONE, SHARE_GRANT, SHARE_ORG)


class AgentSkill(Base):
    """Agent Skill 资产条目（表 agent_skills）

    一个 Skill = 一份可复用的 Agent 配置（prompt + 工具白名单 + 验收用例）。
    归属某作用域，可授权共享，可版本化回退。
    """

    __tablename__ = "agent_skills"
    __table_args__ = (
        # 同 owner_scope+owner_id+name 下 version 唯一
        UniqueConstraint(
            "owner_scope", "owner_id", "name", "version",
            name="uq_skill_owner_name_ver",
        ),
        CheckConstraint(
            "status IN ('draft', 'active', 'archived')",
            name="chk_skill_status",
        ),
        CheckConstraint(
            "owner_scope IN ('personal', 'project', 'team', 'org')",
            name="chk_skill_owner_scope",
        ),
        CheckConstraint(
            "share_scope IN ('none', 'grant', 'org')",
            name="chk_skill_share_scope",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    # 标识
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # 归属（对齐 QM scope）
    owner_scope: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    # personal→user_id / project→project_id / team→team_id / org→固定 "org"

    # Agent 配置（对齐 BaseAgent 类属性）
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="deepseek")
    tools: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON 数组
    cost_tier: Mapped[str] = mapped_column(String(20), nullable=False, default="standard")

    # 验收用例（评估报告要求"完成工作的步骤、边界、工具和验收方式"）
    acceptance_criteria: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]",
    )  # JSON 数组：[{"input":..., "expected":...}]

    # 版本与状态（对齐 KnowledgeEntry）
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=STATUS_DRAFT, index=True,
    )
    parent_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # 回退引用：指向上一版本 id（仅直接 parent，不递归）

    # 共享（对齐 QM share by grant + admin gated promotion）
    share_scope: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SHARE_NONE,
    )
    share_grants: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]",
    )  # JSON 数组：["user_id1", "team_id2"]

    # 审计
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False,
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # skill_pack 导入溯源
    skill_pack_source: Mapped[str | None] = mapped_column(String(500), nullable=True)

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )
