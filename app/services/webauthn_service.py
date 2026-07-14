"""FIDO2/WebAuthn + Passkey 认证服务

基于 webauthn>=3.0 Python 库实现。
"""

import base64
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import webauthn
from webauthn.helpers.structs import (
    PublicKeyCredentialDescriptor,
    AuthenticatorSelectionCriteria,
    ResidentKeyRequirement,
    AttestationConveyancePreference,
    UserVerificationRequirement,
    PublicKeyCredentialHint,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User
from app.models.webauthn_credential import WebAuthnCredential as WACModel

logger = logging.getLogger(__name__)

settings = get_settings()

# 挑战存储（内存，生产环境替换为 Redis）
_challenge_store: dict[str, str] = {}  # challenge_b64 → user_id

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
            WACModel.is_active == True,
        )
    )
    exclude_creds = [
        PublicKeyCredentialDescriptor(
            id=row[0].encode() if isinstance(row[0], str) else row[0],
        )
        for row in result.all()
    ]

    # 使用库生成注册选项
    options = webauthn.generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name="索克家居 · i-home.life",
        user_name=user.phone,
        user_id=user.id.encode(),
        user_display_name=user.name or user.phone,
        timeout=60000,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=None,
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=exclude_creds,
        hints=[PublicKeyCredentialHint.SECURITY_KEY, PublicKeyCredentialHint.CLIENT_DEVICE],
    )

    # 存储挑战映射
    challenge_b64 = _b64(options.challenge)
    _challenge_store[challenge_b64] = user.id

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
        user_id = _challenge_store.pop(challenge, None)
        if not user_id:
            raise ValueError("无效或已过期的挑战")
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
                WACModel.is_active == True,
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
        result = await db.execute(
            select(WACModel).where(WACModel.is_active == True)
        )
        for cred in result.scalars().all():
            allow_credentials.append(
                PublicKeyCredentialDescriptor(
                    id=cred.credential_id.encode(),
                    transports=_transports(cred.credential_type),
                )
            )

    options = webauthn.generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        timeout=60000,
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    challenge_b64 = _b64(options.challenge)
    _challenge_store[f"login:{challenge_b64}"] = "pending"

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
        if _challenge_store.get(f"login:{challenge}") is None:
            raise ValueError("无效或已过期的登录挑战")
    except (ValueError, json.JSONDecodeError) as e:
        raise ValueError(f"WebAuthn 登录验证失败: {e}")

    # 查找凭证
    cred_id = credential_json.get("id", "")
    result = await db.execute(
        select(WACModel).where(
            WACModel.credential_id == cred_id,
            WACModel.is_active == True,
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

    # 清理挑战
    _challenge_store.pop(f"login:{challenge}", None)

    logger.info(f"WebAuthn 登录成功: user={user.id}, credential={cred_id}")
    return user, credential


def _transports(credential_type: str | None) -> list[str] | None:
    """根据凭证类型推断传输方式"""
    if credential_type == "platform":
        return ["internal", "hybrid"]
    return ["usb", "nfc", "ble", "hybrid", "internal"]
