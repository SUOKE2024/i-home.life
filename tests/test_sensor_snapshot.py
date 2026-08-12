"""传感器快照 API 集成测试

覆盖端点:
- POST /api/sensors/snapshot      (上传传感器快照)
- GET  /api/sensors/capabilities   (查询传感器能力)
"""
import pytest
from httpx import AsyncClient


async def _auth_headers(client: AsyncClient, phone: str = "13900040001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "传感器测试", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_upload_sensor_snapshot_full(client: AsyncClient):
    """上传完整传感器快照 — 4 个传感器 + GPS 全部可用"""
    headers = await _auth_headers(client, "13900040011")

    resp = await client.post(
        "/api/sensors/snapshot",
        json={
            "accelerometer": {"x": 0.01, "y": 0.02, "z": 9.81, "available": True},
            "gyroscope": {"x": 0.001, "y": 0.002, "z": 0.003, "available": True},
            "magnetometer": {"x": 10.0, "y": 20.0, "z": 30.0, "heading_deg": 45.0, "available": True},
            "gps": {"latitude": 31.2304, "longitude": 121.4737, "accuracy": 5.0, "altitude": 10.0, "available": True},
            "timestamp": "2026-07-25T10:00:00",
            "platform": "ios",
            "device_id": "device-001",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["received"] is True
    assert data["sensors_count"] == 4
    assert data["timestamp"] == "2026-07-25T10:00:00"


@pytest.mark.asyncio
async def test_upload_sensor_snapshot_partial(client: AsyncClient):
    """上传部分传感器快照 — 仅加速度计 + GPS"""
    headers = await _auth_headers(client, "13900040012")

    resp = await client.post(
        "/api/sensors/snapshot",
        json={
            "accelerometer": {"x": 0.0, "y": 0.0, "z": 9.8, "available": True},
            "gps": {"latitude": 39.9042, "longitude": 116.4074, "accuracy": 10.0, "available": True},
            "timestamp": "2026-07-25T11:00:00",
            "platform": "android",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["received"] is True
    assert data["sensors_count"] == 2


@pytest.mark.asyncio
async def test_upload_sensor_snapshot_none_available(client: AsyncClient):
    """上传快照但所有传感器不可用 — 鸿蒙降级场景"""
    headers = await _auth_headers(client, "13900040013")

    resp = await client.post(
        "/api/sensors/snapshot",
        json={
            "accelerometer": {"x": 0.0, "y": 0.0, "z": 0.0, "available": False},
            "gyroscope": {"x": 0.0, "y": 0.0, "z": 0.0, "available": False},
            "magnetometer": {"x": 0.0, "y": 0.0, "z": 0.0, "heading_deg": 0.0, "available": False},
            "gps": {"latitude": 0.0, "longitude": 0.0, "accuracy": 0.0, "available": False},
            "timestamp": "2026-07-25T12:00:00",
            "platform": "harmonyos",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["received"] is True
    assert data["sensors_count"] == 0


@pytest.mark.asyncio
async def test_get_sensor_capabilities(client: AsyncClient):
    """查询后端传感器能力声明"""
    headers = await _auth_headers(client, "13900040014")

    resp = await client.get("/api/sensors/capabilities", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "accelerometer" in data["supported_sensors"]
    assert "gyroscope" in data["supported_sensors"]
    assert "magnetometer" in data["supported_sensors"]
    assert "gps" in data["supported_sensors"]
    assert data["upload_endpoint"] == "/api/sensors/snapshot"
    assert data["sampling_rate_hz"] == 60
    assert data["auto_trigger_enabled"] is True


@pytest.mark.asyncio
async def test_sensor_snapshot_unauthorized(client: AsyncClient):
    """未认证不能上传传感器快照"""
    resp = await client.post(
        "/api/sensors/snapshot",
        json={
            "accelerometer": {"x": 0.0, "y": 0.0, "z": 0.0, "available": True},
            "timestamp": "2026-07-25T10:00:00",
            "platform": "ios",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_sensor_capabilities_unauthorized(client: AsyncClient):
    """未认证不能查询传感器能力"""
    resp = await client.get("/api/sensors/capabilities")
    assert resp.status_code == 401


# ── 设备链路全量诊断修复（2026-08-12）──


@pytest.mark.asyncio
async def test_upload_sensor_snapshot_persists(client: AsyncClient, db_session):
    """修复：快照真实落库到 sensor_snapshots 表（此前仅返回确认、不存储）"""
    from sqlalchemy import select

    from app.models.sensor_snapshot import SensorSnapshot
    from app.models.user import User

    phone = "13900040015"
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "传感器落库测试", "password": "test123456"},
    )
    assert resp.status_code == 201
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    await client.post(
        "/api/sensors/snapshot",
        json={
            "accelerometer": {"x": 0.01, "y": 0.02, "z": 9.81, "available": True},
            "gyroscope": {"x": 0.1, "y": 0.2, "z": 0.3, "available": True},
            "magnetometer": {"x": 10.0, "y": 20.0, "z": 30.0, "heading_deg": 45.0, "available": True},
            "gps": {"latitude": 31.23, "longitude": 121.47, "accuracy": 5.0, "altitude": 10.0, "available": True},
            "timestamp": "2026-07-25T10:30:00",
            "platform": "ios",
            "device_id": "device-persist-001",
        },
        headers=headers,
    )

    result = await db_session.execute(
        select(SensorSnapshot).order_by(SensorSnapshot.created_at.desc())
    )
    snap = result.scalars().first()
    assert snap is not None
    # 客户端真实读数落库
    assert snap.platform == "ios"
    assert snap.device_id == "device-persist-001"
    assert snap.accelerometer_available is True
    assert snap.accelerometer_x == 0.01
    assert snap.accelerometer_z == 9.81
    assert snap.gyroscope_available is True
    assert snap.gyroscope_x == 0.1
    assert snap.magnetometer_heading_deg == 45.0
    assert snap.gps_available is True
    assert snap.gps_latitude == 31.23
    assert snap.gps_longitude == 121.47
    # 关联到上传用户
    user = (await db_session.execute(
        select(User).where(User.phone == phone)
    )).scalar_one()
    assert snap.user_id == user.id
    # 采样时间正确解析
    assert snap.sampled_at.year == 2026 and snap.sampled_at.month == 7


@pytest.mark.asyncio
async def test_upload_sensor_snapshot_no_fake_ambient_trigger(
    client: AsyncClient, db_session
):
    """修复：移除硬编码假数据 — 加速度计不再伪造温度/占用率触发场景"""
    from sqlalchemy import select

    from app.models.project import Project
    from app.models.scene_automation import SceneAutomation
    from app.models.scene_behavior import SceneBehaviorLog
    from app.models.user import User

    phone = "13900040016"
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "传感器假数据测试", "password": "test123456"},
    )
    assert resp.status_code == 201
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    user = (await db_session.execute(
        select(User).where(User.phone == phone)
    )).scalar_one()
    project = Project(name="传感器假数据项目", owner_id=user.id, total_area=80.0)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    # 温度 > 28 触发的 sensor 场景
    scene = SceneAutomation(
        project_id=project.id,
        scene_name="温度联动",
        scene_type="triggered",
        trigger_condition={"type": "sensor", "condition": {"temperature": {"gt": 28}}},
        actions=[{"device_id": "light-1", "action": "turn_on", "params": {}}],
        enabled=True,
    )
    db_session.add(scene)
    await db_session.commit()

    # 1. 仅加速度计快照（z=9.81）— 历史 bug 会用 accel.z 伪造 temperature=9.81 参与匹配
    await client.post(
        "/api/sensors/snapshot",
        json={
            "accelerometer": {"x": 0.01, "y": 0.02, "z": 9.81, "available": True},
            "timestamp": "2026-07-25T10:30:00",
            "platform": "ios",
        },
        headers=headers,
    )
    logs = (await db_session.execute(select(SceneBehaviorLog))).scalars().all()
    assert list(logs) == [], "加速度计数据不应被伪造为温度触发场景"

    # 2. GPS-only 快照 — 键全部缺失于 condition 时不得空匹配误触发
    await client.post(
        "/api/sensors/snapshot",
        json={
            "gps": {"latitude": 31.23, "longitude": 121.47, "accuracy": 5.0, "available": True},
            "timestamp": "2026-07-25T10:31:00",
            "platform": "android",
        },
        headers=headers,
    )
    logs = (await db_session.execute(select(SceneBehaviorLog))).scalars().all()
    assert list(logs) == [], "GPS-only 数据不应触发 temperature 场景（空匹配误触发）"


@pytest.mark.asyncio
async def test_upload_sensor_snapshot_env_trigger(client: AsyncClient, db_session):
    """修复验证：含环境量 temperature 的快照真实触发 sensor 场景并落库"""
    from sqlalchemy import select

    from app.models.project import Project
    from app.models.scene_automation import SceneAutomation
    from app.models.scene_behavior import SceneBehaviorLog
    from app.models.sensor_snapshot import SensorSnapshot
    from app.models.user import User

    phone = "13900040017"
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "环境量触发测试", "password": "test123456"},
    )
    assert resp.status_code == 201
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    user = (await db_session.execute(
        select(User).where(User.phone == phone)
    )).scalar_one()
    project = Project(name="环境量触发项目", owner_id=user.id, total_area=100.0)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    scene = SceneAutomation(
        project_id=project.id,
        scene_name="高温联动",
        scene_type="triggered",
        trigger_condition={"type": "sensor", "condition": {"temperature": {"gt": 28}}},
        actions=[{"device_id": "light-1", "action": "turn_on", "params": {}}],
        enabled=True,
    )
    db_session.add(scene)
    await db_session.commit()
    scene_id = scene.id

    # 上传含 temperature=30.5 的快照（环境传感器真实上报）
    resp = await client.post(
        "/api/sensors/snapshot",
        json={
            "accelerometer": {"x": 0.01, "y": 0.02, "z": 9.81, "available": True},
            "gps": {"latitude": 31.23, "longitude": 121.47, "accuracy": 5.0, "available": True},
            "temperature": 30.5,
            "humidity": 55.0,
            "light_lux": 320.0,
            "timestamp": "2026-07-25T16:00:00",
            "platform": "harmonyos",
            "device_id": "env-sensor-001",
        },
        headers=headers,
    )
    assert resp.status_code == 201

    # 环境量真实落库
    snap = (await db_session.execute(
        select(SensorSnapshot).order_by(SensorSnapshot.created_at.desc())
    )).scalars().first()
    assert snap is not None
    assert snap.temperature == 30.5
    assert snap.humidity == 55.0
    assert snap.light_lux == 320.0

    # 场景真实触发 + 触发日志落库
    logs = (await db_session.execute(
        select(SceneBehaviorLog).where(SceneBehaviorLog.scene_id == scene_id)
    )).scalars().all()
    assert len(logs) == 1
    assert logs[0].action_type == "sensor_trigger"
    assert logs[0].ambient_data["temperature"] == 30.5


# ── 边缘情况补充测试（2026-08-12）──


@pytest.mark.asyncio
async def test_sensor_snapshot_flag_disabled_503(client: AsyncClient, monkeypatch):
    """feature flag 关闭时返回 503（诚实降级）"""
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "sensor_snapshot_enabled", False)
    headers = await _auth_headers(client, "13900040018")
    resp = await client.post(
        "/api/sensors/snapshot",
        json={"timestamp": "2026-07-25T10:00:00", "platform": "ios"},
        headers=headers,
    )
    assert resp.status_code == 503
    assert "未启用" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_sensor_snapshot_invalid_timestamp(client: AsyncClient, db_session):
    """无效时间戳不 crash：回退当前时间落库"""
    from sqlalchemy import select

    from app.models.sensor_snapshot import SensorSnapshot

    headers = await _auth_headers(client, "13900040019")
    resp = await client.post(
        "/api/sensors/snapshot",
        json={
            "accelerometer": {"x": 0.1, "y": 0.2, "z": 9.8, "available": True},
            "timestamp": "not-a-valid-timestamp",
            "platform": "ios",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    snap = (await db_session.execute(
        select(SensorSnapshot).order_by(SensorSnapshot.created_at.desc())
    )).scalars().first()
    assert snap is not None
    assert snap.accelerometer_x == 0.1  # 正常落库
    assert snap.sampled_at is not None  # 时间戳回退为当前时间


@pytest.mark.asyncio
async def test_upload_sensor_snapshot_temperature_zero_participates(
    client: AsyncClient, db_session
):
    """temperature=0 是合法值：不得因 falsy 被丢弃，应参与条件匹配并触发"""
    from sqlalchemy import select

    from app.models.project import Project
    from app.models.scene_automation import SceneAutomation
    from app.models.scene_behavior import SceneBehaviorLog
    from app.models.sensor_snapshot import SensorSnapshot
    from app.models.user import User

    phone = "13900040020"
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "零度触发测试", "password": "test123456"},
    )
    assert resp.status_code == 201
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    user = (await db_session.execute(
        select(User).where(User.phone == phone)
    )).scalar_one()
    project = Project(name="零度触发项目", owner_id=user.id, total_area=100.0)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    scene = SceneAutomation(
        project_id=project.id,
        scene_name="低温联动",
        scene_type="triggered",
        trigger_condition={"type": "sensor", "condition": {"temperature": {"lt": 5}}},
        actions=[{"device_id": "light-1", "action": "turn_on", "params": {}}],
        enabled=True,
    )
    db_session.add(scene)
    await db_session.commit()
    scene_id = scene.id

    resp = await client.post(
        "/api/sensors/snapshot",
        json={
            "temperature": 0,
            "timestamp": "2026-07-25T17:00:00",
            "platform": "ios",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    # 0 真实落库（而非被当作空值丢弃）
    snap = (await db_session.execute(
        select(SensorSnapshot).order_by(SensorSnapshot.created_at.desc())
    )).scalars().first()
    assert snap is not None
    assert snap.temperature == 0
    # 0 < 5 触发低温联动
    logs = (await db_session.execute(
        select(SceneBehaviorLog).where(SceneBehaviorLog.scene_id == scene_id)
    )).scalars().all()
    assert len(logs) == 1
    assert logs[0].ambient_data["temperature"] == 0


@pytest.mark.asyncio
async def test_upload_sensor_snapshot_empty_body(client: AsyncClient, db_session):
    """完全空快照（无任何传感器字段）：不 crash、不触发、sensors_count=0"""
    from sqlalchemy import select

    from app.models.scene_behavior import SceneBehaviorLog
    from app.models.sensor_snapshot import SensorSnapshot

    headers = await _auth_headers(client, "13900040021")
    resp = await client.post(
        "/api/sensors/snapshot",
        json={"timestamp": "2026-07-25T18:00:00", "platform": "ios"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["received"] is True
    assert data["sensors_count"] == 0
    # 空快照仍落库（无传感器可用），但不触发任何场景
    snap = (await db_session.execute(
        select(SensorSnapshot).order_by(SensorSnapshot.created_at.desc())
    )).scalars().first()
    assert snap is not None
    assert snap.accelerometer_available is False
    logs = (await db_session.execute(select(SceneBehaviorLog))).scalars().all()
    assert list(logs) == []
