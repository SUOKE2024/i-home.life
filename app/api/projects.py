from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectListResponse,
    AcceptanceRequest,
)
from app.auth import get_current_user
from app.rbac import verify_project_access
from app.services.project_service import (
    get_user_projects,
    get_project,
    create_project,
    update_project,
    update_project_phase,
    delete_project,
    ProjectStateError,
    ProjectPhaseError,
)
from app.ws import ws_manager

import asyncio  # v1.2.1: 并行查询优化
import structlog

router = APIRouter(prefix="/projects", tags=["项目管理"])

_ws_logger = structlog.get_logger("ws")


@router.get(
    "",
    response_model=list[ProjectListResponse],
    summary="获取项目列表",
    description="获取当前登录用户创建的所有装修项目列表。",
    response_description="项目列表",
    responses={
        200: {"description": "获取成功"},
        401: {"description": "未登录或 Token 无效"},
    },
)
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    projects = await get_user_projects(db, current_user.id)
    return [ProjectListResponse.model_validate(p) for p in projects]


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="获取项目详情",
    description="根据项目 ID 获取单个装修项目的详细信息。",
    response_description="项目详情",
    responses={
        200: {"description": "获取成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "项目不存在"},
    },
)
async def get_project_detail(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    return ProjectResponse.model_validate(project)


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建项目",
    description="创建一个新的装修项目，包含项目名称、地址、面积等基本信息。",
    response_description="创建成功，返回项目详情",
    responses={
        201: {"description": "创建成功"},
        400: {"description": "请求参数无效"},
        401: {"description": "未登录或 Token 无效"},
    },
)
async def create_project_handler(
    data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await create_project(db, current_user.id, data)
    resp = ProjectResponse.model_validate(project)
    try:
        await ws_manager.broadcast_to_project(project.id, "project.created", resp.model_dump())
    except Exception:
        _ws_logger.warning("project.created broadcast failed", project_id=project.id, exc_info=True)
    return resp


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="更新项目",
    description="根据项目 ID 更新装修项目的部分信息，只更新提交的字段。",
    response_description="更新成功，返回项目详情",
    responses={
        200: {"description": "更新成功"},
        400: {"description": "请求参数无效"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权修改该项目"},
        404: {"description": "项目不存在"},
    },
)
async def update_project_handler(
    project_id: str,
    data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)

    try:
        updated = await update_project(db, project_id, data)
    except (ProjectStateError, ProjectPhaseError) as e:
        # 状态机校验失败 → 409 Conflict（修复断裂 2：原 PATCH 直绕校验）
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"reason": type(e).__name__, "message": str(e)},
        )
    resp = ProjectResponse.model_validate(updated)
    try:
        await ws_manager.broadcast_to_project(project_id, "project.updated", resp.model_dump())
    except Exception:
        _ws_logger.warning("project.updated broadcast failed", project_id=project_id, exc_info=True)
    return resp


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除项目",
    description="根据项目 ID 删除装修项目及其关联的所有数据。",
    response_description="删除成功，无返回内容",
    responses={
        204: {"description": "删除成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权删除该项目"},
        404: {"description": "项目不存在"},
    },
)
async def delete_project_handler(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)

    await delete_project(db, project_id)
    try:
        await ws_manager.broadcast_to_project(project_id, "project.deleted", {"id": project_id})
    except Exception:
        _ws_logger.warning("project.deleted broadcast failed", project_id=project_id, exc_info=True)


# ── 全链路装修阶段进度 ──

@router.get(
    "/{project_id}/timeline",
    summary="获取项目全链路阶段进度",
    description="返回项目 7 阶段（立项→设计→预算→采购→施工→质检→结算）进度状态，供 timeline.html 使用",
    responses={
        200: {"description": "阶段进度数据"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "项目不存在"},
    },
)
async def get_project_timeline(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取项目全链路阶段进度"""
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)

    # 7 阶段定义与进度映射
    stages = [
        {"id": 1, "name": "项目立项", "icon": "🏠", "key": "project",
         "substeps": "房屋测量 · 需求确认 · 风格意向", "module": "project"},
        {"id": 2, "name": "方案设计", "icon": "🎨", "key": "design",
         "substeps": "平面布局 · 3D效果图 · AI出图", "module": "design",
         "action_label": "去设计台 →", "action_url": "studio.html"},
        {"id": 3, "name": "预算规划", "icon": "💰", "key": "budget",
         "substeps": "量房报价 · 费用估算", "module": "budget"},
        {"id": 4, "name": "物料采购", "icon": "📦", "key": "procurement",
         "substeps": "物料清单 · 供应商匹配 · 下单", "module": "procurement"},
        {"id": 5, "name": "施工管理", "icon": "🔨", "key": "construction",
         "substeps": "施工排期 · 进度追踪 · 日志", "module": "construction"},
        {"id": 6, "name": "质量验收", "icon": "✅", "key": "quality",
         "substeps": "自检 · 专项验收 · 终验报告", "module": "quality"},
        {"id": 7, "name": "结算交付", "icon": "🏁", "key": "settlement",
         "substeps": "结算审核 · 支付 · 交付确认", "module": "settlement"},
    ]

    # 根据 phase 直接计算当前活跃阶段（修复断裂 4：原 status_stage_map 引用幻影状态）
    # phase: initiation/design/budget/procurement/construction/quality/settlement/completed/cancelled
    phase_stage_map = {
        "initiation": 1, "design": 2, "budget": 3, "procurement": 4,
        "construction": 5, "quality": 6, "settlement": 7, "completed": 7, "cancelled": 1,
    }
    project_phase = project.phase if hasattr(project, 'phase') and project.phase else "initiation"
    active_stage = phase_stage_map.get(project_phase, 1)

    # 并行查询关联数据（v1.2.1: 3 queries → 1 gather，减少串行等待）
    from sqlalchemy import select, func
    from app.models.budget import Budget
    from app.models.construction import ConstructionTask
    from app.models.settlement import Settlement

    async def _query_budget():
        r = await db.execute(select(Budget).where(Budget.project_id == project_id))
        return r.scalar_one_or_none() is not None

    async def _query_tasks():
        r = await db.execute(
            select(func.count(ConstructionTask.id)).where(ConstructionTask.project_id == project_id)
        )
        return r.scalar() or 0

    async def _query_settlement():
        r = await db.execute(select(Settlement).where(Settlement.project_id == project_id))
        return r.scalar_one_or_none() is not None

    has_budget, task_count, has_settlement = await asyncio.gather(
        _query_budget(), _query_tasks(), _query_settlement()
    )

    # 构建阶段状态
    for stage in stages:
        sid = stage["id"]
        if sid < active_stage:
            stage["status"] = "completed"
        elif sid == active_stage:
            stage["status"] = "active"
        else:
            stage["status"] = "pending"

    # 计算进度百分比（基于 phase；cancelled 视为 0%）
    if project_phase == "completed":
        progress_pct = 100
    elif project_phase == "cancelled":
        progress_pct = 0
    else:
        progress_pct = int((active_stage - 1) / 7 * 100)

    # 统计数据
    stats = {
        "total_stages": 7,
        "completed_stages": active_stage - 1,
        "active_stage": active_stage,
        "progress_pct": progress_pct,
        "has_budget": has_budget,
        "construction_tasks": task_count,
        "has_settlement": has_settlement,
    }

    return {
        "project_id": project_id,
        "project_name": project.name if hasattr(project, 'name') else "",
        "project_phase": project_phase,
        "project_status": project.status if hasattr(project, 'status') else "draft",
        "stages": stages,
        "stats": stats,
    }


# ── 竣工验收 ──

@router.post(
    "/{project_id}/accept",
    summary="竣工验收（强制验收报告闸门）",
    description=(
        "项目级竣工验收：强制闸门校验通过后推进 phase→completed / status→completed。\n\n"
        "闸门规则（强制，无人工绕过路径）：\n"
        "1. 项目当前 phase 必须为 quality 或 settlement\n"
        "2. 调用 quality_service.generate_acceptance_report 生成/取最新报告\n"
        "3. 查询项目下所有 QualityIssue，若存在 status in (open, in_progress) → 409 Conflict\n"
        "4. 报告 pass_rate < 100% 或含 fail 项 → 409 Conflict\n\n"
        "通过后：phase→completed，status→completed，WS 广播 project.accepted。"
    ),
    responses={
        200: {"description": "验收通过"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "项目不存在"},
        409: {"description": "验收闸门未通过（有未闭环质量问题或报告含 fail 项）"},
    },
)
async def accept_project(
    project_id: str,
    data: AcceptanceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """竣工验收端点（强制验收报告闸门）"""
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)

    # 闸门 1：phase 必须处于 quality 或 settlement 阶段
    if project.phase not in ("quality", "settlement"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason": "phase_not_ready",
                "message": f"当前阶段「{project.phase}」不可竣工验收，需先推进到 quality 或 settlement 阶段",
                "current_phase": project.phase,
                "required_phases": ["quality", "settlement"],
            },
        )

    # 闸门 2：查未闭环质量问题
    from sqlalchemy import select as _sel
    from app.models.quality import QualityIssue
    open_issues_result = await db.execute(
        _sel(QualityIssue).where(
            QualityIssue.project_id == project_id,
            QualityIssue.status.in_(["open", "in_progress"]),
        )
    )
    open_issues = list(open_issues_result.scalars().all())
    if open_issues:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason": "open_quality_issues",
                "message": f"存在 {len(open_issues)} 个未闭环质量问题，禁止竣工验收",
                "open_issues": [
                    {
                        "id": i.id,
                        "category": i.category,
                        "severity": i.severity,
                        "status": i.status,
                        "description": i.description,
                    }
                    for i in open_issues
                ],
            },
        )

    # 闸门 3：生成/取最新验收报告，必须 pass_rate==100 且无 fail 项
    from app.services.quality_service import generate_acceptance_report
    report = await generate_acceptance_report(db, project_id, phase=None)
    pass_rate = report.get("pass_rate", 0)
    failed_items = [r for r in report.get("results", []) if r.get("status") == "fail"]
    if failed_items or pass_rate < 100:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason": "acceptance_report_failed",
                "message": f"验收报告未通过：pass_rate={pass_rate}%，{len(failed_items)} 项 fail",
                "pass_rate": pass_rate,
                "failed_items": failed_items,
            },
        )

    # 闸门通过：推进 phase→completed / status→completed
    updated = await update_project_phase(db, project_id, "completed")
    if not updated:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="状态推进失败")

    from datetime import datetime, timedelta, timezone
    # 业务时区（北京时间，对齐 agent_context_service._DEFAULT_TZ）
    _bj_tz = timezone(timedelta(hours=8), name="Asia/Shanghai")
    resp = {
        "project_id": project_id,
        "project_name": project.name,
        "status": updated.status,
        "phase": updated.phase,
        "accepted": True,
        "acceptance_report": report,
        "accepted_at": datetime.now(_bj_tz).isoformat(),
    }
    try:
        await ws_manager.broadcast_to_project(project_id, "project.accepted", resp)
    except Exception:
        _ws_logger.warning("project.accepted broadcast failed", project_id=project_id, exc_info=True)

    return resp
