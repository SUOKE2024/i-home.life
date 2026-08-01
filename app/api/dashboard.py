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

    # ── 项目状态分布（单次聚合查询）──
    status_rows = (
        await db.execute(
            select(Project.status, func.count())
            .where(Project.owner_id == uid)
            .group_by(Project.status)
        )
    ).all()
    projects_by_status = {row[0]: row[1] for row in status_rows}
    total_projects = sum(projects_by_status.values())

    # ── 预算汇总（join projects 限定当前用户，单次聚合）──
    budget_row = (
        await db.execute(
            select(
                func.coalesce(func.sum(Budget.total_estimated), 0.0),
                func.coalesce(func.sum(Budget.total_actual), 0.0),
            )
            .join(Project, Budget.project_id == Project.id)
            .where(Project.owner_id == uid)
        )
    ).one()
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
