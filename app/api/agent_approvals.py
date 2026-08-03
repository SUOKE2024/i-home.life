"""Agent 工具批准管理 API — strict 安全 posture 的人工批准端点

端点（前缀 /agents/approvals）：
  GET    /api/agents/approvals              列出当前用户 pending 批准请求
  GET    /api/agents/approvals/{id}         获取单条批准请求
  POST   /api/agents/approvals/{id}/approve 批准（仅本人或 admin）
  POST   /api/agents/approvals/{id}/reject  拒绝
  POST   /api/agents/approvals/{id}/execute 批准后执行工具

借鉴 YC QM strict posture。所有操作强制 user_id 隔离。
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.services import agent_approval_service

router = APIRouter(prefix="/agents/approvals", tags=["AI Agent 安全批准"])


class ApprovalDecisionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class ApprovalItemResponse(BaseModel):
    id: str
    approval_id: str
    user_id: str
    agent_name: str
    tool_name: str
    arguments: dict
    project_id: str | None = None
    scope: str = "personal"
    trace_id: str | None = None
    state: str
    decided_by: str | None = None
    decided_at: str | None = None
    decision_reason: str | None = None
    expires_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ApprovalListResponse(BaseModel):
    count: int
    items: list[ApprovalItemResponse]


class ApprovalExecuteResponse(BaseModel):
    executed: bool
    result: dict | None = None
    error: str | None = None


def _serialize(a) -> ApprovalItemResponse:
    import json as _json
    return ApprovalItemResponse(
        id=a.id,
        approval_id=a.approval_id,
        user_id=a.user_id,
        agent_name=a.agent_name,
        tool_name=a.tool_name,
        arguments=_json.loads(a.arguments) if a.arguments else {},
        project_id=a.project_id,
        scope=a.scope,
        trace_id=a.trace_id,
        state=a.state,
        decided_by=a.decided_by,
        decided_at=a.decided_at.isoformat() if a.decided_at else None,
        decision_reason=a.decision_reason,
        expires_at=a.expires_at.isoformat() if a.expires_at else None,
        created_at=a.created_at.isoformat() if a.created_at else None,
        updated_at=a.updated_at.isoformat() if a.updated_at else None,
    )


@router.get("", response_model=ApprovalListResponse)
async def list_pending_approvals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户的 pending 批准请求。"""
    rows = await agent_approval_service.list_pending(db, current_user.id)
    items = [_serialize(a) for a in rows]
    return ApprovalListResponse(count=len(items), items=items)


@router.get("/{approval_id}", response_model=ApprovalItemResponse)
async def get_approval(
    approval_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取单条批准请求（仅本人）。"""
    a = await agent_approval_service.get_approval(db, approval_id, current_user.id)
    if a is None:
        raise HTTPException(status_code=404, detail="批准请求不存在或无权访问")
    return _serialize(a)


@router.post("/{approval_id}/approve", response_model=ApprovalItemResponse)
async def approve_request(
    approval_id: str,
    payload: ApprovalDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """批准请求（仅本人或 admin）。仅 pending 可批准。"""
    # 先校验所有权
    existing = await agent_approval_service.get_approval(db, approval_id, current_user.id)
    if existing is None and current_user.role != "admin":
        raise HTTPException(status_code=404, detail="批准请求不存在或无权访问")
    a = await agent_approval_service.approve(
        db, approval_id, current_user.id, reason=payload.reason,
    )
    if a is None:
        raise HTTPException(status_code=409, detail="请求不存在或状态非 pending")
    return _serialize(a)


@router.post("/{approval_id}/reject", response_model=ApprovalItemResponse)
async def reject_request(
    approval_id: str,
    payload: ApprovalDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """拒绝请求（仅本人或 admin）。仅 pending 可拒绝。"""
    existing = await agent_approval_service.get_approval(db, approval_id, current_user.id)
    if existing is None and current_user.role != "admin":
        raise HTTPException(status_code=404, detail="批准请求不存在或无权访问")
    a = await agent_approval_service.reject(
        db, approval_id, current_user.id, reason=payload.reason,
    )
    if a is None:
        raise HTTPException(status_code=409, detail="请求不存在或状态非 pending")
    return _serialize(a)


@router.post("/{approval_id}/execute", response_model=ApprovalExecuteResponse)
async def execute_approved(
    approval_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """执行已批准的工具调用（校验 approved + 未过期）。"""
    result = await agent_approval_service.execute_approved(
        db, approval_id, current_user.id,
    )
    if not result["executed"]:
        # 状态错误返回 409，执行失败返回 500
        err = result.get("error") or ""
        if "状态" in err or "过期" in err or "不存在" in err:
            raise HTTPException(status_code=409, detail=result["error"])
        raise HTTPException(status_code=500, detail=result["error"])
    return ApprovalExecuteResponse(
        executed=True, result=result.get("result"), error=None,
    )
