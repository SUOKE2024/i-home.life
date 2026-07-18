"""IM 群组模型 — F40 三方协作（业主/设计师/工长）"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Text, Integer, Index, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ChatMessage(Base):
    """聊天消息"""
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    sender_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    sender_name: Mapped[str] = mapped_column(String(100), nullable=False)
    sender_role: Mapped[str] = mapped_column(String(30), nullable=False, default="homeowner")
    # homeowner / designer / contractor / admin

    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(30), nullable=False, default="text")
    # text / image / file / system / voice
    # 业务卡片: task_card / photo / approval / document / budget / payment / quote / bom
    #   procurement_order / procurement_orders / escrow / logistics / sample
    #   settlement / milestone_settlement / task_claim / product_card
    #   orchestrator_task / points_card / narrative / stats_card / user_card
    #   product_create_card / product_list_card / quotation_card

    # @提及（JSON 数组，user_id 列表）
    mentions: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 回复引用（被回复的消息 ID）
    reply_to_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # 线程根消息 ID（多层级对话线程支持）
    thread_root_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # 已读状态：{"user_id": "ISO_timestamp"}（JSON dict）
    read_by: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 软删除
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    project = relationship("Project")
    sender = relationship("User")

    __table_args__ = (
        Index("ix_chat_messages_project_id", "project_id"),
        Index("ix_chat_messages_sender_id", "sender_id"),
    )


class ChatRoom(Base):
    """项目聊天室（每个项目一个，记录成员和最后活跃时间）"""
    __tablename__ = "chat_rooms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="项目协作群")
    # 成员数（缓存）
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_message_preview: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
