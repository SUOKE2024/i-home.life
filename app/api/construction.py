from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.construction import ConstructionTask, ConstructionLog
from app.schemas.construction import (
    TaskCreate,
    TaskResponse,
    LogCreate,
    LogResponse,
    InspectionCreate,
    InspectionResponse,
)
from app.schemas.progress import (
    ProgressAlertCreate,
    ProgressAlertResponse,
    MilestoneTrackerResponse,
    ProgressAnalysisRequest,
)
from app.schemas.quality import (
    QualityIssueCreate,
    QualityIssueUpdate,
    QualityIssueResponse,
    RectificationOrderCreate,
    RectificationOrderResponse,
    QualityAssessmentCreate,
    QualityAssessmentResponse,
    QualityDetectRequest,
)
from app.auth import get_current_user
from app.rbac import verify_project_access
from app.services import construction_service, progress_service, quality_service
from app.agents.construction import ConstructionAgent, manage_progress, detect_quality_issues
from app.ws import ws_manager
from app.config import get_settings

router = APIRouter(prefix="/construction", tags=["施工"])


class ConstructionPlanRequest(BaseModel):
    total_area: float = 100.0
    tier: str = "comfort"


class InspectionAnalyzeRequest(BaseModel):
    phase: str = "masonry"
    images: list[dict] = []
    design_reference: str | None = None
    expected_dimensions: dict = {}


class ResolveAlertRequest(BaseModel):
    note: str | None = None


class CompleteMilestoneRequest(BaseModel):
    actual_date: str | None = None
    actual_percent: float | None = None
    note: str | None = None


def _alert_to_response(alert) -> ProgressAlertResponse:
    return ProgressAlertResponse(
        id=alert.id,
        project_id=alert.project_id,
        task_id=alert.task_id,
        phase=alert.phase,
        alert_type=alert.alert_type,
        severity=alert.severity,
        message=alert.message,
        planned_date=alert.planned_date,
        actual_date=alert.actual_date,
        delay_days=alert.delay_days,
        progress_percent=alert.progress_percent,
        suggestion=alert.suggestion,
        status=alert.status,
        resolved_at=alert.resolved_at,
        resolved_by=alert.resolved_by,
        resolution_note=alert.resolution_note,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
    )


def _milestone_to_response(ms) -> MilestoneTrackerResponse:
    return MilestoneTrackerResponse(
        id=ms.id,
        project_id=ms.project_id,
        milestone_code=ms.milestone_code,
        name=ms.name,
        planned_date=ms.planned_date,
        actual_date=ms.actual_date,
        planned_percent=ms.planned_percent,
        actual_percent=ms.actual_percent,
        status=ms.status,
        payment_ratio=ms.payment_ratio,
        note=ms.note,
        created_at=ms.created_at,
        updated_at=ms.updated_at,
    )


@router.get(
    "/tasks/{project_id}",
    response_model=list[TaskResponse],
    summary="获取施工任务列表",
    description="获取指定项目的所有施工任务列表。",
    response_description="任务列表",
    responses={
        200: {"description": "获取成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "项目不存在"},
    },
    tags=["施工管理"],
)
async def list_tasks(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if current_user.role != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    tasks = await construction_service.get_tasks(db, project_id)
    return [TaskResponse.model_validate(t) for t in tasks]


@router.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建施工任务",
    description="为指定项目创建一个新的施工任务，包含任务名称、阶段、工期等信息。",
    response_description="创建成功，返回任务信息",
    responses={
        201: {"description": "创建成功"},
        400: {"description": "请求参数无效"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
    },
    tags=["施工管理"],
)
async def create_task(
    data: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    task = await construction_service.create_task(db, data.model_dump())
    resp = TaskResponse.model_validate(task)
    await ws_manager.broadcast_to_project(data.project_id, "task.created", resp.model_dump())
    return resp


@router.patch(
    "/tasks/{task_id}/status",
    response_model=TaskResponse,
    summary="更新任务状态",
    description="更新施工任务的状态（如：待开始、进行中、已完成、已延期）。",
    response_description="更新成功，返回任务信息",
    responses={
        200: {"description": "更新成功"},
        400: {"description": "无效的状态值"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "任务不存在"},
    },
    tags=["施工管理"],
)
async def update_task_status(
    task_id: str,
    status_val: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # IDOR 修复：先校验任务所属项目归属，再执行变更（mutation 必须在 verify 之后）
    existing = await db.get(ConstructionTask, task_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    await verify_project_access(project_id=existing.project_id, current_user=current_user, db=db)
    task = await construction_service.update_task_status(db, task_id, status_val)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    resp = TaskResponse.model_validate(task)
    await ws_manager.broadcast_to_project(task.project_id, "task.status_updated", resp.model_dump())
    return resp


@router.post(
    "/logs",
    response_model=LogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="添加施工日志",
    description="为施工任务添加施工日志，记录施工进度、现场情况和发现的问题。",
    response_description="创建成功，返回日志信息",
    responses={
        201: {"description": "日志创建成功"},
        400: {"description": "请求参数无效"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
    },
    tags=["施工管理"],
)
async def add_log(
    data: LogCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # IDOR 修复：先校验任务所属项目归属，再添加日志（mutation 必须在 verify 之后）
    task = await db.get(ConstructionTask, data.task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    await verify_project_access(project_id=task.project_id, current_user=current_user, db=db)
    log_data = data.model_dump()
    log_data["created_by"] = current_user.name
    log = await construction_service.add_log(db, log_data)
    resp = LogResponse.model_validate(log)
    await ws_manager.broadcast_to_project(task.project_id, "log.added", resp.model_dump())
    return resp


@router.get(
    "/logs/{task_id}",
    response_model=list[LogResponse],
    summary="获取任务施工日志",
    description="获取指定施工任务的所有施工日志记录。",
    response_description="日志列表",
    responses={
        200: {"description": "获取成功"},
        401: {"description": "未登录或 Token 无效"},
    },
    tags=["施工管理"],
)
async def get_logs(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # IDOR 修复：先校验任务所属项目归属，再返回日志
    task = await db.get(ConstructionTask, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    await verify_project_access(project_id=task.project_id, current_user=current_user, db=db)
    logs = await construction_service.get_logs(db, task_id)
    return [LogResponse.model_validate(log) for log in logs]


@router.post(
    "/inspections",
    response_model=InspectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建质量检查",
    description="为施工任务创建质量检查记录，包含检查结果和照片。",
    response_description="创建成功，返回检查记录",
    responses={
        201: {"description": "检查记录创建成功"},
        400: {"description": "请求参数无效"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
    },
    tags=["施工管理"],
)
async def create_inspection(
    data: InspectionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # IDOR 修复：先校验任务所属项目归属，再创建检查记录（mutation 必须在 verify 之后）
    task = await db.get(ConstructionTask, data.task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    await verify_project_access(project_id=task.project_id, current_user=current_user, db=db)
    inspection = await construction_service.create_inspection(db, data.model_dump())
    resp = InspectionResponse.model_validate(inspection)
    await ws_manager.broadcast_to_project(task.project_id, "inspection.created", resp.model_dump())
    return resp


@router.get(
    "/inspections/{task_id}",
    response_model=list[InspectionResponse],
    summary="获取任务检查记录",
    description="获取指定施工任务的所有质量检查记录。",
    response_description="检查记录列表",
    responses={
        200: {"description": "获取成功"},
        401: {"description": "未登录或 Token 无效"},
    },
    tags=["施工管理"],
)
async def get_inspections(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # IDOR 修复：先校验任务所属项目归属，再返回检查记录
    task = await db.get(ConstructionTask, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    await verify_project_access(project_id=task.project_id, current_user=current_user, db=db)
    inspections = await construction_service.get_inspections(db, task_id)
    return [InspectionResponse.model_validate(i) for i in inspections]


# ── F37 施工计划生成（Gantt 排期） ──
@router.post(
    "/plan",
    summary="AI 生成施工计划",
    description="AI 根据房屋面积和装修档次生成施工计划，包含 Gantt 排期和各阶段任务安排。",
    responses={
        200: {"description": "生成成功"},
        400: {"description": "请求参数无效"},
    },
    tags=["施工管理"],
)
async def generate_construction_plan(
    data: ConstructionPlanRequest,
    current_user: User = Depends(get_current_user),
):
    agent = ConstructionAgent()
    return agent.generate_construction_plan(data.total_area, data.tier)


# ── F38 质检清单查询 ──
@router.get(
    "/quality-checklist/{phase}",
    summary="获取质检清单",
    description="根据施工阶段获取对应的质量检查清单和验收标准。",
    responses={
        200: {"description": "获取成功"},
    },
    tags=["施工管理"],
)
async def get_quality_checklist(
    phase: str,
    current_user: User = Depends(get_current_user),
):
    agent = ConstructionAgent()
    return agent.get_quality_checklist(phase)


# ── F38 AI 图像质检 ──
@router.post(
    "/inspections/analyze",
    summary="AI 图像质检分析",
    description="AI 对施工现场照片进行图像分析，自动检测质量问题与设计偏差。",
    responses={
        200: {"description": "分析成功"},
        400: {"description": "请求参数无效"},
    },
    tags=["施工管理"],
)
async def analyze_inspection_images(
    data: InspectionAnalyzeRequest,
    current_user: User = Depends(get_current_user),
):
    agent = ConstructionAgent()
    return agent.analyze_inspection_images(data.model_dump())


# ── F37 AI 进度管理（预警 + 里程碑跟踪） ──

@router.post(
    "/progress-analysis",
    summary="AI 进度分析",
    description="AI 基于任务列表分析项目进度，自动生成进度预警和里程碑跟踪报告。",
    responses={
        200: {"description": "分析成功"},
        400: {"description": "请求参数无效"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
    },
    tags=["施工管理"],
)
async def analyze_project_progress(
    data: ProgressAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """F37 AI 进度分析 — 基于任务列表生成预警 + 里程碑跟踪"""
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    result = manage_progress(
        project_id=data.project_id,
        tasks=data.tasks,
        current_date=data.current_date,
        milestones=data.milestones,
    )
    await ws_manager.broadcast_to_project(data.project_id, "progress.analyzed", result)
    return result


@router.get(
    "/progress-alerts/{project_id}",
    response_model=list[ProgressAlertResponse],
    summary="获取进度预警列表",
    description="查询项目的进度预警列表，可按状态和严重度筛选。",
    response_description="预警列表",
    responses={
        200: {"description": "获取成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "项目不存在"},
    },
    tags=["施工管理"],
)
async def list_progress_alerts(
    project_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    severity: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询项目进度预警列表"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if current_user.role != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    alerts = await progress_service.list_alerts(db, project_id, status_filter=status_filter, severity=severity)
    return [_alert_to_response(a) for a in alerts]


@router.post(
    "/progress-alerts",
    response_model=ProgressAlertResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建进度预警",
    description="手动创建项目进度预警，标记延期或风险任务。",
    response_description="创建成功，返回预警信息",
    responses={
        201: {"description": "预警创建成功"},
        400: {"description": "请求参数无效"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
    },
    tags=["施工管理"],
)
async def create_progress_alert(
    data: ProgressAlertCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """手动创建进度预警"""
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    alert = await progress_service.create_alert(db, data.model_dump())
    resp = _alert_to_response(alert)
    await ws_manager.broadcast_to_project(data.project_id, "progress.alert", resp.model_dump())
    return resp


@router.patch(
    "/progress-alerts/{alert_id}/resolve",
    response_model=ProgressAlertResponse,
    summary="解决进度预警",
    description="将进度预警标记为已解决，记录解决人和备注信息。",
    response_description="已解决的预警信息",
    responses={
        200: {"description": "解决成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "预警记录不存在"},
    },
    tags=["施工管理"],
)
async def resolve_progress_alert(
    alert_id: str,
    data: ResolveAlertRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """解决进度预警"""
    # 先校验项目归属，再执行变更（防止 IDOR：mutation 必须在 verify 之后）
    existing = await progress_service.get_alert(db, alert_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预警记录不存在")
    await verify_project_access(project_id=existing.project_id, current_user=current_user, db=db)
    alert = await progress_service.resolve_alert(db, alert_id, resolver=current_user.name, note=data.note)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预警记录不存在")
    resp = _alert_to_response(alert)
    await ws_manager.broadcast_to_project(alert.project_id, "progress.alert_resolved", resp.model_dump())
    return resp


@router.get(
    "/milestones/{project_id}",
    response_model=list[MilestoneTrackerResponse],
    summary="获取里程碑列表",
    description="查询项目的里程碑跟踪列表，展示各里程碑的计划和实际完成情况。",
    response_description="里程碑列表",
    responses={
        200: {"description": "获取成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "项目不存在"},
    },
    tags=["施工管理"],
)
async def list_milestones(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询项目里程碑跟踪列表"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if current_user.role != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    milestones = await progress_service.list_milestones(db, project_id)
    return [_milestone_to_response(m) for m in milestones]


@router.post(
    "/milestones",
    response_model=MilestoneTrackerResponse,
    summary="创建/更新里程碑",
    description="创建或更新项目的里程碑跟踪记录。",
    response_description="里程碑记录",
    responses={
        200: {"description": "创建/更新成功"},
        400: {"description": "请求参数无效"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
    },
    tags=["施工管理"],
)
async def upsert_milestone(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建或更新里程碑跟踪记录"""
    # 先校验项目归属，再执行变更（防止 IDOR：mutation 必须在 verify 之后）
    project_id = data.get("project_id")
    if not project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少 project_id")
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    record = await progress_service.upsert_milestone(db, data)
    resp = _milestone_to_response(record)
    await ws_manager.broadcast_to_project(record.project_id, "milestone.updated", resp.model_dump())
    return resp


@router.patch(
    "/milestones/{milestone_id}/complete",
    response_model=MilestoneTrackerResponse,
    summary="完成里程碑",
    description="标记里程碑为已完成，记录实际完成日期和完成百分比。",
    response_description="已完成的里程碑记录",
    responses={
        200: {"description": "标记成功"},
        400: {"description": "请求参数无效"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "里程碑记录不存在"},
    },
    tags=["施工管理"],
)
async def complete_milestone(
    milestone_id: str,
    data: CompleteMilestoneRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记里程碑完成"""
    # 先校验项目归属，再执行变更（防止 IDOR：mutation 必须在 verify 之后）
    from app.models.progress_alert import MilestoneTracker
    existing = await db.get(MilestoneTracker, milestone_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="里程碑记录不存在")
    await verify_project_access(project_id=existing.project_id, current_user=current_user, db=db)
    actual_date = None
    if data.actual_date:
        try:
            actual_date = datetime.fromisoformat(data.actual_date.replace("Z", "+00:00"))
        except Exception:
            actual_date = None
    record = await progress_service.complete_milestone(
        db, milestone_id, actual_date=actual_date, actual_percent=data.actual_percent, note=data.note
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="里程碑记录不存在")
    resp = _milestone_to_response(record)
    await ws_manager.broadcast_to_project(record.project_id, "milestone.completed", resp.model_dump())
    return resp


@router.patch(
    "/milestones/{milestone_id}/status",
    response_model=MilestoneTrackerResponse,
    summary="更新里程碑状态",
    description="更新里程碑的状态（pending/in_progress/delayed/completed）。",
    response_description="更新后的里程碑记录",
    responses={
        200: {"description": "更新成功"},
        400: {"description": "无效的状态转换"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "里程碑记录不存在"},
    },
    tags=["施工管理"],
)
async def update_milestone_status(
    milestone_id: str,
    new_status: str = Query(..., description="目标状态: pending/in_progress/delayed/completed"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新里程碑状态（带状态机校验）"""
    from app.models.progress_alert import MilestoneTracker
    existing = await db.get(MilestoneTracker, milestone_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="里程碑记录不存在")
    await verify_project_access(project_id=existing.project_id, current_user=current_user, db=db)
    record = await progress_service.update_milestone_status(db, milestone_id, new_status)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="里程碑记录不存在")
    resp = _milestone_to_response(record)
    await ws_manager.broadcast_to_project(record.project_id, "milestone.status_changed", resp.model_dump())
    return resp


# ── F38 AI 质量管理（质量问题 + 整改单 + 质量评估） ──

def _issue_to_response(issue) -> QualityIssueResponse:
    return QualityIssueResponse(
        id=issue.id,
        project_id=issue.project_id,
        task_id=issue.task_id,
        inspection_id=issue.inspection_id,
        phase=issue.phase,
        category=issue.category,
        description=issue.description,
        severity=issue.severity,
        status=issue.status,
        images=issue.images,
        detected_by=issue.detected_by,
        standard=issue.standard,
        location=issue.location,
        resolution=issue.resolution,
        resolved_at=issue.resolved_at,
        resolved_by=issue.resolved_by,
        verified_by=issue.verified_by,
        verified_at=issue.verified_at,
        created_at=issue.created_at,
        updated_at=issue.updated_at,
    )


def _order_to_response(order) -> RectificationOrderResponse:
    return RectificationOrderResponse(
        id=order.id,
        project_id=order.project_id,
        order_no=order.order_no,
        title=order.title,
        description=order.description,
        phase=order.phase,
        issue_ids=order.issue_ids,
        responsible_party=order.responsible_party,
        responsible_phone=order.responsible_phone,
        deadline=order.deadline,
        priority=order.priority,
        status=order.status,
        cost=order.cost,
        notes=order.notes,
        completed_at=order.completed_at,
        verified_at=order.verified_at,
        created_by=order.created_by,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def _assessment_to_response(a) -> QualityAssessmentResponse:
    return QualityAssessmentResponse(
        id=a.id,
        project_id=a.project_id,
        phase=a.phase,
        total_items=a.total_items,
        passed=a.passed,
        failed=a.failed,
        score=a.score,
        verdict=a.verdict,
        assessor=a.assessor,
        summary=a.summary,
        issues_summary=a.issues_summary,
        assessed_at=a.assessed_at,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


@router.post(
    "/quality-detect",
    summary="AI 质量问题检测",
    description="AI 基于质检结果自动识别质量问题，按严重度分类并生成整改建议。",
    responses={
        200: {"description": "检测成功"},
        400: {"description": "请求参数无效"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
    },
    tags=["施工管理"],
)
async def detect_quality_problems(
    data: QualityDetectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """F38 AI 质量问题检测 — 基于质检结果自动识别质量问题"""
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    result = detect_quality_issues(
        project_id=data.project_id,
        phase=data.phase,
        inspection_results=data.inspection_results,
        task_id=data.task_id,
        inspection_id=data.inspection_id,
    )
    await ws_manager.broadcast_to_project(data.project_id, "quality.detected", result)
    return result


@router.post(
    "/quality-issues",
    response_model=QualityIssueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建质量问题",
    description="创建质量问题记录，包含问题描述、严重度、位置和检测标准。",
    response_description="创建成功，返回质量问题记录",
    responses={
        201: {"description": "质量问题创建成功"},
        400: {"description": "请求参数无效"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
    },
    tags=["施工管理"],
)
async def create_quality_issue(
    data: QualityIssueCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建质量问题记录"""
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    issue = await quality_service.create_issue(db, data.model_dump())
    resp = _issue_to_response(issue)
    await ws_manager.broadcast_to_project(data.project_id, "quality.issue_created", resp.model_dump())
    return resp


@router.get(
    "/quality-issues/{project_id}",
    response_model=list[QualityIssueResponse],
    summary="获取质量问题列表",
    description="查询项目的质量问题列表，可按阶段、状态和严重度筛选。",
    response_description="质量问题列表",
    responses={
        200: {"description": "获取成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "项目不存在"},
    },
    tags=["施工管理"],
)
async def list_quality_issues(
    project_id: str,
    phase: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    severity: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询项目质量问题列表"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if current_user.role != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    issues = await quality_service.list_issues(
        db, project_id, phase=phase, status_filter=status_filter, severity=severity
    )
    return [_issue_to_response(i) for i in issues]


@router.patch(
    "/quality-issues/{issue_id}/status",
    response_model=QualityIssueResponse,
    summary="更新质量问题状态",
    description="更新质量问题的处理状态（整改/验收），记录解决方案和验收人。",
    response_description="更新后的质量问题记录",
    responses={
        200: {"description": "更新成功"},
        400: {"description": "请求参数无效"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "质量问题不存在"},
    },
    tags=["施工管理"],
)
async def update_quality_issue_status(
    issue_id: str,
    data: QualityIssueUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新质量问题状态（整改/验收）"""
    # 先校验项目归属，再执行变更（防止 IDOR：mutation 必须在 verify 之后）
    existing = await quality_service.get_issue(db, issue_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="质量问题不存在")
    await verify_project_access(project_id=existing.project_id, current_user=current_user, db=db)
    issue = await quality_service.update_issue_status(
        db, issue_id, data.status,
        resolution=data.resolution,
        resolver=current_user.name,
        verifier=current_user.name,
    )
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="质量问题不存在")
    resp = _issue_to_response(issue)
    await ws_manager.broadcast_to_project(issue.project_id, "quality.issue_updated", resp.model_dump())
    return resp


@router.post(
    "/rectification-orders",
    response_model=RectificationOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建整改单",
    description="创建整改单并自动生成单号，同步关联质量问题状态。",
    response_description="创建成功，返回整改单信息",
    responses={
        201: {"description": "整改单创建成功"},
        400: {"description": "请求参数无效"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
    },
    tags=["施工管理"],
)
async def create_rectification_order(
    data: RectificationOrderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建整改单（自动生成单号 + 同步关联 issue 状态）"""
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    order = await quality_service.create_rectification_order(db, data.model_dump(), created_by=current_user.name)
    resp = _order_to_response(order)
    await ws_manager.broadcast_to_project(data.project_id, "quality.order_created", resp.model_dump())
    return resp


@router.get(
    "/rectification-orders/{project_id}",
    response_model=list[RectificationOrderResponse],
    summary="获取整改单列表",
    description="查询项目的整改单列表，可按状态筛选。",
    response_description="整改单列表",
    responses={
        200: {"description": "获取成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "项目不存在"},
    },
    tags=["施工管理"],
)
async def list_rectification_orders(
    project_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询项目整改单列表"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if current_user.role != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    orders = await quality_service.list_orders(db, project_id, status_filter=status_filter)
    return [_order_to_response(o) for o in orders]


@router.patch(
    "/rectification-orders/{order_id}/status",
    response_model=RectificationOrderResponse,
    summary="更新整改单状态",
    description="更新整改单的处理状态，并同步关联的质量问题状态。",
    response_description="更新后的整改单",
    responses={
        200: {"description": "更新成功"},
        400: {"description": "无效的状态值"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "整改单不存在"},
    },
    tags=["施工管理"],
)
async def update_rectification_order_status(
    order_id: str,
    new_status: str = Query(..., description="pending/in_progress/completed/verified/closed"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新整改单状态（含 issue 状态同步）"""
    # 先校验项目归属，再执行变更（防止 IDOR：mutation 必须在 verify 之后）
    existing = await quality_service.get_order(db, order_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="整改单不存在")
    await verify_project_access(project_id=existing.project_id, current_user=current_user, db=db)
    order = await quality_service.update_order_status(db, order_id, new_status, verifier=current_user.name)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="整改单不存在")
    resp = _order_to_response(order)
    await ws_manager.broadcast_to_project(order.project_id, "quality.order_updated", resp.model_dump())
    return resp


@router.post(
    "/quality-assessments",
    response_model=QualityAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建质量评估汇总",
    description="创建项目的质量评估汇总，统计通过/未通过项并计算评分。",
    response_description="创建成功，返回质量评估汇总",
    responses={
        201: {"description": "评估汇总创建成功"},
        400: {"description": "请求参数无效"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
    },
    tags=["施工管理"],
)
async def create_quality_assessment(
    data: QualityAssessmentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建质量评估汇总"""
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    assessment = await quality_service.create_assessment(db, data.model_dump())
    resp = _assessment_to_response(assessment)
    await ws_manager.broadcast_to_project(data.project_id, "quality.assessed", resp.model_dump())
    return resp


@router.get(
    "/quality-assessments/{project_id}",
    response_model=list[QualityAssessmentResponse],
    summary="获取质量评估列表",
    description="查询项目的所有质量评估汇总记录。",
    response_description="质量评估列表",
    responses={
        200: {"description": "获取成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "项目不存在"},
    },
    tags=["施工管理"],
)
async def list_quality_assessments(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询项目质量评估列表"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if current_user.role != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    assessments = await quality_service.list_assessments(db, project_id)
    return [_assessment_to_response(a) for a in assessments]


@router.post(
    "/logs/analyze-defects",
    summary="AI 施工日志缺陷分析",
    description="AI 分析施工日志中的文本描述，通过关键词匹配和缺陷类别库进行交叉检测，"
    "按严重度（critical/high/medium/low）分类返回潜在问题。",
    responses={
        200: {"description": "分析成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "项目不存在"},
    },
    tags=["施工管理"],
)
async def analyze_construction_logs(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI 分析施工日志中的潜在缺陷

    从施工日志中提取文本描述，通过关键词匹配和 QA Inspector 的缺陷类别库进行交叉检测。
    检测到的潜在问题按严重度（critical/high/medium/low）分类返回。
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if current_user.role != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    from app.agents.qa_inspector import DEFECT_CATEGORIES, DEFECT_KEYWORD_MAP

    # 获取项目的施工日志
    tasks_result = await db.execute(
        select(ConstructionTask).where(ConstructionTask.project_id == project_id)
    )
    tasks = tasks_result.scalars().all()

    if not tasks:
        return {
            "project_id": project_id,
            "issues": [],
            "total_logs": 0,
            "reply": "该项目暂无施工日志",
        }

    # 收集所有日志内容
    all_logs = []
    for task in tasks:
        logs_result = await db.execute(
            select(ConstructionLog).where(ConstructionLog.task_id == task.id)
        )
        logs = logs_result.scalars().all()
        for log in logs:
            all_logs.append(
                {
                    "task_name": task.name or "",
                    "phase": task.phase or "",
                    "content": log.content or "",
                    "created_at": str(log.created_at) if log.created_at else "",
                }
            )

    # 关键词匹配检测
    detected_issues = []
    for log_item in all_logs:
        content = log_item["content"]
        for category_name, keywords in DEFECT_KEYWORD_MAP.items():
            for kw in keywords:
                if kw in content:
                    cat_def = next(
                        (c for c in DEFECT_CATEGORIES if c["name"] == category_name),
                        None,
                    )
                    severity = cat_def["severity"] if cat_def else "low"
                    rectification = (
                        cat_def["rectification"] if cat_def else "需要人工复查"
                    )
                    detected_issues.append(
                        {
                            "task_name": log_item["task_name"],
                            "phase": log_item["phase"],
                            "category": category_name,
                            "keyword_matched": kw,
                            "severity": severity,
                            "log_excerpt": content[:200]
                            + ("..." if len(content) > 200 else ""),
                            "rectification": rectification,
                            "created_at": log_item["created_at"],
                        }
                    )
                    break

    # 按严重度排序
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    detected_issues.sort(
        key=lambda x: severity_order.get(x["severity"], 99)
    )

    critical_count = sum(1 for i in detected_issues if i["severity"] == "critical")
    high_count = sum(1 for i in detected_issues if i["severity"] == "high")

    return {
        "project_id": project_id,
        "total_logs": len(all_logs),
        "issue_count": len(detected_issues),
        "critical_count": critical_count,
        "high_count": high_count,
        "issues": detected_issues,
        "reply": f"施工日志缺陷分析完成：{len(all_logs)} 条日志，检出 {len(detected_issues)} 个潜在问题（严重 {critical_count}，高危 {high_count}）",
        "suggestion": (
            "建议立即处理严重问题"
            if critical_count > 0
            else (
                "暂未发现严重问题"
                if detected_issues
                else "施工日志未检出异常"
            )
        ),
    }


# ── A6 施工预测性维护 ──

from app.services import predictive_maintenance_service as pm_svc
from app.schemas.predictive_maintenance import (
    RiskPredictionResponse,
    RiskMitigateRequest,
    RiskResolveRequest,
)


def _risk_to_response(risk) -> RiskPredictionResponse:
    return RiskPredictionResponse(
        id=risk.id,
        project_id=risk.project_id,
        risk_type=risk.risk_type,
        risk_score=risk.risk_score,
        probability=risk.probability,
        impact_level=risk.impact_level,
        trigger_factors=risk.trigger_factors,
        affected_tasks=risk.affected_tasks,
        mitigation_actions=risk.mitigation_actions,
        status=risk.status,
        predicted_at=risk.predicted_at,
        resolved_at=risk.resolved_at,
        created_at=risk.created_at,
    )


@router.post(
    "/predictive-analysis",
    summary="触发风险分析",
    description="AI 基于项目施工数据、预算、物料和质检记录自动分析项目风险，"
    "检测延期、成本超支、材料短缺、质量问题和劳动力短缺。",
    responses={
        200: {"description": "分析成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "项目不存在"},
    },
    tags=["施工管理"],
)
async def run_predictive_analysis(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """A6 触发项目风险分析"""
    settings = get_settings()
    if not settings.predictive_maintenance_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="预测性维护功能未启用",
        )

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if current_user.role != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")

    analysis = await pm_svc.analyze_project_risks(project_id, db)
    await db.commit()

    active_risks = await pm_svc.get_active_risks(project_id, db)
    risks_list = [_risk_to_response(r) for r in analysis["risks"]]

    return {
        "project_id": project_id,
        "analysis_time": datetime.now().isoformat(),
        "risks_created": analysis["risks_created"],
        "risks_active": len(active_risks),
        "risks_list": risks_list,
        "summary": f"项目 [{project.name}] 风险分析完成：创建 {analysis['risks_created']} 个新风险，当前 {len(active_risks)} 个活跃风险。",
    }


@router.get(
    "/risks/{project_id}",
    response_model=list[RiskPredictionResponse],
    summary="获取风险列表",
    description="获取项目的所有风险预测记录，包含活跃、已缓解和已解除的风险。",
    response_description="风险列表",
    responses={
        200: {"description": "获取成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "项目不存在"},
    },
    tags=["施工管理"],
)
async def get_project_risks(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取项目风险列表"""
    settings = get_settings()
    if not settings.predictive_maintenance_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="预测性维护功能未启用",
        )

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if current_user.role != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")

    risks = await pm_svc.get_all_risks(project_id, db)
    return [_risk_to_response(r) for r in risks]


@router.patch(
    "/risks/{risk_id}/mitigate",
    response_model=RiskPredictionResponse,
    summary="标记风险已缓解",
    description="将风险预测记录标记为已缓解，记录缓解措施备注。",
    response_description="已缓解的风险记录",
    responses={
        200: {"description": "缓解成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "风险记录不存在"},
    },
    tags=["施工管理"],
)
async def mitigate_project_risk(
    risk_id: str,
    data: RiskMitigateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记风险已缓解"""
    settings = get_settings()
    if not settings.predictive_maintenance_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="预测性维护功能未启用",
        )

    risk = await pm_svc.get_risk(risk_id, db)
    if not risk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风险记录不存在")
    await verify_project_access(project_id=risk.project_id, current_user=current_user, db=db)

    risk = await pm_svc.mitigate_risk(risk_id, db, note=data.note)
    await db.commit()
    return _risk_to_response(risk)


@router.patch(
    "/risks/{risk_id}/resolve",
    response_model=RiskPredictionResponse,
    summary="标记风险已解决",
    description="将风险预测记录标记为已解决，记录解决时间和备注。",
    response_description="已解决的风险记录",
    responses={
        200: {"description": "解决成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "风险记录不存在"},
    },
    tags=["施工管理"],
)
async def resolve_project_risk(
    risk_id: str,
    data: RiskResolveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记风险已解决"""
    settings = get_settings()
    if not settings.predictive_maintenance_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="预测性维护功能未启用",
        )

    risk = await pm_svc.get_risk(risk_id, db)
    if not risk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风险记录不存在")
    await verify_project_access(project_id=risk.project_id, current_user=current_user, db=db)

    risk = await pm_svc.resolve_risk(risk_id, db, note=data.note)
    await db.commit()
    return _risk_to_response(risk)


@router.get(
    "/dashboard/{project_id}",
    summary="施工健康度仪表盘",
    description="获取项目的综合施工健康度仪表盘，包含风险统计、健康评分和各维度风险分布。",
    responses={
        200: {"description": "获取成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "项目不存在"},
    },
    tags=["施工管理"],
)
async def get_construction_dashboard(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取施工健康度仪表盘"""
    settings = get_settings()
    if not settings.predictive_maintenance_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="预测性维护功能未启用",
        )

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if current_user.role != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")

    dashboard = await pm_svc.get_dashboard(project_id, db, project_name=project.name)
    dashboard["active_risks"] = [_risk_to_response(r) for r in dashboard["active_risks"]]
    return dashboard
