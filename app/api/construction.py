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


@router.get("/tasks/{project_id}", response_model=list[TaskResponse])
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


@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
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


@router.patch("/tasks/{task_id}/status", response_model=TaskResponse)
async def update_task_status(
    task_id: str,
    status_val: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await construction_service.update_task_status(db, task_id, status_val)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    await verify_project_access(project_id=task.project_id, current_user=current_user, db=db)
    resp = TaskResponse.model_validate(task)
    await ws_manager.broadcast_to_project(task.project_id, "task.status_updated", resp.model_dump())
    return resp


@router.post("/logs", response_model=LogResponse, status_code=status.HTTP_201_CREATED)
async def add_log(
    data: LogCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    log_data = data.model_dump()
    log_data["created_by"] = current_user.name
    log = await construction_service.add_log(db, log_data)
    resp = LogResponse.model_validate(log)
    # 通过 task_id 查询 project_id 用于广播
    task_result = await db.execute(select(ConstructionTask).where(ConstructionTask.id == data.task_id))
    task = task_result.scalar_one_or_none()
    if task:
        await verify_project_access(project_id=task.project_id, current_user=current_user, db=db)
        await ws_manager.broadcast_to_project(task.project_id, "log.added", resp.model_dump())
    return resp


@router.get("/logs/{task_id}", response_model=list[LogResponse])
async def get_logs(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    logs = await construction_service.get_logs(db, task_id)
    return [LogResponse.model_validate(log) for log in logs]


@router.post("/inspections", response_model=InspectionResponse, status_code=status.HTTP_201_CREATED)
async def create_inspection(
    data: InspectionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    inspection = await construction_service.create_inspection(db, data.model_dump())
    resp = InspectionResponse.model_validate(inspection)
    # 通过 task_id 查询 project_id 用于广播
    task_result = await db.execute(select(ConstructionTask).where(ConstructionTask.id == data.task_id))
    task = task_result.scalar_one_or_none()
    if task:
        await verify_project_access(project_id=task.project_id, current_user=current_user, db=db)
        await ws_manager.broadcast_to_project(task.project_id, "inspection.created", resp.model_dump())
    return resp


@router.get("/inspections/{task_id}", response_model=list[InspectionResponse])
async def get_inspections(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    inspections = await construction_service.get_inspections(db, task_id)
    return [InspectionResponse.model_validate(i) for i in inspections]


# ── F37 施工计划生成（Gantt 排期） ──
@router.post("/plan")
async def generate_construction_plan(
    data: ConstructionPlanRequest,
    current_user: User = Depends(get_current_user),
):
    agent = ConstructionAgent()
    return agent.generate_construction_plan(data.total_area, data.tier)


# ── F38 质检清单查询 ──
@router.get("/quality-checklist/{phase}")
async def get_quality_checklist(
    phase: str,
    current_user: User = Depends(get_current_user),
):
    agent = ConstructionAgent()
    return agent.get_quality_checklist(phase)


# ── F38 AI 图像质检 ──
@router.post("/inspections/analyze")
async def analyze_inspection_images(
    data: InspectionAnalyzeRequest,
    current_user: User = Depends(get_current_user),
):
    agent = ConstructionAgent()
    return agent.analyze_inspection_images(data.model_dump())


# ── F37 AI 进度管理（预警 + 里程碑跟踪） ──

@router.post("/progress-analysis")
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


@router.get("/progress-alerts/{project_id}", response_model=list[ProgressAlertResponse])
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


@router.post("/progress-alerts", response_model=ProgressAlertResponse, status_code=status.HTTP_201_CREATED)
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


@router.patch("/progress-alerts/{alert_id}/resolve", response_model=ProgressAlertResponse)
async def resolve_progress_alert(
    alert_id: str,
    data: ResolveAlertRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """解决进度预警"""
    alert = await progress_service.resolve_alert(db, alert_id, resolver=current_user.name, note=data.note)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预警记录不存在")
    await verify_project_access(project_id=alert.project_id, current_user=current_user, db=db)
    resp = _alert_to_response(alert)
    await ws_manager.broadcast_to_project(alert.project_id, "progress.alert_resolved", resp.model_dump())
    return resp


@router.get("/milestones/{project_id}", response_model=list[MilestoneTrackerResponse])
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


@router.post("/milestones", response_model=MilestoneTrackerResponse)
async def upsert_milestone(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建或更新里程碑跟踪记录"""
    record = await progress_service.upsert_milestone(db, data)
    await verify_project_access(project_id=record.project_id, current_user=current_user, db=db)
    resp = _milestone_to_response(record)
    await ws_manager.broadcast_to_project(record.project_id, "milestone.updated", resp.model_dump())
    return resp


@router.patch("/milestones/{milestone_id}/complete", response_model=MilestoneTrackerResponse)
async def complete_milestone(
    milestone_id: str,
    data: CompleteMilestoneRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记里程碑完成"""
    from datetime import datetime
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
    await verify_project_access(project_id=record.project_id, current_user=current_user, db=db)
    resp = _milestone_to_response(record)
    await ws_manager.broadcast_to_project(record.project_id, "milestone.completed", resp.model_dump())
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


@router.post("/quality-detect")
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


@router.post("/quality-issues", response_model=QualityIssueResponse, status_code=status.HTTP_201_CREATED)
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


@router.get("/quality-issues/{project_id}", response_model=list[QualityIssueResponse])
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


@router.patch("/quality-issues/{issue_id}/status", response_model=QualityIssueResponse)
async def update_quality_issue_status(
    issue_id: str,
    data: QualityIssueUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新质量问题状态（整改/验收）"""
    issue = await quality_service.update_issue_status(
        db, issue_id, data.status,
        resolution=data.resolution,
        resolver=current_user.name,
        verifier=current_user.name,
    )
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="质量问题不存在")
    await verify_project_access(project_id=issue.project_id, current_user=current_user, db=db)
    resp = _issue_to_response(issue)
    await ws_manager.broadcast_to_project(issue.project_id, "quality.issue_updated", resp.model_dump())
    return resp


@router.post("/rectification-orders", response_model=RectificationOrderResponse, status_code=status.HTTP_201_CREATED)
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


@router.get("/rectification-orders/{project_id}", response_model=list[RectificationOrderResponse])
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


@router.patch("/rectification-orders/{order_id}/status", response_model=RectificationOrderResponse)
async def update_rectification_order_status(
    order_id: str,
    new_status: str = Query(..., description="pending/in_progress/completed/verified/closed"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新整改单状态（含 issue 状态同步）"""
    order = await quality_service.update_order_status(db, order_id, new_status, verifier=current_user.name)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="整改单不存在")
    await verify_project_access(project_id=order.project_id, current_user=current_user, db=db)
    resp = _order_to_response(order)
    await ws_manager.broadcast_to_project(order.project_id, "quality.order_updated", resp.model_dump())
    return resp


@router.post("/quality-assessments", response_model=QualityAssessmentResponse, status_code=status.HTTP_201_CREATED)
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


@router.get("/quality-assessments/{project_id}", response_model=list[QualityAssessmentResponse])
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


@router.post("/logs/analyze-defects")
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
