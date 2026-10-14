import base64
import logging
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, cast

import paseto
from paseto.keys.asymmetric_key import AsymmetricPublicKey, AsymmetricSecretKey
from paseto.keys.symmetric_key import SymmetricKey
from paseto.protocols.v4 import ProtocolVersion4 as v4

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


# ── v1.8.1 P0-2: Token 撤销列表（logout 主动失效） ──────────────────
# v1.8.2 P2.5: 加 Redis backend（受 paseto_revocation_redis_enabled 控制）
# v1.14.1 起默认 True：Redis 共享撤销列表（多 worker 必需），Redis 不可用时
# best-effort 降级到内存；显式设 False 回到进程内 dict[jti -> expires_at_timestamp]
_revoked_tokens: dict[str, float] = {}
_redis_client: Any = None
_redis_init_attempted: bool = False


def _get_redis_client() -> Any:
    """延迟初始化 Redis 客户端（best-effort，失败返回 None 降级到内存）。

    单例：_redis_init_attempted 防重复初始化。paseto_handler 是同步代码，
    用同步 redis 客户端（非 redis.asyncio）。
    """
    global _redis_client, _redis_init_attempted
    if _redis_init_attempted:
        return _redis_client
    _redis_init_attempted = True
    url = getattr(settings, "paseto_revocation_redis_url", "")
    if not url:
        logger.warning(
            "paseto_revocation_redis_enabled=True 但 paseto_revocation_redis_url 未配置，降级到内存撤销列表"
        )
        return None
    try:
        import redis  # redis>=5.2.0（已在 requirements.txt）
        _redis_client = redis.from_url(url, decode_responses=True)
        _redis_client.ping()  # 健康检查
        logger.info("paseto_revocation: Redis backend 已启用")
    except Exception as e:
        logger.warning("paseto_revocation: Redis 初始化失败，降级到内存: %s", e)
        _redis_client = None
    return _redis_client


def _use_redis_backend() -> bool:
    """是否启用 Redis 撤销列表 backend（flag 开 + Redis 可用）。"""
    if not getattr(settings, "paseto_revocation_redis_enabled", False):
        return False
    return _get_redis_client() is not None


def revoke_token(jti: str, exp_iso: str) -> None:
    """撤销指定 token（logout 调用）。TTL = 剩余 exp 时间，自动过期清理。

    Args:
        jti: token 唯一标识（payload.jti）
        exp_iso: token 过期时间 ISO 字符串（payload.exp），用于计算 TTL

    Notes:
        - 内存模式：进程内 dict，进程重启即清空（已知限制）
        - Redis 模式（v1.8.2）：多 worker 共享，setex 自动过期
        - 已过期 token 无需撤销（直接返回）
    """
    try:
        exp = datetime.fromisoformat(exp_iso)
    except (ValueError, TypeError):
        return  # exp 无效，跳过（不阻断 logout 主流程）

    now_dt = datetime.now(timezone.utc)
    ttl_seconds = (exp - now_dt).total_seconds()
    if ttl_seconds <= 0:
        return  # 已过期，无需撤销

    # v1.8.2: Redis backend（flag 开时优先）
    if _use_redis_backend():
        try:
            client = _get_redis_client()
            client.setex(f"revoked_jti:{jti}", int(ttl_seconds), "1")
            return
        except Exception as e:
            logger.warning("paseto_revocation: Redis setex 失败，降级到内存: %s", e)

    # 内存 backend
    _revoked_tokens[jti] = time.time() + ttl_seconds
    # 惰性清理：每 100 次撤销清一次过期项，防内存增长
    if len(_revoked_tokens) % 100 == 0:
        cleanup_revoked_tokens()


def is_token_revoked(jti: str) -> bool:
    """检查 token 是否被撤销。"""
    # v1.8.2: Redis backend（flag 开时优先）
    if _use_redis_backend():
        try:
            client = _get_redis_client()
            return int(client.exists(f"revoked_jti:{jti}")) > 0
        except Exception as e:
            logger.warning("paseto_revocation: Redis 查询失败，降级到内存: %s", e)
    # 内存 backend
    exp_ts = _revoked_tokens.get(jti)
    if exp_ts is None:
        return False
    if time.time() < exp_ts:
        return True
    _revoked_tokens.pop(jti, None)  # 已过期，清理
    return False


def cleanup_revoked_tokens() -> None:
    """清理已过期的撤销记录（仅内存 backend 需要，Redis setex 自动过期）。"""
    now = time.time()
    expired = [jti for jti, ts in _revoked_tokens.items() if ts <= now]
    for jti in expired:
        _revoked_tokens.pop(jti, None)


class TokenExpiredError(Exception):
    """Token 已过期"""


class TokenInvalidError(Exception):
    """Token 无效（签名错误/格式错误等）"""


# ── PASETO v4.public（Ed25519 非对称）密钥加载 ──────────────────────
# 项目约定：PASETO 而非 JWT。签发用私钥、验签用公钥。
# 密钥来源（优先级 settings → 环境变量）；支持 Ed25519 PEM 或 PASERK（k4.secret./k4.public.）。
# 说明：paseto 2.0.0 的非对称密钥 from_encoded_string 存在缺陷，故统一用 cryptography
# 解析 PEM 得到原始字节、PASERK 手工 base64url 解码，再以原始字节构造 Key。
_V4_SECRET_PREFIX = "k4.secret."
_V4_PUBLIC_PREFIX = "k4.public."

# legacy v4.local 令牌命中计数（观测用；过渡窗口到期后可据此提前摘除兼容分支）
_legacy_local_hits = 0


def _b64url_decode_material(s: str) -> bytes:
    s = s.strip()
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _secret64_from_seed(seed: bytes) -> bytes:
    """由 32 字节种子构造 libsodium 64 字节私钥（seed||pub）。

    注意：paseto 2.0.0 的 AsymmetricSecretKey 种子分支误取 keypair[0]（实为公钥），
    会得到 32 字节私钥并触发 'Truncated secret key'，故此处直接传入完整 64 字节。
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    sk = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
    pk = sk.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return seed + pk


def _normalize_secret(raw: bytes) -> bytes:
    """规整私钥材料为 64 字节：64 直接用；32 视为种子扩展；96 截取前 64。"""
    if len(raw) == 64:
        return raw
    if len(raw) == 32:
        return _secret64_from_seed(raw)
    if len(raw) == 96:
        return raw[:64]
    raise ValueError(f"PASETO_PRIVATE_KEY 材料长度非法: {len(raw)} 字节")


def _secret_key_from_material(value: str) -> AsymmetricSecretKey:
    v = value.strip()
    if v.startswith(_V4_SECRET_PREFIX):
        raw = _b64url_decode_material(v[len(_V4_SECRET_PREFIX):])
        return AsymmetricSecretKey(key_material=_normalize_secret(raw), protocol=v4)
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    key = serialization.load_pem_private_key(v.encode(), password=None)
    if not isinstance(key, ed25519.Ed25519PrivateKey):
        raise ValueError("PASETO_PRIVATE_KEY 必须是 Ed25519 私钥 PEM 或 k4.secret. PASERK")
    seed = key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    return AsymmetricSecretKey(key_material=_secret64_from_seed(seed), protocol=v4)


def _public_key_from_material(value: str) -> AsymmetricPublicKey:
    v = value.strip()
    if v.startswith(_V4_PUBLIC_PREFIX):
        raw = _b64url_decode_material(v[len(_V4_PUBLIC_PREFIX):])
        return AsymmetricPublicKey(key_material=raw, protocol=v4)
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    key = serialization.load_pem_public_key(v.encode())
    if not isinstance(key, ed25519.Ed25519PublicKey):
        raise ValueError("PASETO_PUBLIC_KEY 必须是 Ed25519 公钥 PEM 或 k4.public. PASERK")
    raw = key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return AsymmetricPublicKey(key_material=raw, protocol=v4)


def _is_dev_env() -> bool:
    """是否处于 dev/test 环境（未配置密钥时允许自动生成临时 Ed25519 密钥对）。

    判据：debug=True 或 ENVIRONMENT/APP_ENV 明确为开发/测试。
    注意：**不以 `paseto_strict_mode=False` 作为判据**——该 flag 是"放宽密钥强度校验"的
    回滚开关；生产应急回滚时若据此自动生成临时密钥，会导致多实例/重启间密钥不一致、
    验签互相失败。开发/测试请显式设 DEBUG=true 或 ENVIRONMENT=test。
    """
    env = (os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or "").strip().lower()
    return settings.debug or env in {"dev", "development", "test", "local"}


def _configured_private() -> str:
    return (getattr(settings, "paseto_private_key", "") or os.getenv("PASETO_PRIVATE_KEY") or "").strip()


def _configured_public() -> str:
    return (getattr(settings, "paseto_public_key", "") or os.getenv("PASETO_PUBLIC_KEY") or "").strip()


@lru_cache(maxsize=1)
def _get_sign_key() -> AsymmetricSecretKey:
    """签发私钥（仅签发侧）。生产必须配置；dev/test 未配置时自动生成临时 Ed25519 密钥对。"""
    private = _configured_private()
    if private:
        return _secret_key_from_material(private)
    if _is_dev_env():
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519

        logger.warning(
            "PASETO_PRIVATE_KEY 未配置，dev/test 自动生成临时 Ed25519 密钥对（进程重启即失效）"
        )
        dev_key = ed25519.Ed25519PrivateKey.generate()
        seed = dev_key.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        )
        return AsymmetricSecretKey(key_material=_secret64_from_seed(seed), protocol=v4)
    raise ValueError(
        "生产环境必须配置 PASETO_PRIVATE_KEY（Ed25519 私钥 PEM 或 k4.secret. PASERK）"
    )


@lru_cache(maxsize=1)
def _get_verify_key() -> AsymmetricPublicKey:
    """验签公钥。优先显式公钥；否则用签发私钥派生；dev/test 无配置时与签发侧共享临时密钥。"""
    public = _configured_public()
    if public:
        return _public_key_from_material(public)
    private = _configured_private()
    if private:
        return _secret_key_from_material(private).get_public_key()
    if _is_dev_env():
        return _get_sign_key().get_public_key()
    raise ValueError(
        "生产环境必须配置 PASETO_PUBLIC_KEY（Ed25519 公钥 PEM 或 k4.public. PASERK）"
    )


@lru_cache(maxsize=1)
def _get_local_key() -> SymmetricKey:
    """legacy v4.local 对称密钥（仅过渡期验签旧令牌，不再用于签发）。

    v1.2.1 P1-7：密钥 <32 字节时 strict_mode 硬 raise，仅 strict_mode=False 回退 \\x00 填充。
    """
    key_bytes = settings.paseto_secret_key.encode()
    if len(key_bytes) < 32:
        if getattr(settings, "paseto_strict_mode", True):
            raise ValueError(
                "PASETO secret key 长度不足 32 字节（当前 %d 字节），legacy v4.local 验签拒绝。"
                % len(key_bytes)
            )
        logger.warning("PASETO secret key 长度不足 32 字节，legacy v4.local 回退 \\x00 填充")
        key_bytes = key_bytes.ljust(32, b"\x00")
    return SymmetricKey(key_material=key_bytes[:32], protocol=v4)


def _legacy_local_accepted() -> bool:
    """legacy v4.local 令牌是否仍在接受窗口内（paseto_local_accept_until 为 epoch 秒，0=不接受）。"""
    try:
        until = float(getattr(settings, "paseto_local_accept_until", 0) or 0)
    except (TypeError, ValueError):
        until = 0.0
    return until > 0 and time.time() < until


def create_token(user_id: str, role: str) -> str:
    """创建 v4.public 访问令牌（access）。

    生态契约统一（增量别名）：在保留本品牌 claim（sub/role）的同时，
    一并写入 `user_id`（=sub）与 `type`（="access"，对应俱乐部 typ="at"）及 iss/aud，
    使三品牌令牌可被彼此的验签侧以统一命名消费；不使在途令牌失效。
    """
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.paseto_token_expire_minutes)
    payload = {
        "sub": user_id,
        "user_id": user_id,  # 生态契约别名（统一 sub/user_id）
        "role": role,
        "type": "access",  # 生态契约（统一 typ/type；对应俱乐部 typ="at"）
        "iss": "i-home-auth",
        "aud": "i-home-app",
        "iat": now.isoformat(),
        "exp": exp.isoformat(),
        # v1.8.1 P1-1: jti 唯一标识，支持 logout 主动撤销。
        "jti": str(uuid.uuid4()),
    }
    key = _get_sign_key()
    return cast(str, paseto.create(key=key, purpose="public", claims=payload))


def create_refresh_token(user_id: str, role: str, jti: str | None = None) -> str:
    """创建 v4.public 刷新令牌（refresh）。

    刷新令牌与访问令牌同 claim 结构，用 PASETO footer {"typ": "rt"} 区分（footer 经签名
    认证但不属于 claims）。生态契约统一（增量别名）：一并写入 `user_id`（=sub）、
    `type="refresh"`（对应俱乐部 typ="rt"）及 iss/aud，便于跨品牌统一命名识别。
    """
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=settings.paseto_refresh_token_expire_days)
    payload = {
        "sub": user_id,
        "user_id": user_id,  # 生态契约别名（统一 sub/user_id）
        "role": role,
        "type": "refresh",  # 生态契约（统一 typ/type；对应俱乐部 typ="rt"）
        "iss": "i-home-auth",
        "aud": "i-home-app",
        "iat": now.isoformat(),
        "exp": exp.isoformat(),
        "jti": jti or str(uuid.uuid4()),
    }
    key = _get_sign_key()
    return cast(
        str,
        paseto.create(key=key, purpose="public", claims=payload, footer={"typ": "rt"}),
    )


def create_token_pair(user_id: str, role: str, family_id: str | None = None) -> dict:
    """签发 access + refresh 令牌对。

    Returns: 含 access_token/refresh_token/token_type/expires_in + 内部字段
    refresh_jti/family_id（返回客户端前须由调用方剥离内部字段）。
    """
    fam = family_id or ("fam_" + uuid.uuid4().hex[:12])
    rt_jti = str(uuid.uuid4())
    return {
        "access_token": create_token(user_id, role),
        "refresh_token": create_refresh_token(user_id, role, jti=rt_jti),
        "token_type": "Bearer",
        "expires_in": settings.paseto_token_expire_minutes * 60,
        "refresh_jti": rt_jti,
        "family_id": fam,
    }


def create_ops_token(subject: str, role: str, ttl_seconds: int) -> str:
    """运维专用：签发指定 TTL 的 v4.public access 令牌（如 i-home FC 定时器静态 admin 令牌）。

    ⚠️ 仅供离线运维脚本（scripts/mint_paseto_token.py）调用，**不得由任何 HTTP 端点暴露**——
    用户 access 令牌 TTL 恒由 paseto_token_expire_minutes 钳制（见 create_token），
    此函数是唯一的长 TTL 签发口，暴露即等于给全站开长效口子。

    subject 必须是数据库中真实存在且启用的用户 id、且 role 具备目标端点所需权限
    （get_current_user 会按 sub 查库；admin 走硬编码 bypass）。
    """
    ttl = int(ttl_seconds)
    if ttl <= 0:
        raise ValueError("ttl_seconds 必须为正整数")
    now = datetime.now(timezone.utc)
    exp = now + timedelta(seconds=ttl)
    payload = {
        "sub": subject,
        "user_id": subject,  # 生态契约别名（统一 sub/user_id）
        "role": role,
        "type": "access",  # 生态契约（统一 typ/type）
        "iss": "i-home-auth",
        "aud": "i-home-app",
        "iat": now.isoformat(),
        "exp": exp.isoformat(),
        "jti": str(uuid.uuid4()),
    }
    key = _get_sign_key()
    return cast(str, paseto.create(key=key, purpose="public", claims=payload))


def _check_exp_and_revocation(payload: dict) -> None:
    """exp 有效性 + jti 撤销校验（fail-closed）。access/refresh 校验共用。"""
    exp_str = payload.get("exp")
    if not exp_str:
        raise TokenInvalidError("Token 缺少 exp 字段")
    try:
        exp = datetime.fromisoformat(str(exp_str).replace("Z", "+00:00"))
    except (ValueError, TypeError) as e:
        raise TokenInvalidError(f"Token exp 格式无效: {exp_str!r}") from e
    if datetime.now(timezone.utc) > exp:
        raise TokenExpiredError("Token 已过期，请重新登录")
    jti = payload.get("jti")
    if jti and is_token_revoked(jti):
        raise TokenInvalidError("Token 已被撤销")


def _decode_public(token: str) -> tuple[dict, dict]:
    """验签 v4.public 令牌，返回 (payload, footer)。"""
    try:
        result = paseto.parse(
            key=_get_verify_key(), token=token, purpose="public", validate=False
        )
    except Exception as e:
        raise TokenInvalidError(f"Token 无效: {e}") from e
    payload: dict = result["message"]
    footer: dict = result["footer"] or {}
    _check_exp_and_revocation(payload)
    return payload, footer


def _decode_legacy_local(token: str) -> dict:
    """验签 legacy v4.local 令牌（仅过渡窗口内）。"""
    global _legacy_local_hits
    _legacy_local_hits += 1
    logger.warning(
        "paseto_legacy_local_accepted: 收到旧版 v4.local 令牌（累计 %d 次），请尽快完成迁移",
        _legacy_local_hits,
    )
    try:
        result = paseto.parse(
            key=_get_local_key(), token=token, purpose="local", validate=False
        )
    except Exception as e:
        raise TokenInvalidError(f"Token 无效: {e}") from e
    payload: dict = result["message"]
    _check_exp_and_revocation(payload)
    return payload


def verify_token(token: str) -> dict:
    """校验访问令牌（access），返回 payload。

    - v4.public：验签 + exp + jti 撤销 + 拒绝 footer typ=rt（刷新令牌不可访问）
    - v4.local / v2.local：仅过渡窗口内接受（legacy 兼容），否则要求重新登录

    Raises:
        TokenExpiredError: token 已过期
        TokenInvalidError: token 无效/格式不支持/被撤销/为刷新令牌/legacy 已停用
    """
    if token.startswith("v4.public."):
        payload, footer = _decode_public(token)
        # 刷新令牌不可作访问令牌：footer typ=rt 或 type=refresh（生态契约别名）任一命中即拒
        if (footer or {}).get("typ") == "rt" or payload.get("type") == "refresh":
            raise TokenInvalidError("刷新令牌不可用于访问接口")
        return payload
    if token.startswith("v4.local.") or token.startswith("v2.local."):
        if not _legacy_local_accepted():
            raise TokenInvalidError("旧版对称令牌已停用，请重新登录")
        return _decode_legacy_local(token)
    raise TokenInvalidError("不支持的令牌格式")


def verify_refresh_token(token: str) -> dict:
    """校验刷新令牌（refresh），返回 payload；要求 footer typ=rt。

    Raises:
        TokenExpiredError / TokenInvalidError
    """
    if not token.startswith("v4.public."):
        raise TokenInvalidError("刷新令牌格式无效")
    payload, footer = _decode_public(token)
    if (footer or {}).get("typ") != "rt":
        raise TokenInvalidError("非刷新令牌")
    return payload
