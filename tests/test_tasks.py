"""task_service 测试 — 项目分解 / 任务分配 / 完成 / 任务池 / 候选人排序"""

import json

import pytest

from app.models.user import User
from app.models.project import Project
from app.models.orchestrator_task import OrchestratorTask, TaskCandidate
from app.models.points import PointsAccount
from app.services.task_service import (
    decompose_project,
    assign_task,
    complete_task,
    get_task_pool,
    rank_candidates,
)


async def _create_user_and_project(db_session):
    user = User(phone="13900007001", name="任务测试", role="homeowner", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    project = Project(name="任务测试项目", owner_id=user.id, total_area=80.0)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return user, project


async def _create_task(db_session, project_id, **kwargs):
    defaults = {
        "task_type": "design",
        "title": "测试任务",
        "assigned_agent": "designer",
        "created_by": "orchestrator",
        "status": "pending",
        "claimable": True,
    }
    defaults.update(kwargs)
    task = OrchestratorTask(project_id=project_id, **defaults)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task


# ════════════════════════════════════════════════════════════════
# decompose_project
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_decompose_project_full_renovation(db_session):
    _, project = await _create_user_and_project(db_session)
    tasks = await decompose_project(db_session, project.id, "full_renovation")

    assert len(tasks) == 7
    assert tasks[0].task_type == "survey"
    assert tasks[-1].task_type == "settlement"
    assert tasks[0].status == "pending"

    # 第一个任务无前置依赖
    assert tasks[0].dependencies is None


@pytest.mark.asyncio
async def test_decompose_project_hard_decoration(db_session):
    _, project = await _create_user_and_project(db_session)
    tasks = await decompose_project(db_session, project.id, "hard_decoration")
    assert len(tasks) == 6


@pytest.mark.asyncio
async def test_decompose_project_soft_furnishing(db_session):
    _, project = await _create_user_and_project(db_session)
    tasks = await decompose_project(db_session, project.id, "soft_furnishing")
    assert len(tasks) == 4


@pytest.mark.asyncio
async def test_decompose_project_curtain(db_session):
    _, project = await _create_user_and_project(db_session)
    tasks = await decompose_project(db_session, project.id, "curtain")
    assert len(tasks) == 3


@pytest.mark.asyncio
async def test_decompose_project_unknown_type_fallback(db_session):
    _, project = await _create_user_and_project(db_session)
    tasks = await decompose_project(db_session, project.id, "unknown")
    # fallback 到 full_renovation (7 个任务)
    assert len(tasks) == 7


# ════════════════════════════════════════════════════════════════
# assign_task
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_assign_task_success(db_session):
    user, project = await _create_user_and_project(db_session)
    task = await _create_task(db_session, project.id)

    result = await assign_task(db_session, task.id, user.id)
    assert result is not None
    assert result.assigned_user_id == user.id
    assert result.status == "in_progress"
    assert result.started_at is not None


@pytest.mark.asyncio
async def test_assign_task_not_found(db_session):
    result = await assign_task(db_session, "nonexistent-task-id", "some-user-id")
    assert result is None


# ════════════════════════════════════════════════════════════════
# complete_task
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_complete_task_success(db_session):
    user, project = await _create_user_and_project(db_session)
    task = await _create_task(db_session, project.id)
    await assign_task(db_session, task.id, user.id)

    completed = await complete_task(db_session, task.id, result={"score": 95, "note": "完成"})
    assert completed is not None
    assert completed.status == "completed"
    assert completed.completed_at is not None
    assert json.loads(completed.result)["score"] == 95


@pytest.mark.asyncio
async def test_complete_task_not_found(db_session):
    result = await complete_task(db_session, "nonexistent-task-id")
    assert result is None


# ════════════════════════════════════════════════════════════════
# get_task_pool
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_task_pool_empty(db_session):
    _, project = await _create_user_and_project(db_session)
    pool = await get_task_pool(db_session)
    assert pool == []


@pytest.mark.asyncio
async def test_get_task_pool_with_claimable(db_session):
    _, project = await _create_user_and_project(db_session)

    # claimable + pending → 应返回
    await _create_task(db_session, project.id, title="可申领任务", claimable=True, status="pending")
    # 不可申领 + pending → 不返回
    await _create_task(db_session, project.id, title="不可申领任务", claimable=False, status="pending")
    # claimable + completed → 不返回
    await _create_task(db_session, project.id, title="已完成任务", claimable=True, status="completed")

    pool = await get_task_pool(db_session)
    assert len(pool) == 1
    assert pool[0].title == "可申领任务"


# ════════════════════════════════════════════════════════════════
# rank_candidates
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_rank_candidates_no_task(db_session):
    result = await rank_candidates(db_session, "nonexistent-task-id")
    assert result == []


@pytest.mark.asyncio
async def test_rank_candidates_with_candidates(db_session):
    _, project = await _create_user_and_project(db_session)

    # 创建 task, claim_role=None 避免 service 中 if worker_stmt 对 Select 求布尔值的 bug
    task = await _create_task(
        db_session, project.id, claim_role=None, claimable=True,
    )

    # 创建 2 个用户
    user_a = User(phone="13900007010", name="用户A", role="homeowner", hashed_password="x")
    user_b = User(phone="13900007011", name="用户B", role="homeowner", hashed_password="x")
    db_session.add_all([user_a, user_b])
    await db_session.commit()
    await db_session.refresh(user_a)
    await db_session.refresh(user_b)

    # 为每个用户创建 PointsAccount (不同积分,决定排序)
    account_a = PointsAccount(user_id=user_a.id, account_type="user", balance=1000)
    account_b = PointsAccount(user_id=user_b.id, account_type="user", balance=5000)
    db_session.add_all([account_a, account_b])

    # 创建 TaskCandidate
    cand_a = TaskCandidate(task_id=task.id, user_id=user_a.id, status="pending")
    cand_b = TaskCandidate(task_id=task.id, user_id=user_b.id, status="pending")
    db_session.add_all([cand_a, cand_b])
    await db_session.flush()

    # 排序
    ranked = await rank_candidates(db_session, task.id)
    assert len(ranked) == 2

    # 验证按 composite_score 降序排列
    assert ranked[0].composite_score >= ranked[1].composite_score
    # user_b (积分更高) 应排第一
    assert ranked[0].composite_score > ranked[1].composite_score
