"""任务协调 API — 任务池、申领、候选人排序、分配、完成"""
import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.orchestrator_task import OrchestratorTask, TaskCandidate
from app.auth import get_current_user
from app.schemas.task import (
    TaskCreateRequest, TaskClaimRequest, TaskAssignRequest,
    TaskResponse, TaskCandidateResponse, TaskListResponse,
)
from app.services import task_service
from app.services import points_service
from app.ws import ws_manager

router = APIRouter(prefix="/tasks", tags=["任务协调"])


async def _verify_project_owner(db: AsyncSession, project_id: str, user: User) -> Project:
    """校验当前用户是项目所有者（admin 角色豁免），否则抛 403"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if user.role != "admin" and project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    return project


async def _verify_task_owner(db: AsyncSession, task_id: str, user: User) -> OrchestratorTask:
    """校验任务存在且其所属项目归当前用户所有（admin 豁免），否则抛 403/404"""
    task = await db.get(OrchestratorTask, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    await _verify_project_owner(db, task.project_id, user)
    return task


def _task_to_response(task: OrchestratorTask, candidates: list | None = None) -> TaskResponse:
    deps = json.loads(task.dependencies) if task.dependencies else None
    result = json.loads(task.result) if task.result else None
    assigned_name = task.assigned_user.name if task.assigned_user else None
    cand_resp = None
    if candidates:
        cand_resp = [
            TaskCandidateResponse(
                id=c.id, task_id=c.task_id, user_id=c.user_id,
                user_name=None, user_avatar=None,
                points_score=c.points_score, experience_score=c.experience_score,
                rating_score=c.rating_score, composite_score=c.composite_score,
                score_breakdown=json.loads(c.score_breakdown) if c.score_breakdown else None,
                status=c.status,
            )
            for c in candidates
        ]
    return TaskResponse(
        id=task.id, project_id=task.project_id, task_type=task.task_type,
        title=task.title, description=task.description,
        assigned_agent=task.assigned_agent,
        assigned_user_id=task.assigned_user_id,
        assigned_user_name=assigned_name,
        priority=task.priority, status=task.status,
        parent_task_id=task.parent_task_id, dependencies=deps,
        claimable=task.claimable, claim_deadline=task.claim_deadline,
        claim_role=task.claim_role, result=result,
        created_by=task.created_by, created_at=task.created_at,
        started_at=task.started_at, completed_at=task.completed_at,
        candidates=cand_resp,
    )


@router.post("", response_model=TaskResponse)
async def create_task(
    data: TaskCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建任务（业主或总控Agent）"""
    await _verify_project_owner(db, data.project_id, current_user)
    task = OrchestratorTask(
        project_id=data.project_id,
        task_type=data.task_type,
        title=data.title,
        description=data.description,
        assigned_agent=data.assigned_agent,
        priority=data.priority,
        parent_task_id=data.parent_task_id,
        dependencies=json.dumps(data.dependencies) if data.dependencies else None,
        claimable=data.claimable,
        claim_deadline=data.claim_deadline,
        claim_role=data.claim_role,
        created_by=current_user.id,
        status="pending",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # WebSocket 推送新任务
    await ws_manager.broadcast_to_project(data.project_id, "task.created", {
        "task_id": task.id,
        "title": task.title,
        "task_type": task.task_type,
        "claim_role": task.claim_role,
        "priority": task.priority,
    })

    return _task_to_response(task)


@router.get("/pool", response_model=TaskListResponse)
async def get_task_pool(
    claim_role: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, le=100),
):
    """获取可申领的任务池"""
    tasks = await task_service.get_task_pool(db, claim_role=claim_role, limit=limit)
    return TaskListResponse(
        tasks=[_task_to_response(t) for t in tasks],
        total=len(tasks),
    )


@router.get("/project/{project_id}", response_model=TaskListResponse)
async def get_project_tasks(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取项目的所有任务"""
    await _verify_project_owner(db, project_id, current_user)
    stmt = (
        select(OrchestratorTask)
        .where(OrchestratorTask.project_id == project_id)
        .order_by(OrchestratorTask.created_at.desc())
    )
    result = await db.execute(stmt)
    tasks = list(result.scalars().all())
    return TaskListResponse(tasks=[_task_to_response(t) for t in tasks], total=len(tasks))


@router.get("/mine", response_model=TaskListResponse)
async def get_my_tasks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取我的任务（已接取/进行中）"""
    stmt = (
        select(OrchestratorTask)
        .where(
            OrchestratorTask.assigned_user_id == current_user.id,
            OrchestratorTask.status.in_(["claimed", "in_progress"]),
        )
        .order_by(desc(OrchestratorTask.priority))
    )
    result = await db.execute(stmt)
    tasks = list(result.scalars().all())
    return TaskListResponse(tasks=[_task_to_response(t) for t in tasks], total=len(tasks))


@router.post("/claim", response_model=TaskResponse)
async def claim_task(
    data: TaskClaimRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """申领任务（设计师/工长/供应商）"""
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="请先完成实名认证后再申领任务")

    stmt = select(OrchestratorTask).where(OrchestratorTask.id == data.task_id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.claimable:
        raise HTTPException(status_code=400, detail="该任务不允许申领")
    if task.status != "pending":
        raise HTTPException(status_code=400, detail="任务已被申领或已完成")

    # 检查角色匹配
    if task.claim_role and current_user.role != task.claim_role:
        raise HTTPException(status_code=403, detail=f"该任务仅限{task.claim_role}申领")

    # 创建候选人记录
    existing = await db.execute(
        select(TaskCandidate).where(
            TaskCandidate.task_id == task.id,
            TaskCandidate.user_id == current_user.id,
        )
    )
    if existing.scalar_one_or_none():
        return _task_to_response(task)

    candidate = TaskCandidate(
        task_id=task.id,
        user_id=current_user.id,
        status="pending",
    )
    db.add(candidate)
    task.status = "claimed"
    await db.commit()

    # 重新排序所有候选人
    candidates = await task_service.rank_candidates(db, task.id)

    # 通过 WebSocket 推送候选人更新
    await ws_manager.broadcast_to_project(task.project_id, "task.candidate_update", {
        "task_id": task.id,
        "candidate_count": len(candidates),
    })

    return _task_to_response(task, candidates)


@router.get("/{task_id}/candidates", response_model=list[TaskCandidateResponse])
async def get_task_candidates(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查看任务候选人（按积分/经验/评分排序）"""
    await _verify_task_owner(db, task_id, current_user)
    candidates = await task_service.rank_candidates(db, task_id)
    return [
        TaskCandidateResponse(
            id=c.id, task_id=c.task_id, user_id=c.user_id,
            user_name=None, user_avatar=None,
            points_score=c.points_score, experience_score=c.experience_score,
            rating_score=c.rating_score, composite_score=c.composite_score,
            score_breakdown=json.loads(c.score_breakdown) if c.score_breakdown else None,
            status=c.status,
        )
        for c in candidates
    ]


@router.post("/assign", response_model=TaskResponse)
async def assign_task(
    data: TaskAssignRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """业主选择候选人分配任务"""
    await _verify_task_owner(db, data.task_id, current_user)
    task = await task_service.assign_task(db, task_id=data.task_id, user_id=data.user_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 奖励积分：申领成功
    await points_service.earn_points(db, data.user_id, "task_claim")

    # WebSocket 推送任务分配
    await ws_manager.broadcast_to_project(task.project_id, "task.assigned", {
        "task_id": task.id,
        "assigned_user_id": data.user_id,
    })

    return _task_to_response(task)


@router.post("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: str,
    result: dict | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """完成任务（项目所有者或被分配者）"""
    task = await db.get(OrchestratorTask, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    # 项目所有者（或 admin）可完成；被分配该任务的施工方也可完成
    if current_user.role != "admin":
        project = await db.get(Project, task.project_id)
        if not project or (
            project.owner_id != current_user.id
            and task.assigned_user_id != current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权完成该任务",
            )
    task = await task_service.complete_task(db, task_id=task_id, result=result)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    # 奖励积分：完成任务
    if task.assigned_user_id:
        await points_service.earn_points(
            db, task.assigned_user_id, "task_complete",
            reference_id=task_id,
            description=f"完成任务: {task.title}",
        )

    # WebSocket 推送任务完成
    await ws_manager.broadcast_to_project(task.project_id, "task.completed", {
        "task_id": task.id,
        "task_type": task.task_type,
    })

    return _task_to_response(task)
