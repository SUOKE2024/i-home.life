from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.auth import get_current_user


class RoleChecker:
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    async def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        # 子角色检查：如果 primary_role 不在列表中，检查是否 contractor 子角色
        if current_user.role not in self.allowed_roles:
            if current_user.role == "contractor" and "contractor" in self.allowed_roles:
                return current_user
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"角色 {current_user.role} 无权执行此操作。需要: {', '.join(self.allowed_roles)}",
            )
        return current_user


# 所有角色可访问（包括工种子角色）
allow_homeowner = RoleChecker(["homeowner", "designer", "admin"])
allow_designer = RoleChecker(["designer", "admin"])
allow_admin = RoleChecker(["admin"])
# 允许所有已认证用户（用于开放项目发布等）
allow_any = RoleChecker(["homeowner", "designer", "contractor", "supplier", "admin"])


async def verify_project_access(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
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
