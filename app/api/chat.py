"""IM 路由 — F40 三方协作群组（业主/设计师/工长）"""

import json

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatRoomResponse,
)
from app.auth import get_current_user
from app.rbac import verify_project_access
from app.services import chat_service
from app.ws import ws_manager

router = APIRouter(prefix="/chat", tags=["IM 协作"])


def _to_response(msg) -> ChatMessageResponse:
    """将 ChatMessage ORM 对象转换为响应模型（解析 JSON 字段）"""
    try:
        mentions = json.loads(msg.mentions or "[]")
    except Exception:
        mentions = []
    try:
        read_by = json.loads(msg.read_by or "[]")
    except Exception:
        read_by = []
    return ChatMessageResponse(
        id=msg.id,
        project_id=msg.project_id,
        sender_id=msg.sender_id,
        sender_name=msg.sender_name,
        sender_role=msg.sender_role,
        content=msg.content,
        message_type=msg.message_type,
        mentions=mentions,
        reply_to_id=msg.reply_to_id,
        read_by=read_by,
        created_at=msg.created_at,
    )


@router.get("/rooms/{project_id}", response_model=ChatRoomResponse)
async def get_room(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    room = await chat_service.get_or_create_room(db, project_id)
    return ChatRoomResponse.model_validate(room)


@router.get("/messages/{project_id}", response_model=list[ChatMessageResponse])
async def list_messages(
    project_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    msgs = await chat_service.get_messages(db, project_id, limit=limit)
    return [_to_response(m) for m in msgs]


@router.post("/messages", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    data: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
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
    await verify_project_access(project_id=msg.project_id, current_user=current_user, db=db)
    return _to_response(msg)


@router.get("/unread/{project_id}")
async def unread_count(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    count = await chat_service.get_unread_count(db, project_id, current_user.id)
    return {"project_id": project_id, "unread_count": count}
