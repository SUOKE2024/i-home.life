"""MCP Enterprise 扩展（对齐 MCP 2026 Roadmap — Enterprise Readiness）

MCP 2026 Roadmap（2026-03-05）将 Enterprise Readiness 列为四大优先方向之一，
以轻量扩展形式输出：审计轨迹、SSO 集成、网关模式（gateway patterns）。

本扩展将索克已有的企业级能力以 MCP 扩展形式暴露，供企业客户端/网关发现与消费：
- enterprise/status : 企业级能力声明（审计 / SSO / 网关就绪状态）
- enterprise/audit  : 审计轨迹查询（追溯最近审计日志，HMAC 完整性由 audit_integrity 保证）

能力映射（复用既有实现，不重复造轮子）：
- 审计轨迹 : app/services/audit_log_service（audit_log_enabled + audit_hmac_enabled）
- SSO     : WebAuthn / Passkey（app/services/webauthn_service）+ PASETO 会话
- 网关     : stateless 核心 + Nginx round-robin（MCP 2026-07-28 stateless 支持水平扩缩容）

与 A2A 保持一致：扩展方法经 POST /api/mcp JSON-RPC 分发，纯 deserialize 无副作用（audit 为只读查询）。
"""

from typing import Any

from sqlalchemy import select

from app.config import get_settings
from app.mcp.extensions import Extension
from app.models.audit_log import AuditLog

VERSION = "1.0.0"


class EnterpriseExtension(Extension):
    """MCP Enterprise 扩展 —— 企业级就绪能力声明与审计轨迹查询"""

    NAME = "enterprise"
    VERSION = VERSION

    async def dispatch(
        self,
        method: str,
        params: dict | None = None,
        db: Any = None,
    ) -> tuple[dict | None, dict | None]:
        params = params or {}
        if method == "enterprise/status":
            return self.status(), None
        if method == "enterprise/audit":
            return await self.audit(params, db)
        return None, {"code": -32601, "message": f"Enterprise 方法不存在: {method}"}

    def status(self) -> dict:
        """企业级能力声明（纯元数据，无副作用）"""
        settings = get_settings()
        return {
            "extension": self.NAME,
            "version": self.VERSION,
            "enterprise_readiness": {
                "audit": {
                    "enabled": settings.audit_log_enabled,
                    "hmac_integrity": settings.audit_hmac_enabled,
                    "description": "敏感操作审计轨迹，HMAC-SHA256 防篡改签名",
                },
                "sso": {
                    "webauthn": True,  # WebAuthn / Passkey 已实现
                    "session": "paseto_v4_local",  # 禁 JWT，PASETO v4.local
                    "description": "WebAuthn/Passkey + PASETO 会话",
                },
                "gateway": {
                    "stateless": True,  # MCP 2026-07-28 stateless 核心
                    "load_balancing": "round_robin",
                    "description": "无会话状态，支持 Nginx round-robin 水平扩缩容",
                },
            },
        }

    async def audit(self, params: dict, db: Any) -> tuple[dict | None, dict | None]:
        """审计轨迹查询（只读，追溯到最近 N 条审计日志）

        需 db session（由 API 层注入）。未提供 db 时返回不可用错误。
        """
        limit = min(int(params.get("limit", 20) or 20), 100)  # 上限 100 防滥用
        action = params.get("action")
        if db is None:
            return None, {"code": -32602, "message": "Enterprise/audit 需要数据库会话"}
        try:
            stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
            if action:
                stmt = stmt.where(AuditLog.action == action)
            rows = (await db.execute(stmt)).scalars().all()
            return {
                "count": len(rows),
                "entries": [
                    {
                        "id": r.id,
                        "user_id": r.user_id,
                        "action": r.action,
                        "resource_type": r.resource_type,
                        "resource_id": r.resource_id,
                        "request_ip": r.request_ip,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in rows
                ],
            }, None
        except Exception as exc:  # noqa: BLE001 — 查询失败返回可读错误
            return None, {"code": -32603, "message": f"审计查询失败: {exc}"}