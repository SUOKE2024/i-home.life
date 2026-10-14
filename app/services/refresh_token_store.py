"""刷新令牌服务端会话存储（v4.public 轮换 + 复用检测 + 族撤销）。

与 suoke_club auth-svc 的 refresh 会话表语义对齐：
- 每个 refresh 令牌一行（jti 主键），同族（family_id）滚动轮换；
- 旧令牌首次使用 → 标记 used_at/rotated_to；
- grace 窗口内重放 → 视为网络抖动，返回轮换后的令牌；
- 超窗重放 → 视为被盗 → 撤销整族。

本模块仅做持久化，业务判定（grace/撤销）在 app/api/auth.py 的 /auth/refresh。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.refresh_token import RefreshToken

settings = get_settings()


async def persist_refresh_token(db: AsyncSession, pair: dict, user_id: str) -> RefreshToken:
    """持久化新签发的 refresh 令牌会话行（调用方负责 commit）。"""
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.paseto_refresh_token_expire_days
    )
    row = RefreshToken(
        jti=pair["refresh_jti"],
        user_id=user_id,
        family_id=pair["family_id"],
        token_text=pair["refresh_token"],
        expires_at=expires_at,
        revoked=False,
    )
    db.add(row)
    await db.flush()
    return row


async def get_refresh_token(db: AsyncSession, jti: str) -> RefreshToken | None:
    if not jti:
        return None
    return await db.get(RefreshToken, jti)


async def mark_refresh_token_used(
    db: AsyncSession, jti: str, rotated_to: str, used_at: datetime
) -> None:
    row = await db.get(RefreshToken, jti)
    if row is not None:
        row.used_at = used_at
        row.rotated_to = rotated_to
        await db.flush()


async def revoke_refresh_token_family(db: AsyncSession, family_id: str) -> None:
    """撤销整族（复用检测命中时调用）。"""
    if not family_id:
        return
    await db.execute(
        update(RefreshToken).where(RefreshToken.family_id == family_id).values(revoked=True)
    )
    await db.flush()


async def revoke_refresh_token(db: AsyncSession, jti: str) -> None:
    row = await db.get(RefreshToken, jti)
    if row is not None:
        row.revoked = True
        await db.flush()
