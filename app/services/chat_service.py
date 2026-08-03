"""IM 服务 — F40 三方协作（业主/设计师/工长）+ Agent 群成员自动回复"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatRoom
from app.models.user import User

logger = logging.getLogger(__name__)

# F40: 可加入 IM 群聊的 Agent 名单（对齐 harness 注册表 + 全平台 Agent 名称）
AGENT_ROSTER: list[str] = [
    "orchestrator", "designer", "budget", "procurement", "construction",
    "settlement", "qa_inspector", "concierge", "content_publisher", "admin",
    "kitchen", "bathroom", "mep", "appliance", "furniture", "door_window",
    "files", "products", "identity", "notifications", "takeoff", "ifc_export",
]

# Agent 显示名（群成员展示，缺失时回退为 agent_name）
AGENT_DISPLAY_NAMES: dict[str, str] = {
    "orchestrator": "AI 总管家",
    "designer": "AI 设计师",
    "budget": "AI 预算师",
    "procurement": "AI 采购师",
    "construction": "AI 施工管家",
    "settlement": "AI 结算师",
    "qa_inspector": "AI 质检员",
    "concierge": "AI 客服",
    "content_publisher": "AI 内容官",
    "admin": "AI 管理员",
}

# Agent 系统用户 ID 前缀（ChatMessage.sender_id 外键指向 users.id，
# 生产 PG 外键约束要求真实用户行，故为每个 Agent 惰性创建系统机器人用户）
_AGENT_USER_ID_PREFIX = "agent:"


async def ensure_agent_user(db: AsyncSession, agent_name: str) -> User:
    """获取（或惰性创建）Agent 对应的系统机器人用户，保证消息外键在 PG 下有效。

    role 使用独立值 "agent"（不在任何 RoleChecker 白名单内），
    系统机器人无法通过任何登录/鉴权端点，仅用于消息归属。
    """
    uid = f"{_AGENT_USER_ID_PREFIX}{agent_name}"
    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if user:
        return user
    user = User(
        id=uid,
        phone=f"{_AGENT_USER_ID_PREFIX}{agent_name}",
        name=AGENT_DISPLAY_NAMES.get(agent_name, agent_name),
        role="agent",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


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


def parse_agent_members(room: ChatRoom) -> list[str]:
    """解析房间 Agent 成员 JSON 数组，容错返回 []"""
    try:
        members = json.loads(room.agent_members or "[]")
    except Exception:
        return []
    if not isinstance(members, list):
        return []
    return [m for m in members if isinstance(m, str)]


async def get_room_by_id(db: AsyncSession, room_id: str) -> ChatRoom | None:
    result = await db.execute(select(ChatRoom).where(ChatRoom.id == room_id))
    return result.scalar_one_or_none()


async def add_agent_member(db: AsyncSession, room: ChatRoom, agent_name: str) -> list[str]:
    """将 Agent 加入房间（去重），返回更新后的成员列表。"""
    members = parse_agent_members(room)
    if agent_name not in members:
        members.append(agent_name)
        room.agent_members = json.dumps(members, ensure_ascii=False)
        await db.commit()
        await db.refresh(room)
    return members


async def get_messages(
    db: AsyncSession,
    project_id: str,
    limit: int = 50,
    before: str | None = None,
) -> list[ChatMessage]:
    """获取消息历史（支持分页，before 为消息 ID，排除已删除消息）"""
    stmt = (
        select(ChatMessage)
        .where(
            ChatMessage.project_id == project_id,
            ChatMessage.is_deleted == False,  # noqa: E712
        )
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
    thread_root_id: str | None = None,
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
        thread_root_id=thread_root_id,
        read_by=json.dumps({sender_id: datetime.now(timezone.utc).isoformat()}, ensure_ascii=False),
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

    # F40: 房间存在 Agent 成员且消息来自业主/工长时，为每个 Agent 生成自动回复。
    # 不阻塞原消息创建：任何异常仅记录日志。
    try:
        if msg.sender_role in ("homeowner", "contractor") and parse_agent_members(room):
            await generate_agent_auto_reply(db, room, msg)
    except Exception as e:
        logger.warning("agent_auto_reply_failed: %s", e)

    return msg


async def mark_read(db: AsyncSession, message_id: str, user_id: str) -> ChatMessage | None:
    result = await db.execute(
        select(ChatMessage).where(ChatMessage.id == message_id)
    )
    msg = result.scalar_one_or_none()
    if not msg:
        return None
    try:
        read_dict = json.loads(msg.read_by or "{}")
    except Exception:
        read_dict = {}
    if user_id not in read_dict:
        read_dict[user_id] = datetime.now(timezone.utc).isoformat()
        msg.read_by = json.dumps(read_dict, ensure_ascii=False)
        await db.commit()
        await db.refresh(msg)
    return msg


async def get_unread_count(db: AsyncSession, project_id: str, user_id: str) -> int:
    """获取用户在项目中的未读消息数（排除已软删除 + 已被标记已读的消息）

    使用 LIKE 匹配 read_by JSON dict 中的 user_id key。
    read_by 格式: {"uid1": "ISO_ts", "uid2": "..."}
    """
    result = await db.execute(
        select(func.count(ChatMessage.id)).where(
            ChatMessage.project_id == project_id,
            ChatMessage.sender_id != user_id,
            ChatMessage.is_deleted == False,  # noqa: E712
            # 未读 = read_by 为 NULL 或不包含当前 user_id key
            ~ChatMessage.read_by.like(f'%"{user_id}"%'),
        )
    )
    return result.scalar() or 0


async def soft_delete_message(db: AsyncSession, message_id: str) -> ChatMessage | None:
    """软删除消息（标记 is_deleted + 记录删除时间）"""
    result = await db.execute(
        select(ChatMessage).where(
            ChatMessage.id == message_id,
            ChatMessage.is_deleted == False,  # noqa: E712
        )
    )
    msg = result.scalar_one_or_none()
    if not msg:
        return None
    msg.is_deleted = True
    msg.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(msg)
    return msg


# ── F40 Agent 群成员自动回复 ──


def _resolve_agent_class(agent_name: str):
    """按名称解析 Agent 类（优先 harness 注册表；未注册返回 None → 规则路径）"""
    try:
        from app.agents.harness import get_harness
        return get_harness()._agent_registry.get(agent_name)
    except Exception:
        return None


async def _call_agent_auto_reply(agent_name: str, user_message: str) -> tuple[str, dict]:
    """为群内 Agent 生成自动回复。

    优先级：真实 Agent（harness 调用处理文本）→ 规则路径 → 诚实降级占位。
    返回 (content, annotations)；annotations 含 generated_by/agent_mode，
    规则或降级路径额外携带 engine="rule_based"（占位再附 is_placeholder）。
    """
    agent_cls = _resolve_agent_class(agent_name)
    if agent_cls is None:
        # 规则路径：Agent 未注册/无对应类时使用简单规则回复
        display = AGENT_DISPLAY_NAMES.get(agent_name, agent_name)
        reply = f"已收到您的消息，{display}将尽快跟进项目进展，请稍候。"
        return reply, {
            "generated_by": f"agent:{agent_name}",
            "agent_mode": "auto_reply",
            "engine": "rule_based",
        }

    agent = agent_cls()
    try:
        from app.agents.harness import get_harness
        result = await get_harness().run(agent, user_message)
        reply = (result.get("reply") or "").strip()
        if result.get("fallback") or not reply or reply.startswith("[mock]"):
            # Agent 处理失败/超时/降级 → 诚实占位
            return "Agent 暂时无法响应（服务降级）", {
                "generated_by": f"agent:{agent_name}",
                "agent_mode": "auto_reply",
                "engine": "rule_based",
                "is_placeholder": True,
            }
        return reply, {
            "generated_by": f"agent:{agent_name}",
            "agent_mode": "auto_reply",
        }
    except Exception as e:
        logger.warning("agent_auto_reply_error: name=%s error=%s", agent_name, e)
        return "Agent 暂时无法响应（服务降级）", {
            "generated_by": f"agent:{agent_name}",
            "agent_mode": "auto_reply",
            "engine": "rule_based",
            "is_placeholder": True,
        }
    finally:
        try:
            await agent.close()
        except Exception:
            pass


async def generate_agent_auto_reply(
    db: AsyncSession, room: ChatRoom, trigger_msg: ChatMessage
) -> list[ChatMessage]:
    """房间存在 Agent 成员时，为每个 Agent 生成自动回复消息（不抛出异常）。

    回复消息 sender_role="agent"、sender_id 指向系统 Agent 机器人用户
    （id 为 "agent:<name>"，惰性创建以保证 PG 外键有效），标注写入
    auto_reply_meta（generated_by/agent_mode/engine/is_placeholder）。
    """
    members = parse_agent_members(room)
    if not members:
        return []
    replies: list[ChatMessage] = []
    for name in members:
        content, annotations = await _call_agent_auto_reply(name, trigger_msg.content)
        agent_user = await ensure_agent_user(db, name)
        msg = ChatMessage(
            project_id=room.project_id,
            sender_id=agent_user.id,
            sender_name=AGENT_DISPLAY_NAMES.get(name, name),
            sender_role="agent",
            content=content,
            message_type="text",
            mentions=json.dumps([trigger_msg.id], ensure_ascii=False),
            read_by=json.dumps({}, ensure_ascii=False),
            auto_reply_meta=json.dumps(annotations, ensure_ascii=False),
        )
        db.add(msg)
        replies.append(msg)
    await db.commit()
    for m in replies:
        await db.refresh(m)
    return replies
