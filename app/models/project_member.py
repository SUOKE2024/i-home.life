import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# 协作角色单源：与 rbac.verify_project_collaborator_access 的放行集合逐字一致。
# 改此处必须同步 rbac.py（两处不一致会导致「能加成员但校验不认」或反之）。
MEMBER_ROLES = ("designer", "contractor", "supplier")


class ProjectMember(Base):
    """项目成员 —— F40 三方协作的显式授权载体

    背景（2026-09-24 生产交叉验证 C-01，Critical）：
      ``verify_project_collaborator_access`` 此前只校验「角色属于 designer/contractor/
      supplier」就放行，**完全不校验该用户与该项目是否存在成员关系**，导致任何协作角色
      可读取全平台任意项目数据（实测供应商读业主项目 feed，泄漏 budget_breakdown 逐项
      单价与 settlement_summary 结算金额）。根因是 F40 三方协作的授权前提
      「协作方被指派到具体项目」在数据层从未落地——全库存无「用户 ↔ 项目」关系实体。

    本表即该关系的落地：协作类端点（feed / chat / files / floorplans /
    construction_drawing / construction_snapshot / hard_decoration / gaussian_recon /
    vr_panorama 共 9 个模块）据此判定访问权。

    role 仅限协作角色，不含 owner / admin —— 后者由 ``projects.owner_id`` 与
    ``users.role`` 直接判定，在此冗余存储会造成两处真相（改 owner 需同步改成员表）。
    """

    __tablename__ = "project_members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    # 该用户在项目中的协作角色（designer / contractor / supplier）
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project")
    user = relationship("User")

    __table_args__ = (
        # 同一用户在同一项目内只保留一条成员记录（角色调整走 UPDATE，不新增行）
        UniqueConstraint("project_id", "user_id", name="uq_project_member_project_user"),
        CheckConstraint(
            "role IN ('designer', 'contractor', 'supplier')",
            name="chk_project_member_role",
        ),
    )
