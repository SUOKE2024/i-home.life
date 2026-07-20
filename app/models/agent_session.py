"""Agent 会话持久化模型 — 智能体对话历史存储

保存用户与 AI Agent 的完整对话会话，支持：
1. 跨页面/跨端会话恢复（Web ↔ Flutter）
2. 历史会话浏览和继续对话
3. 会话元数据（标题、agent类型、项目关联）
4. 隐私保护：内容摘要化存储，支持软删除
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Integer, Text, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AgentSession(Base):
    """Agent 对话会话"""
    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("projects.id"), nullable=True, index=True)

    # 会话标题：自动从首条用户消息截取（最多 100 字符），去除 PII
    title: Mapped[str] = mapped_column(String(100), nullable=False, default="新的对话")

    # 会话中的主要 agent 类型（多个 agent 参与时取首次路由结果）
    primary_agent_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 消息数量（缓存，避免每次 COUNT）
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 软删除
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    # 关系
    user = relationship("User")
    project = relationship("Project")
    messages = relationship("AgentMessage", back_populates="session", cascade="all, delete-orphan",
                            order_by="AgentMessage.sequence")


class AgentMessage(Base):
    """Agent 对话中的单条消息"""
    __tablename__ = "agent_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_sessions.id"), nullable=False, index=True)

    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user / assistant / system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    agent_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 消息序号（在会话内自增，用于排序和分页）
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 消息内容哈希（用于去重和反馈关联）
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关系
    session = relationship("AgentSession", back_populates="messages")
