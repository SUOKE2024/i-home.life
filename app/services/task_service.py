"""任务协调服务 — 任务创建、申领、候选人排序、分配"""

import json
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.orchestrator_task import OrchestratorTask, TaskCandidate
from app.models.points import PointsAccount
from app.models.service_worker import ServiceWorker
from app.models.construction_crew import ConstructionCrew

logger = logging.getLogger(__name__)

# ── 项目类型 → 标准任务流 ──

PROJECT_TASK_FLOWS = {
    "full_renovation": [
        {"task_type": "survey", "title": "房屋勘查测量", "assigned_agent": "orchestrator", "claim_role": None, "priority": 10},
        {"task_type": "design", "title": "全案设计方案", "assigned_agent": "designer", "claim_role": "designer", "priority": 9},
        {"task_type": "budget", "title": "预算评估编制", "assigned_agent": "budget", "claim_role": None, "priority": 8},
        {"task_type": "procurement", "title": "物料采购计划", "assigned_agent": "procurement", "claim_role": "supplier", "priority": 7},
        {"task_type": "construction", "title": "施工执行管理", "assigned_agent": "construction", "claim_role": "contractor", "priority": 7},
        {"task_type": "qa_inspector", "title": "质量验收检查", "assigned_agent": "qa_inspector", "claim_role": None, "priority": 6},
        {"task_type": "settlement", "title": "项目结算对账", "assigned_agent": "settlement", "claim_role": None, "priority": 5},
    ],
    "hard_decoration": [
        {"task_type": "design", "title": "硬装设计方案", "assigned_agent": "designer", "claim_role": "designer", "priority": 9},
        {"task_type": "budget", "title": "硬装预算编制", "assigned_agent": "budget", "claim_role": None, "priority": 8},
        {"task_type": "procurement", "title": "硬装物料采购", "assigned_agent": "procurement", "claim_role": "supplier", "priority": 7},
        {"task_type": "construction", "title": "硬装施工执行", "assigned_agent": "construction", "claim_role": "contractor", "priority": 7},
        {"task_type": "qa_inspector", "title": "硬装质量验收", "assigned_agent": "qa_inspector", "claim_role": None, "priority": 6},
        {"task_type": "settlement", "title": "硬装结算", "assigned_agent": "settlement", "claim_role": None, "priority": 5},
    ],
    "soft_furnishing": [
        {"task_type": "design", "title": "软装方案设计", "assigned_agent": "designer", "claim_role": "designer", "priority": 8},
        {"task_type": "budget", "title": "软装预算", "assigned_agent": "budget", "claim_role": None, "priority": 7},
        {"task_type": "procurement", "title": "软装采购", "assigned_agent": "procurement", "claim_role": "supplier", "priority": 6},
        {"task_type": "settlement", "title": "软装结算", "assigned_agent": "settlement", "claim_role": None, "priority": 5},
    ],
    "curtain": [
        {"task_type": "design", "title": "窗帘测量与设计", "assigned_agent": "designer", "claim_role": "designer", "priority": 8},
        {"task_type": "procurement", "title": "窗帘采购定制", "assigned_agent": "procurement", "claim_role": "supplier", "priority": 7},
        {"task_type": "construction", "title": "窗帘安装施工", "assigned_agent": "construction", "claim_role": "contractor", "priority": 6},
    ],
}


async def decompose_project(
    db: AsyncSession,
    project_id: str,
    project_type: str = "full_renovation",
    created_by: str = "orchestrator",
) -> list[OrchestratorTask]:
    """将项目分解为标准任务序列"""
    flow = PROJECT_TASK_FLOWS.get(project_type, PROJECT_TASK_FLOWS["full_renovation"])

    tasks = []
    prev_task_id = None
    for step in flow:
        task = OrchestratorTask(
            project_id=project_id,
            task_type=step["task_type"],
            title=step["title"],
            assigned_agent=step["assigned_agent"],
            priority=step.get("priority", 5),
            claimable=step.get("claim_role") is not None,
            claim_role=step.get("claim_role"),
            created_by=created_by,
            status="pending",
        )
        if prev_task_id:
            task.dependencies = json.dumps([prev_task_id])
        db.add(task)
        tasks.append(task)
        prev_task_id = task.id

    await db.flush()
    return tasks


# ── 候选人排序 ──

