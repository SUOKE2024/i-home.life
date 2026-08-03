"""Agent 工具批准服务 — strict 安全 posture 的状态机管理

借鉴 YC QM strict posture。FC 无状态环境调整为"拒绝-重新触发"模式：
- create_approval：strict 高危工具调用被拦截时创建 pending 记录
- approve/reject：用户决策，仅 pending 可转换
- execute_approved：校验 approved + 未过期 → 调 tool_registry.execute（传 _posture="dangerous" 绕过二次批准）
- expire_outdated：批量过期超 TTL 的 pending

权限：仅本人或 admin 可 approve/reject/execute 自己的 approval。
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.agent_approval import (
    AgentApproval, STATE_PENDING, STATE_APPROVED, STATE_REJECTED,
    STATE_EXPIRED, APPROVAL_DEFAULT_TTL_HOURS,
)

logger = logging.getLogger(__name__)


def _ensure_aware(dt: datetime) -> datetime:
    """SQLite 存储的 datetime 无 tzinfo，统一转为 UTC-aware 再比较。

    对齐 agent_session_service._purge_expired_sessions 的兼容方案。
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _gen_approval_id() -> str:
    return f"apr_{uuid.uuid4().hex[:12]}"


async def create_approval(
    db: AsyncSession,
    user_id: str,
    agent_name: str,
    tool_name: str,
    arguments: dict,
    project_id: str | None = None,
    scope: str = "personal",
    trace_id: str | None = None,
) -> AgentApproval:
    """创建一条 pending 批准请求。"""
    settings = get_settings()
    ttl_hours = settings.agent_approval_ttl_hours or APPROVAL_DEFAULT_TTL_HOURS
    approval = AgentApproval(
        id=str(uuid.uuid4()),
        approval_id=_gen_approval_id(),
        user_id=user_id,
        agent_name=agent_name,
        tool_name=tool_name,
        arguments=json.dumps(arguments, ensure_ascii=False),
        project_id=project_id,
        scope=scope,
        trace_id=trace_id,
        state=STATE_PENDING,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
    )
    db.add(approval)
    await db.commit()
    await db.refresh(approval)
    return approval


async def get_approval(
    db: AsyncSession, approval_id: str, user_id: str,
) -> AgentApproval | None:
    """获取单条批准请求（权限校验：仅本人，admin 由调用方额外判断）。"""
    stmt = select(AgentApproval).where(
        AgentApproval.approval_id == approval_id,
        AgentApproval.user_id == user_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_pending(
    db: AsyncSession, user_id: str, limit: int = 50,
) -> list[AgentApproval]:
    """列出用户的 pending 批准请求。"""
    stmt = (
        select(AgentApproval)
        .where(AgentApproval.user_id == user_id, AgentApproval.state == STATE_PENDING)
        .order_by(AgentApproval.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def approve(
    db: AsyncSession, approval_id: str, decided_by: str, reason: str | None = None,
) -> AgentApproval | None:
    """批准请求（仅 pending 可批准）。返回 None 表示状态不允许或不存在。"""
    stmt = select(AgentApproval).where(AgentApproval.approval_id == approval_id)
    result = await db.execute(stmt)
    approval = result.scalar_one_or_none()
    if approval is None or approval.state != STATE_PENDING:
        return None
    approval.state = STATE_APPROVED
    approval.decided_by = decided_by
    approval.decided_at = datetime.now(timezone.utc)
    approval.decision_reason = reason
    await db.commit()
    await db.refresh(approval)
    return approval


async def reject(
    db: AsyncSession, approval_id: str, decided_by: str, reason: str | None = None,
) -> AgentApproval | None:
    """拒绝请求（仅 pending 可拒绝）。"""
    stmt = select(AgentApproval).where(AgentApproval.approval_id == approval_id)
    result = await db.execute(stmt)
    approval = result.scalar_one_or_none()
    if approval is None or approval.state != STATE_PENDING:
        return None
    approval.state = STATE_REJECTED
    approval.decided_by = decided_by
    approval.decided_at = datetime.now(timezone.utc)
    approval.decision_reason = reason
    await db.commit()
    await db.refresh(approval)
    return approval


async def execute_approved(
    db: AsyncSession, approval_id: str, user_id: str,
) -> dict:
    """执行已批准的工具调用。

    校验：state=approved + 未过期 + user_id 匹配。
    执行：调 tool_registry.execute，传 _posture="dangerous" 绕过二次批准。

    Returns:
        {"executed": bool, "result": ..., "error": ...}
    """
    approval = await get_approval(db, approval_id, user_id)
    if approval is None:
        return {"executed": False, "error": "批准请求不存在或无权访问"}
    if approval.state != STATE_APPROVED:
        return {"executed": False, "error": f"状态非 approved（当前 {approval.state}）"}
    if datetime.now(timezone.utc) > _ensure_aware(approval.expires_at):
        approval.state = STATE_EXPIRED
        await db.commit()
        return {"executed": False, "error": "批准已过期"}

    # 解析参数并执行
    try:
        arguments = json.loads(approval.arguments) if approval.arguments else {}
    except json.JSONDecodeError:
        arguments = {}

    from app.services.agent_tool_registry import tool_registry
    try:
        result = await tool_registry.execute(
            approval.tool_name, arguments,
            _db=db, _project_id=approval.project_id or "",
            _user_id=approval.user_id,
            _scope=approval.scope,
            _trace_id=approval.trace_id or "",
            _posture="dangerous",  # 绕过二次批准
        )
        return {"executed": True, "result": result}
    except Exception as e:
        logger.error("approval_execute_failed: %s", e)
        return {"executed": False, "error": f"执行失败：{e}"}


async def expire_outdated(db: AsyncSession) -> int:
    """批量过期超 TTL 的 pending 请求。返回过期数量。"""
    # SQLite 存储 naive datetime，用 naive UTC 比较（对齐 ar_scan_service 等既有模式）
    # synchronize_session=False 避免 ORM 在 Python 侧 eval WHERE（aware/naive 冲突）
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    stmt = (
        update(AgentApproval)
        .where(AgentApproval.state == STATE_PENDING, AgentApproval.expires_at < now)
        .values(state=STATE_EXPIRED)
        .execution_options(synchronize_session=False)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount or 0
