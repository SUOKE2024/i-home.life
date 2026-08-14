"""P0 设备热点联动 API 集成测试（2026-08-12 工程落地）

覆盖端点:
- POST /api/smart-home/devices/{device_id}/command   (设备命令，3D 场景/语音入口)
- POST /api/scene-automation/scenes/{scene_id}/execute (场景执行，手动触发)
- GET  /api/vr/projects/{project_id}/device-overlay  (3D 设备图层聚合)
"""
import pytest
from httpx import AsyncClient


async def _auth_headers(client: AsyncClient, phone: str = "13930030001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "设备联动测试", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "联动测试项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 100.0}, headers=headers,
    )
    return resp.json()["id"]


async def _create_scheme(client: AsyncClient, headers: dict, project_id: str) -> dict:
    resp = await client.post(
        "/api/smart-home/schemes",
        json={
            "project_id": project_id, "room_name": "客厅",
            "room_type": "living_room", "protocol": "zigbee", "hub_brand": "xiaomi",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()


async def _create_device(
    client: AsyncClient, headers: dict, scheme_id: str, name: str = "客厅灯",
    position: dict | None = None,
) -> dict:
    body = {
        "device_type": "light",
        "device_name": name,
        "brand": "yeelight",
        "protocol": "zigbee",
        "control_mode": "voice",
        "power_w": 24.0,
        "status": "online",
    }
    if position:
        body.update(position)
    resp = await client.post(
        f"/api/smart-home/schemes/{scheme_id}/devices", json=body, headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_scene(
    client: AsyncClient, headers: dict, project_id: str, scheme_id: str, device_id: str,
) -> str:
    resp = await client.post(
        "/api/scene-automation/scenes",
        json={
            "project_id": project_id,
            "scheme_id": scheme_id,
            "scene_name": "观影模式",
            "scene_type": "manual",
            "trigger_condition": None,
            "actions": [{"device_id": device_id, "action": "turn_off", "params": {}}],
            "enabled": True,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ── 设备命令 ──


@pytest.mark.asyncio
async def test_device_command_pending_honest(client: AsyncClient, db_session):
    """设备命令：白名单动作 → 落 SceneBehaviorLog + action_status=pending 诚实标注"""
    from sqlalchemy import select

    from app.models.scene_behavior import SceneBehaviorLog

    headers = await _auth_headers(client, "13930030002")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id)
    device = await _create_device(client, headers, scheme["id"])

    resp = await client.post(
        f"/api/smart-home/devices/{device['id']}/command",
        json={"action": "turn_off", "params": {}, "source": "vr_overlay"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] is True
    assert data["action_status"] == "pending"  # 生态桥未接真机 → 诚实 pending
    assert data["device_id"] == device["id"]
    assert "bridge_not_configured" in (data["note"] or "")  # 诚实标注桥接未接入
    assert data["state"] is None  # pending 不写 state（诚实：无真机数据不伪造）

    # 触发日志真实落库（SceneBehaviorLog 无 device_id 列，校验 project_id + 类型）
    logs = (await db_session.execute(
        select(SceneBehaviorLog).where(SceneBehaviorLog.action_type == "device_command")
    )).scalars().all()
    assert len(logs) == 1
    assert logs[0].project_id == project_id


@pytest.mark.asyncio
async def test_device_command_action_not_allowed(client: AsyncClient):
    """设备命令：动作不在白名单 → 422"""
    headers = await _auth_headers(client, "13930030003")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id)
    device = await _create_device(client, headers, scheme["id"])

    resp = await client.post(
        f"/api/smart-home/devices/{device['id']}/command",
        json={"action": "fly", "params": {}},
        headers=headers,
    )
    assert resp.status_code == 422
    assert "不支持动作" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_device_command_unauthorized(client: AsyncClient):
    """设备命令：未认证 → 401"""
    resp = await client.post(
        "/api/smart-home/devices/fake-device/command",
        json={"action": "turn_on"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_device_command_other_user_forbidden(client: AsyncClient):
    """设备命令：越权访问他人项目设备 → 403/404"""
    owner_headers = await _auth_headers(client, "13930030004")
    project_id = await _create_project(client, owner_headers)
    scheme = await _create_scheme(client, owner_headers, project_id)
    device = await _create_device(client, owner_headers, scheme["id"])

    other_headers = await _auth_headers(client, "13930030005")
    resp = await client.post(
        f"/api/smart-home/devices/{device['id']}/command",
        json={"action": "turn_on"},
        headers=other_headers,
    )
    assert resp.status_code in (403, 404)


# ── 场景执行 ──


@pytest.mark.asyncio
async def test_scene_execute_manual_trigger(client: AsyncClient, db_session):
    """场景执行：manual_trigger 落库 + 动作 pending 诚实标注 + WS 广播"""
    from sqlalchemy import select

    from app.models.scene_behavior import SceneBehaviorLog

    headers = await _auth_headers(client, "13930030006")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id)
    device = await _create_device(client, headers, scheme["id"])
    scene_id = await _create_scene(client, headers, project_id, scheme["id"], device["id"])

    resp = await client.post(
        f"/api/scene-automation/scenes/{scene_id}/execute",
        json={"trigger_source": "vr_overlay"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["executed"] is True
    assert len(data["actions"]) == 1
    act = data["actions"][0]
    assert act["device_id"] == device["id"]
    assert act["action_status"] == "pending"  # 生态桥未接真机 → 诚实 pending
    assert "triggered_at" in data

    # manual_trigger 日志真实落库
    logs = (await db_session.execute(
        select(SceneBehaviorLog).where(SceneBehaviorLog.action_type == "manual_trigger")
    )).scalars().all()
    assert len(logs) == 1
    assert logs[0].scene_id == scene_id


@pytest.mark.asyncio
async def test_scene_execute_not_found(client: AsyncClient):
    """场景执行：场景不存在 → 404"""
    headers = await _auth_headers(client, "13930030007")
    resp = await client.post(
        "/api/scene-automation/scenes/fake-scene/execute",
        json={"trigger_source": "voice"},
        headers=headers,
    )
    assert resp.status_code == 404


# ── 3D 设备图层聚合 ──


@pytest.mark.asyncio
async def test_device_overlay_aggregation(client: AsyncClient, db_session):
    """设备图层：设备锚点(含 yaw/pitch) + 关联场景 + 最近传感器快照"""
    headers = await _auth_headers(client, "13930030008")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id)
    device = await _create_device(
        client, headers, scheme["id"], position={
            "position_x": 1.0, "position_y": 2.0, "position_z": 3.0,
        },
    )
    scene_id = await _create_scene(client, headers, project_id, scheme["id"], device["id"])

    # 上传一条真实传感器快照（供联动上下文）
    resp = await client.post(
        "/api/sensors/snapshot",
        json={
            "temperature": 26.5,
            "humidity": 50.0,
            "timestamp": "2026-07-25T16:00:00",
            "platform": "ios",
        },
        headers=headers,
    )
    assert resp.status_code == 201

    resp = await client.get(
        f"/api/vr/projects/{project_id}/device-overlay", headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["device_count"] == 1
    d = data["devices"][0]
    assert d["device_id"] == device["id"]
    assert d["type"] == "light"
    assert d["status"] == "online"
    assert "state" in d  # 实时状态字段（未真机执行过 → None，诚实）
    assert d["state"] is None
    assert 0 <= d["yaw"] < 360  # position → yaw 球坐标换算
    assert scene_id in d["scene_ids"]
    # 最近真实传感器快照
    assert data["latest_sensor"] is not None
    assert data["latest_sensor"]["temperature"] == 26.5


@pytest.mark.asyncio
async def test_device_overlay_unauthorized(client: AsyncClient):
    """设备图层：未认证 → 401"""
    resp = await client.get("/api/vr/projects/fake/device-overlay")
    assert resp.status_code == 401


# ── 并行执行（2026-08-12 两阶段重构）──


async def _create_n_devices(client, headers, scheme_id, n: int) -> list[dict]:
    devices = []
    for i in range(n):
        d = await _create_device(
            client, headers, scheme_id, name=f"设备{i}",
            position={"position_x": i + 1.0, "position_y": 2.0, "position_z": 3.0},
        )
        devices.append(d)
    return devices


@pytest.mark.asyncio
async def test_scene_execute_parallel_multi_action(client: AsyncClient, db_session):
    """并行执行：3 动作场景 → 全部 pending（桥未接入）+ SceneBehaviorLog 落库 3 条"""
    from sqlalchemy import select

    from app.models.scene_behavior import SceneBehaviorLog

    headers = await _auth_headers(client, "13930030009")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id)
    devices = await _create_n_devices(client, headers, scheme["id"], 3)

    resp = await client.post(
        "/api/scene-automation/scenes",
        json={
            "project_id": project_id,
            "scheme_id": scheme["id"],
            "scene_name": "全屋联动",
            "scene_type": "manual",
            "trigger_condition": None,
            "actions": [
                {"device_id": devices[0]["id"], "action": "turn_off", "params": {}},
                {"device_id": devices[1]["id"], "action": "turn_off", "params": {}},
                {"device_id": devices[2]["id"], "action": "turn_off", "params": {}},
            ],
            "enabled": True,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    scene_id = resp.json()["id"]

    resp = await client.post(
        f"/api/scene-automation/scenes/{scene_id}/execute",
        json={"trigger_source": "vr_overlay"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["executed"] is True
    assert len(data["actions"]) == 3
    # 全部 pending（生态桥未接真机，诚实标注）
    assert all(a["action_status"] == "pending" for a in data["actions"])
    # 每个动作独立 SceneBehaviorLog 落库
    logs = (await db_session.execute(
        select(SceneBehaviorLog).where(SceneBehaviorLog.scene_id == scene_id)
    )).scalars().all()
    assert len(logs) == 3


@pytest.mark.asyncio
async def test_plan_scene_actions_waves():
    """波次规划：无依赖一波并行，depends_on 依赖的进下一波"""
    from app.services.scene_automation_service import _plan_scene_actions

    # 设备 id → 设备占位对象（仅需 .id/.device_type/.device_name）
    class _D:
        def __init__(self, id_, type_):
            self.id = id_
            self.device_type = type_
            self.device_name = id_

    device_map = {f"dev{i}": _D(f"dev{i}", "light") for i in range(3)}
    actions = [
        {"device_id": "dev0", "action": "turn_off"},
        {"device_id": "dev1", "action": "turn_off", "depends_on": 0},
        {"device_id": "dev2", "action": "turn_off", "depends_on": 0},
    ]
    waves, plan = _plan_scene_actions(actions, device_map)
    assert len(waves) == 2  # 波1: dev0；波2: dev1+dev2（并行）
    assert [it["idx"] for it in waves[0]] == [0]
    assert sorted(it["idx"] for it in waves[1]) == [1, 2]
    assert all(it["status"] == "ok" for it in plan)


@pytest.mark.asyncio
async def test_plan_scene_actions_dependency_cycle_fallback():
    """环依赖退化：互相 depends_on 时退化为串行不悬挂"""
    from app.services.scene_automation_service import _plan_scene_actions

    class _D:
        def __init__(self, id_, type_):
            self.id = id_
            self.device_type = type_
            self.device_name = id_

    device_map = {f"dev{i}": _D(f"dev{i}", "light") for i in range(2)}
    # 互相依赖（环）：0 依赖 1，1 依赖 0
    actions = [
        {"device_id": "dev0", "action": "turn_off", "depends_on": 1},
        {"device_id": "dev1", "action": "turn_off", "depends_on": 0},
    ]
    waves, plan = _plan_scene_actions(actions, device_map)
    # 每波仅 1 个动作（退化串行），两个动作均被调度
    assert len(waves) == 2
    assert [it["idx"] for it in waves[0]] == [0]
    assert [it["idx"] for it in waves[1]] == [1]
    assert len(plan) == 2


@pytest.mark.asyncio
async def test_plan_scene_actions_skipped_rejected():
    """规划校验：设备不存在 → skipped；动作不在白名单 → rejected"""
    from app.services.scene_automation_service import _plan_scene_actions

    class _D:
        def __init__(self, id_, type_):
            self.id = id_
            self.device_type = type_
            self.device_name = id_

    device_map = {"dev0": _D("dev0", "light")}
    actions = [
        {"device_id": "missing", "action": "turn_off"},   # 设备不存在
        {"device_id": "dev0", "action": "fly"},           # 白名单外动作
        {"device_id": "dev0", "action": "turn_off"},      # 正常
    ]
    waves, plan = _plan_scene_actions(actions, device_map)
    statuses = [it["status"] for it in plan]
    assert statuses == ["skipped", "rejected", "ok"]
    # 波次仅含 ok 动作
    assert len(waves) == 1 and [it["idx"] for it in waves[0]] == [2]


async def test_plan_scene_actions_sensor_empty_whitelist_rejected():
    """传感器（只读，白名单为空）/ 未知类型 的动作应被拒绝，而非绕过校验"""
    from app.services.scene_automation_service import _plan_scene_actions

    class _D:
        def __init__(self, id_, type_):
            self.id = id_
            self.device_type = type_
            self.device_name = id_

    device_map = {
        "sensor0": _D("sensor0", "sensor"),        # 白名单显式空
        "unknown0": _D("unknown0", "robot"),       # 未知类型 → 空白名单
    }
    actions = [
        {"device_id": "sensor0", "action": "turn_on"},
        {"device_id": "unknown0", "action": "turn_on"},
    ]
    waves, plan = _plan_scene_actions(actions, device_map)
    statuses = [it["status"] for it in plan]
    assert statuses == ["rejected", "rejected"]
    assert waves == []  # 无 ok 动作


# ── 边界场景补充（2026-08-12 覆盖率报告第 4 节 7 项）──


class _FakeBridge:
    """可配置 fake 桥：ok=True 返回成功；exc 设置则 send_command 抛异常；
    connect_exc 设置则 connect 抛异常（用于 #4/#5/#7/#8）。"""

    def __init__(self, ok=True, exc=None, connect_exc=None):
        self.ok = ok
        self.exc = exc
        self.connect_exc = connect_exc
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.send_calls = 0

    async def connect(self, credentials):
        self.connect_calls += 1
        if self.connect_exc:
            raise self.connect_exc
        return True

    async def disconnect(self):
        self.disconnect_calls += 1

    async def send_command(self, device_id, command, params):
        self.send_calls += 1
        if self.exc:
            raise self.exc
        return self.ok


def _patch_bridge(monkeypatch, fake: _FakeBridge):
    from app.services import ecosystem_bridge as eb
    monkeypatch.setattr(
        eb.BridgeFactory, "get_bridge",
        lambda ecosystem, credentials=None: fake,
    )
    return fake


@pytest.mark.asyncio
async def test_scene_execute_empty_actions(client: AsyncClient):
    """边界 #1：空 actions 场景执行 → executed=True + 空列表，不崩溃"""
    headers = await _auth_headers(client, "13930030010")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id)
    resp = await client.post(
        "/api/scene-automation/scenes",
        json={
            "project_id": project_id,
            "scheme_id": scheme["id"],
            "scene_name": "空场景",
            "scene_type": "manual",
            "actions": [],
            "enabled": True,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    scene_id = resp.json()["id"]

    resp = await client.post(
        f"/api/scene-automation/scenes/{scene_id}/execute",
        json={"trigger_source": "vr_overlay"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["executed"] is True
    assert data["actions"] == []


@pytest.mark.asyncio
async def test_plan_scene_actions_non_dict_item_skipped():
    """边界 #2：actions 含非 dict 项 → 跳过（执行层防御路径）"""
    from app.services.scene_automation_service import _plan_scene_actions

    class _D:
        def __init__(self, id_, type_):
            self.id = id_
            self.device_type = type_
            self.device_name = id_

    device_map = {"dev0": _D("dev0", "light")}
    actions = ["not-a-dict", {"device_id": "dev0", "action": "turn_off"}]
    waves, plan = _plan_scene_actions(actions, device_map)
    assert len(plan) == 1          # 非 dict 项被跳过
    assert plan[0]["status"] == "ok"
    assert len(waves) == 1


@pytest.mark.asyncio
async def test_plan_scene_actions_dangling_depends_fallback():
    """边界 #3：depends_on 引用不存在 idx → 退化串行不悬挂"""
    from app.services.scene_automation_service import _plan_scene_actions

    class _D:
        def __init__(self, id_, type_):
            self.id = id_
            self.device_type = type_
            self.device_name = id_

    device_map = {"dev0": _D("dev0", "light")}
    actions = [{"device_id": "dev0", "action": "turn_off", "depends_on": 99}]
    waves, plan = _plan_scene_actions(actions, device_map)
    assert len(waves) == 1          # 悬挂依赖 → 退化单波
    assert waves[0][0]["idx"] == 0  # 仍被调度，不悬挂


@pytest.mark.asyncio
async def test_scene_execute_bridge_success(monkeypatch, client: AsyncClient, db_session):
    """边界 #4：桥 success 分支（send_command 返回 True → action_status=success）+ 连接池复用"""
    from sqlalchemy import select

    from app.models.scene_behavior import SceneBehaviorLog

    fake = _patch_bridge(monkeypatch, _FakeBridge(ok=True))
    headers = await _auth_headers(client, "13930030011")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id)
    device = await _create_device(client, headers, scheme["id"])
    scene_id = await _create_scene(client, headers, project_id, scheme["id"], device["id"])

    resp = await client.post(
        f"/api/scene-automation/scenes/{scene_id}/execute",
        json={"trigger_source": "vr_overlay"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["actions"][0]["action_status"] == "success"
    assert fake.connect_calls == 1   # 连接池：单场景 1 次 connect
    assert fake.send_calls == 1
    assert fake.disconnect_calls == 1  # close_all 归还
    # 日志仍真实落库
    logs = (await db_session.execute(
        select(SceneBehaviorLog).where(SceneBehaviorLog.scene_id == scene_id)
    )).scalars().all()
    assert len(logs) == 1
    # 真机执行成功 → 设备实时状态落库（场景动作 turn_off）
    from app.models.smart_home import SmartDevice
    dev = (await db_session.execute(
        select(SmartDevice).where(SmartDevice.id == device["id"])
    )).scalar_one()
    assert dev.state == {"power": False}


@pytest.mark.asyncio
async def test_device_command_bridge_success(monkeypatch, client: AsyncClient, db_session):
    """边界 #4b：设备命令 success 分支"""
    fake = _patch_bridge(monkeypatch, _FakeBridge(ok=True))
    headers = await _auth_headers(client, "13930030012")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id)
    device = await _create_device(client, headers, scheme["id"])

    resp = await client.post(
        f"/api/smart-home/devices/{device['id']}/command",
        json={"action": "turn_off", "params": {}, "source": "vr_overlay"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action_status"] == "success"
    assert data["state"] == {"power": False}  # 真机执行成功 → 实时状态落库
    assert fake.connect_calls == 1
    assert fake.disconnect_calls == 1

    # DB 中 state 真实持久化
    from sqlalchemy import select
    from app.models.smart_home import SmartDevice
    dev = (await db_session.execute(
        select(SmartDevice).where(SmartDevice.id == device["id"])
    )).scalar_one()
    assert dev.state == {"power": False}


@pytest.mark.asyncio
async def test_scene_execute_mixed_statuses(monkeypatch, client: AsyncClient, db_session):
    """边界 #5：混合状态 API 级（success + skipped + rejected 保持动作顺序）"""
    from sqlalchemy import select

    from app.models.scene_behavior import SceneBehaviorLog

    fake = _patch_bridge(monkeypatch, _FakeBridge(ok=True))  # noqa: F841
    headers = await _auth_headers(client, "13930030013")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id)
    device = await _create_device(client, headers, scheme["id"])

    resp = await client.post(
        "/api/scene-automation/scenes",
        json={
            "project_id": project_id,
            "scheme_id": scheme["id"],
            "scene_name": "混合状态",
            "scene_type": "manual",
            "actions": [
                {"device_id": device["id"], "action": "turn_off", "params": {}},   # success
                {"device_id": "missing-dev", "action": "turn_off", "params": {}},  # skipped
                {"device_id": device["id"], "action": "fly", "params": {}},        # rejected
            ],
            "enabled": True,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    scene_id = resp.json()["id"]

    resp = await client.post(
        f"/api/scene-automation/scenes/{scene_id}/execute",
        json={"trigger_source": "vr_overlay"},
        headers=headers,
    )
    assert resp.status_code == 200
    statuses = [a["action_status"] for a in resp.json()["actions"]]
    assert statuses == ["success", "skipped", "rejected"]  # 保持原始顺序
    # 仅 ok 动作落库（1 条）
    logs = (await db_session.execute(
        select(SceneBehaviorLog).where(SceneBehaviorLog.scene_id == scene_id)
    )).scalars().all()
    assert len(logs) == 1


@pytest.mark.asyncio
async def test_device_overlay_empty_project(client: AsyncClient):
    """边界 #6：空项目（无设备 + 无传感器）→ device_count=0 + latest_sensor=None"""
    headers = await _auth_headers(client, "13930030014")
    project_id = await _create_project(client, headers, name="空项目")

    resp = await client.get(
        f"/api/vr/projects/{project_id}/device-overlay", headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["device_count"] == 0
    assert data["devices"] == []
    assert data["latest_sensor"] is None


@pytest.mark.asyncio
async def test_scene_execute_bridge_error_cleanup(monkeypatch, client: AsyncClient, db_session):
    """边界 #7：桥 send_command 抛异常 → failed + close_all 正确清理连接"""
    from sqlalchemy import select

    from app.models.scene_behavior import SceneBehaviorLog

    fake = _patch_bridge(monkeypatch, _FakeBridge(exc=RuntimeError("bridge boom")))
    headers = await _auth_headers(client, "13930030015")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id)
    device = await _create_device(client, headers, scheme["id"])
    scene_id = await _create_scene(client, headers, project_id, scheme["id"], device["id"])

    resp = await client.post(
        f"/api/scene-automation/scenes/{scene_id}/execute",
        json={"trigger_source": "vr_overlay"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["actions"][0]["action_status"] == "failed"
    assert "bridge_error" in (data["actions"][0]["note"] or "")
    # close_all 清理：连接被归还（disconnect 调用 1 次，不泄漏）
    assert fake.connect_calls == 1
    assert fake.disconnect_calls == 1
    assert fake.send_calls == 1
    # 触发日志仍落库（failed 也记录意图）
    logs = (await db_session.execute(
        select(SceneBehaviorLog).where(SceneBehaviorLog.scene_id == scene_id)
    )).scalars().all()
    assert len(logs) == 1


@pytest.mark.asyncio
async def test_device_overlay_default_position(client: AsyncClient):
    """边界 #9：设备无 position（None）→ yaw/pitch 兜底 0.0，不崩溃"""
    headers = await _auth_headers(client, "13930030017")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id)
    await _create_device(client, headers, scheme["id"])  # 不传 position_x/z

    resp = await client.get(
        f"/api/vr/projects/{project_id}/device-overlay", headers=headers,
    )
    assert resp.status_code == 200
    d = resp.json()["devices"][0]
    assert d["yaw"] == 0.0
    assert d["pitch"] == 0.0


@pytest.mark.asyncio
async def test_scene_execute_bridge_connect_error(monkeypatch, client: AsyncClient, db_session):
    """边界 #8：桥 connect 抛异常 → failed + bridge_error 标注；连接未入池，close_all 无泄漏"""
    from sqlalchemy import select

    from app.models.scene_behavior import SceneBehaviorLog

    fake = _patch_bridge(
        monkeypatch, _FakeBridge(ok=True, connect_exc=RuntimeError("connect boom")),
    )
    headers = await _auth_headers(client, "13930030016")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id)
    device = await _create_device(client, headers, scheme["id"])
    scene_id = await _create_scene(client, headers, project_id, scheme["id"], device["id"])

    resp = await client.post(
        f"/api/scene-automation/scenes/{scene_id}/execute",
        json={"trigger_source": "vr_overlay"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["actions"][0]["action_status"] == "failed"
    assert "bridge_error" in (data["actions"][0]["note"] or "")
    assert fake.connect_calls == 1      # 仅 1 次建连尝试
    assert fake.send_calls == 0         # 建连失败，未下发命令
    assert fake.disconnect_calls == 0   # 连接未入池，无需断开（不泄漏）
    # 触发日志仍落库（failed 也记录意图）
    logs = (await db_session.execute(
        select(SceneBehaviorLog).where(SceneBehaviorLog.scene_id == scene_id)
    )).scalars().all()
    assert len(logs) == 1


# ── WS 端到端（2026-08-12）：1.4 数据流闭环验证 ──
# /ws/{project_id} 连接 → device command → 收 smart.device.state
#                     → scene execute → 收 scene.triggered
# 说明：httpx AsyncClient 不支持 WS，用 fastapi TestClient（同步，双实例并行）：
# ws_client 持有 WS 会话，http_client 并行发 REST 命令，验证广播事件可达。


def test_ws_broadcast_device_command_and_scene():
    """WS 端到端：connected → smart.device.state → scene.triggered 事件闭环"""
    from fastapi.testclient import TestClient

    from app.main import app

    http = TestClient(app)
    ws = TestClient(app)

    # 准备数据：注册 → 项目 → 方案 → 设备
    reg = http.post(
        "/api/auth/register",
        json={"phone": "13930030999", "name": "WS联动测试", "password": "test123456"},
    )
    assert reg.status_code == 201, reg.text
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = http.post(
        "/api/projects", json={"name": "WS联动项目", "total_area": 100.0}, headers=headers,
    ).json()["id"]
    scheme = http.post(
        "/api/smart-home/schemes",
        json={
            "project_id": project_id, "room_name": "客厅",
            "room_type": "living_room", "protocol": "zigbee", "hub_brand": "xiaomi",
        },
        headers=headers,
    ).json()
    device = http.post(
        f"/api/smart-home/schemes/{scheme['id']}/devices",
        json={
            "device_type": "light", "device_name": "客厅灯", "brand": "yeelight",
            "protocol": "zigbee", "control_mode": "voice", "power_w": 24.0,
            "status": "online",
        },
        headers=headers,
    ).json()
    # 场景在 WS 连接前创建（创建会广播 scene.created，避免污染会话内断言）
    scene = http.post(
        "/api/scene-automation/scenes",
        json={
            "project_id": project_id,
            "scheme_id": scheme["id"],
            "scene_name": "观影模式",
            "scene_type": "manual",
            "trigger_condition": None,
            "actions": [{"device_id": device["id"], "action": "turn_off", "params": {}}],
            "enabled": True,
        },
        headers=headers,
    ).json()

    # WS 连接（PASETO token 认证 + 项目归属校验）
    with ws.websocket_connect(f"/ws/{project_id}?token={token}") as sock:
        msg = sock.receive_json()
        assert msg["event"] == "connected"

        # ① 设备命令 → smart.device.state 广播
        cmd = http.post(
            f"/api/smart-home/devices/{device['id']}/command",
            json={"action": "turn_off", "params": {}, "source": "vr_overlay"},
            headers=headers,
        )
        assert cmd.status_code == 200
        ev = sock.receive_json()
        assert ev["event"] == "smart.device.state"
        assert ev["data"]["device_id"] == device["id"]
        assert ev["data"]["action"] == "turn_off"
        assert "action_status" in ev["data"]

        # ② 场景执行 → scene.triggered 广播
        exc = http.post(
            f"/api/scene-automation/scenes/{scene['id']}/execute",
            json={"trigger_source": "vr_overlay"},
            headers=headers,
        )
        assert exc.status_code == 200
        ev = sock.receive_json()
        assert ev["event"] == "scene.triggered"
        assert ev["data"]["scene_id"] == scene["id"]
        assert ev["data"]["result"]["actions"][0]["device_id"] == device["id"]
