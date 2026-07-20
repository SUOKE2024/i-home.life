"""Agent 会话 Schema — 请求/响应模型"""

from datetime import datetime

from pydantic import BaseModel, Field


# ── 会话 ──

class AgentSessionCreate(BaseModel):
    """创建新会话（由前端在首次发送消息前调用）"""
    project_id: str | None = None
    title: str = Field(default="新的对话", max_length=100)


class AgentSessionUpdate(BaseModel):
    """更新会话（如修改标题）"""
    title: str | None = Field(default=None, max_length=100)


class AgentMessageResponse(BaseModel):
    """会话中的单条消息"""
    id: str
    role: str
    content: str
    agent_type: str | None = None
    sequence: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentSessionResponse(BaseModel):
    """会话列表项 / 详情"""
    id: str
    title: str
    project_id: str | None = None
    primary_agent_type: str | None = None
    message_count: int
    created_at: datetime
    updated_at: datetime
    messages: list[AgentMessageResponse] = []

    model_config = {"from_attributes": True}


class AgentSessionListItem(BaseModel):
    """会话列表摘要（不包含消息内容）"""
    id: str
    title: str
    project_id: str | None = None
    primary_agent_type: str | None = None
    message_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentChatRequest(BaseModel):
    """扩展的 Agent 聊天请求（支持 session_id 语义）"""
    message: str = Field(min_length=1, max_length=2000)
    agent_type: str = Field(default="orchestrator")
    project_id: str | None = None
    session_id: str | None = Field(
        default=None,
        description="会话 ID。传入已有 session_id 将继续对话并自动保存消息；"
                    "不传则自动创建新会话。"
    )
    history: list[dict] = Field(
        default_factory=list, max_length=20,
        description="最近 N 轮对话历史（session_id 模式下可省略，后端从 DB 加载）",
    )
