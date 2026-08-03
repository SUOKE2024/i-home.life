"""Agent 长期记忆模型 — 跨会话结构化记忆存储

保存用户级长期记忆（偏好 / 位置 / 关键事实），支持：
1. 跨会话记忆：对话自动提取（extract_and_store_memories）+ 手动管理
2. 时间/空间感知注入：location 类目记忆供空间感知上下文使用
3. 偏好学习增强：preference 类目记忆与 L4 反馈学习互补

隐私约束（对齐 CLAUDE.md 会话加密硬约束）：
- 记忆内容 user_id 强隔离，查询必须携带 user_id
- 记忆文本只存短句（extract 截断），不做 PII 明文扩散
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    String, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentMemory(Base):
    """用户级 Agent 长期记忆条目

    category: preference(偏好) / location(位置) / fact(关键事实)
    memory_key: 记忆键（如 style / city / budget_range），同 user+category 内唯一
    memory_value: 记忆内容文本
    source: 来源（chat 自动提取 / manual 手动 / agent_name）
    """

    __tablename__ = "agent_memories"
    __table_args__ = (
        # v1.4.x: 唯一约束加入 scope/project_id，支持同 user 在不同
        # 项目/团队作用域下保存同名记忆（如各项目的「风格偏好」）。
        UniqueConstraint(
            "user_id", "category", "scope", "project_id", "memory_key",
            name="uq_agent_memory_user_cat_scope_key",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False, default="fact")
    memory_key: Mapped[str] = mapped_column(String(100), nullable=False)
    memory_value: Mapped[str] = mapped_column(Text, nullable=False)

    # v1.4.x 记忆作用域（借鉴 YC QM Scope）：
    # personal=仅本人（默认）/ project=项目内共享 / team=团队 / org=全组织
    # project_id 在 scope=project 时记录所属项目，保证记忆归属可追溯。
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="personal", index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    # 来源：chat（对话自动提取）/ manual（用户手动保存）/ agent_name（Agent 写入）
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 重要度（1-5），上下文注入排序用
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # 访问统计（可观测：哪些记忆被高频使用）
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )
