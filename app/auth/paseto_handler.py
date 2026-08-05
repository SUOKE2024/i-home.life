import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, cast

import paseto
from paseto.keys.symmetric_key import SymmetricKey
from paseto.protocols.v4 import ProtocolVersion4 as v4

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


# ── v1.8.1 P0-2: Token 撤销列表（logout 主动失效） ──────────────────
# v1.8.2 P2.5: 加 Redis backend（受 paseto_revocation_redis_enabled 控制）
# - False（默认）：进程内 dict[jti -> expires_at_timestamp]，FC 单实例场景 OK
# - True：Redis 共享撤销列表（多 worker 必需），Redis 不可用时 best-effort 降级到内存
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


@lru_cache(maxsize=1)
def _get_key() -> SymmetricKey:
    """缓存 SymmetricKey 对象，避免每次请求重建。

    密钥内容来自 settings.paseto_secret_key，进程生命周期内不变，
    使用 lru_cache(maxsize=1) 实现模块级单例。

    v1.2.1 P1-7 修复：原密钥 <32 字节时用 \\x00 填充（弱化密钥，安全风险）。
    现 paseto_strict_mode=True 时硬 raise，仅 strict_mode=False 时回退 \\x00 填充（紧急回滚用）。
    注意：config.py 的 model_validator 已在启动时拦截默认/过短密钥，此处为运行期二次防御。
    """
    key_bytes = settings.paseto_secret_key.encode()
    if len(key_bytes) < 32:
        if getattr(settings, "paseto_strict_mode", True):
            # 严格模式：硬失败，拒绝弱密钥（生产默认）
            raise ValueError(
                "PASETO secret key 长度不足 32 字节（当前 %d 字节），paseto_strict_mode=True 拒绝填充。"
                "请在 .env 配置强密钥，或设 PASETO_STRICT_MODE=false 临时回退（不推荐生产）。"
                % len(key_bytes)
            )
        logger.warning(
            "PASETO secret key 长度不足 32 字节，正在用 \\x00 填充，生产环境必须配置强密钥"
        )
        key_bytes = key_bytes.ljust(32, b"\x00")
    return SymmetricKey(key_material=key_bytes[:32], protocol=v4)


def create_token(user_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.paseto_token_expire_minutes)

    payload = {
        "sub": user_id,
        "role": role,
        "iat": now.isoformat(),
        "exp": exp.isoformat(),
        # v1.8.1 P1-1: jti 唯一标识，支持 logout 主动撤销。
        # 旧 token 无此字段，verify_token 视为"不可撤销"通过（向后兼容）。
        "jti": str(uuid.uuid4()),
    }
    key = _get_key()
    return cast(str, paseto.create(key=key, purpose="local", claims=payload))


def verify_token(token: str) -> dict:
    """校验 PASETO token，返回 payload。

    Raises:
        TokenExpiredError: token 已过期
        TokenInvalidError: token 无效（签名/格式/密钥错误/exp 缺失或格式错/被撤销）

    v1.8.1 P0-1 修复：原 exp 字段缺失或解析失败时 `except: pass` → fail-open
    （token 被视为永不过期）。现 fail-closed：exp 缺失或格式错 → TokenInvalidError。
    v1.8.1 P0-2 新增：jti 在撤销列表中 → TokenInvalidError。
    """
    try:
        key = _get_key()
        result = paseto.parse(key=key, purpose="local", token=token)
        payload: dict = result["message"]

        # v1.8.1 P0-1: fail-closed。exp 缺失或格式错 → 拒绝（原 fail-open 视为永不过期）
        exp_str = payload.get("exp")
        if not exp_str:
            raise TokenInvalidError("Token 缺少 exp 字段")
        try:
            exp = datetime.fromisoformat(exp_str)
        except (ValueError, TypeError) as e:
            raise TokenInvalidError(f"Token exp 格式无效: {exp_str!r}") from e
        if datetime.now(timezone.utc) > exp:
            raise TokenExpiredError("Token 已过期，请重新登录")

        # v1.8.1 P0-2: 检查 token 撤销列表（logout 主动失效）
        jti = payload.get("jti")
        if jti and is_token_revoked(jti):
            raise TokenInvalidError("Token 已被撤销")

        return payload
    except (TokenExpiredError, TokenInvalidError):
        raise
    except Exception as e:
        raise TokenInvalidError(f"Token 无效: {e}") from e
