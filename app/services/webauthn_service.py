"""FIDO2/WebAuthn + Passkey 认证服务

兼容 webauthn>=2.5.0 和 webauthn>=3.0。
挑战存储支持 Redis（生产环境）和内存字典（开发降级），均带 TTL 自动过期。
"""

import base64
import json
import logging
import time
import uuid
from datetime import datetime, timezone

import webauthn
from webauthn.helpers.structs import (
    PublicKeyCredentialDescriptor,
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    ResidentKeyRequirement,
    AttestationConveyancePreference,
    UserVerificationRequirement,
)

# v3 才有 PublicKeyCredentialHint
try:
    from webauthn.helpers.structs import PublicKeyCredentialHint
    _HAS_HINTS = True
except ImportError:
    _HAS_HINTS = False
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User
from app.models.webauthn_credential import WebAuthnCredential as WACModel

logger = logging.getLogger(__name__)

settings = get_settings()


# ═══════════════════════════════════════════
#  挑战存储层（Redis 优先 / 内存降级，均带 TTL）
# ═══════════════════════════════════════════


class ChallengeStore:
    """挑战存储抽象基类"""

    async def set(self, key: str, value: str, ttl: int) -> None:
        raise NotImplementedError

    async def get(self, key: str) -> str | None:
        raise NotImplementedError

    async def pop(self, key: str) -> str | None:
        """读取并删除（用于一次性挑战）"""
        value = await self.get(key)
        if value is not None:
            await self.delete(key)
        return value

    async def delete(self, key: str) -> None:
        raise NotImplementedError


class MemoryChallengeStore(ChallengeStore):
    """内存字典存储（开发环境降级方案）

    带 TTL 自动过期，每次访问时惰性清理过期项。
    注意：多进程/多实例部署不共享，生产环境应使用 RedisChallengeStore。
    """

    def __init__(self) -> None:
        # key -> (value, expire_timestamp)
        self._store: dict[str, tuple[str, float]] = {}

    def _cleanup_expired(self) -> None:
        """惰性清理过期挑战"""
        now = time.time()
        expired = [k for k, (_, exp) in self._store.items() if exp <= now]
        for k in expired:
            self._store.pop(k, None)

    async def set(self, key: str, value: str, ttl: int) -> None:
        self._cleanup_expired()
        self._store[key] = (value, time.time() + ttl)

    async def get(self, key: str) -> str | None:
        self._cleanup_expired()
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expire = entry
        if time.time() > expire:
            self._store.pop(key, None)
            return None
        return value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


class RedisChallengeStore(ChallengeStore):
    """Redis 存储（生产环境推荐）

    多 worker/多实例共享，原生 TTL 支持。
    """

    def __init__(self, redis_client) -> None:
        self._redis = redis_client

    async def set(self, key: str, value: str, ttl: int) -> None:
        await self._redis.set(key, value, ex=ttl)

    async def get(self, key: str) -> str | None:
        value = await self._redis.get(key)
        if value is None:
            return None
        return value.decode() if isinstance(value, bytes) else value

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)


# ── 存储工厂（懒加载，避免导入时连接 Redis） ──

_challenge_store: ChallengeStore | None = None
_redis_client = None


def _get_challenge_store() -> ChallengeStore:
    """根据配置选择挑战存储后端"""
    global _challenge_store, _redis_client

    if _challenge_store is not None:
        return _challenge_store

    redis_url = settings.redis_url.strip()
    if redis_url:
        try:
            import redis.asyncio as aioredis  # type: ignore
            _redis_client = aioredis.from_url(
                redis_url, decode_responses=False, socket_timeout=2.0
            )
            _challenge_store = RedisChallengeStore(_redis_client)
            logger.info("WebAuthn 挑战存储: Redis (%s)", redis_url)
        except Exception as e:
            logger.warning(
                "Redis 连接失败，降级为内存存储: %s。多 worker 部署下挑战将不共享。", e
            )
            _challenge_store = MemoryChallengeStore()
    else:
        _challenge_store = MemoryChallengeStore()
        logger.info("WebAuthn 挑战存储: 内存字典（开发模式）")

    return _challenge_store


