"""Agent 工具调用批准模型 — strict 安全 posture 的异步批准状态机

借鉴 YC QM（2026-07-31 开源）的 strict posture：每个工具调用暂停等人批准。
在 FC 无状态环境下调整为"拒绝-重新触发"模式：
- strict 模式下高危工具调用 → 创建 AgentApproval(state=pending) → 返回 needs_approval
- 用户通过 API 显式 approve → state=approved
- 用户显式调 execute → 校验 approved + 未过期 → 执行工具（绕过二次批准）
- 超 TTL → state=expired

对齐 a2a_task.py 的异步状态机范式（submitted/working/completed + TTL）。
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import (
    String, Text, DateTime, CheckConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# 批准请求默认 TTL：24 小时（对齐 A2A_TASK_DEFAULT_TTL_HOURS）
APPROVAL_DEFAULT_TTL_HOURS = 24

# 状态常量
STATE_PENDING = "pending"
STATE_APPROVED = "approved"
STATE_REJECTED = "rejected"
STATE_EXPIRED = "expired"
_ALL_STATES = (STATE_PENDING, STATE_APPROVED, STATE_REJECTED, STATE_EXPIRED)


class AgentApproval(Base):
    """Agent 工具调用批准请求（表 agent_approvals）

    一条记录 = 一次 strict 模式下被拦截的工具调用。
    """

    __tablename__ = "agent_approvals"
    __table_args__ = (
        CheckConstraint(
            "state IN ('pending', 'approved', 'rejected', 'expired')",
            name="chk_approval_state",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    approval_id: Mapped[str] = mapped_column(
        String(48), nullable=False, unique=True, index=True,
    )  # apr_ 前缀 + 12 位 hex

    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    arguments: Mapped[str] = mapped_column(Text, nullable=False, default="{}")  # JSON

    # 上下文（对齐 AgentTrace）
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="personal")
    trace_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # 状态机
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=STATE_PENDING, index=True,
    )
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc) + timedelta(hours=APPROVAL_DEFAULT_TTL_HOURS),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )
