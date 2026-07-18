from datetime import datetime

from pydantic import BaseModel, Field


class ChatMessageCreate(BaseModel):
    project_id: str
    content: str = Field(min_length=1, max_length=5000)
    message_type: str = Field(default="text")
    mentions: list[str] = []
    reply_to_id: str | None = None
    thread_root_id: str | None = None


class ChatMessageResponse(BaseModel):
    id: str
    project_id: str
    sender_id: str
    sender_name: str
    sender_role: str
    content: str
    message_type: str
    mentions: list[str] = []
    reply_to_id: str | None = None
    thread_root_id: str | None = None
    read_by: list[str] = []
    is_deleted: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatRoomResponse(BaseModel):
    id: str
    project_id: str
    name: str
    member_count: int
    last_message_at: datetime | None = None
    last_message_preview: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
