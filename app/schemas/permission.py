"""RBAC 权限相关 Pydantic schemas"""

from datetime import datetime

from pydantic import BaseModel, Field


class PermissionResponse(BaseModel):
    """权限定义响应"""
    id: str
    code: str
    name: str
    resource: str
    action: str
    description: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RolePermissionResponse(BaseModel):
    """角色权限关联响应"""
    id: str
    role: str
    permission_code: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RolePermissionsFull(BaseModel):
    """角色完整权限信息"""
    role: str
    permissions: list[str]  # permission code 列表


class UpdateUserRoleRequest(BaseModel):
    """修改用户角色请求"""
    role: str = Field(min_length=1, max_length=30)
    sub_role: str | None = Field(None, max_length=30)


class UpdateUserStatusRequest(BaseModel):
    """修改用户状态请求"""
    is_active: bool


class UpdateRolePermissionsRequest(BaseModel):
    """修改角色权限请求"""
    permission_codes: list[str] = Field(min_length=0, max_length=100)


class PlatformStatsResponse(BaseModel):
    """平台统计数据"""
    total_projects: int = 0
    total_users: int = 0
    active_projects: int = 0
    pending_verifications: int = 0
    total_materials: int = 0
    total_suppliers: int = 0
    weekly_new_users: int = 0