async def rank_candidates(
    db: AsyncSession,
    task_id: str,
) -> list[TaskCandidate]:
    """为任务申领者计算综合得分并排序"""

    # 获取任务
    stmt = select(OrchestratorTask).where(OrchestratorTask.id == task_id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        return []

    # 获取所有候选人
    stmt = select(TaskCandidate).where(
        TaskCandidate.task_id == task_id,
        TaskCandidate.status == "pending",
    )
    result = await db.execute(stmt)
    candidates = list(result.scalars().all())

    for candidate in candidates:
        # 获取用户积分
        points_stmt = select(PointsAccount).where(PointsAccount.user_id == candidate.user_id)
        points_result = await db.execute(points_stmt)
        points_account = points_result.scalar_one_or_none()

        points = points_account.balance if points_account else 0
        points_level = points_account.level if points_account else "bronze"

        # 根据角色获取经验和评分
        user_stmt = select(User).where(User.id == candidate.user_id)
        user_result = await db.execute(user_stmt)
        user = user_result.scalar_one_or_none()

        experience = 0
        rating = 0.0
        completed_projects = 0

        if task.claim_role == "designer":
            worker_stmt = select(ServiceWorker).where(ServiceWorker.phone == user.phone) if user else None
            if worker_stmt:
                worker_result = await db.execute(worker_stmt)
                worker = worker_result.scalar_one_or_none()
                if worker:
                    experience = worker.years_of_experience
                    rating = worker.rating
                    completed_projects = worker.completed_projects
        elif task.claim_role == "contractor":
            crew_stmt = select(ConstructionCrew).where(ConstructionCrew.phone == user.phone) if user else None
            if crew_stmt:
                crew_result = await db.execute(crew_stmt)
                crew = crew_result.scalar_one_or_none()
                if crew:
                    experience = crew.completed_projects // 5  # 估算年数
                    rating = crew.rating
                    completed_projects = crew.completed_projects

        # 归一化计算
        max_experience = max(experience, 1)
        experience_normalized = min(experience / 15, 1.0) * 100  # 15年=满分

        rating_normalized = (rating / 5.0) * 100 if rating > 0 else 60

        max_points = max(points, 1)
        points_normalized = min(points / 5000, 1.0) * 100  # 5000分=满分

        # 综合得分 = 积分40% + 经验20% + 评分20% + 完成数20%
        composite = round(
            points_normalized * 0.40 +
            experience_normalized * 0.20 +
            rating_normalized * 0.20 +
            min(completed_projects / 200, 1.0) * 100 * 0.20,
            2,
        )

        candidate.points_score = round(points_normalized, 2)
        candidate.experience_score = round(experience_normalized, 2)
        candidate.rating_score = round(rating_normalized, 2)
        candidate.composite_score = composite
        candidate.score_breakdown = json.dumps({
            "points": points,
            "experience_years": experience,
            "rating": rating,
            "completed_projects": completed_projects,
            "level": points_level,
        })

    # 按综合得分排序
    candidates.sort(key=lambda c: c.composite_score, reverse=True)
    await db.flush()
    return candidates


# ── 任务分配 ──

async def assign_task(
    db: AsyncSession,
    task_id: str,
    user_id: str,
) -> OrchestratorTask | None:
    """将任务分配给指定用户"""
    stmt = select(OrchestratorTask).where(OrchestratorTask.id == task_id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        return None

    task.assigned_user_id = user_id
    task.status = "in_progress"
    task.started_at = datetime.now(timezone.utc)

    # 更新候选人状态
    cand_stmt = select(TaskCandidate).where(
        TaskCandidate.task_id == task_id,
        TaskCandidate.user_id == user_id,
    )
    cand_result = await db.execute(cand_stmt)
    candidate = cand_result.scalar_one_or_none()
    if candidate:
        candidate.status = "confirmed"

    # 拒绝其他候选人
    other_stmt = select(TaskCandidate).where(
        TaskCandidate.task_id == task_id,
        TaskCandidate.user_id != user_id,
    )
    other_result = await db.execute(other_stmt)
    for other in other_result.scalars().all():
        other.status = "rejected"

    await db.flush()
    return task


async def complete_task(
    db: AsyncSession,
    task_id: str,
    result: dict | None = None,
) -> OrchestratorTask | None:
    """完成任务"""
    stmt = select(OrchestratorTask).where(OrchestratorTask.id == task_id)
    result_obj = await db.execute(stmt)
    task = result_obj.scalar_one_or_none()
    if not task:
        return None

    task.status = "completed"
    task.completed_at = datetime.now(timezone.utc)
    task.result = json.dumps(result, ensure_ascii=False) if result else None

    await db.flush()
    return task


async def get_task_pool(
    db: AsyncSession,
    claim_role: str | None = None,
    status: str = "pending",
    limit: int = 50,
) -> list[OrchestratorTask]:
    """获取可申领的任务池"""
    conditions = [
        OrchestratorTask.claimable == True,
        OrchestratorTask.status == status,
    ]
    if claim_role:
        conditions.append(OrchestratorTask.claim_role == claim_role)

    stmt = (
        select(OrchestratorTask)
        .where(*conditions)
        .order_by(desc(OrchestratorTask.priority), desc(OrchestratorTask.created_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
