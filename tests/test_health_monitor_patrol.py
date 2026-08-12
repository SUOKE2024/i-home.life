"""health_monitor 巡检 `_trigger_alerts` 去重回归测试。

背景（2026-08-12 生产巡检报错）：progress_alerts 表对 (project_id, alert_type,
status) 无唯一约束，同组合可能存在多条 active 记录（历史数据/并发巡检/种子数据
重复注入）。原实现用 `existing.scalar_one_or_none()` 判断「是否已有同类活跃预警」，
遇多条即抛 `MultipleResultsFound`，导致 health_monitor 巡检每轮对坏项目报
`health_check_project_error` 并中断该项目的预警生成。

修复：去重查询改为 `select(ProgressAlert.id).limit(1)` + `scalar()`——只需「存在即
跳过」，不要求唯一。本测试覆盖多条 active 预警场景，验证不抛错且不重复创建。
"""

import pytest
from sqlalchemy import func, select

from app.models.project import Project
from app.models.user import User
from app.services.health_monitor import (
    HealthCheckResult,
    HealthStatus,
    health_monitor,
)


async def _create_project_with_owner(db_session) -> Project:
    """创建测试用户 + 项目并返回 Project 实例。"""
    user = User(phone="13900009001", name="巡检测试", hashed_password="x", role="homeowner")
    db_session.add(user)
    await db_session.flush()
    project = Project(
        name="巡检去重测试项目",
        total_area=100.0,
        status="active",
        phase="construction",
        project_type="full_renovation",
        source="manual",
        owner_id=user.id,
    )
    db_session.add(project)
    await db_session.flush()
    return project


def _make_unhealthy_result(project_id: str) -> HealthCheckResult:
    """构造一条会触发预警的健康检查结果（非 NORMAL 级）。"""
    return HealthCheckResult(
        project_id=project_id,
        project_name="巡检去重测试项目",
        health_score=40.0,
        status=HealthStatus.CRITICAL,
        total_milestones=3,
        completed_milestones=0,
        delayed_milestones=1,
        planned_progress=60.0,
        actual_progress=10.0,
        deviation=-50.0,
        alerts=[{
            "level": "critical",
            "reason": "2 个里程碑已超期未完成",
            "project_id": project_id,
            "health_score": 40.0,
            "planned": 60.0,
            "actual": 10.0,
            "delayed": 1,
            "overdue": 2,
        }],
    )


@pytest.mark.asyncio
async def test_trigger_alerts_with_duplicate_active_alerts_no_crash(db_session):
    """多条 active 同类型预警时，_trigger_alerts 不应抛 MultipleResultsFound。

    回归：生产曾因 2 条 (project, health_check, active) 记录致
    scalar_one_or_none() 抛错，巡检中断。修复后应「存在即跳过」。
    """
    from app.models.progress_alert import ProgressAlert

    project = await _create_project_with_owner(db_session)

    # 预置 2 条同组合 active 预警（模拟历史重复/并发巡检产生的脏数据）
    for _ in range(2):
        db_session.add(ProgressAlert(
            project_id=project.id,
            alert_type="health_check",
            status="active",
            severity="medium",
            phase="overall",
            message="施工健康预警: 测试",
            progress_percent=10.0,
        ))
    await db_session.commit()

    result = _make_unhealthy_result(project.id)
    # 不应抛异常（修复前 MultipleResultsFound）
    await health_monitor._trigger_alerts(db_session, project, result)

    # 仍只有预置的 2 条——去重生效，未重复创建
    count = await db_session.execute(
        select(func.count()).select_from(ProgressAlert).where(
            ProgressAlert.project_id == project.id,
            ProgressAlert.alert_type == "health_check",
            ProgressAlert.status == "active",
        )
    )
    assert count.scalar() == 2


@pytest.mark.asyncio
async def test_trigger_alerts_creates_when_none_active(db_session):
    """无 active 预警时应正常创建一条（不误伤正常路径）。"""
    from app.models.progress_alert import ProgressAlert

    project = await _create_project_with_owner(db_session)
    await db_session.commit()

    result = _make_unhealthy_result(project.id)
    await health_monitor._trigger_alerts(db_session, project, result)

    count = await db_session.execute(
        select(func.count()).select_from(ProgressAlert).where(
            ProgressAlert.project_id == project.id,
            ProgressAlert.alert_type == "health_check",
            ProgressAlert.status == "active",
        )
    )
    assert count.scalar() == 1


@pytest.mark.asyncio
async def test_trigger_alerts_skips_when_single_active_exists(db_session):
    """已有 1 条 active 预警时跳过，不重复创建（原语义保持）。"""
    from app.models.progress_alert import ProgressAlert

    project = await _create_project_with_owner(db_session)
    db_session.add(ProgressAlert(
        project_id=project.id,
        alert_type="health_check",
        status="active",
        severity="medium",
        phase="overall",
        message="施工健康预警: 已存在",
        progress_percent=10.0,
    ))
    await db_session.commit()

    result = _make_unhealthy_result(project.id)
    await health_monitor._trigger_alerts(db_session, project, result)

    count = await db_session.execute(
        select(func.count()).select_from(ProgressAlert).where(
            ProgressAlert.project_id == project.id,
            ProgressAlert.alert_type == "health_check",
            ProgressAlert.status == "active",
        )
    )
    assert count.scalar() == 1
