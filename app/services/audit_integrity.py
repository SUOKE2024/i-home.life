"""审计完整性服务 — HMAC-SHA256 签名与防篡改校验

为审计日志（AuditLog）添加 HMAC-SHA256 数字签名，确保日志写入后不可篡改。
参照索克生活 Vault AppRole 模式的字段级权限 + 合规签名思路，但独立实现。

能力：
1. 写入时自动对 (user_id + action + resource_id + timestamp + details_checksum) 计算 HMAC
2. 校验端点可批量验证审计日志完整性
3. 支持密钥轮换（versioned keys），旧密钥验证旧日志，新密钥签新日志
4. 字段级脱敏标记：结算金额/支付明细等敏感字段按角色标记脱敏级别

设计原则：
- 永不阻断主流程：签名失败仅记录错误日志
- 受 settings.audit_hmac_enabled feature flag 控制
- HMAC key 从 settings.paseto_secret_key 派生（复用主密钥，不引入新密钥管理负担）
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# 密钥版本化：当前版本号用于新日志签名
_CURRENT_KEY_VERSION = 1


def _derive_hmac_key(version: int = _CURRENT_KEY_VERSION) -> bytes:
    """从 PASETO secret key 派生 HMAC 密钥（版本化）。

    HKDF 简化版：SHA256(paseto_key + version_string) → 32 字节 HMAC key。
    不同版本生成不同密钥，支持密钥轮换。
    """
    base = settings.paseto_secret_key.encode()
    version_bytes = f"audit_hmac_v{version}".encode()
    return hashlib.sha256(base + version_bytes).digest()


def compute_hmac(
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str | None,
    details: dict[str, Any] | None,
    timestamp: str,
    key_version: int = _CURRENT_KEY_VERSION,
) -> str:
    """计算审计日志的 HMAC-SHA256 签名。

    Args:
        user_id: 操作者 ID
        action: 操作类型
        resource_type: 资源类型
        resource_id: 资源 ID
        details: 操作详情（脱敏后）
        timestamp: ISO8601 时间戳
        key_version: 密钥版本号

    Returns:
        64 字符 hex 签名
    """
    # 构建规范化待签名消息
    detail_checksum = hashlib.sha256(
        json.dumps(details or {}, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:16]

    message = "|".join([
        user_id,
        action,
        resource_type,
        resource_id or "",
        detail_checksum,
        timestamp,
    ])

    key = _derive_hmac_key(key_version)
    sig = hmac.new(key, message.encode(), hashlib.sha256).hexdigest()
    return sig


def verify_hmac(
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str | None,
    details: dict[str, Any] | None,
    timestamp: str,
    signature: str,
    key_version: int = _CURRENT_KEY_VERSION,
) -> bool:
    """验证审计日志 HMAC 签名。

    使用 hmac.compare_digest 防止时序攻击。

    Returns:
        True 表示签名有效，日志未被篡改
    """
    try:
        expected = compute_hmac(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            timestamp=timestamp,
            key_version=key_version,
        )
        return hmac.compare_digest(expected, signature)
    except Exception as e:
        logger.debug("hmac_verify_error: %s", e)
        return False


def sign_audit_entry(
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """为审计日志条目生成签名元数据。

    调用方可直接将返回的 dict 合并到 AuditLog.details 或独立字段。

    Returns:
        {
            "hmac_signature": "abc123...",
            "hmac_key_version": 1,
            "signed_at": "2026-07-22T10:00:00+00:00"
        }
        或在 audit_hmac_enabled=False 时返回 None
    """
    if not settings.audit_hmac_enabled:
        return None

    try:
        ts = datetime.now(timezone.utc).isoformat()
        sig = compute_hmac(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            timestamp=ts,
        )
        return {
            "hmac_signature": sig,
            "hmac_key_version": _CURRENT_KEY_VERSION,
            "signed_at": ts,
        }
    except Exception as e:
        logger.error("audit_hmac_sign_failed: user=%s action=%s error=%s", user_id, action, e)
        return None


# ════════════════════════════════════════════════════════════════
# 批量完整性校验
# ════════════════════════════════════════════════════════════════


class AuditIntegrityReport:
    """审计日志完整性校验报告"""

    def __init__(self):
        self.total: int = 0
        self.valid: int = 0
        self.tampered: int = 0
        self.unsigned: int = 0  # 无签名的旧日志（升级前写入）
        self.tampered_ids: list[str] = []

    @property
    def integrity_rate(self) -> float:
        if self.total == 0:
            return 100.0
        return round(self.valid / self.total * 100, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "valid": self.valid,
            "tampered": self.tampered,
            "unsigned": self.unsigned,
            "integrity_rate": self.integrity_rate,
            "tampered_ids": self.tampered_ids[:20],  # 最多返回前 20 条
        }


async def verify_audit_integrity(
    db_session,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = 1000,
) -> AuditIntegrityReport:
    """批量验证审计日志完整性。

    查询指定时间范围内的审计日志，逐条验证 HMAC 签名。
    返回完整性报告。

    Args:
        db_session: 异步数据库会话
        start_time: 起始时间（默认不限）
        end_time: 截止时间（默认不限）
        limit: 最大验证条数

    Returns:
        AuditIntegrityReport
    """
    from sqlalchemy import select
    from app.models.audit_log import AuditLog

    report = AuditIntegrityReport()

    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if start_time:
        stmt = stmt.where(AuditLog.created_at >= start_time)
    if end_time:
        stmt = stmt.where(AuditLog.created_at <= end_time)

    result = await db_session.execute(stmt)
    entries = result.scalars().all()
    report.total = len(entries)

    for entry in entries:
        details = entry.details or {}
        sig_meta = {}

        # 从 details 或独立字段提取签名元数据
        if isinstance(details, dict):
            sig_meta = details.get("_hmac", {}) or {}

        signature = sig_meta.get("signature", "")
        key_version = sig_meta.get("key_version", _CURRENT_KEY_VERSION)

        if not signature:
            report.unsigned += 1
            continue

        ts = entry.created_at.isoformat() if entry.created_at else ""
        valid = verify_hmac(
            user_id=entry.user_id,
            action=entry.action,
            resource_type=entry.resource_type,
            resource_id=entry.resource_id,
            details=details,
            timestamp=ts,
            signature=signature,
            key_version=key_version,
        )

        if valid:
            report.valid += 1
        else:
            report.tampered += 1
            report.tampered_ids.append(entry.id)
            logger.warning(
                "audit_integrity_tampered: id=%s user=%s action=%s",
                entry.id, entry.user_id, entry.action,
            )

    return report


# ════════════════════════════════════════════════════════════════
# 字段级脱敏标记
# ════════════════════════════════════════════════════════════════


# 敏感字段定义：key → 脱敏级别
_SENSITIVE_FIELDS: dict[str, str] = {
    "amount": "L2",           # 金额 — 非财务角色脱敏
    "settlement_amount": "L2",
    "price": "L2",
    "cost": "L2",
    "payment_amount": "L2",
    "bank_account": "L3",     # 银行账号 — 仅管理员可见
    "phone": "L1",            # 手机号 — PII 脱敏后可见
    "id_card": "L3",
    "real_name": "L1",
    "address": "L1",
}

MASK_LEVELS = {
    "L0": "公开",
    "L1": "PII 脱敏后可见",
    "L2": "非财务角色脱敏",
    "L3": "仅管理员可见",
}


def get_field_mask_level(field_name: str) -> str:
    """获取字段的脱敏级别。

    Returns:
        "L0" | "L1" | "L2" | "L3"
    """
    return _SENSITIVE_FIELDS.get(field_name.lower(), "L0")


def should_mask_field(field_name: str, role: str) -> bool:
    """判断当前角色是否应对该字段脱敏。

    Args:
        field_name: 字段名（如 "settlement_amount"）
        role: 当前用户角色（homeowner/designer/contractor/supplier/admin）

    Returns:
        True 表示应对该字段做脱敏处理
    """
    level = get_field_mask_level(field_name)
    if level == "L0":
        return False
    if level == "L3":
        return role != "admin"
    if level == "L2":
        return role not in ("admin", "homeowner")
    # L1: 始终脱敏（PII 已有 pii_masking 处理）
    return True
