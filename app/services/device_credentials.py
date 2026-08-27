"""Matter 网络凭据加密存储（2026-08-27 设备链路加固）

wifi_credentials（含 WiFi 密码）与 thread_credentials（含 Thread master_key）
为高敏凭据，禁止明文落库（此前以明文 JSON 存于 matter_devices 表）。
此处用 PASETO 主密钥派生 AES-256-GCM 密钥加密：

- 密钥派生：SHA-256(paseto_secret_key)，进程生命周期稳定，与鉴权密钥同源
- 存储格式：JSON 列存 {"encrypted": "<base64(nonce+ct)>"}，保持 ORM dict 类型不变
- 加密失败（密钥缺失等）返回 None，由调用方决定拒绝落库（fail-closed）
- 解密失败/篡改/密钥轮换期返回 None，调用方不得伪装成功（诚实降级）
"""
import base64
import hashlib
import json
import logging
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings

logger = logging.getLogger("ihome.device_credentials")

_ENCRYPTED_KEY = "encrypted"


def _derive_key() -> bytes:
    """派生 AES-256-GCM 密钥（SHA-256(paseto_secret_key)）。"""
    settings = get_settings()
    raw = settings.paseto_secret_key.encode()
    if len(raw) < 32:
        if getattr(settings, "paseto_strict_mode", True):
            raise ValueError(
                "PASETO secret key 长度不足 32 字节，无法派生设备凭据加密密钥"
            )
        raw = raw.ljust(32, b"\x00")
    return hashlib.sha256(raw).digest()


def encrypt_device_credentials(data: dict[str, Any] | None) -> dict[str, str] | None:
    """加密网络凭据 dict → {"encrypted": "<b64>"}；None/空 dict 原样返回 None。"""
    if not data:
        return None
    try:
        key = _derive_key()
        nonce = os.urandom(12)
        plain = json.dumps(data, ensure_ascii=False).encode("utf-8")
        ciphertext = AESGCM(key).encrypt(nonce, plain, None)
        return {_ENCRYPTED_KEY: base64.b64encode(nonce + ciphertext).decode("ascii")}
    except Exception as e:  # noqa: BLE001 — 加密失败诚实返回 None，由调用方拒绝落库
        logger.error("device_credentials_encrypt_failed: %s", e)
        return None


def decrypt_device_credentials(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """解密 {"encrypted": "<b64>"} → 原始 dict；None/非法/篡改返回 None（不伪装）。"""
    if not isinstance(payload, dict):
        return None
    b64 = payload.get(_ENCRYPTED_KEY)
    if not isinstance(b64, str) or not b64:
        return None
    try:
        key = _derive_key()
        raw = base64.b64decode(b64)
        if len(raw) < 13:  # 至少 12 字节 nonce + 1 字节密文
            return None
        nonce, ciphertext = raw[:12], raw[12:]
        plain = AESGCM(key).decrypt(nonce, ciphertext, None)
        result = json.loads(plain.decode("utf-8"))
        return result if isinstance(result, dict) else None
    except Exception as e:  # noqa: BLE001 — 解密失败（篡改/密钥轮换）诚实降级
        logger.error("device_credentials_decrypt_failed: %s", e)
        return None
