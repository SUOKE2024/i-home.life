"""管理后台 API — RBAC 用户管理、角色权限、平台统计"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.user import User
from app.models.permission import Permission, RolePermission
from app.models.project import Project
from app.models.material import Material
from app.models.procurement import Supplier
from app.models.identity_verification import IdentityVerification
from app.auth import get_current_user
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
    RolePermissionResponse,
    RolePermissionsFull,
    UpdateUserRoleRequest,
    UpdateUserStatusRequest,
    UpdateRolePermissionsRequest,
    PlatformStatsResponse,
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
    stmt = select(User)
    if role:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(stmt)
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(require_user_read),
    db: AsyncSession = Depends(get_db),
):
    """管理员查看单个用户详情"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
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

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    if user.id == current_user.id and data.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能修改自己的角色",
        )

    user.role = data.role
    user.sub_role = data.sub_role
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.put("/users/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: str,
    data: UpdateUserStatusRequest,
    current_user: User = Depends(require_user_manage),
    db: AsyncSession = Depends(get_db),
):
    """管理员启用/禁用用户"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能禁用自己的账户",
        )

    user.is_active = data.is_active
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


# ── 权限管理 ──


@router.get("/permissions", response_model=list[PermissionResponse])
async def list_permissions(
    resource: str | None = Query(None, description="按资源类型筛选"),
    current_user: User = Depends(allow_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理员查看所有权限定义"""
    stmt = select(Permission)
    if resource:
        stmt = stmt.where(Permission.resource == resource)
    stmt = stmt.order_by(Permission.resource, Permission.action)
    result = await db.execute(stmt)
    permissions = result.scalars().all()
    return [PermissionResponse.model_validate(p) for p in permissions]


@router.get("/roles/{role}/permissions", response_model=RolePermissionsFull)
async def get_role_permissions(
    role: str,
    current_user: User = Depends(allow_admin),
    db: AsyncSession = Depends(get_db),
):
    """查看某个角色的权限列表"""
    result = await db.execute(
        select(RolePermission).where(RolePermission.role == role)
    )
    mappings = result.scalars().all()
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

    # 删除旧权限
    await db.execute(
        select(RolePermission).where(RolePermission.role == role)
    )
    old = (await db.execute(
        select(RolePermission).where(RolePermission.role == role)
    )).scalars().all()
    for m in old:
        await db.delete(m)

    # 插入新权限
    for code in data.permission_codes:
        db.add(RolePermission(role=role, permission_code=code))

    await db.commit()

    return RolePermissionsFull(role=role, permissions=data.permission_codes)


# ── 平台统计 ──


@router.get("/stats", response_model=PlatformStatsResponse)
async def get_platform_stats(
    current_user: User = Depends(require_platform_manage),
    db: AsyncSession = Depends(get_db),
):
    """管理员查看平台统计数据"""
    # 总项目数
    result = await db.execute(select(func.count()).select_from(Project))
    total_projects = result.scalar() or 0

    # 活跃项目数
    result = await db.execute(
        select(func.count()).select_from(Project).where(
            Project.status.in_(["active", "in_progress", "construction"])
        )
    )
    active_projects = result.scalar() or 0

    # 总用户数
    result = await db.execute(select(func.count()).select_from(User))
    total_users = result.scalar() or 0

    # 待审核认证数
    result = await db.execute(
        select(func.count()).select_from(IdentityVerification).where(
            IdentityVerification.status == "pending"
        )
    )
    pending_verifications = result.scalar() or 0

    # 材料 SKU 数
    result = await db.execute(select(func.count()).select_from(Material))
    total_materials = result.scalar() or 0

    # 供应商数
    result = await db.execute(select(func.count()).select_from(Supplier))
    total_suppliers = result.scalar() or 0

    # 本周新增用户（近 7 天）
    from datetime import datetime, timedelta
    week_ago = datetime.utcnow() - timedelta(days=7)
    result = await db.execute(
        select(func.count()).select_from(User).where(User.created_at >= week_ago)
    )
    weekly_new_users = result.scalar() or 0

    return PlatformStatsResponse(
        total_projects=total_projects,
        total_users=total_users,
        active_projects=active_projects,
        pending_verifications=pending_verifications,
        total_materials=total_materials,
        total_suppliers=total_suppliers,
        weekly_new_users=weekly_new_users,
    )
