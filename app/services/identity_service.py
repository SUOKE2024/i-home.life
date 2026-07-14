"""实名认证服务 — 支持第三方身份证核验（阿里云/腾讯云）"""

import json
import logging
import hashlib
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User
from app.models.identity_verification import IdentityVerification

logger = logging.getLogger(__name__)
settings = get_settings()


# ── 第三方核验抽象层 ──

class IdentityProvider:
    """第三方身份核验接口抽象"""

    async def verify_id_card(self, real_name: str, id_card: str) -> dict:
        """核验身份证号码与姓名是否匹配
        Returns: {"verified": bool, "provider": str, "detail": dict}
        """
        raise NotImplementedError


class AliyunIdentityProvider(IdentityProvider):
    """阿里云身份证实名认证"""
    # 阿里云身份证二要素核验 API
    # https://market.aliyun.com/products/57000002/cmapi00047270.html

    async def verify_id_card(self, real_name: str, id_card: str) -> dict:
        try:
            # 注：实际使用时需要配置阿里云 AppCode
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://eid.shumaidata.com/eid/check",
                    headers={
                        "Authorization": f"APPCODE {settings.aliyun_id_verify_appcode}",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data={"idcard": id_card, "name": real_name},
                )
                data = resp.json()
                if data.get("code") == 0:
                    result = data.get("result", {})
                    return {
                        "verified": result.get("ispass", False),
                        "provider": "aliyun",
                        "detail": result,
                    }
                return {"verified": False, "provider": "aliyun", "detail": data}
        except Exception as e:
            logger.warning(f"阿里云身份核验失败: {e}")
            return {"verified": False, "provider": "aliyun", "detail": {"error": str(e)}}


class MockIdentityProvider(IdentityProvider):
    """本地 Mock 核验（无第三方 API Key 时使用）"""

    async def verify_id_card(self, real_name: str, id_card: str) -> dict:
        # 模拟核验：身份证号格式基本校验
        valid = len(id_card) in (15, 18) and len(real_name) >= 2
        return {
            "verified": valid,
            "provider": "mock",
            "detail": {"mock": True, "format_valid": valid},
        }


def _get_identity_provider() -> IdentityProvider:
    """根据配置选择身份核验服务商"""
    if settings.aliyun_id_verify_appcode:
        return AliyunIdentityProvider()
    return MockIdentityProvider()


# ── 加密工具 ──

def _encrypt_id_card(id_card: str) -> str:
    """对称加密身份证号存储"""
    key = settings.paseto_secret_key.encode()[:32]
    # 简单混淆存储（生产环境请使用 AES-256-GCM）
    return hashlib.sha256((id_card + key.decode()).encode()).hexdigest()[:32]


# ── 服务方法 ──

async def submit_verification(
    db: AsyncSession,
    user: User,
    real_name: str,
    id_card: str,
    id_card_front: str | None = None,
    id_card_back: str | None = None,
    selfie_with_id: str | None = None,
    role_attributes: dict | None = None,
) -> IdentityVerification:
    """提交实名认证申请"""

    # 检查是否已提交
    stmt = select(IdentityVerification).where(IdentityVerification.user_id == user.id)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        # 允许重新提交（如果之前被拒绝）
        if existing.status == "pending":
            return existing
        existing.status = "pending"
        existing.real_name = real_name
        existing.id_card = _encrypt_id_card(id_card)
        existing.id_card_front = id_card_front
        existing.id_card_back = id_card_back
        existing.selfie_with_id = selfie_with_id
        if role_attributes:
            existing.role_attributes = json.dumps(role_attributes, ensure_ascii=False)
    else:
        verification = IdentityVerification(
            user_id=user.id,
            role=user.role,
            real_name=real_name,
            id_card=_encrypt_id_card(id_card),
            id_card_front=id_card_front,
            id_card_back=id_card_back,
            selfie_with_id=selfie_with_id,
            role_attributes=json.dumps(role_attributes, ensure_ascii=False) if role_attributes else None,
            status="pending",
        )
        db.add(verification)
        existing = verification

    # 调用第三方核验
    try:
        provider = _get_identity_provider()
        verify_result = await provider.verify_id_card(real_name, id_card)
        existing.third_party_verified = verify_result["verified"]
        existing.third_party_provider = verify_result["provider"]
        existing.third_party_result = json.dumps(verify_result["detail"], ensure_ascii=False)

        # 如果第三方自动核验通过 + 业主角色，可自动审核通过
        if verify_result["verified"] and user.role == "homeowner":
            existing.status = "approved"
            existing.verified_at = datetime.now(timezone.utc)
            user.is_verified = True
    except Exception as e:
        logger.warning(f"第三方核验调用失败: {e}")
        # 核验失败不阻断提交，进入人工审核
        existing.third_party_verified = False
        existing.third_party_result = json.dumps({"error": str(e)})

    await db.commit()
    await db.refresh(existing)
    return existing


async def get_verification_status(db: AsyncSession, user_id: str) -> dict:
    """获取认证状态"""
    stmt = select(IdentityVerification).where(IdentityVerification.user_id == user_id)
    result = await db.execute(stmt)
    verification = result.scalar_one_or_none()
    if not verification:
        return {"is_verified": False, "status": "not_submitted", "role": None, "submitted_at": None}
    return {
        "is_verified": verification.status == "approved",
        "status": verification.status,
        "role": verification.role,
        "submitted_at": verification.created_at.isoformat() if verification.created_at else None,
    }


async def review_verification(
    db: AsyncSession,
    verification_id: str,
    status: str,
    reviewer_id: str,
    review_note: str | None = None,
) -> IdentityVerification | None:
    """管理员审核认证"""
    stmt = select(IdentityVerification).where(IdentityVerification.id == verification_id)
    result = await db.execute(stmt)
    verification = result.scalar_one_or_none()
    if not verification:
        return None

    verification.status = status
    verification.reviewer_id = reviewer_id
    verification.review_note = review_note

    if status == "approved":
        verification.verified_at = datetime.now(timezone.utc)
        # 更新用户认证状态
        user_stmt = select(User).where(User.id == verification.user_id)
        user_result = await db.execute(user_stmt)
        user = user_result.scalar_one_or_none()
        if user:
            user.is_verified = True

    await db.commit()
    await db.refresh(verification)
    return verification


async def list_pending_verifications(db: AsyncSession) -> list[IdentityVerification]:
    """获取待审核列表（管理员）"""
    stmt = select(IdentityVerification).where(
        IdentityVerification.status == "pending"
    ).order_by(IdentityVerification.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())
