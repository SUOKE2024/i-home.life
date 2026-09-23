"""2026-09-23 智能家居生态全链路接入修复验证

覆盖（对应本轮全链路审计的 P0/P1/P2 项）：
- P1-4 生态注册表 key 与 BridgeFactory 逐字一致（此前 "harmony" vs "harmonyos" 漂移 → 恒 pending）
- P1-4 /api/ecosystem/status 支持 project_id 报告项目级真实凭据就绪度（不再与真机通道脱节），凭据值不出接口
- P1-6 无桥生态（alexa/google_home）不再被 schema 接受（假能力），sync 归因 unsupported_ecosystem
- P1-7 设备命令 ecosystem 缺省时按项目凭据自动解析（消除与场景执行的真机可达性不对称）
- P2-11 /scenes/parse 与 /matter/device-types 补鉴权
"""
import pytest
from httpx import AsyncClient


# ── 辅助 ──


async def _auth_headers(client: AsyncClient, phone: str = "13970010001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "生态链路测试", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "生态链路项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 88.0}, headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_scheme(client: AsyncClient, headers: dict, project_id: str) -> dict:
    resp = await client.post(
        "/api/smart-home/schemes",
        json={"project_id": project_id, "room_name": "客厅", "room_type": "living_room"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_device(client: AsyncClient, headers: dict, scheme_id: str) -> dict:
    resp = await client.post(
        f"/api/smart-home/schemes/{scheme_id}/devices",
        json={"device_type": "light", "device_name": "客厅灯", "status": "online"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_ecosystem(
    client: AsyncClient, headers: dict, project_id: str,
    ecosystem: str = "mijia", config: dict | None = None,
) -> dict:
    resp = await client.post(
        "/api/scene-automation/ecosystems",
        json={"project_id": project_id, "ecosystem": ecosystem, "config": config},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


class _CapturingBridge:
    """记录 connect/send 的假桥；无凭据时抛 ValueError（对齐真实桥的必要凭据语义）。"""

    def __init__(self, require_credentials: bool = True):
        self.require_credentials = require_credentials
        self.connect_calls = 0
        self.send_calls = 0
        self.last_credentials: dict | None = None

    async def connect(self, credentials=None):
        self.connect_calls += 1
        if self.require_credentials and not credentials:
            raise ValueError("桥接需要凭据（username/password）")
        self.last_credentials = credentials

    async def disconnect(self):
        return None

    async def send_command(self, device_id, action, params=None):
        self.send_calls += 1
        return True


def _patch_bridge(monkeypatch, fake: _CapturingBridge, captured: list):
    from app.services import ecosystem_bridge as eb

    def _get(ecosystem, credentials=None):
        captured.append((ecosystem, credentials))
        return fake

    monkeypatch.setattr(eb.BridgeFactory, "get_bridge", _get)
    return fake


# ── P1-4：注册表 / schema / 桥工厂三方一致（防再次漂移）──


@pytest.mark.asyncio
async def test_registry_keys_match_bridge_factory(client: AsyncClient):
    """生态注册表 key 必须与 BridgeFactory 可解析键逐字一致（历史 harmony→harmonyos 漂移）"""
    from app.services import ecosystem_bridge_status as ebs
    from app.services.ecosystem_bridge import BridgeFactory

    headers = await _auth_headers(client, "13970010002")
    listed = await client.get("/api/ecosystem/bridges", headers=headers)
    assert listed.status_code == 200
    registry_keys = [b["key"] for b in listed.json()["bridges"]]
    assert registry_keys == ["mijia", "harmonyos", "homekit", "tuya"]

    for item in ebs.ECOSYSTEMS:
        assert item["bridge"] == item["key"]
        # 注册表 key 必须能被工厂解析（否则按注册表配置的生态会 ValueError → 恒 pending）
        assert BridgeFactory.get_bridge(item["key"]) is not None

    implemented = {b["key"]: b["implemented"] for b in listed.json()["bridges"]}
    assert implemented["mijia"] is True          # 米家已接真机（python-miio 云/局域网）
    assert implemented["harmonyos"] is False     # 其余仍为 stub（诚实标注）


@pytest.mark.asyncio
async def test_ecosystem_schema_literal_matches_bridges(client: AsyncClient):
    """EcosystemIntegrationCreate 接受的生态集合 == 有桥生态集合（防 schema 与工厂漂移）"""
    from typing import get_args

    from app.schemas.scene_automation import EcosystemName
    from app.services.ecosystem_bridge import BridgeFactory

    literal = get_args(EcosystemName)[0]
    assert set(get_args(literal)) == set(BridgeFactory._bridges.keys())


# ── P1-4：状态报告接项目级真实凭据通道 ──


@pytest.mark.asyncio
async def test_status_report_project_readiness(client: AsyncClient):
    """带 project_id 时报告项目级真实凭据就绪度，且凭据值永不出接口"""
    headers = await _auth_headers(client, "13970010003")
    project_id = await _create_project(client, headers)
    await _create_ecosystem(
        client, headers, project_id, "mijia",
        {"username": "mi-user", "password": "mi-secret"},
    )

    resp = await client.get(
        f"/api/ecosystem/status?project_id={project_id}", headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["project_id"] == project_id
    assert "credential_channel_note" in data

    mijia = next(b for b in data["bridges"] if b["key"] == "mijia")
    assert mijia["project_configured"] is True
    assert mijia["has_credentials"] is True
    assert sorted(mijia["credential_keys"]) == ["password", "username"]  # 只回露字段名

    # 凭据值绝不外泄
    body = resp.text
    assert "mi-user" not in body and "mi-secret" not in body

    # 未接入的项目生态不得因 mijia 有凭据而被判就绪
    alive = next(b for b in data["bridges"] if b["key"] == "homekit")
    assert alive["project_configured"] is False


@pytest.mark.asyncio
async def test_status_report_without_project_id_is_none(client: AsyncClient):
    """不传 project_id 时 project_configured 为 None（区分「未查询」与「查询无凭据」）"""
    headers = await _auth_headers(client, "13970010004")
    resp = await client.get("/api/ecosystem/status", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] is None
    for bridge in data["bridges"]:
        assert bridge["project_configured"] is None
        assert bridge["has_credentials"] is None


@pytest.mark.asyncio
async def test_status_report_project_idor(client: AsyncClient):
    """他人项目：status?project_id= 必须拒绝（403），不得泄露凭据就绪度"""
    owner_headers = await _auth_headers(client, "13970010005")
    project_id = await _create_project(client, owner_headers, "owner 项目")
    await _create_ecosystem(
        client, owner_headers, project_id, "mijia",
        {"username": "u", "password": "p"},
    )
    other_headers = await _auth_headers(client, "13970010006")
    resp = await client.get(
        f"/api/ecosystem/status?project_id={project_id}", headers=other_headers,
    )
    assert resp.status_code == 403


# ── P1-6：无桥生态不伪装能力 ──


@pytest.mark.asyncio
async def test_create_ecosystem_rejects_ecosystem_without_bridge(client: AsyncClient):
    """alexa/google_home 无桥接实现 → 创建生态对接触发 422（不再产生"创建成功却永不可同步"）"""
    from app.services.ecosystem_bridge import BridgeFactory

    assert "alexa" not in BridgeFactory._bridges
    assert "google_home" not in BridgeFactory._bridges

    headers = await _auth_headers(client, "13970010007")
    project_id = await _create_project(client, headers)
    for eco in ("alexa", "google_home"):
        resp = await client.post(
            "/api/scene-automation/ecosystems",
            json={"project_id": project_id, "ecosystem": eco},
            headers=headers,
        )
        assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_sync_unsupported_ecosystem_attribution(client: AsyncClient):
    """sync 到无桥生态：归因 unsupported_ecosystem（不再误报「凭据未配置或不完整」）"""
    from app.services import ecosystem_bridge as eb

    headers = await _auth_headers(client, "13970010008")
    project_id = await _create_project(client, headers)
    scene_resp = await client.post(
        "/api/scene-automation/scenes",
        json={
            "project_id": project_id, "scene_name": "回家模式", "scene_type": "manual",
            "actions": [{"device_id": "d1", "action": "turn_on"}],
        },
        headers=headers,
    )
    assert scene_resp.status_code == 201, scene_resp.text
    scene_id = scene_resp.json()["id"]

    # 无桥生态：mock 工厂行为不受影响，走的是不存在的生态键
    assert eb.BridgeFactory._bridges.get("alexa") is None
    resp = await client.post(
        f"/api/scene-automation/scenes/{scene_id}/sync",
        json={"ecosystem": "alexa"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["synced"] is False
    assert data["reason"].startswith("unsupported_ecosystem")
    assert "凭据" not in data["message"]           # 不误导为凭据问题

    # 失败生态不落库生态对接（避免脏记录）
    listed = await client.get(
        f"/api/scene-automation/ecosystems/project/{project_id}", headers=headers,
    )
    assert listed.status_code == 200
    assert listed.json() == []


# ── P1-7：设备命令生态自动解析（与场景执行对称）──


@pytest.mark.asyncio
async def test_device_command_auto_resolves_project_ecosystem(
    monkeypatch, client: AsyncClient, db_session,
):
    """设备命令不传 ecosystem → 自动解析到项目已配置凭据的米家桥（此前硬默认 matter → 恒 pending）"""
    headers = await _auth_headers(client, "13970010009")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id)
    device = await _create_device(client, headers, scheme["id"])
    await _create_ecosystem(
        client, headers, project_id, "mijia",
        {"username": "mi-user", "password": "mi-secret"},
    )

    captured: list = []
    fake = _patch_bridge(monkeypatch, _CapturingBridge(), captured)

    resp = await client.post(
        f"/api/smart-home/devices/{device['id']}/command",
        json={"action": "turn_on", "params": {}, "source": "vr_overlay"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["action_status"] == "success"
    assert fake.send_calls == 1
    assert captured[0][0] == "mijia"                                  # 自动解析到项目生态
    assert captured[0][1] == {"username": "mi-user", "password": "mi-secret"}


@pytest.mark.asyncio
async def test_device_command_auto_resolve_fallback_matter(
    monkeypatch, client: AsyncClient, db_session,
):
    """项目无任何生态凭据 → 仍兜底 matter（保持历史行为），桥缺凭据诚实 pending"""
    headers = await _auth_headers(client, "13970010010")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id)
    device = await _create_device(client, headers, scheme["id"])

    captured: list = []
    _patch_bridge(monkeypatch, _CapturingBridge(), captured)

    resp = await client.post(
        f"/api/smart-home/devices/{device['id']}/command",
        json={"action": "turn_on", "params": {}, "source": "app"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["action_status"] == "pending"
    assert captured[0][0] == "matter"


# ── P2-11：补鉴权端点 ──


@pytest.mark.asyncio
async def test_parse_and_device_types_require_auth(client: AsyncClient):
    """场景自然语言解析与 Matter 设备类型目录均需认证（此前匿名可调）"""
    headers = await _auth_headers(client, "13970010011")

    unauth_parse = await client.post(
        "/api/scene-automation/scenes/parse", json={"text": "回家时打开灯"},
    )
    assert unauth_parse.status_code == 401
    auth_parse = await client.post(
        "/api/scene-automation/scenes/parse",
        json={"text": "回家时打开灯"},
        headers=headers,
    )
    assert auth_parse.status_code == 200
    assert auth_parse.json()["parsed"] is True

    unauth_types = await client.get("/api/smart-home/matter/device-types")
    assert unauth_types.status_code == 401
    auth_types = await client.get("/api/smart-home/matter/device-types", headers=headers)
    assert auth_types.status_code == 200
