"""仪表盘聚合 API — 跨项目概览（v1.2.9 Bento Dashboard）

聚合当前用户的项目状态分布、预算汇总，供控制台/移动端 Dashboard 页消费。

项目约定：
- 所有端点校验 get_current_user 身份认证
- 仅返回当前用户拥有的项目数据（owner_id 过滤），避免越权
- 复用 selectinload/聚合查询模式，避免 N+1
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_user
from app.models.user import User
from app.models.project import Project
from app.models.budget import Budget

router = APIRouter(prefix="/dashboard", tags=["仪表盘"])


@router.get(
    "/overview",
    summary="跨项目仪表盘概览",
    description="聚合当前用户的项目状态分布与预算汇总，供 Bento 仪表盘消费。",
    response_description="项目统计 + 预算汇总",
    responses={
        200: {"description": "概览数据"},
        401: {"description": "未登录或 Token 无效"},
    },
)
async def get_dashboard_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    uid = current_user.id
    # admin 口径修复（2026-09-24 生产交叉验证 H-06）：此前恒按 owner_id 过滤，管理员
    # 无自有项目 → 概览项目总数恒 0，与 /api/admin/stats 矛盾，控制台项目维度页面全空。
    # admin 现按全平台口径聚合（与 verify_project_access 放行 admin 的语义对齐）。
    is_admin = current_user.role == "admin"

    # ── 项目状态分布（单次聚合查询）──
    status_stmt = select(Project.status, func.count()).group_by(Project.status)
    if not is_admin:
        status_stmt = status_stmt.where(Project.owner_id == uid)
    status_rows = (await db.execute(status_stmt)).all()
    projects_by_status = {row[0]: row[1] for row in status_rows}
    total_projects = sum(projects_by_status.values())

    # ── 预算汇总（join projects 限定归属，单次聚合）──
    budget_stmt = (
        select(
            func.coalesce(func.sum(Budget.total_estimated), 0.0),
            func.coalesce(func.sum(Budget.total_actual), 0.0),
        )
        .join(Project, Budget.project_id == Project.id)
    )
    if not is_admin:
        budget_stmt = budget_stmt.where(Project.owner_id == uid)
    budget_row = (await db.execute(budget_stmt)).one()
    total_estimated = float(budget_row[0] or 0.0)
    total_actual = float(budget_row[1] or 0.0)

    return {
        "projects": {
            "total": total_projects,
            "draft": projects_by_status.get("draft", 0),
            "in_progress": projects_by_status.get("in_progress", 0),
            "completed": projects_by_status.get("completed", 0),
        },
        "budget": {
            "total_estimated": total_estimated,
            "total_actual": total_actual,
            # 预算执行率 = 实际/预估，预估为 0 时记 0 避免除零
            "utilization": round(total_actual / total_estimated, 2)
            if total_estimated > 0
            else 0.0,
        },
    }
