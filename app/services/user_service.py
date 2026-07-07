import hashlib
import secrets

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.schemas.user import UserCreate


def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{h}", salt


def _verify_password(password: str, stored: str) -> bool:
    salt, _ = stored.split(":", 1)
    hashed, _ = _hash_password(password, salt)
    return hashed == stored


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    hashed, _ = _hash_password(data.password)
    user = User(
        phone=data.phone,
        name=data.name,
        role=data.role,
        hashed_password=hashed,
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
    if not _verify_password(password, user.hashed_password):
        return None
    return user
