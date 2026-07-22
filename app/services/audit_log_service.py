"""审计日志服务 — 记录敏感操作

设计原则：
1. 永不阻断主流程：写入失败仅记录错误日志，不向上抛出
2. 受 audit_log_enabled 开关控制：关闭时直接跳过
3. 使用独立事务（savepoint）防止主事务回滚影响审计记录
4. details 字段使用 JSON 存储任意上下文（注意脱敏 PII）

典型用法::

    @router.post("/login")
    async def login(request: Request, db: AsyncSession = Depends(get_db)):
        # ... 业务逻辑 ...
        await log_audit_event(
            db=db,
            user_id=user.id,
            action="LOGIN",
            resource_type="user",
            resource_id=user.id,
            details={"role": user.role},
            request_ip=request.client.host if request.client else "",
            user_agent=request.headers.get("user-agent"),
        )
"""

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.audit_log import AuditLog

logger = structlog.get_logger("ihome")

settings = get_settings()


# 审计动作枚举（用于校验和文档化）
AUDIT_ACTIONS = frozenset(
    {
        "CREATE",
        "UPDATE",
        "DELETE",
        "LOGIN",
        "LOGOUT",
        "EXPORT",
        "PERMISSION_CHANGE",
        # 扩展动作（非枚举但允许）
        "REGISTER",
    }
)


async def log_audit_event(
    db: AsyncSession,
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
    request_ip: str = "",
    user_agent: str | None = None,
) -> AuditLog | None:
    """记录一条审计日志。

    安全保证：
    - audit_log_enabled=False 时立即返回 None，不写库
    - 任何异常都被捕获并记录错误日志，不会抛出
    - 使用 savepoint 隔离写入，避免影响主事务
    - v1.1.28: details 字段经 PII 脱敏（借鉴索克生活 pii_masking），
      自动屏蔽手机号/身份证/邮箱/银行卡等 8 类 PII

    Args:
        db: 当前请求的 AsyncSession
        user_id: 操作者用户 ID（必填）
        action: 操作类型，建议取自 AUDIT_ACTIONS 枚举
        resource_type: 资源类型（如 user/project/payment）
        resource_id: 资源 ID（可选，登录类操作可为空）
        details: 任意 JSON 上下文，写入前自动 PII 脱敏
        request_ip: 客户端 IP
        user_agent: 客户端 User-Agent

    Returns:
        成功写入返回 AuditLog 对象，跳过或失败返回 None
    """
    try:
        if not settings.audit_log_enabled:
            return None

        # v1.1.28: PII 全量脱敏（借鉴索克生活 pii_masking）
        masked_details = details
        if settings.pii_masking_enabled and details:
            try:
                from app.utils.pii_masking import mask_dict
                masked_details = mask_dict(details)
            except Exception:
                masked_details = details  # 脱敏失败用原文，不阻断审计写入

        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=masked_details,
            request_ip=request_ip or "",
            user_agent=user_agent,
        )
        db.add(entry)
        await db.flush()
        return entry
    except Exception as exc:
        # 关键：审计日志失败绝不阻断主流程
        logger.error(
            "audit_log_write_failed",
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            error=str(exc),
            exc_info=True,
        )
        return None
