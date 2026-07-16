"""RBAC 权限模型 — 细粒度权限控制"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Permission(Base):
    """权限定义表"""
    __tablename__ = "permissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    # 权限编码，如 "user:read"、"user:write"、"project:delete"、"material:create"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    resource: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # 资源类型: user, project, material, budget, procurement, construction, settlement, platform
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    # 操作类型: read, create, update, delete, manage
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RolePermission(Base):
    """角色-权限关联表"""
    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role", "permission_code", name="uq_role_permission"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    role: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # homeowner / designer / contractor / supplier / admin
    permission_code: Mapped[str] = mapped_column(String(100), ForeignKey("permissions.code"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    permission = relationship("Permission")
