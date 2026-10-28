"""A2A Agent Card 的 Ed25519 签名（原生签名对象，**不是 JWS**）。

家居硬约束「PASETO v4.public（Ed25519 非对称签发/验签），禁止使用 JWT/JWS」——
因此这里签的是**规范化 JSON 摘要**，签名字段是普通对象
``{"alg": "Ed25519", "kid": <公钥指纹前 8 位>, "sig": <base64url 无填充>}``，
不采用 JWS compact / JWT 结构，避免与既有鉴权体系混用。

密钥来源：``settings.a2a_card_ed25519_seed``（base64 编码 32 字节种子）。
未配置或格式非法 → 卡片不签名（``signature=None``），发现端点仍可用；
这是**诚实降级**，不得伪造签名字段。
"""

import base64
import json
import logging
from typing import Any, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.config import get_settings

logger = logging.getLogger(__name__)

ALG = "Ed25519"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _seed_bytes() -> Optional[bytes]:
    """读取并解码种子；缺失/非法返回 None（不抛异常，避免拖垮公开发现端点）。"""
    raw = (get_settings().a2a_card_ed25519_seed or "").strip()
    if not raw:
        return None
    try:
        seed = base64.b64decode(raw, validate=True)
    except Exception as e:
        logger.warning("A2A_CARD_ED25519_SEED base64 解码失败，卡片将以未签名发布: %s", e)
        return None
    if len(seed) != 32:
        logger.warning("A2A_CARD_ED25519_SEED 长度应为 32 字节，实际 %d，卡片将以未签名发布", len(seed))
        return None
    return seed


def _public_key_b64url(seed: bytes) -> str:
    pub = Ed25519PrivateKey.from_private_bytes(seed).public_key()
    return _b64url(pub.public_bytes(Encoding.Raw, PublicFormat.Raw))


def _fingerprint(public_key_b64url: str) -> str:
    """指纹取公钥字符串前 8 位（与索克生活/俱乐部卡片 `signature.kid` 口径一致）。"""
    return public_key_b64url[:8]


def canonical_payload(card: dict[str, Any]) -> bytes:
    """签名载荷：剔除 signature 字段后的规范化 JSON（键排序、紧凑分隔符）。

    验签方必须用同一规范化规则，否则摘要不一致。
    """
    payload = {k: v for k, v in card.items() if k != "signature"}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sign_agent_card(card: dict[str, Any]) -> Optional[dict[str, Any]]:
    """对卡片签名；未配置密钥返回 None。"""
    seed = _seed_bytes()
    if seed is None:
        return None
    try:
        sig = Ed25519PrivateKey.from_private_bytes(seed).sign(canonical_payload(card))
    except Exception as e:  # pragma: no cover - 密钥合法时不应触发
        logger.warning("A2A Card Ed25519 签名失败，卡片将以未签名发布: %s", e)
        return None
    pub = _public_key_b64url(seed)
    return {"alg": ALG, "kid": _fingerprint(pub), "sig": _b64url(sig)}


def public_key_document() -> Optional[dict[str, Any]]:
    """对外验签材料（公钥 + 指纹）；未配置密钥返回 None。"""
    seed = _seed_bytes()
    if seed is None:
        return None
    pub = _public_key_b64url(seed)
    return {"alg": ALG, "public_key": pub, "fingerprint": _fingerprint(pub)}


def verify_agent_card(card: dict[str, Any], public_key_b64url: str) -> bool:
    """验签（供测试与外部对端参考实现）。"""
    signature = card.get("signature") or {}
    sig = signature.get("sig")
    if not sig:
        return False
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        raw = base64.urlsafe_b64decode(public_key_b64url + "=" * (-len(public_key_b64url) % 4))
        key = Ed25519PublicKey.from_public_bytes(raw)
        key.verify(
            base64.urlsafe_b64decode(sig + "=" * (-len(sig) % 4)),
            canonical_payload(card),
        )
        return True
    except Exception:
        return False
