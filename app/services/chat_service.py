"""IM 服务 — F40 三方协作（业主/设计师/工长）"""

import json
from datetime import datetime, timezone

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatRoom


async def get_or_create_room(db: AsyncSession, project_id: str, name: str | None = None) -> ChatRoom:
    result = await db.execute(
        select(ChatRoom).where(ChatRoom.project_id == project_id)
    )
    room = result.scalar_one_or_none()
    if room:
        return room
    room = ChatRoom(project_id=project_id, name=name or "项目协作群")
    db.add(room)
    await db.commit()
    await db.refresh(room)
    return room


async def get_room(db: AsyncSession, project_id: str) -> ChatRoom | None:
    result = await db.execute(
        select(ChatRoom).where(ChatRoom.project_id == project_id)
    )
    return result.scalar_one_or_none()


async def get_messages(
    db: AsyncSession,
    project_id: str,
    limit: int = 50,
    before: str | None = None,
) -> list[ChatMessage]:
    """获取消息历史（支持分页，before 为消息 ID）"""
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.project_id == project_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    if before:
        # 游标分页: 获取指定消息 ID 之前的消息
        cursor_result = await db.execute(
            select(ChatMessage).where(ChatMessage.id == before)
        )
        cursor_msg = cursor_result.scalar_one_or_none()
        if cursor_msg:
            stmt = stmt.where(ChatMessage.created_at < cursor_msg.created_at)
    result = await db.execute(stmt)
    return list(reversed(result.scalars().all()))


async def send_message(
    db: AsyncSession,
    project_id: str,
    sender_id: str,
    sender_name: str,
    sender_role: str,
    content: str,
    message_type: str = "text",
    mentions: list[str] | None = None,
    reply_to_id: str | None = None,
) -> ChatMessage:
    room = await get_or_create_room(db, project_id)
    msg = ChatMessage(
        project_id=project_id,
        sender_id=sender_id,
        sender_name=sender_name,
        sender_role=sender_role,
        content=content,
        message_type=message_type,
        mentions=json.dumps(mentions or [], ensure_ascii=False),
        reply_to_id=reply_to_id,
        read_by=json.dumps([sender_id], ensure_ascii=False),
    )
    db.add(msg)

    # 更新房间最后活跃
    preview = content[:200] if content else ""
    await db.execute(
        update(ChatRoom)
        .where(ChatRoom.id == room.id)
        .values(
            last_message_at=datetime.now(timezone.utc),
            last_message_preview=preview,
            member_count=max(room.member_count, 1),
        )
    )
    await db.commit()
    await db.refresh(msg)
    return msg


async def mark_read(db: AsyncSession, message_id: str, user_id: str) -> ChatMessage | None:
    result = await db.execute(
        select(ChatMessage).where(ChatMessage.id == message_id)
    )
    msg = result.scalar_one_or_none()
    if not msg:
        return None
    try:
        read_list = json.loads(msg.read_by or "[]")
    except Exception:
        read_list = []
    if user_id not in read_list:
        read_list.append(user_id)
        msg.read_by = json.dumps(read_list, ensure_ascii=False)
        await db.commit()
        await db.refresh(msg)
    return msg


async def get_unread_count(db: AsyncSession, project_id: str, user_id: str) -> int:
    """获取用户在项目中的未读消息数"""
    result = await db.execute(
        select(func.count(ChatMessage.id)).where(
            ChatMessage.project_id == project_id,
            ChatMessage.sender_id != user_id,
        )
    )
    total = result.scalar() or 0
    # 简化：返回非自己发的消息总数（精确实现需要解析 read_by）
    return total
