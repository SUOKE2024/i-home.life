"""Agent 会话持久化服务

提供 Agent 会话和消息的 CRUD 操作，以及自动持久化能力。
隐私保护设计：
- 会话标题：从首条用户消息自动生成，过滤 PII（手机号/身份证号/地址等）
- 消息内容：Fernet 对称加密存储（密钥源自 PASETO secret_key）
- 支持软删除（is_deleted 标记）+ TTL 自动物理清理
- 跨用户严格隔离
"""

import base64
import hashlib
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_session import AgentSession, AgentMessage

logger = logging.getLogger(__name__)

MAX_SESSION_TITLE_LENGTH = 100
MAX_SESSIONS_PER_USER = 50  # 每个用户最多保留 50 个会话
# 软删除会话保留天数（超过后物理删除）
DELETED_SESSION_TTL_DAYS = 30

# ── 加密 ──


def _get_fernet() -> Fernet | None:
    """获取 Fernet 加密实例。

    密钥派生自 PASETO secret_key（SHA256 → 32 字节 → base64 → Fernet key）。
    若 PASETO key 未配置（开发环境默认值），则加密层自动降级为空操作。
    """
    try:
        from app.config import get_settings
        paseto_key = get_settings().paseto_secret_key
        if not paseto_key or paseto_key == "change-me-to-a-random-32-byte-key-minimum":
            return None
        # 从 PASETO key 派生稳定的 Fernet key（32 字节 URL-safe base64）
        key_bytes = hashlib.sha256(paseto_key.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        return Fernet(fernet_key)
    except Exception:
        return None


def _encrypt(text: str) -> str:
    """加密消息内容。若 Fernet 不可用则原样返回（开发/测试降级）。"""
    f = _get_fernet()
    if f is None:
        return text
    try:
        return f.encrypt(text.encode()).decode()
    except Exception:
        return text


def _decrypt(text: str) -> str:
    """解密消息内容。若 Fernet 不可用则原样返回。"""
    f = _get_fernet()
    if f is None:
        return text
    try:
        return f.decrypt(text.encode()).decode()
    except Exception:
        return text


# ── PII 过滤 ──

# 中国手机号：1[3-9]开头 + 9位数字
_PHONE_RE = re.compile(r'1[3-9]\d{9}')
# 身份证号：18位（末位可能是X）
_IDCARD_RE = re.compile(r'\d{17}[\dXx]')
# 地址片段（含小区/街道/路/号/栋/单元/室等关键词）
_ADDR_RE = re.compile(
    r'[\u4e00-\u9fff]{2,6}(?:市|区|县|镇|乡|街道|路|街|巷|弄|号|栋|单元|号楼?|小区|花园|家园|公寓|大厦|广场)',
)


def _sanitize_title(text: str, max_len: int = MAX_SESSION_TITLE_LENGTH) -> str:
    """从用户消息中提取安全标题（PII 已脱敏）。

    规则：
    1. 滤除手机号、身份证号、地址片段
    2. 截取第一句（以 。！？.!?\n 结尾）
    3. 裁剪到 max_len 字符
    4. 空文本回退到默认标题
    """
    if not text:
        return "新的对话"
    text = text.strip()
    if not text:
        return "新的对话"

    # 脱敏 PII
    text = _PHONE_RE.sub('****', text)
    text = _IDCARD_RE.sub('****', text)
    text = _ADDR_RE.sub('**', text)

    # 取第一句
    for i, ch in enumerate(text):
        if ch in "。！？.!?\n":
            text = text[:i + 1]
            break
    if len(text) > max_len:
        text = text[:max_len - 3] + "..."
    return text or "新的对话"


def _content_hash(content: str) -> str:
    """计算消息内容的 SHA256 哈希（用于去重和反馈关联）"""
    return hashlib.sha256(content.encode()).hexdigest()


# ── CRUD ──


async def create_session(
    db: AsyncSession,
    user_id: str,
    project_id: str | None = None,
    title: str = "新的对话",
) -> AgentSession:
    """创建新会话"""
    session = AgentSession(
        user_id=user_id,
        project_id=project_id,
        title=title,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_or_create_session(
    db: AsyncSession,
    user_id: str,
    session_id: str | None = None,
    project_id: str | None = None,
    first_message: str = "",
) -> AgentSession:
    """获取已有会话或创建新会话。

    Args:
        session_id: 若提供则查找已有会话，不存在则创建新会话
        first_message: 用于自动生成标题（PII 已脱敏）
    """
    # 定期清理过期软删除会话（概率触发，不阻塞）
    if uuid.uuid4().int % 10 == 0:
        await _purge_expired_sessions(db)

    if session_id:
        result = await db.execute(
            select(AgentSession).where(
                AgentSession.id == session_id,
                AgentSession.user_id == user_id,
                AgentSession.is_deleted == False,  # noqa: E712
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        logger.warning(f"agent_session: session_id={session_id} not found, creating new")

    # 检查用户会话数量，超过上限时软删除最旧的会话
    count_result = await db.execute(
        select(func.count(AgentSession.id)).where(
            AgentSession.user_id == user_id,
            AgentSession.is_deleted == False,  # noqa: E712
        )
    )
    current_count = count_result.scalar() or 0
    if current_count >= MAX_SESSIONS_PER_USER:
        oldest_result = await db.execute(
            select(AgentSession).where(
                AgentSession.user_id == user_id,
                AgentSession.is_deleted == False,  # noqa: E712
            ).order_by(AgentSession.created_at.asc()).limit(1)
        )
        oldest = oldest_result.scalar_one_or_none()
        if oldest:
            oldest.is_deleted = True
            oldest.deleted_at = datetime.now(timezone.utc)
            logger.info(f"agent_session: auto-deleted oldest session {oldest.id} for user {user_id}")

    title = _sanitize_title(first_message) if first_message else "新的对话"
    return await create_session(db, user_id, project_id, title)


async def persist_message(
    db: AsyncSession,
    session: AgentSession,
    role: str,
    content: str,
    agent_type: str | None = None,
) -> AgentMessage:
    """持久化一条消息到数据库（内容加密存储）。

    Args:
        session: 会话对象（必须已存在于 DB）
        role: "user" / "assistant"
        content: 消息明文内容（自动加密后写入 DB）
        agent_type: Agent 类型（assistant 消息时使用）
    """
    encrypted = _encrypt(content)
    msg = AgentMessage(
        session_id=session.id,
        role=role,
        content=encrypted,
        agent_type=agent_type,
        sequence=session.message_count,
        content_hash=_content_hash(content),
    )
    db.add(msg)

    # 更新会话消息计数和最后活跃时间
    session.message_count = session.message_count + 1
    session.updated_at = datetime.now(timezone.utc)

    # 首条助手消息时更新 primary_agent_type
    if role == "assistant" and agent_type and not session.primary_agent_type:
        session.primary_agent_type = agent_type

    # 首条用户消息时自动更新标题
    if role == "user" and session.title == "新的对话" and content:
        session.title = _sanitize_title(content)

    await db.commit()
    await db.refresh(msg)
    return msg


async def list_sessions(
    db: AsyncSession,
    user_id: str,
    project_id: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> list[AgentSession]:
    """列出用户的会话列表（按最后活跃时间倒序）"""
    stmt = (
        select(AgentSession)
        .where(
            AgentSession.user_id == user_id,
            AgentSession.is_deleted == False,  # noqa: E712
        )
    )
    if project_id:
        stmt = stmt.where(AgentSession.project_id == project_id)
    stmt = stmt.order_by(AgentSession.updated_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_session(
    db: AsyncSession,
    session_id: str,
    user_id: str,
    include_messages: bool = True,
    message_limit: int = 50,
) -> AgentSession | None:
    """获取会话详情（含消息，消息内容自动解密）"""
    from sqlalchemy.orm import selectinload

    stmt = (
        select(AgentSession)
        .options(selectinload(AgentSession.messages))
        .where(
            AgentSession.id == session_id,
            AgentSession.user_id == user_id,
            AgentSession.is_deleted == False,  # noqa: E712
        )
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if session and include_messages:
        # 解密消息内容
        for msg in session.messages:
            msg.content = _decrypt(msg.content)
    return session


async def soft_delete_session(
    db: AsyncSession,
    session_id: str,
    user_id: str,
) -> AgentSession | None:
    """软删除会话（标记删除并记录时间，30 天后自动物理清理）"""
    result = await db.execute(
        select(AgentSession).where(
            AgentSession.id == session_id,
            AgentSession.user_id == user_id,
            AgentSession.is_deleted == False,  # noqa: E712
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return None
    session.is_deleted = True
    session.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session_history(
    db: AsyncSession,
    session_id: str,
    user_id: str,
    limit: int = 20,
) -> list[dict]:
    """获取会话的最近 N 条消息，转换为 history 格式（用于注入 Agent prompt）。

    消息内容自动解密后在内存中截断到 500 字符。
    """
    stmt = (
        select(AgentMessage)
        .join(AgentSession, AgentMessage.session_id == AgentSession.id)
        .where(
            AgentSession.id == session_id,
            AgentSession.user_id == user_id,
            AgentSession.is_deleted == False,  # noqa: E712
        )
        .order_by(AgentMessage.sequence.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    messages = list(result.scalars().all())
    messages.reverse()  # 按时间正序返回

    history = []
    for msg in messages:
        decrypted = _decrypt(msg.content)
        history.append({
            "role": msg.role,
            "content": decrypted[:500],  # 截断超长消息
            "agent_type": msg.agent_type or "",
        })
    return history


# ── TTL 清理 ──


async def _purge_expired_sessions(db: AsyncSession) -> int:
    """物理删除超过 TTL 的软删除会话及其关联消息。

    通过 cascade="all, delete-orphan" 自动级联删除关联的 AgentMessage。
    先查询后删除（而非在 WHERE 中比较 datetime），避免 SQLAlchemy evaluator
    在 SQLite 和 PostgreSQL 间处理 timezone-aware/naive 的兼容性问题。
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=DELETED_SESSION_TTL_DAYS)

    # 查询所有软删除会话，Python 侧过滤已过期的
    result = await db.execute(
        select(AgentSession).where(
            AgentSession.is_deleted == True,  # noqa: E712
            AgentSession.deleted_at.isnot(None),
        )
    )
    sessions = result.scalars().all()

    expired_ids = []
    for s in sessions:
        dt = s.deleted_at
        # 统一转为 UTC-aware 进行比较
        if dt and (dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt) < cutoff:
            expired_ids.append(s.id)

    if not expired_ids:
        return 0

    # 按 ID 批量删除
    del_stmt = delete(AgentSession).where(AgentSession.id.in_(expired_ids))
    del_result = await db.execute(del_stmt)
    await db.commit()

    count = del_result.rowcount or 0
    if count > 0:
        logger.info(f"agent_session: purged {count} expired sessions")
    return count


async def purge_all_expired_sessions(db: AsyncSession) -> int:
    """管理员 / 定时任务调用：立即清理所有过期会话"""
    return await _purge_expired_sessions(db)
