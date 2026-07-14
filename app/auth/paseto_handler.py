import logging
from datetime import datetime, timedelta, timezone

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


def _get_key() -> SymmetricKey:
    key_bytes = settings.paseto_secret_key.encode()
    if len(key_bytes) < 32:
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
