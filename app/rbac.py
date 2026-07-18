from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.permission import RolePermission
from app.auth import get_current_user


class RoleChecker:
    """基于角色的访问检查（兼容旧接口）"""

    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    async def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in self.allowed_roles:
            if current_user.role == "contractor" and "contractor" in self.allowed_roles:
                return current_user
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"角色 {current_user.role} 无权执行此操作。需要: {', '.join(self.allowed_roles)}",
            )
        return current_user


# 预置角色检查器（兼容旧代码）
allow_homeowner = RoleChecker(["homeowner", "designer", "admin"])
allow_designer = RoleChecker(["designer", "admin"])
allow_admin = RoleChecker(["admin"])
allow_any = RoleChecker(["homeowner", "designer", "contractor", "supplier", "admin"])


class PermissionChecker:
    """基于权限码的细粒度访问检查。

    Usage::
        require_manage_users = PermissionChecker("user:manage")
        @router.get("/users", dependencies=[Depends(require_manage_users)])
    """

    def __init__(self, permission_code: str):
        self.permission_code = permission_code

    async def __call__(
        self,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        # admin 角色拥有所有权限
        if current_user.role == "admin":
            return current_user

        # 查询角色权限表
        result = await db.execute(
            select(RolePermission).where(
                RolePermission.role == current_user.role,
                RolePermission.permission_code == self.permission_code,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"角色 {current_user.role} 无权限执行此操作（需要: {self.permission_code}）",
            )
        return current_user


async def verify_project_access(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    """验证项目访问权限：admin 或项目 owner"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    if current_user.role == "admin":
        return project

    if project.owner_id == current_user.id:
        return project

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="无权访问此项目",
    )


async def verify_project_chat_access(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    """验证项目聊天访问权限：admin/owner/所有认证角色（F40 三方协作）"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    if current_user.role == "admin":
        return project

    if project.owner_id == current_user.id:
        return project

    # F40 三方协作：允许所有认证角色参与项目群聊
    # （homeowner/designer/contractor/supplier）
    return project


# ── 预设权限检查器（按资源 + 操作命名） ──

# 用户管理
require_user_read = PermissionChecker("user:read")
require_user_write = PermissionChecker("user:write")
require_user_manage = PermissionChecker("user:manage")

# 项目管理
require_project_manage = PermissionChecker("project:manage")

# 材料管理
require_material_read = PermissionChecker("material:read")
require_material_write = PermissionChecker("material:write")

# 平台管理
require_platform_manage = PermissionChecker("platform:manage")


# ── 默认权限定义 ──

DEFAULT_PERMISSIONS = [
    # 用户管理
    {"code": "user:read", "name": "查看用户", "resource": "user", "action": "read", "description": "查看用户列表和基本信息"},
    {"code": "user:write", "name": "修改用户", "resource": "user", "action": "write", "description": "修改用户角色和状态"},
    {"code": "user:manage", "name": "管理用户", "resource": "user", "action": "manage", "description": "完全管理用户（含删除）"},

    # 项目管理
    {"code": "project:read", "name": "查看项目", "resource": "project", "action": "read", "description": "查看所有项目"},
    {"code": "project:write", "name": "编辑项目", "resource": "project", "action": "write", "description": "编辑项目信息"},
    {"code": "project:manage", "name": "管理项目", "resource": "project", "action": "manage", "description": "完全管理项目（含删除）"},

    # 材料管理
    {"code": "material:read", "name": "查看材料", "resource": "material", "action": "read", "description": "查看材料库"},
    {"code": "material:write", "name": "编辑材料", "resource": "material", "action": "write", "description": "添加/编辑材料信息"},
    {"code": "material:manage", "name": "管理材料", "resource": "material", "action": "manage", "description": "完全管理材料库"},

    # 预算管理
    {"code": "budget:read", "name": "查看预算", "resource": "budget", "action": "read", "description": "查看项目预算"},
    {"code": "budget:write", "name": "编辑预算", "resource": "budget", "action": "write", "description": "创建/修改预算"},

    # 平台管理
    {"code": "platform:manage", "name": "平台管理", "resource": "platform",
     "action": "manage", "description": "平台统计、配置管理"},
    {"code": "platform:identity_review", "name": "身份认证审核", "resource": "platform",
     "action": "write", "description": "审核用户实名认证"},
    {"code": "platform:points_manage", "name": "积分管理", "resource": "platform",
     "action": "manage", "description": "管理积分规则和手动发放"},
]


# ── 默认角色-权限映射 ──

DEFAULT_ROLE_PERMISSIONS = {
    "admin": [
        # admin 实际不走权限表检查（hard-coded bypass），
        # 但保留映射以便权限列表查询时展示完整信息
        "user:read", "user:write", "user:manage",
        "project:read", "project:write", "project:manage",
        "material:read", "material:write", "material:manage",
        "budget:read", "budget:write",
        "platform:manage", "platform:identity_review", "platform:points_manage",
    ],
    "designer": [
        "project:read", "project:write",
        "material:read",
        "budget:read",
    ],
    "homeowner": [
        "project:read",
        "material:read",
        "budget:read",
    ],
    "contractor": [
        "project:read",
        "material:read",
        "budget:read",
    ],
    "supplier": [
        "project:read",
        "material:read", "material:write",
    ],
}