async def close_challenge_store() -> None:
    """应用关闭时清理资源"""
    global _challenge_store, _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.close()
        except Exception:
            pass
    _challenge_store = None
    _redis_client = None


# ── 辅助函数 ──

def _b64(v: bytes) -> str:
    return base64.urlsafe_b64encode(v).rstrip(b"=").decode()


def _b64_decode(s: str) -> str:
    """补齐 padding 并解码为 UTF-8 字符串"""
    s = s + "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s).decode()


def _b64_decode_bytes(s: str) -> bytes:
    """补齐 padding 并解码为 bytes"""
    s = s + "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)


# ═══════════════════════════════════════════
#  注册
# ═══════════════════════════════════════════

async def webauthn_register_begin(
    db: AsyncSession,
    user: User,
    device_name: str | None = None,
) -> dict:
    """生成注册挑战"""

    # 获取已注册的凭证（排除列表）
    result = await db.execute(
        select(WACModel.credential_id).where(
            WACModel.user_id == user.id,
            WACModel.is_active.is_(True),
        )
    )
    exclude_creds = [
        PublicKeyCredentialDescriptor(
            id=row[0].encode() if isinstance(row[0], str) else row[0],
        )
        for row in result.all()
    ]

    # 准备注册选项关键字参数
    reg_kwargs = {
        "rp_id": settings.webauthn_rp_id,
        "rp_name": "索克家居 · i-home.life",
        "user_name": user.phone,
        "user_id": user.id.encode(),
        "user_display_name": user.name or user.phone,
        "timeout": 60000,
        "attestation": AttestationConveyancePreference.NONE,
        "authenticator_selection": AuthenticatorSelectionCriteria(
            authenticator_attachment=None,
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        "exclude_credentials": exclude_creds,
    }
    if _HAS_HINTS:
        reg_kwargs["hints"] = [PublicKeyCredentialHint.SECURITY_KEY, PublicKeyCredentialHint.CLIENT_DEVICE]

    options = webauthn.generate_registration_options(**reg_kwargs)

    # 存储挑战映射（带 TTL）
    challenge_b64 = _b64(options.challenge)
    store = _get_challenge_store()
    await store.set(
        challenge_b64,
        user.id,
        ttl=settings.webauthn_challenge_ttl,
    )

    # 序列化为 JSON
    return json.loads(webauthn.options_to_json(options))


async def webauthn_register_complete(
    db: AsyncSession,
    credential_json: dict,
    device_name: str | None = None,
    transports: list[str] | None = None,
) -> WACModel:
    """验证注册结果"""

    # 提取挑战并获取 user_id
    challenge_b64 = credential_json.get("response", {}).get("clientDataJSON", "")
    try:
        cdj = json.loads(_b64_decode(challenge_b64))
        challenge = cdj.get("challenge", "")
        store = _get_challenge_store()
        user_id = await store.pop(challenge)
        if not user_id:
            raise ValueError("无效或已过期的挑战，请重新发起注册")
    except (ValueError, json.JSONDecodeError) as e:
        raise ValueError(f"WebAuthn 注册验证失败: {e}")

    # 验证用户
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("用户不存在")

    # 检查凭证 ID 去重
    cred_id = credential_json.get("id", "")
    existing = await db.execute(
        select(WACModel).where(WACModel.credential_id == cred_id)
    )
    if existing.scalar_one_or_none():
        raise ValueError("该 Passkey 已注册，请勿重复注册")

    # 使用库验证
    try:
        verification = webauthn.verify_registration_response(
            credential=credential_json,
            expected_challenge=_b64_decode_bytes(challenge),
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origin,
        )
    except Exception as e:
        logger.error(f"WebAuthn 注册验证失败: {e}")
        raise ValueError(f"Passkey 注册验证失败: {e}")

    # 保存凭证
    pub_key_b64 = _b64(verification.credential_public_key)
    credential_type = "platform"
    if transports and "internal" not in transports:
        credential_type = "cross-platform"

    credential = WACModel(
        id=str(uuid.uuid4()),
        user_id=user_id,
        credential_id=cred_id,
        public_key=pub_key_b64,
        sign_count=verification.credential_current_sign_count,
        device_name=device_name or "未知设备",
        credential_type=credential_type,
        aaguid=verification.aaguid or None,
        is_passkey=True,
    )
    db.add(credential)
    await db.commit()
    await db.refresh(credential)

    logger.info(f"WebAuthn 凭证注册成功: user={user_id}, credential={cred_id}")
    return credential


# ═══════════════════════════════════════════
#  登录
# ═══════════════════════════════════════════

async def webauthn_login_begin(
    db: AsyncSession,
    phone: str | None = None,
) -> dict:
    """生成登录挑战"""

    allow_credentials = []
    if phone:
        result = await db.execute(
            select(WACModel).join(User).where(
                User.phone == phone,
                WACModel.is_active.is_(True),
            )
        )
        for cred in result.scalars().all():
            allow_credentials.append(
                PublicKeyCredentialDescriptor(
                    id=cred.credential_id.encode(),
                    transports=_transports(cred.credential_type),
                )
            )
    else:
        # 不传 phone 时走 discoverable credentials 模式（空 allow_credentials），
        # 由浏览器自动匹配已注册的 Passkey，避免泄露全局凭证 ID 列表
        pass

    options = webauthn.generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        timeout=60000,
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    challenge_b64 = _b64(options.challenge)
    store = _get_challenge_store()
    # 登录挑战用 "login:" 前缀以与注册挑战区分；value 为 "pending"
    await store.set(
        f"login:{challenge_b64}",
        "pending",
        ttl=settings.webauthn_challenge_ttl,
    )

    return json.loads(webauthn.options_to_json(options))


async def webauthn_login_complete(
    db: AsyncSession,
    credential_json: dict,
) -> tuple[User, WACModel]:
    """验证登录断言"""

    # 提取挑战
    challenge_b64 = credential_json.get("response", {}).get("clientDataJSON", "")
    try:
        cdj = json.loads(_b64_decode(challenge_b64))
        challenge = cdj.get("challenge", "")
        store = _get_challenge_store()
        if await store.get(f"login:{challenge}") is None:
            raise ValueError("无效或已过期的登录挑战，请重新发起登录")
        # 一次性消费
        await store.delete(f"login:{challenge}")
    except (ValueError, json.JSONDecodeError) as e:
        raise ValueError(f"WebAuthn 登录验证失败: {e}")

    # 查找凭证
    cred_id = credential_json.get("id", "")
    result = await db.execute(
        select(WACModel).where(
            WACModel.credential_id == cred_id,
            WACModel.is_active.is_(True),
        )
    )
    credential = result.scalar_one_or_none()
    if not credential:
        raise ValueError("未找到该 Passkey 凭证，请先注册")

    # 查找用户
    result = await db.execute(select(User).where(User.id == credential.user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise ValueError("用户不存在或已被禁用")

    # 验证断言
    try:
        verification = webauthn.verify_authentication_response(
            credential=credential_json,
            expected_challenge=_b64_decode_bytes(challenge),
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origin,
            credential_public_key=_b64_decode_bytes(credential.public_key),
            credential_current_sign_count=credential.sign_count,
        )
    except Exception as e:
        logger.error(f"WebAuthn 登录验证失败: {e}")
        raise ValueError(f"Passkey 登录验证失败: {e}")

    # 更新签名计数器和最后使用时间
    credential.sign_count = verification.new_sign_count
    credential.last_used_at = datetime.now(timezone.utc)
    await db.commit()

    logger.info(f"WebAuthn 登录成功: user={user.id}, credential={cred_id}")
    return user, credential


def _transports(credential_type: str | None) -> list[AuthenticatorTransport] | None:
    """根据凭证类型推断传输方式（返回枚举列表以兼容 webauthn 库序列化）"""
    if credential_type == "platform":
        return [AuthenticatorTransport.INTERNAL, AuthenticatorTransport.HYBRID]
    return [
        AuthenticatorTransport.USB,
        AuthenticatorTransport.NFC,
        AuthenticatorTransport.BLE,
        AuthenticatorTransport.HYBRID,
        AuthenticatorTransport.INTERNAL,
    ]
