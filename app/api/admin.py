"""管理后台 API — RBAC 用户管理、角色权限、平台统计"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.permission import Permission
from app.models.audit_log import AuditLog
from app.rbac import (
    allow_admin,
    require_user_read,
    require_user_write,
    require_platform_manage,
    require_user_manage,
)
from app.schemas.user import UserResponse
from app.schemas.permission import (
    PermissionResponse,
    RolePermissionsFull,
    UpdateUserRoleRequest,
    UpdateUserStatusRequest,
    UpdateRolePermissionsRequest,
    PlatformStatsResponse,
)
from app.services.admin_service import (
    get_users,
    get_user_by_id,
    update_user_role as _svc_update_user_role,
    update_user_status as _svc_update_user_status,
    get_permissions,
    get_role_permissions as _svc_get_role_permissions,
    update_role_permissions as _svc_update_role_permissions,
    get_platform_stats as _svc_get_platform_stats,
)

router = APIRouter(prefix="/admin", tags=["管理后台"])


# ── 用户管理 ──


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    role: str | None = Query(None, description="按角色筛选"),
    is_active: bool | None = Query(None, description="按激活状态筛选"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_user_read),
    db: AsyncSession = Depends(get_db),
):
    """管理员查看用户列表（支持角色/状态筛选 + 分页）"""
    users = await get_users(db, role=role, is_active=is_active, skip=offset, limit=limit)
    return [UserResponse.model_validate(u) for u in users]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(require_user_read),
    db: AsyncSession = Depends(get_db),
):
    """管理员查看单个用户详情"""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return UserResponse.model_validate(user)


@router.put("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: str,
    data: UpdateUserRoleRequest,
    current_user: User = Depends(require_user_write),
    db: AsyncSession = Depends(get_db),
):
    """管理员修改用户角色"""
    valid_roles = {"homeowner", "designer", "contractor", "supplier", "admin"}
    if data.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效角色。有效角色: {', '.join(valid_roles)}",
        )

    # 防止权限提升：只有 admin 可以将用户提升为 admin 角色
    if data.role == "admin" and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权将用户提升为管理员角色",
        )

    # 防止修改自己的角色
    if user_id == current_user.id and data.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能修改自己的角色",
        )

    user = await _svc_update_user_role(db, user_id, data.role, data.sub_role)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    return UserResponse.model_validate(user)


@router.put("/users/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: str,
    data: UpdateUserStatusRequest,
    current_user: User = Depends(require_user_manage),
    db: AsyncSession = Depends(get_db),
):
    """管理员启用/禁用用户"""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能禁用自己的账户",
        )

    user = await _svc_update_user_status(db, user_id, data.is_active)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    # 性能优化（v1.1.12）：禁用/启用用户后清除用户缓存
    from app.auth import invalidate_user_cache
    invalidate_user_cache(user.id)
    return UserResponse.model_validate(user)


# ── 权限管理 ──


@router.get("/permissions", response_model=list[PermissionResponse])
async def list_permissions(
    resource: str | None = Query(None, description="按资源类型筛选"),
    current_user: User = Depends(allow_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理员查看所有权限定义"""
    permissions = await get_permissions(db)
    if resource:
        permissions = [p for p in permissions if p.resource == resource]
    return [PermissionResponse.model_validate(p) for p in permissions]


@router.get("/roles/{role}/permissions", response_model=RolePermissionsFull)
async def get_role_permissions(
    role: str,
    current_user: User = Depends(allow_admin),
    db: AsyncSession = Depends(get_db),
):
    """查看某个角色的权限列表"""
    mappings = await _svc_get_role_permissions(db, role)
    return RolePermissionsFull(
        role=role,
        permissions=[m.permission_code for m in mappings],
    )


@router.put("/roles/{role}/permissions", response_model=RolePermissionsFull)
async def update_role_permissions(
    role: str,
    data: UpdateRolePermissionsRequest,
    current_user: User = Depends(allow_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理员修改某个角色的权限（全量替换）"""
    valid_roles = {"homeowner", "designer", "contractor", "supplier", "admin"}
    if role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效角色。有效角色: {', '.join(valid_roles)}",
        )

    # 验证所有 permission_code 存在
    if data.permission_codes:
        result = await db.execute(
            select(Permission).where(Permission.code.in_(data.permission_codes))
        )
        existing_codes = {p.code for p in result.scalars().all()}
        invalid_codes = set(data.permission_codes) - existing_codes
        if invalid_codes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效权限码: {', '.join(invalid_codes)}",
            )

    await _svc_update_role_permissions(db, role, data.permission_codes)

    return RolePermissionsFull(role=role, permissions=data.permission_codes)


# ── 平台统计 ──


@router.get("/stats", response_model=PlatformStatsResponse)
async def get_platform_stats(
    current_user: User = Depends(require_platform_manage),
    db: AsyncSession = Depends(get_db),
):
    """管理员查看平台统计数据"""
    stats = await _svc_get_platform_stats(db)
    return PlatformStatsResponse(**stats)


# ── 审计日志 ──


@router.get("/audit-logs")
async def list_audit_logs(
    user_id: str | None = Query(None, description="按操作者 user_id 筛选"),
    action: str | None = Query(None, description="按操作类型筛选（CREATE/UPDATE/DELETE/LOGIN 等）"),
    resource_type: str | None = Query(None, description="按资源类型筛选"),
    start_date: datetime | None = Query(None, description="起始时间（ISO 8601，含）"),
    end_date: datetime | None = Query(None, description="结束时间（ISO 8601，含）"),
    skip: int = Query(default=0, ge=0, description="分页偏移量"),
    limit: int = Query(default=50, ge=1, le=200, description="每页数量，最大 200"),
    current_user: User = Depends(allow_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """管理员查询审计日志（支持过滤 + 分页）。

    需 admin 角色。返回 `{"items": [...], "total": N, "skip": ..., "limit": ...}`。
    """
    stmt = select(AuditLog)
    count_stmt = select(AuditLog.id)

    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
        count_stmt = count_stmt.where(AuditLog.user_id == user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
        count_stmt = count_stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
        count_stmt = count_stmt.where(AuditLog.resource_type == resource_type)
    if start_date:
        stmt = stmt.where(AuditLog.created_at >= start_date)
        count_stmt = count_stmt.where(AuditLog.created_at >= start_date)
    if end_date:
        stmt = stmt.where(AuditLog.created_at <= end_date)
        count_stmt = count_stmt.where(AuditLog.created_at <= end_date)

    # 总数
    from sqlalchemy import func as sa_func
    total_result = await db.execute(select(sa_func.count()).select_from(count_stmt.subquery()))
    total = total_result.scalar() or 0

    # 分页查询
    stmt = stmt.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    items = result.scalars().all()

    return {
        "items": [
            {
                "id": item.id,
                "user_id": item.user_id,
                "action": item.action,
                "resource_type": item.resource_type,
                "resource_id": item.resource_id,
                "details": item.details,
                "request_ip": item.request_ip,
                "user_agent": item.user_agent,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in items
        ],
        "total": total,
        "skip": skip,
        "limit": limit,
    }
