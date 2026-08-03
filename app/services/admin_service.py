"""管理员 Service — 用户管理、权限管理、平台统计"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.user import User
from app.models.project import Project
from app.models.material import Material
from app.models.permission import Permission, RolePermission


# ── 用户管理 ──


async def get_users(
    db: AsyncSession,
    role: str | None = None,
    is_active: bool | None = None,
    is_verified: bool | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[User]:
    stmt = select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)

    if role:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    if is_verified is not None:
        stmt = stmt.where(User.is_verified.is_(is_verified))

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def update_user_role(
    db: AsyncSession,
    user_id: str,
    role: str,
    sub_role: str | None = None,
) -> User | None:
    user = await get_user_by_id(db, user_id)
    if not user:
        return None
    user.role = role
    user.sub_role = sub_role
    await db.commit()
    await db.refresh(user)
    return user


async def update_user_status(
    db: AsyncSession, user_id: str, is_active: bool,
) -> User | None:
    user = await get_user_by_id(db, user_id)
    if not user:
        return None
    user.is_active = is_active
    await db.commit()
    await db.refresh(user)
    return user


# ── 权限管理 ──


async def get_permissions(db: AsyncSession) -> list[Permission]:
    result = await db.execute(
        select(Permission).order_by(Permission.code)
    )
    return list(result.scalars().all())


async def get_role_permissions(
    db: AsyncSession, role: str,
) -> list[RolePermission]:
    result = await db.execute(
        select(RolePermission).where(RolePermission.role == role)
    )
    return list(result.scalars().all())


async def get_role_permission_codes(db: AsyncSession, role: str) -> list[str]:
    perms = await get_role_permissions(db, role)
    return [p.permission_code for p in perms]


async def update_role_permissions(
    db: AsyncSession, role: str, permission_codes: list[str],
) -> list[RolePermission]:
    """替换角色权限 — 先删后建"""
    # 删除现有权限关联
    existing = await get_role_permissions(db, role)
    for rp in existing:
        await db.delete(rp)

    # 批量创建新关联
    new_links: list[RolePermission] = []
    for code in permission_codes:
        link = RolePermission(role=role, permission_code=code)
        db.add(link)
        new_links.append(link)

    await db.commit()
    return new_links


# ── 平台统计 ──


async def get_platform_stats(db: AsyncSession) -> dict:
    """获取平台统计数据"""

    # 总用户数
    total_users_result = await db.execute(
        select(func.count(User.id)).where(User.is_active.is_(True))
    )
    total_users = total_users_result.scalar() or 0

    # 总项目数
    total_projects_result = await db.execute(
        select(func.count(Project.id))
    )
    total_projects = total_projects_result.scalar() or 0

    # 活跃项目数
    active_projects_result = await db.execute(
        select(func.count(Project.id)).where(Project.status == "active")
    )
    active_projects = active_projects_result.scalar() or 0

    # 待验证用户
    pending_verifications_result = await db.execute(
        select(func.count(User.id)).where(
            User.is_active.is_(True),
            User.is_verified.is_(False),
        )
    )
    pending_verifications = pending_verifications_result.scalar() or 0

    # 总物料数
    total_materials_result = await db.execute(
        select(func.count(Material.id)).where(Material.is_active.is_(True))
    )
    total_materials = total_materials_result.scalar() or 0

    # 供应商数
    total_suppliers_result = await db.execute(
        select(func.count(User.id)).where(
            User.is_active.is_(True),
            User.role == "supplier",
        )
    )
    total_suppliers = total_suppliers_result.scalar() or 0

    return {
        "total_projects": total_projects,
        "total_users": total_users,
        "active_projects": active_projects,
        "pending_verifications": pending_verifications,
        "total_materials": total_materials,
        "total_suppliers": total_suppliers,
        "weekly_new_users": 0,  # 占位，后续可实现
    }
