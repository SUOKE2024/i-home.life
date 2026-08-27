"""设备链路加固测试（2026-08-27 评估修复验证）

覆盖评估报告 P0/P1 修复项：
1. 传感器快照数据完整性校验（数值范围 → 422）
2. 健康监测 monitor_type 枚举 + value 结构校验（→ 422）
3. 传感器快照 per-user 上传限流（→ 429，按用户隔离）
4. 生态桥命令超时 + 重试（_bridge_send_command + execute_device_command 集成）
5. Matter 凭据加密存储（单元往返 + commission 端点落库断言）
6. SceneAutomation.trigger_type 派生列（create/update 派生 + 校验）
"""
import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.services import scene_automation_service as svc
from app.services.device_credentials import (
    decrypt_device_credentials,
    encrypt_device_credentials,
)


async def _auth_headers(client: AsyncClient, phone: str) -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "加固测试", "password": "test123456"},
    )
    assert resp.status_code == 201, resp.json()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project(client: AsyncClient, headers, name: str = "加固测试项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 80.0}, headers=headers,
    )
    assert resp.status_code == 201, resp.json()
    return resp.json()["id"]


async def _create_scheme(client, headers, project_id: str) -> str:
    resp = await client.post(
        "/api/smart-home/schemes",
        json={
            "project_id": project_id,
            "room_name": "客厅",
            "room_type": "living_room",
            "protocol": "matter",
            "hub_brand": "xiaomi",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.json()
    return resp.json()["id"]


# ════════════════════════════════════════════════════════════════
# 1. 传感器快照数据完整性校验
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_sensor_snapshot_out_of_range_values_rejected(client: AsyncClient):
    """越界环境量/GPS 数值被 422 拒绝（防脏数据污染场景触发）"""
    headers = await _auth_headers(client, "13960040001")
    base = {"timestamp": "2026-08-27T10:00:00", "platform": "ios"}

    cases = [
        {"temperature": 9999.0},          # 温度越界（>80）
        {"temperature": -99.0},           # 温度越界（<-40）
        {"humidity": 150.0},              # 湿度越界（>100）
        {"humidity": -5.0},               # 湿度越界（<0）
        {"light_lux": -1.0},              # 光照越界（<0）
        {"gps": {"latitude": 91.0, "longitude": 0.0, "accuracy": 1.0, "available": True}},   # 纬度越界
        {"gps": {"latitude": 0.0, "longitude": 181.0, "accuracy": 1.0, "available": True}},  # 经度越界
        {"gps": {"latitude": 0.0, "longitude": 0.0, "accuracy": -1.0, "available": True}},   # 精度为负
    ]
    for extra in cases:
        resp = await client.post(
            "/api/sensors/snapshot", json={**base, **extra}, headers=headers,
        )
        assert resp.status_code == 422, f"应拒绝越界值: {extra} → {resp.text}"


@pytest.mark.asyncio
async def test_sensor_snapshot_boundary_values_accepted(client: AsyncClient, db_session):
    """边界合法值仍被接受（-40/80 温度、0/100 湿度、±90/±180 坐标）"""
    headers = await _auth_headers(client, "13960040002")
    resp = await client.post(
        "/api/sensors/snapshot",
        json={
            "gps": {"latitude": 90.0, "longitude": 180.0, "accuracy": 0.0, "available": True},
            "temperature": 80.0,
            "humidity": 100.0,
            "light_lux": 200000.0,
            "timestamp": "2026-08-27T10:00:00",
            "platform": "ios",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text


# ════════════════════════════════════════════════════════════════
# 2. 健康监测 monitor_type 枚举 + value 结构校验
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_health_record_invalid_monitor_type_rejected(client):
    """非法 monitor_type 被 422 拒绝（枚举校验）"""
    headers = await _auth_headers(client, "13960040003")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)
    resp = await client.post(
        "/api/health-monitor/records",
        json={
            "project_id": project_id, "scheme_id": scheme_id,
            "monitor_type": "not_a_real_type", "value": {"bpm": 72},
        },
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_health_record_missing_required_value_key_rejected(client):
    """heart_rate 缺少 bpm 键被 422 拒绝（value 结构校验）"""
    headers = await _auth_headers(client, "13960040004")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)
    resp = await client.post(
        "/api/health-monitor/records",
        json={
            "project_id": project_id, "scheme_id": scheme_id,
            "monitor_type": "heart_rate", "value": {"spo2": 99},
        },
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_health_record_valid_value_accepted(client):
    """合法记录仍被接受（回归保护）"""
    headers = await _auth_headers(client, "13960040005")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)
    resp = await client.post(
        "/api/health-monitor/records",
        json={
            "project_id": project_id, "scheme_id": scheme_id,
            "monitor_type": "sleep_quality", "value": {"sleep_score": 80},
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text


# ════════════════════════════════════════════════════════════════
# 3. 传感器快照 per-user 上传限流
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_sensor_snapshot_rate_limit_per_user(client, monkeypatch):
    """超限返回 429；不同用户互不影响"""
    from app.api import sensor_snapshot as snap_mod
    from app.config import get_settings

    snap_mod.reset_sensor_upload_rate_store()
    monkeypatch.setattr(get_settings(), "sensor_snapshot_rate_limit_per_minute", 3)

    headers = await _auth_headers(client, "13960040006")
    other_headers = await _auth_headers(client, "13960040007")
    payload = {"timestamp": "2026-08-27T10:00:00", "platform": "ios"}

    for _ in range(3):
        resp = await client.post("/api/sensors/snapshot", json=payload, headers=headers)
        assert resp.status_code == 201
    # 第 4 次触发限流
    resp = await client.post("/api/sensors/snapshot", json=payload, headers=headers)
    assert resp.status_code == 429, resp.text
    assert "频繁" in resp.json()["detail"]
    # 其他用户不受影响
    resp = await client.post("/api/sensors/snapshot", json=payload, headers=other_headers)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_sensor_snapshot_rate_limit_zero_disabled(client, monkeypatch):
    """limit=0 视为不限流（测试/特殊场景）"""
    from app.api import sensor_snapshot as snap_mod
    from app.config import get_settings

    snap_mod.reset_sensor_upload_rate_store()
    monkeypatch.setattr(get_settings(), "sensor_snapshot_rate_limit_per_minute", 0)

    headers = await _auth_headers(client, "13960040008")
    payload = {"timestamp": "2026-08-27T10:00:00", "platform": "ios"}
    for _ in range(5):
        resp = await client.post("/api/sensors/snapshot", json=payload, headers=headers)
        assert resp.status_code == 201


# ════════════════════════════════════════════════════════════════
# 4. 生态桥命令超时 + 重试
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_bridge_send_command_timeout_retries_then_raises(monkeypatch):
    """命令挂起：超时重试 1 次后抛 TimeoutError（确定性失败不吞）"""
    calls = {"n": 0}
    monkeypatch.setattr(svc, "BRIDGE_COMMAND_TIMEOUT_SECONDS", 0.1)

    class SlowBridge:
        async def send_command(self, device_id, command, params):
            calls["n"] += 1
            await asyncio.sleep(5)
            return True

    with pytest.raises(TimeoutError):
        await svc._bridge_send_command(SlowBridge(), "d1", "turn_on", {})
    assert calls["n"] == 2, "超时应重试 1 次（共 2 次尝试）"


@pytest.mark.asyncio
async def test_bridge_send_command_transient_retry_success(monkeypatch):
    """瞬时错误：重试后成功"""
    calls = {"n": 0}

    class FlakyBridge:
        async def send_command(self, device_id, command, params):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("transient network error")
            return True

    ok = await svc._bridge_send_command(FlakyBridge(), "d1", "turn_on", {})
    assert ok is True
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_bridge_send_command_deterministic_failure_no_retry():
    """确定性失败（stub NotImplementedError）不重试"""
    calls = {"n": 0}

    class StubBridge:
        async def send_command(self, device_id, command, params):
            calls["n"] += 1
            raise NotImplementedError("TODO: need API key")

    with pytest.raises(NotImplementedError):
        await svc._bridge_send_command(StubBridge(), "d1", "turn_on", {})
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_execute_device_command_timeout_marks_failed(client, db_session, monkeypatch):
    """集成：命令挂起超时 → action_status=failed 诚实标注，不悬挂"""
    from app.models.project import Project
    from app.models.smart_home import SmartDevice, SmartHomeScheme
    from app.models.user import User

    phone = "13960040009"
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "超时测试", "password": "test123456"},
    )
    assert resp.status_code == 201

    user = (await db_session.execute(select(User).where(User.phone == phone))).scalar_one()
    project = Project(name="超时测试项目", owner_id=user.id, total_area=80.0)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    scheme = SmartHomeScheme(
        project_id=project.id, room_name="客厅", room_type="living_room",
    )
    db_session.add(scheme)
    await db_session.commit()
    await db_session.refresh(scheme)
    device = SmartDevice(
        scheme_id=scheme.id, device_type="light", device_name="客厅灯", protocol="matter",
    )
    db_session.add(device)
    await db_session.commit()
    await db_session.refresh(device)

    calls = {"n": 0}
    monkeypatch.setattr(svc, "BRIDGE_COMMAND_TIMEOUT_SECONDS", 0.15)

    class SlowBridge:
        async def send_command(self, device_id, command, params):
            calls["n"] += 1
            await asyncio.sleep(30)
            return True

    class FakePool:
        async def get(self, ecosystem, credentials=None):
            return SlowBridge()

        async def close_all(self):
            pass

    monkeypatch.setattr("app.services.ecosystem_bridge.BridgeConnectionPool", FakePool)

    outcome = await svc.execute_device_command(
        db=db_session, device=device, project_id=project.id,
        action="turn_on", params={}, user_id=user.id, ecosystem="matter",
    )
    assert outcome["accepted"] is True
    assert outcome["action_status"] == "failed", outcome
    assert "超时" in (outcome["note"] or ""), outcome
    assert calls["n"] == 2, "超时应重试 1 次后判定 failed"


# ════════════════════════════════════════════════════════════════
# 5. Matter 凭据加密存储
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_device_credentials_roundtrip():
    """加密→解密往返一致；密文不含明文"""
    data = {"ssid": "ihome", "password": "secret-123", "security": "WPA2"}
    enc = encrypt_device_credentials(data)
    assert enc is not None
    assert "encrypted" in enc
    assert "secret-123" not in str(enc)
    assert decrypt_device_credentials(enc) == data


@pytest.mark.asyncio
async def test_device_credentials_none_and_tamper():
    """None 输入原样返回；篡改/非法密文解密为 None（不伪装成功）"""
    assert encrypt_device_credentials(None) is None
    assert encrypt_device_credentials({}) is None
    assert decrypt_device_credentials(None) is None
    assert decrypt_device_credentials({}) is None
    assert decrypt_device_credentials({"other": 1}) is None

    enc = encrypt_device_credentials({"ssid": "x"})
    assert enc is not None
    tampered = dict(enc)
    suffix = tampered["encrypted"][-2:]
    replacement = "AA" if suffix != "AA" else "BB"
    tampered["encrypted"] = tampered["encrypted"][:-2] + replacement
    assert decrypt_device_credentials(tampered) is None


@pytest.mark.asyncio
async def test_commission_stores_encrypted_credentials(client, db_session, monkeypatch):
    """commission 端点：凭据加密落库（非明文），可解密还原"""
    from app.models.matter_device import MatterDevice
    from app.models.user import User

    headers = await _auth_headers(client, "13960040010")
    user = (await db_session.execute(
        select(User).where(User.phone == "13960040010")
    )).scalar_one()
    project = await _create_project(client, headers)

    from app.services.ecosystem_bridge import MatterBridge

    async def fake_commission(self, passcode, discriminator, thread_credentials=None, wifi_credentials=None):
        return {"commissioning_state": "commissioned", "node_id": 1234, "fabric_index": 1}

    monkeypatch.setattr(MatterBridge, "commission_device", fake_commission)

    resp = await client.post(
        "/api/smart-home/matter/commission",
        json={
            "project_id": project,
            "passcode": 12345678901,
            "discriminator": 3840,
            "wifi_credentials": {"ssid": "ihome", "password": "secret-123"},
            "thread_credentials": {"network_name": "thread-net", "master_key": "0xDEADBEEF"},
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    dev = (await db_session.execute(
        select(MatterDevice).where(MatterDevice.project_id == project)
    )).scalars().first()
    assert dev is not None
    assert isinstance(dev.wifi_credentials, dict) and "encrypted" in dev.wifi_credentials
    assert "secret-123" not in str(dev.wifi_credentials)
    assert isinstance(dev.thread_credentials, dict) and "encrypted" in dev.thread_credentials
    assert decrypt_device_credentials(dev.wifi_credentials) == {
        "ssid": "ihome", "password": "secret-123",
    }
    assert decrypt_device_credentials(dev.thread_credentials) == {
        "network_name": "thread-net", "master_key": "0xDEADBEEF",
    }
    # 归属仍是配网用户
    assert dev.project_id == project
    assert user is not None


# ════════════════════════════════════════════════════════════════
# 6. SceneAutomation.trigger_type 派生列
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_scene_derives_trigger_type(db_session):
    """create_scene 从 trigger_condition 派生 trigger_type"""
    from app.models.project import Project
    from app.models.user import User

    user = User(phone="13960040011", name="派生测试", role="homeowner", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    project = Project(name="派生项目", owner_id=user.id, total_area=80.0)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    scene = await svc.create_scene(db_session, {
        "project_id": project.id,
        "scene_name": "传感器联动",
        "scene_type": "triggered",
        "trigger_condition": {"type": "sensor", "condition": {"temperature": {"gt": 28}}},
        "actions": [{"device_id": "l1", "action": "turn_on", "params": {}}],
        "enabled": True,
    })
    assert scene.trigger_type == "sensor"


@pytest.mark.asyncio
async def test_update_scene_rederives_trigger_type(db_session):
    """update_scene 变更 trigger_condition 后重派 trigger_type"""
    from app.models.project import Project
    from app.models.user import User

    user = User(phone="13960040012", name="重派测试", role="homeowner", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    project = Project(name="重派项目", owner_id=user.id, total_area=80.0)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    scene = await svc.create_scene(db_session, {
        "project_id": project.id,
        "scene_name": "定时场景",
        "scene_type": "scheduled",
        "trigger_condition": {"type": "time", "cron": "0 7 * * *"},
        "actions": [],
        "enabled": True,
    })
    assert scene.trigger_type == "time"

    updated = await svc.update_scene(db_session, scene.id, {
        "trigger_condition": {"type": "geo", "latitude": 31.0, "longitude": 121.0, "radius": 500},
    })
    assert updated.trigger_type == "geo"


@pytest.mark.asyncio
async def test_derive_trigger_type_unknown_returns_none():
    """未知/缺失触发类型派生为 None（诚实，不猜测）"""
    assert svc._derive_trigger_type(None) is None
    assert svc._derive_trigger_type({"type": "unknown_trigger"}) is None
    assert svc._derive_trigger_type({}) is None
    assert svc._derive_trigger_type("not-a-dict") is None
    assert svc._derive_trigger_type({"type": "sensor", "condition": {}}) == "sensor"


@pytest.mark.asyncio
async def test_check_sensor_triggers_skips_non_sensor_scenes(db_session):
    """trigger_type != sensor 的场景不被传感器数据触发（SQL 层预过滤）"""
    from app.models.project import Project
    from app.models.scene_automation import SceneAutomation
    from app.models.scene_behavior import SceneBehaviorLog
    from app.models.user import User

    user = User(phone="13960040013", name="预过滤测试", role="homeowner", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    project = Project(name="预过滤项目", owner_id=user.id, total_area=80.0)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    # time 触发场景（trigger_type=time）
    db_session.add(SceneAutomation(
        project_id=project.id,
        scene_name="定时场景",
        scene_type="scheduled",
        trigger_condition={"type": "time", "cron": "0 7 * * *"},
        trigger_type="time",
        actions=[{"device_id": "l1", "action": "turn_on", "params": {}}],
        enabled=True,
    ))
    # 手动场景（trigger_type=None）
    db_session.add(SceneAutomation(
        project_id=project.id,
        scene_name="手动场景",
        scene_type="manual",
        trigger_condition=None,
        trigger_type=None,
        actions=[{"device_id": "l1", "action": "turn_on", "params": {}}],
        enabled=True,
    ))
    await db_session.commit()

    triggered = await svc.check_sensor_triggers(
        db=db_session, user_id=user.id,
        ambient_data={"temperature": 30.0},
    )
    assert triggered == []
    logs = (await db_session.execute(select(SceneBehaviorLog))).scalars().all()
    assert list(logs) == []


# ════════════════════════════════════════════════════════════════
# 7. device.state 并发保护（per-device 串行化，2026-08-27 P2 遗留）
# ════════════════════════════════════════════════════════════════


async def _make_device_env(db_session, phone: str) -> tuple:
    """构造 user/project/scheme/device，返回 (user, project, device)。"""
    from app.models.project import Project
    from app.models.smart_home import SmartDevice, SmartHomeScheme
    from app.models.user import User

    user = User(phone=phone, name="并发测试", role="homeowner", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    project = Project(name="并发测试项目", owner_id=user.id, total_area=80.0)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    scheme = SmartHomeScheme(project_id=project.id, room_name="客厅", room_type="living_room")
    db_session.add(scheme)
    await db_session.commit()
    await db_session.refresh(scheme)
    device = SmartDevice(scheme_id=scheme.id, device_type="light", device_name="客厅灯", protocol="matter")
    db_session.add(device)
    await db_session.commit()
    await db_session.refresh(device)
    return user, project, device


class _TimingBridge:
    """记录每次 send_command 的起止时间（验证串行化）。"""

    def __init__(self):
        self.times = []

    async def send_command(self, device_id, command, params):
        import time as time_mod
        t0 = time_mod.monotonic()
        await asyncio.sleep(0.05)
        t1 = time_mod.monotonic()
        self.times.append((t0, t1))
        return True


class _FakePool:
    def __init__(self, bridge):
        self._bridge = bridge

    async def get(self, ecosystem, credentials=None):
        return self._bridge

    async def close_all(self):
        pass


@pytest.mark.asyncio
async def test_device_state_concurrent_commands_serialized(client, db_session, monkeypatch):
    """同设备并发命令串行化：桥调用时间无重叠（per-device asyncio.Lock）"""
    from app.database import async_session
    from app.models.smart_home import SmartDevice

    user, project, device = await _make_device_env(db_session, "13960040022")
    bridge = _TimingBridge()
    monkeypatch.setattr(
        "app.services.ecosystem_bridge.BridgeConnectionPool",
        lambda: _FakePool(bridge),
    )

    async def _cmd(action):
        async with async_session() as db:
            dev = (await db.execute(
                select(SmartDevice).where(SmartDevice.id == device.id)
            )).scalar_one()
            return await svc.execute_device_command(
                db=db, device=dev, project_id=project.id,
                action=action, params={}, user_id=user.id, ecosystem="matter",
            )

    r1, r2 = await asyncio.gather(_cmd("turn_on"), _cmd("turn_off"))
    assert r1["action_status"] == "success"
    assert r2["action_status"] == "success"
    assert len(bridge.times) == 2
    ordered = sorted(bridge.times)
    assert ordered[1][0] >= ordered[0][1], "同设备命令应串行执行（桥调用时间无重叠）"

    # 最终 state 合并无丢失（两个 delta 都保留，串行 refresh 防覆盖）
    async with async_session() as db:
        final = (await db.execute(
            select(SmartDevice).where(SmartDevice.id == device.id)
        )).scalar_one()
        assert final.state == {"power": False}  # 后执行 turn_off


# ════════════════════════════════════════════════════════════════
# 8. 命令/场景异步化（2026-08-27 P2 遗留）
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_device_command_async_queued_then_executed(client, db_session, monkeypatch):
    """execute_async=True：请求立即返回 queued，后台任务最终执行并落 state"""
    from app.database import async_session
    from app.models.project import Project
    from app.models.smart_home import SmartDevice, SmartHomeScheme
    from app.models.user import User

    phone = "13960040023"
    headers = await _auth_headers(client, phone)
    user = (await db_session.execute(
        select(User).where(User.phone == phone)
    )).scalar_one()
    project = Project(name="异步命令项目", owner_id=user.id, total_area=80.0)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    scheme = SmartHomeScheme(project_id=project.id, room_name="客厅", room_type="living_room")
    db_session.add(scheme)
    await db_session.commit()
    await db_session.refresh(scheme)
    device = SmartDevice(scheme_id=scheme.id, device_type="light", device_name="客厅灯", protocol="matter")
    db_session.add(device)
    await db_session.commit()
    await db_session.refresh(device)

    monkeypatch.setattr(
        "app.services.ecosystem_bridge.BridgeConnectionPool",
        lambda: _FakePool(_TimingBridge()),
    )

    resp = await client.post(
        f"/api/smart-home/devices/{device.id}/command",
        json={"action": "turn_on", "params": {}, "execute_async": True},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["action_status"] == "queued"
    assert data["async_queued"] is True
    assert "异步" in data["note"]

    # 后台任务（ASGITransport 在响应后执行）→ 短暂等待后 state 已更新
    import time as time_mod
    deadline = time_mod.monotonic() + 3.0
    state = None
    while time_mod.monotonic() < deadline:
        async with async_session() as db:
            dev = (await db.execute(
                select(SmartDevice).where(SmartDevice.id == device.id)
            )).scalar_one()
            state = dev.state
        if state is not None:
            break
        await asyncio.sleep(0.1)
    assert state == {"power": True}, "异步命令后台执行后应写入真实状态"


@pytest.mark.asyncio
async def test_scene_execute_async_queued(client, db_session, monkeypatch):
    """场景 execute_async=True：请求立即返回 queued + async_queued 标注"""
    from app.models.project import Project
    from app.models.scene_automation import SceneAutomation
    from app.models.user import User

    phone = "13960040024"
    headers = await _auth_headers(client, phone)
    user = (await db_session.execute(
        select(User).where(User.phone == phone)
    )).scalar_one()
    project = Project(name="异步场景项目", owner_id=user.id, total_area=80.0)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    scene = SceneAutomation(
        project_id=project.id, scene_name="异步场景", scene_type="manual",
        trigger_condition=None, trigger_type=None,
        actions=[{"device_id": "l1", "action": "turn_on", "params": {}}],
        enabled=True,
    )
    db_session.add(scene)
    await db_session.commit()

    resp = await client.post(
        f"/api/scene-automation/scenes/{scene.id}/execute",
        json={"trigger_source": "vr_overlay", "execute_async": True},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["executed"] is True
    assert data["async_queued"] is True
    assert data["actions"] == []


# ════════════════════════════════════════════════════════════════
# 9. GB 50311 合规接入布线规划（2026-08-27 P2 遗留）
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_wiring_plan_includes_gb50311_compliance(client, db_session):
    """plan_wiring 返回 weak_current_box（GB 50311）与 safety 合规（可选字段兼容）"""
    from app.models.project import Project
    from app.models.smart_home import SmartDevice, SmartHomeScheme
    from app.models.user import User

    phone = "13960040025"
    headers = await _auth_headers(client, phone)
    user = (await db_session.execute(
        select(User).where(User.phone == phone)
    )).scalar_one()
    project = Project(name="合规布线项目", owner_id=user.id, total_area=80.0)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    scheme = SmartHomeScheme(project_id=project.id, room_name="客厅", room_type="living_room")
    db_session.add(scheme)
    await db_session.commit()
    await db_session.refresh(scheme)
    device = SmartDevice(
        scheme_id=scheme.id, device_type="light", device_name="客厅灯",
        protocol="matter", wiring_required=True,
        wiring_spec={"零火线": True},
        room_name="客厅",
    )
    db_session.add(device)
    await db_session.commit()

    resp = await client.get(
        f"/api/smart-home/schemes/{scheme.id}/wiring", headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "wiring_items" in data
    assert "weak_current_box" in data and data["weak_current_box"] is not None
    assert "recommended_size" in data["weak_current_box"]
    assert "suggestions" in data["weak_current_box"]
    assert "safety" in data and data["safety"] is not None
    assert "compliant" in data["safety"]
    assert data["wiring_items"][0]["requirement"] == "零火线预留"
