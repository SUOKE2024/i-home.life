"""F32 场景编辑 API 测试

覆盖端点:
- POST /api/scene-automation/scenes
- GET  /api/scene-automation/scenes/{project_id}
- PATCH /api/scene-automation/scenes/{id}
- DELETE /api/scene-automation/scenes/{id}
"""
import uuid
import pytest
from httpx import AsyncClient


async def _create_project(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": f"场景测试项目-{uuid.uuid4().hex[:6]}", "total_area": 100.0},
        headers=headers,
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_scenes_unauthorized(client: AsyncClient):
    """未认证用户无法访问场景"""
    resp = await client.get("/api/scene-automation/scenes/fake-id")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_scene(auth_headers: dict, client: AsyncClient):
    """创建场景自动化"""
    project_id = await _create_project(client, auth_headers)
    resp = await client.post(
        "/api/scene-automation/scenes",
        json={
            "project_id": project_id,
            "name": "回家模式",
            "trigger_type": "schedule",
            "trigger_config": {"time": "18:00", "days": ["mon", "tue", "wed", "thu", "fri"]},
            "actions": [{"device": "light", "command": "on", "params": {"brightness": 80}}],
        },
        headers=auth_headers,
    )
    assert resp.status_code in (200, 201)


@pytest.mark.asyncio
async def test_list_scenes(auth_headers: dict, client: AsyncClient):
    """列出项目场景"""
    project_id = await _create_project(client, auth_headers)
    await client.post(
        "/api/scene-automation/scenes",
        json={
            "project_id": project_id, "name": "离家模式",
            "trigger_type": "manual", "actions": [{"device": "all", "command": "off"}],
        },
        headers=auth_headers,
    )
    resp = await client.get(f"/api/scene-automation/scenes/project/{project_id}", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_scene(auth_headers: dict, client: AsyncClient):
    """更新场景"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/scene-automation/scenes",
        json={
            "project_id": project_id, "name": "睡眠模式",
            "trigger_type": "manual", "actions": [{"device": "curtain", "command": "close"}],
        },
        headers=auth_headers,
    )
    scene_id = create_resp.json()["id"]
    resp = await client.patch(
        f"/api/scene-automation/scenes/{scene_id}",
        json={"name": "深度睡眠模式"},
        headers=auth_headers,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_scene(auth_headers: dict, client: AsyncClient):
    """删除场景"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/scene-automation/scenes",
        json={
            "project_id": project_id, "name": "待删除场景",
            "trigger_type": "manual", "actions": [],
        },
        headers=auth_headers,
    )
    scene_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/scene-automation/scenes/{scene_id}", headers=auth_headers)
    assert resp.status_code in (200, 204)


@pytest.mark.asyncio
async def test_cross_user_scene_access(auth_headers: dict, client: AsyncClient):
    """其他用户无法操作非自己项目的场景"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/scene-automation/scenes",
        json={
            "project_id": project_id, "name": "观影模式",
            "trigger_type": "manual", "actions": [],
        },
        headers=auth_headers,
    )
    scene_id = create_resp.json()["id"]
    reg = await client.post(
        "/api/auth/register",
        json={"phone": f"1395501{uuid.uuid4().int % 10000:04d}", "name": "他人", "password": "test123456"},
    )
    other_headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    resp = await client.patch(
        f"/api/scene-automation/scenes/{scene_id}",
        json={"name": "hacked"},
        headers=other_headers,
    )
    assert resp.status_code in (403, 404)


# ── 传感器实时触发（check_sensor_triggers）──


async def _create_sensor_scene(db_session, user_id: str, project_id: str, condition: dict) -> str:
    from app.models.scene_automation import SceneAutomation
    scene = SceneAutomation(
        project_id=project_id,
        scene_name="传感器联动",
        scene_type="triggered",
        trigger_condition={"type": "sensor", "condition": condition},
        actions=[{"device_id": "light-1", "action": "turn_on", "params": {}}],
        enabled=True,
    )
    db_session.add(scene)
    await db_session.commit()
    await db_session.refresh(scene)
    return scene.id


@pytest.mark.asyncio
async def test_check_sensor_triggers_hit(db_session):
    """传感器数据命中场景条件：返回触发列表并写入 scene_behavior_logs"""
    from app.models.user import User
    from app.models.project import Project
    from app.models.scene_behavior import SceneBehaviorLog
    from sqlalchemy import select
    from app.services.scene_automation_service import check_sensor_triggers

    user = User(phone="13955010101", name="传感器测试", role="homeowner", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    project = Project(name="传感器项目", owner_id=user.id, total_area=80.0)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    scene_id = await _create_sensor_scene(
        db_session, user.id, project.id,
        {"temperature": {"gt": 28}, "motion_detected": True},
    )

    triggered = await check_sensor_triggers(
        db_session,
        user_id=user.id,
        ambient_data={"temperature": 30.5, "motion_detected": True, "light_lux": 0},
    )

    assert len(triggered) == 1
    assert triggered[0]["scene_id"] == scene_id
    assert triggered[0]["action_status"] == "pending"  # 生态桥接未接入，诚实标注

    # 触发日志真实落库
    result = await db_session.execute(
        select(SceneBehaviorLog).where(SceneBehaviorLog.scene_id == scene_id)
    )
    logs = list(result.scalars().all())
    assert len(logs) == 1
    assert logs[0].action_type == "sensor_trigger"
    assert logs[0].ambient_data["temperature"] == 30.5


@pytest.mark.asyncio
async def test_check_sensor_triggers_no_hit(db_session):
    """传感器数据不满足条件：不触发、不写日志"""
    from app.models.user import User
    from app.models.project import Project
    from app.models.scene_behavior import SceneBehaviorLog
    from sqlalchemy import select
    from app.services.scene_automation_service import check_sensor_triggers

    user = User(phone="13955010102", name="传感器测试2", role="homeowner", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    project = Project(name="传感器项目2", owner_id=user.id, total_area=80.0)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    await _create_sensor_scene(
        db_session, user.id, project.id,
        {"temperature": {"gt": 28}},
    )

    triggered = await check_sensor_triggers(
        db_session,
        user_id=user.id,
        ambient_data={"temperature": 20.0},
    )

    assert triggered == []
    result = await db_session.execute(select(SceneBehaviorLog))
    assert list(result.scalars().all()) == []


@pytest.mark.asyncio
async def test_check_sensor_triggers_other_user_isolated(db_session):
    """归属隔离：只触发用户自己项目下的场景"""
    from app.models.user import User
    from app.models.project import Project
    from app.services.scene_automation_service import check_sensor_triggers

    owner = User(phone="13955010103", name="场景拥有者", role="homeowner", hashed_password="x")
    db_session.add(owner)
    await db_session.commit()
    await db_session.refresh(owner)
    project = Project(name="他人项目", owner_id=owner.id, total_area=80.0)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    await _create_sensor_scene(db_session, owner.id, project.id, {"temperature": {"gt": 0}})

    # 另一个用户上传传感器数据，不应触发他人场景
    triggered = await check_sensor_triggers(
        db_session,
        user_id="some-other-user",
        ambient_data={"temperature": 99.0},
    )

    assert triggered == []
