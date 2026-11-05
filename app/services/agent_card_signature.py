"""A2A Agent Card 的 Ed25519 签名（W-4 2026-11-05：统一为 JWS 信封）。

口径澄清（重要，勿误读）：
- **鉴权**仍然只走 PASETO v4.public，禁止 JWT/JWS 作**令牌**——这条硬约束不变。
- **Agent Card 完整性签名**改用 JWS JSON Serialization（RFC 7515 general 语法），
  与索克生活 / 索克俱乐部同格式，消费方用同一段验签代码即可跨三端；
  此前三端各写一套（JWS 包裹 / signed_ed25519 字段 / 本仓原生 signature 对象），
  跨端必须写三套解析，这正是 W-4 要收口的原因。

仍保留 `sign_agent_card()` 原生签名（内部审计 `agent_governance_audit` 与
既有单测在用）；对外发现端点只发 JWS 信封。

密钥来源：``settings.a2a_card_ed25519_seed``（base64 编码 32 字节种子）。
未配置或格式非法 → 卡片不签名（``signed=false``），发现端点仍可用；
这是**诚实降级**，不得伪造签名字段。
"""

import base64
import json
import logging
from typing import Any, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.config import get_settings

logger = logging.getLogger(__name__)

# RFC 8037：Ed25519 曲线的 JWS `alg` 就是 EdDSA；曲线名放 `crv`。
ALG = "EdDSA"
CRV = "Ed25519"
KID = "ihome-a2a-card-ed25519"


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
    """对外验签材料；未配置密钥返回 None。

    W-3（2026-11-05）：同时给标准 base64（带填充）与 base64url（无填充）两种编码。
    三端此前一为 base64-pad、一为 base64url-nopad，客户端写同一段解码逻辑必挂一边。
    """
    seed = _seed_bytes()
    if seed is None:
        return None
    pub_b64url = _public_key_b64url(seed)  # 无填充 base64url
    pub_std = base64.b64encode(
        base64.urlsafe_b64decode(pub_b64url + "=" * (-len(pub_b64url) % 4))
    ).decode()
    return {
        "alg": ALG,
        "crv": CRV,
        "kid": KID,
        # 兼容旧消费方（此前只有 public_key，且是 base64url 无填充）
        "public_key": pub_b64url,
        "public_key_b64url": pub_b64url,
        "public_key_base64": pub_std,
        "key_encoding": {"public_key": "base64url-nopad", "public_key_base64": "base64"},
        "fingerprint": _fingerprint(pub_b64url),
    }


# ---------------------------------------------------------------------------
# W-4：JWS JSON Serialization（general 语法）——三端统一签名承载
# ---------------------------------------------------------------------------


def _jws_protected() -> str:
    return _b64url(
        json.dumps({"alg": ALG, "kid": KID}, sort_keys=True, separators=(",", ":")).encode()
    )


def sign_agent_card_jws(card: dict[str, Any]) -> Optional[dict[str, Any]]:
    """把卡片签成 JWS 信封；未配置密钥返回 None。

    与索克生活 `shared.agent_card.sign_agent_card_jws_ed25519`、
    索克俱乐部 `shared.agent_card.sign_agent_card` 字节级同构：
    ``{"payload": b64url(card), "signatures": [{"protected", "signature"}]}``
    payload 规范化固定 sort_keys + 紧凑分隔符，保证可复现。
    """
    seed = _seed_bytes()
    if seed is None:
        return None
    payload = _b64url(
        json.dumps(card, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    )
    protected = _jws_protected()
    try:
        signature = Ed25519PrivateKey.from_private_bytes(seed).sign(
            f"{protected}.{payload}".encode("ascii")
        )
    except Exception as e:  # pragma: no cover - 密钥合法时不应触发
        logger.warning("A2A Card JWS 签名失败，卡片将以未签名发布: %s", e)
        return None
    return {"payload": payload, "signatures": [{"protected": protected, "signature": _b64url(signature)}]}


def verify_agent_card_jws(doc: dict[str, Any], public_key_b64: str) -> dict[str, Any]:
    """验签 JWS 信封，返回内层卡片；失败抛 ValueError（供测试与对端参考实现）。"""
    payload = doc.get("payload")
    signatures = doc.get("signatures") or []
    if not isinstance(payload, str) or not signatures:
        raise ValueError("JWS 结构无效")
    protected = signatures[0].get("protected")
    signature = signatures[0].get("signature")
    raw_key = public_key_b64.strip().replace("-", "+").replace("_", "/")
    raw_key += "=" * (-len(raw_key) % 4)
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(raw_key)).verify(
            base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4)),
            f"{protected}.{payload}".encode("ascii"),
        )
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Agent Card JWS 验签失败") from exc
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


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
