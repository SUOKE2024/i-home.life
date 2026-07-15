import uuid

import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.schemas.user import UserCreate


def _hash_password(password: str) -> str:
    """使用 bcrypt 哈希密码，盐值内嵌于结果中"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, stored_hash: str) -> bool:
    """验证密码是否与 bcrypt 哈希匹配"""
    return bcrypt.checkpw(password.encode(), stored_hash.encode())


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
