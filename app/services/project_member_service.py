"""项目成员服务 —— F40 三方协作的显式授权（2026-09-24 交叉验证 C-01 修复）

背景见 ``app/models/project_member.py`` 与 ``app/rbac.py:verify_project_collaborator_access``。
本模块只负责成员关系的增删查与前置换校验；访问权判定在 rbac 层。
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project_member import MEMBER_ROLES, ProjectMember
from app.models.user import User


class ProjectMemberError(Exception):
    """项目成员操作前置校验失败（由 API 层映射为 4xx）。"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


async def list_members(db: AsyncSession, project_id: str) -> list[ProjectMember]:
    """列出项目全部协作成员（不含 owner / admin —— 二者由角色与 owner_id 判定）。"""
    result = await db.execute(
        select(ProjectMember)
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.created_at.asc())
    )
    return list(result.scalars().all())


async def get_member(db: AsyncSession, project_id: str, user_id: str) -> ProjectMember | None:
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def add_member(db: AsyncSession, project_id: str, user_id: str, role: str) -> ProjectMember:
    """添加（或更新角色）项目成员。

    前置校验：目标用户须存在、角色须为协作角色、且不与 owner 重复。
    同 (project_id, user_id) 已存在时**更新 role**（符合 uq_project_member_project_user
    「一人一条」的设计，避免唯一约束冲突）。
    """
    if role not in MEMBER_ROLES:
        raise ProjectMemberError(
            f"role 非法：{role}，合法值为 {'/'.join(MEMBER_ROLES)}"
        )

    target = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not target:
        raise ProjectMemberError(f"用户不存在：{user_id}")
    if target.role == "admin":
        raise ProjectMemberError("admin 无需加入项目成员（已由角色直通项目访问）")
    if target.role not in MEMBER_ROLES:
        raise ProjectMemberError(
            f"用户角色为 {target.role}，不是协作角色（需为 {'/'.join(MEMBER_ROLES)}）"
        )

    existing = await get_member(db, project_id, user_id)
    if existing:
        existing.role = role
        await db.commit()
        await db.refresh(existing)
        return existing

    member = ProjectMember(project_id=project_id, user_id=user_id, role=role)
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


async def remove_member(db: AsyncSession, project_id: str, user_id: str) -> bool:
    """移除项目成员；不存在返回 False（供 API 区分 404）。"""
    member = await get_member(db, project_id, user_id)
    if not member:
        return False
    await db.delete(member)
    await db.commit()
    return True
