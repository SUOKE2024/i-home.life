import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import paseto
from paseto.keys.symmetric_key import SymmetricKey
from paseto.protocols.v4 import ProtocolVersion4 as v4

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


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
    }
    key = _get_key()
    return paseto.create(key=key, purpose="local", claims=payload)


def verify_token(token: str) -> dict:
    """校验 PASETO token，返回 payload。

    Raises:
        TokenExpiredError: token 已过期
        TokenInvalidError: token 无效（签名/格式/密钥错误）
    """
    try:
        key = _get_key()
        result = paseto.parse(key=key, purpose="local", token=token)
        payload = result["message"]

        # 检查过期
        exp_str = payload.get("exp")
        if exp_str:
            try:
                exp = datetime.fromisoformat(exp_str)
                if datetime.now(timezone.utc) > exp:
                    raise TokenExpiredError("Token 已过期，请重新登录")
            except (ValueError, TypeError):
                pass

        return payload
    except (TokenExpiredError, TokenInvalidError):
        raise
    except Exception as e:
        raise TokenInvalidError(f"Token 无效: {e}") from e
