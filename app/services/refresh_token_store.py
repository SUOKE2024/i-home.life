"""刷新令牌服务端会话存储（v4.public 轮换 + 复用检测 + 族撤销）。

与 suoke_club auth-svc 的 refresh 会话表语义对齐：
- 每个 refresh 令牌一行（jti 主键），同族（family_id）滚动轮换；
- 旧令牌首次使用 → 标记 used_at/rotated_to；
- grace 窗口内重放 → 视为网络抖动，返回轮换后的令牌；
- 超窗重放 → 视为被盗 → 撤销整族。

本模块仅做持久化，业务判定（grace/撤销）在 app/api/auth.py 的 /auth/refresh。

落库为 AES-256-GCM 密文（v1. 前缀），密钥由 PASETO_SECRET_KEY 派生。
注意：轮换 PASETO_SECRET_KEY 会使历史 refresh 密文不可解，用户需重新登录；
轮换前应清空 refresh_tokens 或保留旧密钥解密窗口。
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.refresh_token import RefreshToken

settings = get_settings()
logger = logging.getLogger(__name__)

_TOKEN_CIPHER_PREFIX = "v1."
_TOKEN_CIPHER_AAD = b"i-home-refresh-token-v1"


def _cipher_key() -> bytes:
    """从对称主密钥派生 AES-256-GCM 密钥；与设备凭据加密同源。"""
    return hashlib.sha256(settings.paseto_secret_key.encode("utf-8")).digest()


def encrypt_refresh_token(token: str) -> str:
    """加密 refresh 令牌原文，落库不出现明文。"""
    nonce = os.urandom(12)
    ciphertext = AESGCM(_cipher_key()).encrypt(nonce, token.encode("utf-8"), _TOKEN_CIPHER_AAD)
    blob = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii").rstrip("=")
    return _TOKEN_CIPHER_PREFIX + blob


def decrypt_refresh_token(blob: str | None) -> str | None:
    """解密 refresh 令牌；legacy 明文原样返回，密文损坏返回 None。"""
    if not blob:
        return None
    if not blob.startswith(_TOKEN_CIPHER_PREFIX):
        return blob
    try:
        encoded = blob[len(_TOKEN_CIPHER_PREFIX):]
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        nonce, ciphertext = raw[:12], raw[12:]
        return AESGCM(_cipher_key()).decrypt(nonce, ciphertext, _TOKEN_CIPHER_AAD).decode("utf-8")
    except Exception:
        logger.warning("refresh token decrypt failed")
        return None


async def read_refresh_token_text(db: AsyncSession, row: RefreshToken) -> str | None:
    """读取 refresh 原文；legacy 明文行在首次读取时就地加密迁移。"""
    blob = row.token_text
    if not blob:
        return None
    if blob.startswith(_TOKEN_CIPHER_PREFIX):
        return decrypt_refresh_token(blob)
    row.token_text = encrypt_refresh_token(blob)
    await db.flush()
    return blob


async def persist_refresh_token(db: AsyncSession, pair: dict, user_id: str) -> RefreshToken:
    """持久化新签发的 refresh 令牌会话行（调用方负责 commit）。"""
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.paseto_refresh_token_expire_days
    )
    row = RefreshToken(
        jti=pair["refresh_jti"],
        user_id=user_id,
        family_id=pair["family_id"],
        token_text=encrypt_refresh_token(pair["refresh_token"]),
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
