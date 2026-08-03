"""IM 路由 — F40 三方协作群组（业主/设计师/工长）+ Agent 群成员"""

import json

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatRoomResponse,
)
from app.auth import get_current_user
from app.rbac import verify_project_chat_access
from app.services import chat_service
from app.ws import ws_manager

router = APIRouter(prefix="/chat", tags=["IM 协作"])


class ChatMessageResponseExt(ChatMessageResponse):
    """F40: 扩展消息响应 — Agent 自动回复标注（向后兼容，缺失字段为 None）"""

    generated_by: str | None = None
    agent_mode: str | None = None
    engine: str | None = None
    is_placeholder: bool | None = None


class AgentMemberAdd(BaseModel):
    """F40: 将 Agent 加入聊天室请求"""

    agent_name: str


def _to_response(msg) -> ChatMessageResponseExt:
    """将 ChatMessage ORM 对象转换为响应模型（解析 JSON 字段 + Agent 自动回复标注）"""
    try:
        mentions = json.loads(msg.mentions or "[]")
    except Exception:
        mentions = []
    try:
        read_raw = json.loads(msg.read_by or "{}")
    except Exception:
        read_raw = {}
    # read_by 存储格式：{"user_id": "ISO_timestamp"}（dict）
    # 响应格式：user_id 列表（backward compatible）
    if isinstance(read_raw, dict):
        read_by = list(read_raw.keys())
    else:
        read_by = read_raw
    # F40: 解析 Agent 自动回复标注（auto_reply_meta JSON dict）
    meta = {}
    try:
        raw_meta = getattr(msg, "auto_reply_meta", None) or ""
        meta = json.loads(raw_meta) if raw_meta else {}
    except Exception:
        meta = {}
    return ChatMessageResponseExt(
        id=msg.id,
        project_id=msg.project_id,
        sender_id=msg.sender_id,
        sender_name=msg.sender_name,
        sender_role=msg.sender_role,
        content=msg.content,
        message_type=msg.message_type,
        mentions=mentions,
        reply_to_id=msg.reply_to_id,
        thread_root_id=getattr(msg, 'thread_root_id', None),
        read_by=read_by,
        is_deleted=getattr(msg, 'is_deleted', False),
        created_at=msg.created_at,
        generated_by=meta.get("generated_by"),
        agent_mode=meta.get("agent_mode"),
        engine=meta.get("engine"),
        is_placeholder=meta.get("is_placeholder"),
    )


@router.get("/rooms/{project_id}", response_model=ChatRoomResponse)
async def get_room(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_chat_access(project_id=project_id, current_user=current_user, db=db)
    room = await chat_service.get_or_create_room(db, project_id)
    return ChatRoomResponse.model_validate(room)


@router.get("/messages/{project_id}", response_model=list[ChatMessageResponseExt])
async def list_messages(
    project_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_chat_access(project_id=project_id, current_user=current_user, db=db)
    msgs = await chat_service.get_messages(db, project_id, limit=limit)
    return [_to_response(m) for m in msgs]


@router.post("/messages", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    data: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_chat_access(project_id=data.project_id, current_user=current_user, db=db)
    msg = await chat_service.send_message(
        db,
        project_id=data.project_id,
        sender_id=current_user.id,
        sender_name=current_user.name,
        sender_role=current_user.role,
        content=data.content,
        message_type=data.message_type,
        mentions=data.mentions,
        reply_to_id=data.reply_to_id,
        thread_root_id=data.thread_root_id,
    )
    resp = _to_response(msg)
    # 通过 WebSocket 实时推送
    await ws_manager.broadcast_to_project(data.project_id, "chat.message", resp.model_dump())
    return resp


@router.post("/messages/{message_id}/read", response_model=ChatMessageResponse)
async def mark_message_read(
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg = await chat_service.mark_read(db, message_id, current_user.id)
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="消息不存在")
    # 校验消息所属项目的访问权限
    await verify_project_chat_access(project_id=msg.project_id, current_user=current_user, db=db)
    return _to_response(msg)


@router.get("/unread/{project_id}")
async def unread_count(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_chat_access(project_id=project_id, current_user=current_user, db=db)
    count = await chat_service.get_unread_count(db, project_id, current_user.id)
    return {"project_id": project_id, "unread_count": count}


@router.delete("/messages/{message_id}", status_code=status.HTTP_200_OK)
async def delete_message(
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """软删除消息（仅消息发送者或 admin 可删除）"""
    msg = await chat_service.soft_delete_message(db, message_id)
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="消息不存在或已删除")
    # 权限校验：仅发送者本人或 admin 可删除
    if current_user.role != "admin" and msg.sender_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除此消息")
    await verify_project_chat_access(project_id=msg.project_id, current_user=current_user, db=db)
    # 通知客户端消息已删除
    await ws_manager.broadcast_to_project(msg.project_id, "chat.message_deleted", {
        "message_id": message_id,
    })
    return {"message_id": message_id, "deleted": True}


# ── F40 Agent 群成员管理 ──


@router.post("/rooms/{room_id}/agents", status_code=status.HTTP_201_CREATED)
async def add_agent_to_room(
    room_id: str,
    data: AgentMemberAdd,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """F40: 将 Agent 加入聊天室（校验 Agent 名称在 AGENT_ROSTER 内）"""
    room = await chat_service.get_room_by_id(db, room_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="聊天室不存在")
    await verify_project_chat_access(project_id=room.project_id, current_user=current_user, db=db)
    if data.agent_name not in chat_service.AGENT_ROSTER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"未知 Agent: {data.agent_name}，可选: {', '.join(chat_service.AGENT_ROSTER)}",
        )
    members = await chat_service.add_agent_member(db, room, data.agent_name)
    return {"room_id": room.id, "project_id": room.project_id, "agent_members": members}


@router.get("/rooms/{room_id}/agents")
async def list_room_agents(
    room_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """F40: 查询聊天室内的 Agent 成员"""
    room = await chat_service.get_room_by_id(db, room_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="聊天室不存在")
    await verify_project_chat_access(project_id=room.project_id, current_user=current_user, db=db)
    members = chat_service.parse_agent_members(room)
    return {"room_id": room.id, "project_id": room.project_id, "agent_members": members}
