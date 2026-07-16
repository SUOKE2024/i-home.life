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
        hashed = _hash_password(data.password)

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


async def authenticate_user(db: AsyncSession, phone: str, password: str) -> User | None:
    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    if not user:
        return None
    # 纯 Passkey 用户无密码，不能通过传统密码登录
    if not user.hashed_password:
        return None
    if not _verify_password(password, user.hashed_password):
        return None
    return user
