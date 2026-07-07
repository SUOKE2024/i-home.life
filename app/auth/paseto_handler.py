from datetime import datetime, timedelta, timezone

import paseto
from paseto.keys.symmetric_key import SymmetricKey
from paseto.protocols.v4 import ProtocolVersion4 as v4

from app.config import get_settings

settings = get_settings()


def _get_key() -> SymmetricKey:
    key_bytes = settings.paseto_secret_key.encode()
    if len(key_bytes) < 32:
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


def verify_token(token: str) -> dict | None:
    try:
        key = _get_key()
        result = paseto.parse(key=key, purpose="local", token=token)
        payload = result["message"]
        return payload
    except Exception:
        return None
