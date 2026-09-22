"""2026-09-22 P0/P1 修复验证：生态桥凭据通道 + 生态凭据加密 + 传感器触发执行闭环

覆盖（对应 docs/reports/partner-franchise-tech-assessment-20260922.md）：
- P0-2 设备命令/场景执行路径注入生态桥凭据（此前 pool.get(ecosystem) 不带凭据 → 真机不可达）
- P0-3 SceneAutomation.ecosystem 显式列 + 项目凭据自动解析 + matter 兜底
- P0-4 check_sensor_triggers 命中后真实执行场景动作（此前仅写日志）
- P1-4 生态凭据 AES-256-GCM 加密落库 + API 响应脱敏 + 历史明文兼容
"""
import pytest
from httpx import AsyncClient


# ── 辅助 ──


async def _auth_headers(client: AsyncClient, phone: str = "13930040001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "凭据通道测试", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "凭据通道项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 100.0}, headers=headers,
    )
    assert resp.status_code == 201, resp.text
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
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_device(client: AsyncClient, headers: dict, scheme_id: str) -> dict:
    resp = await client.post(
        f"/api/smart-home/schemes/{scheme_id}/devices",
        json={
            "device_type": "light", "device_name": "客厅灯", "brand": "yeelight",
            "protocol": "zigbee", "control_mode": "voice", "power_w": 24.0, "status": "online",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_ecosystem(
    client: AsyncClient, headers: dict, project_id: str,
    ecosystem: str = "mijia", config: dict | None = None,
) -> dict:
    body = {"project_id": project_id, "ecosystem": ecosystem, "config": config}
    resp = await client.post("/api/scene-automation/ecosystems", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


class _CapturingBridge:
    """记录 connect/send 的假桥；无凭据时抛 ValueError（对齐真实桥的必要凭据语义）。"""

    def __init__(self, ok: bool = True, require_credentials: bool = True):
        self.ok = ok
        self.require_credentials = require_credentials
        self.connect_calls = 0
        self.send_calls = 0
        self.disconnect_calls = 0
        self.last_credentials: dict | None = None

    async def connect(self, credentials=None):
        self.connect_calls += 1
        if self.require_credentials and not credentials:
            raise ValueError("桥接需要凭据（username/password）")
        self.last_credentials = credentials

    async def disconnect(self):
        self.disconnect_calls += 1

    async def send_command(self, device_id, action, params=None):
        self.send_calls += 1
        return self.ok


def _patch_bridge(monkeypatch, fake: _CapturingBridge, captured: list | None = None):
    """替换 BridgeFactory.get_bridge，记录每次调用的 (ecosystem, credentials)。"""
    from app.services import ecosystem_bridge as eb

    def _get(ecosystem, credentials=None):
        if captured is not None:
            captured.append((ecosystem, credentials))
        return fake

    monkeypatch.setattr(eb.BridgeFactory, "get_bridge", _get)
    return fake


# ── P0-2：设备命令注入凭据 ──


@pytest.mark.asyncio
async def test_device_command_injects_ecosystem_credentials(
    monkeypatch, client: AsyncClient, db_session,
):
    """设备命令：项目下 mijia 生态凭据解密后传入桥（此前不带凭据 → 真机不可达）"""
    headers = await _auth_headers(client, "13930040002")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id)
    device = await _create_device(client, headers, scheme["id"])
    await _create_ecosystem(
        client, headers, project_id, "mijia",
        {"username": "mi-user", "password": "mi-secret"},
    )

    captured: list = []
    fake = _patch_bridge(monkeypatch, _CapturingBridge(ok=True), captured)

    resp = await client.post(
        f"/api/smart-home/devices/{device['id']}/command",
        json={"action": "turn_on", "params": {}, "ecosystem": "mijia", "source": "app"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["action_status"] == "success"
    assert fake.connect_calls == 1
    # 凭据真实注入且为解密后的明文（桥需要明文凭据才能登录）
    assert captured and captured[0][0] == "mijia"
    assert captured[0][1] == {"username": "mi-user", "password": "mi-secret"}


@pytest.mark.asyncio
async def test_device_command_without_credentials_stays_pending(
    monkeypatch, client: AsyncClient,
):
    """设备命令：未配置生态凭据 → 诚实 pending + bridge_not_configured（不伪装执行）"""
    headers = await _auth_headers(client, "13930040003")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id)
    device = await _create_device(client, headers, scheme["id"])

    captured: list = []
    _patch_bridge(monkeypatch, _CapturingBridge(ok=True), captured)

    resp = await client.post(
        f"/api/smart-home/devices/{device['id']}/command",
        json={"action": "turn_on", "params": {}, "ecosystem": "mijia", "source": "app"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["action_status"] == "pending"
    assert "bridge_not_configured" in (data["note"] or "")
    assert captured[0][1] == {}  # 无凭据 → 空 dict（桥自身诚实抛错）


# ── P0-3：场景 ecosystem 解析 ──


async def _create_scene(
    client: AsyncClient, headers: dict, project_id: str, scheme_id: str,
    device_id: str, ecosystem: str | None = None,
) -> str:
    body = {
        "project_id": project_id,
        "scheme_id": scheme_id,
        "scene_name": "回家模式",
        "scene_type": "manual",
        "actions": [{"device_id": device_id, "action": "turn_on", "params": {}}],
        "enabled": True,
    }
    if ecosystem:
        body["ecosystem"] = ecosystem
    resp = await client.post("/api/scene-automation/scenes", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_scene_explicit_ecosystem_column_used(monkeypatch, client: AsyncClient):
    """场景显式 ecosystem 列生效：不再恒走 matter 兜底桥"""
    headers = await _auth_headers(client, "13930040004")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id)
    device = await _create_device(client, headers, scheme["id"])
    await _create_ecosystem(client, headers, project_id, "mijia", {"username": "u", "password": "p"})
    scene_id = await _create_scene(client, headers, project_id, scheme["id"], device["id"], "mijia")

    captured: list = []
    _patch_bridge(monkeypatch, _CapturingBridge(ok=True), captured)

    resp = await client.post(
        f"/api/scene-automation/scenes/{scene_id}/execute",
        json={"trigger_source": "vr_overlay"}, headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["actions"][0]["action_status"] == "success"
    assert captured[0][0] == "mijia"
    assert captured[0][1] == {"username": "u", "password": "p"}


@pytest.mark.asyncio
async def test_scene_ecosystem_auto_resolved_from_project_credentials(
    monkeypatch, client: AsyncClient,
):
    """场景未指定 ecosystem → 按项目下首个已配置凭据的生态对接解析"""
    headers = await _auth_headers(client, "13930040005")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id)
    device = await _create_device(client, headers, scheme["id"])
    await _create_ecosystem(client, headers, project_id, "mijia", {"username": "u2", "password": "p2"})
    scene_id = await _create_scene(client, headers, project_id, scheme["id"], device["id"])

    captured: list = []
    _patch_bridge(monkeypatch, _CapturingBridge(ok=True), captured)

    resp = await client.post(
        f"/api/scene-automation/scenes/{scene_id}/execute",
        json={"trigger_source": "vr_overlay"}, headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["actions"][0]["action_status"] == "success"
    assert captured[0][0] == "mijia"
    assert captured[0][1] == {"username": "u2", "password": "p2"}


@pytest.mark.asyncio
async def test_scene_ecosystem_fallback_matter_when_unconfigured(
    monkeypatch, client: AsyncClient,
):
    """无任何生态凭据 → 兜底 matter（保持历史行为），桥缺凭据诚实 pending"""
    headers = await _auth_headers(client, "13930040006")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id)
    device = await _create_device(client, headers, scheme["id"])
    scene_id = await _create_scene(client, headers, project_id, scheme["id"], device["id"])

    class _Stub(_CapturingBridge):
        async def connect(self, credentials=None):
            self.connect_calls += 1
            raise NotImplementedError("Matter 桥未实现")

    fake = _patch_bridge(monkeypatch, _Stub())

    resp = await client.post(
        f"/api/scene-automation/scenes/{scene_id}/execute",
        json={"trigger_source": "vr_overlay"}, headers=headers,
    )
    assert resp.status_code == 200, resp.text
    action = resp.json()["actions"][0]
    assert action["action_status"] == "pending"
    assert "bridge_not_configured" in (action["note"] or "")
    assert fake.connect_calls == 1


@pytest.mark.asyncio
async def test_scene_ecosystem_response_field(client: AsyncClient):
    """SceneAutomationResponse 暴露 ecosystem 字段（创建/读取一致）"""
    headers = await _auth_headers(client, "13930040007")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id)
    device = await _create_device(client, headers, scheme["id"])
    scene_id = await _create_scene(client, headers, project_id, scheme["id"], device["id"], "mijia")

    resp = await client.get(
        f"/api/scene-automation/scenes/project/{project_id}", headers=headers,
    )
    assert resp.status_code == 200, resp.text
    scenes = resp.json()
    target = next(s for s in scenes if s["id"] == scene_id)
    assert target["ecosystem"] == "mijia"


# ── P0-4：传感器触发执行闭环 ──


async def _create_sensor_scene(
    client: AsyncClient, headers: dict, project_id: str, scheme_id: str, device_id: str,
) -> str:
    resp = await client.post(
        "/api/scene-automation/scenes",
        json={
            "project_id": project_id,
            "scheme_id": scheme_id,
            "scene_name": "高温联动",
            "scene_type": "triggered",
            "trigger_condition": {"type": "sensor", "condition": {"temperature": {"gt": 28}}},
            "actions": [{"device_id": device_id, "action": "turn_on", "params": {}}],
            "ecosystem": "mijia",
            "enabled": True,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _upload_hot_snapshot(client: AsyncClient, headers: dict) -> dict:
    resp = await client.post(
        "/api/sensors/snapshot",
        json={
            "temperature": 30.5,
            "humidity": 55.0,
            "timestamp": "2026-09-22T10:00:00",
            "platform": "ios",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_sensor_trigger_actually_executes_actions(
    monkeypatch, client: AsyncClient, db_session,
):
    """P0-4：传感器命中 → 真实调用桥执行动作（此前仅写日志恒 pending）"""
    headers = await _auth_headers(client, "13930040008")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id)
    device = await _create_device(client, headers, scheme["id"])
    await _create_ecosystem(client, headers, project_id, "mijia", {"username": "u3", "password": "p3"})
    scene_id = await _create_sensor_scene(
        client, headers, project_id, scheme["id"], device["id"],
    )

    captured: list = []
    fake = _patch_bridge(monkeypatch, _CapturingBridge(ok=True), captured)
    await _upload_hot_snapshot(client, headers)

    assert fake.send_calls == 1, "传感器命中必须真实执行动作"
    assert captured[0][0] == "mijia" and captured[0][1] == {"username": "u3", "password": "p3"}

    # 设备状态真实回写（执行成功才写，诚实数据源）
    from sqlalchemy import select

    from app.models.smart_home import SmartDevice
    dev = (await db_session.execute(
        select(SmartDevice).where(SmartDevice.id == device["id"])
    )).scalar_one()
    assert dev.state == {"power": True}

    # 触发日志真实落库（scene_id 关联）
    from app.models.scene_behavior import SceneBehaviorLog
    logs = (await db_session.execute(
        select(SceneBehaviorLog).where(SceneBehaviorLog.scene_id == scene_id)
    )).scalars().all()
    assert len(logs) >= 1
    assert all(log.action_type == "sensor_trigger" for log in logs)


@pytest.mark.asyncio
async def test_sensor_trigger_uses_scene_ecosystem(monkeypatch, client: AsyncClient):
    """传感器触发同样走场景显式 ecosystem（凭据注入一致）"""
    headers = await _auth_headers(client, "13930040009")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id)
    device = await _create_device(client, headers, scheme["id"])
    await _create_ecosystem(client, headers, project_id, "mijia", {"username": "u4", "password": "p4"})
    scene_id = await _create_scene(client, headers, project_id, scheme["id"], device["id"], "mijia")

    resp = await client.patch(
        f"/api/scene-automation/scenes/{scene_id}",
        json={"trigger_condition": {"type": "sensor", "condition": {"temperature": {"gt": 28}}}},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    captured: list = []
    fake = _patch_bridge(monkeypatch, _CapturingBridge(ok=True), captured)
    await _upload_hot_snapshot(client, headers)

    assert fake.send_calls == 1
    assert captured[0] == ("mijia", {"username": "u4", "password": "p4"})


# ── P1-4：生态凭据加密与脱敏 ──


@pytest.mark.asyncio
async def test_ecosystem_config_encrypted_at_rest(client: AsyncClient, db_session):
    """POST /ecosystems：config 加密落库，DB 中不含明文凭据"""
    from sqlalchemy import select

    from app.models.scene_automation import EcosystemIntegration
    from app.services.device_credentials import decrypt_device_credentials

    headers = await _auth_headers(client, "13930040010")
    project_id = await _create_project(client, headers)
    eco = await _create_ecosystem(
        client, headers, project_id, "mijia",
        {"username": "mi-user", "password": "mi-secret"},
    )

    row = (await db_session.execute(
        select(EcosystemIntegration).where(EcosystemIntegration.id == eco["id"])
    )).scalar_one()
    assert isinstance(row.config, dict)
    assert "encrypted" in row.config
    assert "mi-secret" not in str(row.config)  # 明文绝不落库
    assert decrypt_device_credentials(row.config) == {
        "username": "mi-user", "password": "mi-secret",
    }


@pytest.mark.asyncio
async def test_ecosystem_config_redacted_in_api_response(client: AsyncClient):
    """API 响应脱敏：只回露字段名，不回露任何凭据值（此前原样回露）"""
    headers = await _auth_headers(client, "13930040011")
    project_id = await _create_project(client, headers)
    created = await _create_ecosystem(
        client, headers, project_id, "mijia",
        {"username": "mi-user", "password": "mi-secret"},
    )
    assert "mi-secret" not in str(created)
    assert created["config"] == {"redacted": True, "keys": ["password", "username"]}

    lst = await client.get(
        f"/api/scene-automation/ecosystems/project/{project_id}", headers=headers,
    )
    assert lst.status_code == 200, lst.text
    assert "mi-secret" not in lst.text
    assert lst.json()[0]["config"] == {"redacted": True, "keys": ["password", "username"]}


@pytest.mark.asyncio
async def test_ecosystem_without_config_keeps_none(client: AsyncClient):
    """无 config 的生态对接：config 保持 None（不产生空密文）"""
    headers = await _auth_headers(client, "13930040012")
    project_id = await _create_project(client, headers)
    eco = await _create_ecosystem(client, headers, project_id, "homekit")
    assert eco["config"] is None


@pytest.mark.asyncio
async def test_legacy_plaintext_config_still_resolved(client: AsyncClient, db_session):
    """历史明文行（未迁移）读取路径兼容：仍能被解析为桥凭据"""
    from app.models.scene_automation import EcosystemIntegration
    from app.services.scene_automation_service import _resolve_ecosystem_credentials

    headers = await _auth_headers(client, "13930040013")
    project_id = await _create_project(client, headers)

    legacy = EcosystemIntegration(
        project_id=project_id,
        ecosystem="tuya",
        auth_status="disconnected",
        config={"access_id": "legacy-id", "access_secret": "legacy-secret"},
    )
    db_session.add(legacy)
    await db_session.commit()

    creds = await _resolve_ecosystem_credentials(db_session, project_id, "tuya")
    assert creds == {"access_id": "legacy-id", "access_secret": "legacy-secret"}


@pytest.mark.asyncio
async def test_sync_to_ecosystem_uses_decrypted_credentials(client: AsyncClient, db_session):
    """场景同步路径同样解密凭据（此前直接传 eco.config → 加密后必失败）"""
    from app.models.scene_automation import SceneAutomation
    from app.services.scene_automation_service import sync_to_ecosystem

    headers = await _auth_headers(client, "13930040014")
    project_id = await _create_project(client, headers)
    await _create_ecosystem(client, headers, project_id, "mijia", {"username": "u5", "password": "p5"})

    scene = SceneAutomation(
        project_id=project_id,
        scene_name="同步场景",
        scene_type="manual",
        actions=[],
        enabled=True,
    )
    db_session.add(scene)
    await db_session.commit()
    await db_session.refresh(scene)

    from app.services.ecosystem_bridge import MijiaBridge

    calls: list = []

    async def _fake_connect(self, credentials=None):
        calls.append(credentials)

    async def _fake_sync(self, scenes):
        return None

    async def _fake_disconnect(self):
        return None

    import pytest as _pytest
    monkey = _pytest.MonkeyPatch()
    monkey.setattr(MijiaBridge, "connect", _fake_connect)
    monkey.setattr(MijiaBridge, "sync_scenes", _fake_sync)
    monkey.setattr(MijiaBridge, "disconnect", _fake_disconnect)
    try:
        result = await sync_to_ecosystem(db_session, scene, "mijia")
    finally:
        monkey.undo()

    assert result["synced"] is True, result
    assert calls == [{"username": "u5", "password": "p5"}]
