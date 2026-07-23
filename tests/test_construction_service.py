"""施工服务层单元测试 — WBS 生成 / 任务依赖 / 工期估算 / 关键路径 / AI 预测"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Project, Floor, Room, ConstructionTask
from app.services.construction_service import (
    generate_wbs,
    add_task_dependency,
    estimate_duration,
    calculate_critical_path,
    ai_predict_duration,
)


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """创建一个测试用户"""
    user = User(
        phone="13900000101",
        name="施工测试用户",
        hashed_password="hashed_test_password",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_project(db_session: AsyncSession, test_user: User):
    """创建一个测试项目，含 total_area"""
    project = Project(
        name="施工测试项目",
        total_area=120.0,
        owner_id=test_user.id,
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest.fixture
async def test_project_with_floors(db_session: AsyncSession, test_user: User):
    """创建含楼层和房间的测试项目"""
    project = Project(
        name="有楼层施工项目",
        total_area=100.0,
        owner_id=test_user.id,
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    floor = Floor(project_id=project.id, name="1F", floor_number=1, area=100.0)
    db_session.add(floor)
    await db_session.commit()
    await db_session.refresh(floor)

    rooms = [
        Room(floor_id=floor.id, name="客厅", room_type="living", area=35.0),
        Room(floor_id=floor.id, name="主卧", room_type="bedroom", area=20.0),
        Room(floor_id=floor.id, name="厨房", room_type="kitchen", area=10.0),
    ]
    for r in rooms:
        db_session.add(r)
    await db_session.commit()

    return project


@pytest.mark.asyncio
async def test_generate_wbs(db_session: AsyncSession, test_project: Project):
    """测试 generate_wbs 创建 8 个阶段并建立正确的依赖关系"""
    result = await generate_wbs(db_session, test_project.id)

    assert result["project_id"] == test_project.id
    assert result["total_phases"] == 8
    assert result["project_area_sqm"] > 0

    phases = result["phases"]
    phase_names = [p["name"] for p in phases]
    assert "拆除" in phase_names
    assert "水电改造" in phase_names
    assert "防水" in phase_names
    assert "瓦工" in phase_names
    assert "木工" in phase_names
    assert "油漆" in phase_names
    assert "安装" in phase_names
    assert "竣工验收" in phase_names

    # 验证依赖关系：每个阶段（除第一个）应有 predecessor_id
    phase_by_name = {p["name"]: p for p in phases}
    demo = phase_by_name["拆除"]
    assert demo["predecessor_id"] is None  # 拆除无前置

    electrical = phase_by_name["水电改造"]
    assert electrical["predecessor_id"] == demo["id"]

    waterproof = phase_by_name["防水"]
    assert waterproof["predecessor_id"] == electrical["id"]

    masonry = phase_by_name["瓦工"]
    assert masonry["predecessor_id"] == waterproof["id"]

    carpentry = phase_by_name["木工"]
    assert carpentry["predecessor_id"] == masonry["id"]

    painting = phase_by_name["油漆"]
    assert painting["predecessor_id"] == carpentry["id"]

    install = phase_by_name["安装"]
    assert install["predecessor_id"] == painting["id"]

    inspection = phase_by_name["竣工验收"]
    assert inspection["predecessor_id"] == install["id"]

    # 验证所有任务状态为 pending
    for p in phases:
        assert p["status"] == "pending"

    # 验证优先级递增
    priorities = [p["priority"] for p in phases]
    assert priorities == sorted(priorities)


@pytest.mark.asyncio
async def test_generate_wbs_idempotent(db_session: AsyncSession, test_project: Project):
    """测试重复调用 generate_wbs 不会重复创建任务"""
    result1 = await generate_wbs(db_session, test_project.id)
    assert result1["total_phases"] == 8

    # 第二次调用应返回已存在的 WBS
    result2 = await generate_wbs(db_session, test_project.id)
    assert result2["total_phases"] == 8
    assert "WBS 已存在" in result2["message"]


@pytest.mark.asyncio
async def test_generate_wbs_project_not_found(db_session: AsyncSession):
    """测试不存在的项目应抛出 ValueError"""
    with pytest.raises(ValueError, match="项目不存在"):
        await generate_wbs(db_session, "non-existent-project-id")


@pytest.mark.asyncio
async def test_add_task_dependency(db_session: AsyncSession, test_project: Project):
    """测试在两个 WBS 任务之间添加依赖关系"""
    # 创建两个任务
    parent = ConstructionTask(
        project_id=test_project.id,
        name="前置任务",
        phase="demolition",
        status="pending",
        priority=1,
    )
    child = ConstructionTask(
        project_id=test_project.id,
        name="后续任务",
        phase="water_electricity",
        status="pending",
        priority=2,
    )
    db_session.add_all([parent, child])
    await db_session.commit()
    await db_session.refresh(parent)
    await db_session.refresh(child)

    # 添加依赖
    result = await add_task_dependency(db_session, parent.id, child.id)
    assert result is not None
    assert result.predecessor_id == parent.id

    # 重新查询确认
    await db_session.refresh(child)
    assert child.predecessor_id == parent.id


@pytest.mark.asyncio
async def test_add_task_dependency_self_dependency(db_session: AsyncSession, test_project: Project):
    """测试任务不能依赖自身"""
    task = ConstructionTask(
        project_id=test_project.id,
        name="自依赖任务",
        phase="demolition",
        status="pending",
        priority=1,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    with pytest.raises(ValueError, match="任务不能依赖自身"):
        await add_task_dependency(db_session, task.id, task.id)


@pytest.mark.asyncio
async def test_circular_dependency_prevention(db_session: AsyncSession, test_project: Project):
    """测试添加循环依赖应抛出 ValueError"""
    parent = ConstructionTask(
        project_id=test_project.id,
        name="任务A",
        phase="demolition",
        status="pending",
        priority=1,
    )
    child = ConstructionTask(
        project_id=test_project.id,
        name="任务B",
        phase="water_electricity",
        status="pending",
        priority=2,
        predecessor_id=None,
    )
    db_session.add_all([parent, child])
    await db_session.commit()
    await db_session.refresh(parent)
    await db_session.refresh(child)

    # B 依赖 A（正常）
    await add_task_dependency(db_session, parent.id, child.id)
    await db_session.refresh(parent)
    await db_session.refresh(child)
    assert child.predecessor_id == parent.id

    # 尝试让 A 依赖 B（形成循环）
    with pytest.raises(ValueError, match="不能形成循环依赖"):
        await add_task_dependency(db_session, child.id, parent.id)


@pytest.mark.asyncio
async def test_add_task_dependency_parent_not_found(db_session: AsyncSession, test_project: Project):
    """测试前置任务不存在应抛出 ValueError"""
    child = ConstructionTask(
        project_id=test_project.id,
        name="孤立任务",
        phase="demolition",
        status="pending",
        priority=1,
    )
    db_session.add(child)
    await db_session.commit()
    await db_session.refresh(child)

    with pytest.raises(ValueError, match="前置任务不存在"):
        await add_task_dependency(db_session, "non-existent-parent-id", child.id)


@pytest.mark.asyncio
async def test_estimate_duration(db_session: AsyncSession, test_project: Project):
    """测试工期估算基于项目面积"""
    task = ConstructionTask(
        project_id=test_project.id,
        name="瓦工任务",
        phase="masonry",
        status="pending",
        priority=1,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    result = await estimate_duration(db_session, task.id)

    assert result["task_id"] == task.id
    assert result["task_name"] == task.name
    assert result["phase"] == task.phase
    assert result["project_area_sqm"] > 0
    assert result["estimated_min_days"] > 0
    assert result["estimated_max_days"] > 0
    assert result["estimated_min_days"] <= result["estimated_max_days"]
    assert result["recommended_days"] == result["estimated_max_days"]
    # masonry 标准 (5, 7) 天，项目面积 120，area_ratio = 1.2
    # estimated_max = 7 * 1.2 = 8.4
    assert result["estimated_max_days"] == pytest.approx(8.4, abs=0.1)


@pytest.mark.asyncio
async def test_estimate_duration_large_area(db_session: AsyncSession, test_user: User):
    """测试大面积项目工期放大"""
    project = Project(
        name="大面积项目",
        total_area=300.0,
        owner_id=test_user.id,
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    task = ConstructionTask(
        project_id=project.id,
        name="大面积瓦工",
        phase="masonry",
        status="pending",
        priority=1,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    result = await estimate_duration(db_session, task.id)

    # 300㎡ 面积比 100㎡ 大 3 倍，工期应相应放大
    assert result["project_area_sqm"] == 300.0
    # masonry 标准 5-7 天，乘以 3.0 面积比
    assert result["estimated_min_days"] == pytest.approx(15.0, abs=0.1)
    assert result["estimated_max_days"] == pytest.approx(21.0, abs=0.1)


@pytest.mark.asyncio
async def test_estimate_duration_task_not_found(db_session: AsyncSession):
    """测试不存在的任务应抛出 ValueError"""
    with pytest.raises(ValueError, match="任务不存在"):
        await estimate_duration(db_session, "non-existent-task-id")


@pytest.mark.asyncio
async def test_calculate_critical_path(db_session: AsyncSession, test_project: Project):
    """测试关键路径计算 — 手动创建依赖链验证 CPM 算法"""
    # 手动创建任务链（使用模型约束中合法的 phase）
    # 阶段: demolition → masonry → carpentry → painting → installation
    tasks = []
    for idx, (name, phase) in enumerate([
        ("拆除", "demolition"),
        ("瓦工", "masonry"),
        ("木工", "carpentry"),
        ("油漆", "painting"),
        ("安装", "installation"),
    ]):
        task = ConstructionTask(
            project_id=test_project.id,
            name=name,
            phase=phase,
            status="pending",
            priority=idx + 1,
        )
        db_session.add(task)
        await db_session.flush()
        tasks.append(task)

    # 建立依赖链
    for i in range(1, len(tasks)):
        tasks[i].predecessor_id = tasks[i - 1].id
    await db_session.commit()
    for t in tasks:
        await db_session.refresh(t)

    result = await calculate_critical_path(db_session, test_project.id)

    assert result["project_id"] == test_project.id
    assert result["total_duration_days"] > 0
    assert result["critical_path_length"] > 0

    # 验证关键路径上的任务
    critical_path = result["critical_path"]
    assert len(critical_path) > 0
    for task in critical_path:
        assert task["is_critical"] is True
        assert "id" in task
        assert "name" in task
        assert "duration_days" in task
        assert "earliest_finish" in task
        assert "slack_days" in task
        assert task["slack_days"] == pytest.approx(0.0, abs=0.1)

    # 验证 all_tasks 包含所有任务
    all_tasks = result["all_tasks"]
    assert len(all_tasks) >= result["critical_path_length"]
    for task in all_tasks:
        assert "is_critical" in task


@pytest.mark.asyncio
async def test_calculate_critical_path_no_tasks(db_session: AsyncSession, test_project: Project):
    """测试无任务时应抛出 ValueError"""
    with pytest.raises(ValueError, match="没有施工任务"):
        await calculate_critical_path(db_session, test_project.id)


@pytest.mark.asyncio
async def test_ai_predict_duration_no_tasks(db_session: AsyncSession, test_project: Project):
    """测试 AI 预测 — 无 WBS 任务时应返回错误信息"""
    result = await ai_predict_duration(db_session, test_project.id)
    assert "error" in result
    assert "Run generate_wbs" in result["error"] or "No WBS tasks" in result["error"]


@pytest.mark.asyncio
async def test_ai_predict_duration_project_not_found(db_session: AsyncSession):
    """测试 AI 预测 — 项目不存在应返回错误"""
    result = await ai_predict_duration(db_session, "non-existent-project-id")
    assert "error" in result


@pytest.mark.asyncio
async def test_ai_predict_duration_with_wbs(db_session: AsyncSession, test_project_with_floors: Project):
    """测试 AI 预测 — 有 WBS 任务时应返回预期字段"""
    # 先生成 WBS
    await generate_wbs(db_session, test_project_with_floors.id)

    result = await ai_predict_duration(db_session, test_project_with_floors.id)

    # 返回结构应包含关键字段
    assert result["project_id"] == test_project_with_floors.id
    assert "predicted_total_days" in result
    if isinstance(result["predicted_total_days"], (int, float)):
        assert result["predicted_total_days"] > 0
    assert "optimistic_days" in result
    assert "pessimistic_days" in result
    assert "confidence" in result
    assert "phase_predictions" in result
    assert "sample_size" in result
    assert "risk_factors" in result

    # 阶段预测应为列表
    phase_predictions = result["phase_predictions"]
    if len(phase_predictions) > 0:
        pred = phase_predictions[0]
        assert "phase" in pred
        assert "predicted" in pred
