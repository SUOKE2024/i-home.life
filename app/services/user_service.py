import asyncio
import hashlib
import logging
import uuid

import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.schemas.user import UserCreate

logger = logging.getLogger(__name__)


def _hash_password(password: str) -> str:
    """使用 bcrypt 哈希密码，盐值内嵌于结果中"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, stored_hash: str) -> bool:
    """验证密码，兼容多种历史哈希格式。

    支持的格式（按优先级）：
    1. bcrypt: 以 '$2b$' 或 '$2a$' 开头
    2. SHA256+salt: 格式 "salt_hex:hash_hex"（生产环境旧数据）
    3. MD5: 32位 hex（早期开发数据）
    """
    if not stored_hash or not password:
        return False

    # 1. bcrypt 哈希（以 '$2b$' 或 '$2a$' 开头）
    if stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$"):
        try:
            return bcrypt.checkpw(password.encode(), stored_hash.encode())
        except ValueError as e:
            logger.warning(f"bcrypt 密码验证失败: {e}")
            return False

    # 2. SHA256+salt 格式: "salt_hex:hash_hex"（生产环境旧数据）
    # salt 是 32 hex 字符（16 bytes），hash 是 64 hex 字符（SHA256）
    if ":" in stored_hash and len(stored_hash) == 97:
        try:
            salt, expected_hash = stored_hash.split(":", 1)
            computed = hashlib.sha256((password + salt).encode()).hexdigest()
            return computed == expected_hash
        except (ValueError, UnicodeEncodeError):
            pass

    # 3. 兼容旧版 MD5 哈希（32位十六进制字符串）
    if len(stored_hash) == 32:
        try:
            int(stored_hash, 16)  # 验证是否是合法 hex
            return hashlib.md5(password.encode()).hexdigest() == stored_hash
        except (ValueError, UnicodeEncodeError):
            pass

    logger.warning(f"无法识别的密码哈希格式: {stored_hash[:10]}...")
    return False


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    """创建用户（支持有密码或无密码的 Passkey 用户）。

    对于纯 Passkey 注册（password 为空字符串），hashed_password 设为 None。
    """
    hashed = None
    if data.password:
        # bcrypt 为 CPU 密集同步操作（~300ms），放入线程池避免阻塞 async 事件循环
        hashed = await asyncio.to_thread(_hash_password, data.password)

    user = User(
        phone=data.phone,
        name=data.name,
        role=data.role,
        sub_role=data.sub_role,
        hashed_password=hashed,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def create_passkey_user(
    db: AsyncSession,
    phone: str,
    name: str,
    role: str = "homeowner",
) -> User:
    """为纯 Passkey 注册创建无密码用户。

    此用户只能通过 WebAuthn/Passkey 登录，无传统密码。
    """
    user = User(
        id=str(uuid.uuid4()),
        phone=phone,
        name=name,
        role=role,
        hashed_password=None,  # passkey-only
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_or_create_phone_user(db: AsyncSession, phone: str) -> User:
    """按手机号查找用户，不存在则创建无密码用户（供一键登录使用）。"""
    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    if user:
        return user

    user = User(
        id=str(uuid.uuid4()),
        phone=phone,
        name=f"用户{phone[-4:]}",
        role="homeowner",
        hashed_password=None,  # 一键登录用户无密码，后续可绑定密码/Passkey
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, phone: str, password: str) -> User | None:
    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    if not user:
        return None
    # 纯 Passkey 用户无密码，不能通过传统密码登录
    if not user.hashed_password:
        return None
    if not await asyncio.to_thread(_verify_password, password, user.hashed_password):
        return None
    return user


async def get_or_create_wechat_user(
    db: AsyncSession,
    openid: str,
    unionid: str | None,
    nickname: str,
    avatar_url: str | None,
) -> User:
    """按 openid 查找微信用户，不存在则创建（phone=NULL，role=homeowner，无密码）。

    昵称/头像仅在创建时写入（不覆盖用户后续自改资料）；unionid 缺失时补录。
    """
    result = await db.execute(select(User).where(User.wechat_openid == openid))
    user = result.scalar_one_or_none()
    if user:
        if not user.wechat_unionid and unionid:
            user.wechat_unionid = unionid
            await db.commit()
            await db.refresh(user)
        return user

    user = User(
        id=str(uuid.uuid4()),
        phone=None,  # 微信登录无手机号，绑手机前短信类能力不可用（诚实降级）
        name=nickname or "微信用户",
        role="homeowner",
        hashed_password=None,
        wechat_openid=openid,
        wechat_unionid=unionid,
        avatar_url=avatar_url or None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def bind_phone_to_user(db: AsyncSession, user: User, phone: str) -> User:
    """为无手机号用户绑定手机号（验真由调用方完成），返回挂载到本 session 的最新对象。

    注意：调用方传入的 user 可能是 get_current_user 缓存的 detached 对象
    （app/auth/_user_cache），必须按 id 重新加载后再变更，否则 commit 静默丢失。
    冲突/已绑定抛 ValueError。
    """
    fresh = await db.get(User, user.id)
    if fresh is None:
        raise ValueError("用户不存在")
    if fresh.phone:
        raise ValueError("当前账号已绑定手机号")
    result = await db.execute(select(User).where(User.phone == phone, User.id != fresh.id))
    if result.scalar_one_or_none():
        raise ValueError("该手机号已绑定其他账号")
    fresh.phone = phone
    await db.commit()
    await db.refresh(fresh)
    return fresh
