"""索克生态 SSO 消费端：验签并映射索克生活（suoke_life）签发的 v4.public 令牌。

与 suoke_club backend/shared/paseto_auth.py::verify_ecosystem_token 同构：
- 令牌白名单：仅 v4.public（显式拒 v4.local / v2.local / v3）
- 验签公钥：Vault KV suoke/ecosystem 字段 suoke-life-public-paserk（或 ECOSYSTEM_PUBLIC_PASERK env）
- claims 归一化 + iss / type 校验（仅接受 access，拒绝 refresh）
- 安全红线：仅映射 homeowner 角色，不授予任何项目归属（越权由 rbac.verify_project_access 天然拒绝）

本轮不改跨品牌 token 契约：直接按索克生活既有 claim 结构
（user_id / username / roles[] / type / iss / aud）取值。
"""
from __future__ import annotations

import base64
import uuid as _uuid
from datetime import datetime, timezone

import paseto
from paseto.keys.asymmetric_key import AsymmetricPublicKey
from paseto.protocols.v4 import ProtocolVersion4 as v4
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

# 索克生活的签发者标识（与 suoke_life auth-service iss 一致）
_ECOSYSTEM_ISSUERS = ("suoke-life-auth",)
_V4_PUBLIC_PREFIX = "k4.public."
# 生态来源标记（写入 users.sub_role，便于区分生态引流账号）
ECOSYSTEM_SOURCE = "ecosystem_life"


class EcosystemAuthError(Exception):
    """生态令牌校验失败（http 为建议状态码）。"""

    def __init__(self, code: str, message: str, http: int = 401):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http = http


def _load_public_key(paserk: str) -> AsymmetricPublicKey:
    """由 PASERK（k4.public.）构造验签公钥（paseto 2.0.0 的 from_encoded_string 有缺陷，手工解码）。"""
    raw = paserk.strip()
    if raw.startswith(_V4_PUBLIC_PREFIX):
        raw = raw[len(_V4_PUBLIC_PREFIX):]
    data = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    return AsymmetricPublicKey(key_material=data, protocol=v4)


def verify_life_token(token: str, public_paserk: str | None) -> dict:
    """验签索克生活 v4.public access 令牌，返回归一化 claims。

    归一化结果：{user_id, username, roles, iss, type}。
    """
    if not token or not token.startswith("v4.public."):
        raise EcosystemAuthError("ECOSYSTEM_TOKEN_INVALID", "生态令牌格式非法（仅接受 v4.public）")
    if not public_paserk:
        raise EcosystemAuthError("ECOSYSTEM_KEY_MISSING", "生态公钥未配置", http=503)

    try:
        key = _load_public_key(public_paserk)
        result = paseto.parse(key=key, token=token, purpose="public", validate=False)
    except Exception as e:  # 验签失败统一按无效令牌处理
        raise EcosystemAuthError("ECOSYSTEM_TOKEN_INVALID", f"生态令牌验签失败: {e}") from e

    claims = result["message"] or {}
    if not isinstance(claims, dict):
        raise EcosystemAuthError("ECOSYSTEM_TOKEN_INVALID", "生态令牌载荷非法")

    if claims.get("iss") not in _ECOSYSTEM_ISSUERS:
        raise EcosystemAuthError("ECOSYSTEM_ISSUER_MISMATCH", "生态令牌签发者不符")
    if claims.get("type") != "access":
        raise EcosystemAuthError("ECOSYSTEM_TYPE_MISMATCH", "生态令牌类型不符（仅接受 access）")

    exp_str = claims.get("exp")
    if not exp_str:
        raise EcosystemAuthError("ECOSYSTEM_CLAIM_MISSING", "生态令牌缺少 exp")
    try:
        exp = datetime.fromisoformat(str(exp_str).replace("Z", "+00:00"))
    except (ValueError, TypeError) as e:
        raise EcosystemAuthError("ECOSYSTEM_TOKEN_INVALID", "生态令牌 exp 格式无效") from e
    if datetime.now(timezone.utc) > exp:
        raise EcosystemAuthError("ECOSYSTEM_TOKEN_EXPIRED", "生态令牌已过期")

    user_id = claims.get("user_id") or claims.get("sub")
    if not user_id:
        raise EcosystemAuthError("ECOSYSTEM_CLAIM_MISSING", "生态令牌缺少 user_id")

    return {
        "user_id": str(user_id),
        "username": claims.get("username") or str(user_id),
        "roles": claims.get("roles") or ["user"],
        "iss": claims.get("iss", ""),
        "type": claims.get("type", ""),
    }


def deterministic_user_id(life_user_id: str) -> str:
    """由索克生活 user_id 派生确定性的本系统用户 id（uuid5，幂等）。"""
    return str(_uuid.uuid5(_uuid.NAMESPACE_URL, "suoke-life:" + life_user_id))


async def get_or_create_ecosystem_user(db: AsyncSession, norm: dict) -> User:
    """按确定性 id 幂等建号/复用（生态引流账号，仅 homeowner 角色、无项目归属）。"""
    uid = deterministic_user_id(norm["user_id"])
    user = await db.get(User, uid)
    if user is not None:
        return user

    user = User(
        id=uid,
        phone=None,
        name=norm.get("username") or "索克生活用户",
        role="homeowner",
        sub_role=ECOSYSTEM_SOURCE,
        is_verified=False,
    )
    db.add(user)
    try:
        await db.flush()
    except Exception:
        # 并发首登可能撞 id 主键：回滚该次插入并复用已建账号
        await db.rollback()
        existing = await db.get(User, uid)
        if existing is None:
            raise
        return existing
    return user
