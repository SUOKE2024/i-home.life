"""Agent 用户反馈模型 — L4 自适应学习数据收集

记录用户对 AI Agent 回复的反馈（like/dislike/评分/评论），用于：
1. 离线分析 Agent 质量，识别低满意度场景
2. 在线偏好学习：BaseAgent.think() 注入用户历史正向反馈作为 few-shot 示例
3. PRD §5.4 L4 自适应学习的基础数据层（Phase 5 末项提前布局）
"""
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentFeedback(Base):
    """用户对 Agent 回复的反馈记录"""
    __tablename__ = "agent_feedbacks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False)  # designer/budget/...
    message_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA256(user_message)
    feedback_type: Mapped[str] = mapped_column(String(20), nullable=False)  # like/dislike
    rating: Mapped[int] = mapped_column(Integer, nullable=True)  # 1-5 星，可选
    comment: Mapped[str] = mapped_column(Text, nullable=True)  # 用户文字反馈
    user_message: Mapped[str] = mapped_column(Text, nullable=False)  # 原始用户消息（用于 few-shot）
    agent_reply: Mapped[str] = mapped_column(Text, nullable=False)  # Agent 回复内容
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
