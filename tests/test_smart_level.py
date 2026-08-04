"""F46 全屋智能 L1-L5 智能等级预适配 + 米家桥接诚实降级测试

覆盖：
- smart_level_service.evaluate_smart_level: L1-L5 五级判定（L3 起真智能）
- smart_level_service.list_levels: 五级定义
- MijiaBridge.connect: 未配置凭据诚实报错，不伪装能力
- GET /api/ecosystem/smart-levels / /smart-level/{project_id}
"""
import pytest
from httpx import AsyncClient

from app.services import smart_level_service
from app.services.ecosystem_bridge import BridgeFactory, MijiaBridge


async def _auth_headers(client: AsyncClient, phone: str = "13950060001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "智能等级测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        "/api/projects", json={"name": "智能等级测试项目", "total_area": 100.0}, headers=headers
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ── 纯函数：五级判定 ──


def test_level_l0_empty():
    """无设备 → L0（未达标，诚实标注）"""
    result = smart_level_service.evaluate_smart_level({})
    assert result["level"] == "L0"
    assert result["is_true_smart"] is False
    assert "gap" in result


def test_level_l1_single_device():
    """≥1 设备 → L1 基础单品智能"""
    result = smart_level_service.evaluate_smart_level({
        "device_count": 1, "room_types": 1, "scene_count": 0,
        "triggered_scene_count": 0, "voice_count": 0, "connected_ecosystems": 0,
    })
    assert result["level"] == "L1"
    assert result["is_true_smart"] is False


def test_level_l2_scene_linkage():
    """≥1 场景 + ≥2 设备 → L2 场景联动"""
    result = smart_level_service.evaluate_smart_level({
        "device_count": 2, "room_types": 1, "scene_count": 1,
        "triggered_scene_count": 0, "voice_count": 0, "connected_ecosystems": 0,
    })
    assert result["level"] == "L2"
    assert result["is_true_smart"] is False


def test_level_l3_whole_home_true_smart():
    """多房间 + 多场景 + 语音 → L3 全屋智能（真智能起点）"""
    result = smart_level_service.evaluate_smart_level({
        "device_count": 6, "room_types": 3, "scene_count": 2,
        "triggered_scene_count": 0, "voice_count": 2, "connected_ecosystems": 0,
    })
    assert result["level"] == "L3"
    assert result["is_true_smart"] is True


def test_level_l4_proactive():
    """传感器主动触发场景 → L4 主动智能"""
    result = smart_level_service.evaluate_smart_level({
        "device_count": 8, "room_types": 3, "scene_count": 2,
        "triggered_scene_count": 1, "voice_count": 2, "connected_ecosystems": 0,
    })
    assert result["level"] == "L4"
    assert result["is_true_smart"] is True


def test_level_l5_autonomous():
    """≥2 生态 + 主动触发 + 多场景 → L5 自主智能"""
    result = smart_level_service.evaluate_smart_level({
        "device_count": 12, "room_types": 4, "scene_count": 3,
        "triggered_scene_count": 1, "voice_count": 3, "connected_ecosystems": 2,
    })
    assert result["level"] == "L5"
    assert result["is_true_smart"] is True


def test_levels_definition():
    """五级定义含 L3 起真智能标记"""
    levels = smart_level_service.list_levels()
    assert len(levels) == 5
    codes = [lv["level"] for lv in levels]
    assert codes == ["L1", "L2", "L3", "L4", "L5"]
    true_smart = [lv for lv in levels if lv["is_true_smart"]]
    assert [lv["level"] for lv in true_smart] == ["L3", "L4", "L5"]


# ── 米家桥接诚实降级 ──


@pytest.mark.asyncio
async def test_mijia_bridge_requires_credentials():
    """未配置凭据 → 诚实报错，不伪装能力"""
    bridge = MijiaBridge()
    with pytest.raises(ValueError):
        await bridge.connect({})
    assert bridge.is_connected() is False

    with pytest.raises(ValueError):
        await bridge.connect({"username": "u"})  # 缺 password
    assert bridge.is_connected() is False


@pytest.mark.asyncio
async def test_mijia_bridge_login_failure_is_honest(monkeypatch):
    """云登录失败 → 如实报错，不置为已连接"""
    bridge = MijiaBridge()

    async def _fail(username, password):
        return None

    monkeypatch.setattr(bridge, "_xiaoai_login", _fail)
    with pytest.raises(RuntimeError, match="登录失败"):
        await bridge.connect({"username": "u", "password": "p"})
    assert bridge.is_connected() is False


@pytest.mark.asyncio
async def test_mijia_bridge_login_success(monkeypatch):
    """云登录成功 → 已连接；未接设备签名请求仍诚实 NotImplementedError"""
    bridge = MijiaBridge()

    async def _ok(username, password):
        return "session_cookie=abc"

    monkeypatch.setattr(bridge, "_xiaoai_login", _ok)
    assert await bridge.connect({"username": "u", "password": "p"}) is True
    assert bridge.is_connected() is True

    # 设备清单未接 python-miio，诚实报错而非伪装数据
    with pytest.raises(NotImplementedError):
        await bridge.get_devices()


@pytest.mark.asyncio
async def test_bridge_factory_mijia():
    """工厂能创建米家桥接实例"""
    bridge = BridgeFactory.get_bridge("mijia")
    assert isinstance(bridge, MijiaBridge)


# ── API 集成 ──


@pytest.mark.asyncio
async def test_smart_levels_api(client: AsyncClient):
    """GET /api/ecosystem/smart-levels 返回五级定义"""
    headers = await _auth_headers(client, "13950060002")
    resp = await client.get("/api/ecosystem/smart-levels", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 5


@pytest.mark.asyncio
async def test_smart_level_project_api(client: AsyncClient):
    """GET /api/ecosystem/smart-level/{project_id} 空项目 → L0 诚实标注"""
    headers = await _auth_headers(client, "13950060003")
    project_id = await _create_project(client, headers)
    resp = await client.get(f"/api/ecosystem/smart-level/{project_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["evaluation"]["level"] == "L0"
    assert data["snapshot"]["device_count"] == 0
    assert "gap" in data["evaluation"]


@pytest.mark.asyncio
async def test_smart_level_cross_user_blocked(client: AsyncClient):
    """他人项目智能等级 → 403"""
    headers_a = await _auth_headers(client, "13950060004")
    headers_b = await _auth_headers(client, "13950060005")
    project_id = await _create_project(client, headers_a)
    resp = await client.get(f"/api/ecosystem/smart-level/{project_id}", headers=headers_b)
    assert resp.status_code == 403
