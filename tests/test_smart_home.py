"""F31 智能家居方案设计器 API 集成测试

覆盖端点:
- POST   /api/smart-home/schemes                     (创建方案)
- GET    /api/smart-home/schemes/project/{project_id} (按项目列方案)
- GET    /api/smart-home/schemes/{scheme_id}          (方案详情)
- PATCH  /api/smart-home/schemes/{scheme_id}          (更新方案)
- DELETE /api/smart-home/schemes/{scheme_id}          (删除方案)
- POST   /api/smart-home/schemes/{id}/auto-recommend  (自动推荐)
- GET    /api/smart-home/schemes/{id}/wiring          (布线规划)
- GET    /api/smart-home/schemes/{id}/protocol-advice (协议选型)
- GET    /api/smart-home/schemes/{id}/price           (方案总价)
- POST   /api/smart-home/schemes/{id}/devices         (添加设备)
- GET    /api/smart-home/schemes/{id}/devices          (列出设备)
- DELETE /api/smart-home/devices/{device_id}           (删除设备)
- PATCH  /api/smart-home/devices/{device_id}           (更新设备)
- GET    /api/smart-home/matter/device-types           (Matter 设备类型)
- POST   /api/smart-home/matter/placement-plan         (点位规划)
- POST   /api/smart-home/matter/commission             (配网)
"""
import pytest
from httpx import AsyncClient


async def _auth_headers(client: AsyncClient, phone: str = "13920020001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "智能家居测试", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "智能家居测试项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 100.0}, headers=headers,
    )
    return resp.json()["id"]


async def _create_scheme(
    client: AsyncClient, headers: dict, project_id: str, room_name: str = "客厅",
) -> dict:
    resp = await client.post(
        "/api/smart-home/schemes",
        json={
            "project_id": project_id, "room_name": room_name,
            "room_type": "living_room", "protocol": "zigbee", "hub_brand": "xiaomi",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()


# ── Auth ──


@pytest.mark.asyncio
async def test_smart_home_unauthorized(client: AsyncClient):
    """未认证用户不能创建方案"""
    resp = await client.post(
        "/api/smart-home/schemes",
        json={
            "project_id": "fake", "room_name": "客厅",
            "room_type": "living_room",
        },
    )
    assert resp.status_code == 401


# ── 方案 CRUD ──


@pytest.mark.asyncio
async def test_create_and_get_scheme(client: AsyncClient):
    """创建并获取智能家居方案"""
    headers = await _auth_headers(client, "13920020002")
    project_id = await _create_project(client, headers)

    created = await _create_scheme(client, headers, project_id, "客厅")
    assert created["room_name"] == "客厅"
    assert created["room_type"] == "living_room"
    assert created["protocol"] == "zigbee"

    resp = await client.get(f"/api/smart-home/schemes/{created['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["room_name"] == "客厅"


@pytest.mark.asyncio
async def test_list_schemes_by_project(client: AsyncClient):
    """按项目列出智能家居方案"""
    headers = await _auth_headers(client, "13920020003")
    project_id = await _create_project(client, headers)

    await _create_scheme(client, headers, project_id, "客厅")
    await _create_scheme(client, headers, project_id, "主卧")

    resp = await client.get(
        f"/api/smart-home/schemes/project/{project_id}", headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_update_scheme(client: AsyncClient):
    """更新智能家居方案"""
    headers = await _auth_headers(client, "13920020004")
    project_id = await _create_project(client, headers)
    created = await _create_scheme(client, headers, project_id, "客厅")

    resp = await client.patch(
        f"/api/smart-home/schemes/{created['id']}",
        json={"room_name": "主卧", "protocol": "matter"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["room_name"] == "主卧"
    assert data["protocol"] == "matter"


@pytest.mark.asyncio
async def test_delete_scheme(client: AsyncClient):
    """删除智能家居方案"""
    headers = await _auth_headers(client, "13920020005")
    project_id = await _create_project(client, headers)
    created = await _create_scheme(client, headers, project_id, "客厅")

    resp = await client.delete(f"/api/smart-home/schemes/{created['id']}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/smart-home/schemes/{created['id']}", headers=headers)
    assert resp.status_code == 404


# ── 设备 CRUD ──


@pytest.mark.asyncio
async def test_add_list_update_delete_device(client: AsyncClient):
    """设备的完整生命周期：添加 → 列表 → 更新 → 删除"""
    headers = await _auth_headers(client, "13920020006")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id, "客厅")

    # 添加设备
    resp = await client.post(
        f"/api/smart-home/schemes/{scheme['id']}/devices",
        json={
            "device_type": "light", "device_name": "吸顶灯",
            "brand": "Aqara", "protocol": "zigbee",
            "position_x": 0.0, "position_y": 0.0,
            "power_w": 12.0, "price": 199.0,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    device = resp.json()
    assert device["device_name"] == "吸顶灯"
    assert device["price"] == 199.0

    # 列表
    resp = await client.get(
        f"/api/smart-home/schemes/{scheme['id']}/devices", headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # 更新设备
    resp = await client.patch(
        f"/api/smart-home/devices/{device['id']}",
        json={"device_name": "智能吸顶灯", "power_w": 15.0},
        headers=headers,
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["device_name"] == "智能吸顶灯"
    assert updated["power_w"] == 15.0

    # 删除设备
    resp = await client.delete(f"/api/smart-home/devices/{device['id']}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(
        f"/api/smart-home/schemes/{scheme['id']}/devices", headers=headers,
    )
    assert len(resp.json()) == 0


# ── 自动推荐 / 布线 / 协议 / 价格 ──


@pytest.mark.asyncio
async def test_auto_recommend(client: AsyncClient):
    """自动推荐设备"""
    headers = await _auth_headers(client, "13920020007")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id, "客厅")

    resp = await client.post(
        f"/api/smart-home/schemes/{scheme['id']}/auto-recommend",
        json={"room_type": "living_room", "room_area": 25.0},
        headers=headers,
    )
    assert resp.status_code == 200
    result = resp.json()
    assert "recommended_devices" in result
    assert result["room_type"] == "living_room"


@pytest.mark.asyncio
async def test_wiring_plan(client: AsyncClient):
    """布线规划"""
    headers = await _auth_headers(client, "13920020008")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id, "客厅")

    resp = await client.get(
        f"/api/smart-home/schemes/{scheme['id']}/wiring", headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "wiring_items" in data
    assert "notes" in data


@pytest.mark.asyncio
async def test_protocol_advice(client: AsyncClient):
    """协议选型建议"""
    headers = await _auth_headers(client, "13920020009")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id, "客厅")

    resp = await client.get(
        f"/api/smart-home/schemes/{scheme['id']}/protocol-advice", headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "recommended_protocol" in data
    assert "alternative_protocols" in data


@pytest.mark.asyncio
async def test_compute_price(client: AsyncClient):
    """方案总价"""
    headers = await _auth_headers(client, "13920020010")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id, "客厅")

    # 先添加设备
    await client.post(
        f"/api/smart-home/schemes/{scheme['id']}/devices",
        json={
            "device_type": "light", "device_name": "吸顶灯",
            "brand": "Aqara", "protocol": "zigbee",
            "power_w": 12.0, "price": 199.0,
        },
        headers=headers,
    )

    resp = await client.get(
        f"/api/smart-home/schemes/{scheme['id']}/price", headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["scheme_id"] == scheme["id"]
    assert "total_price" in data


# ── Matter ──


@pytest.mark.asyncio
async def test_matter_device_types(client: AsyncClient):
    """获取 Matter 设备类型列表（无需认证）"""
    resp = await client.get("/api/smart-home/matter/device-types")
    assert resp.status_code == 200
    data = resp.json()
    assert data["protocol"] == "Matter 2.0"
    assert len(data["categories"]) >= 4


@pytest.mark.asyncio
async def test_matter_placement_plan(client: AsyncClient):
    """生成 Matter 设备点位规划"""
    headers = await _auth_headers(client, "13920020011")
    project_id = await _create_project(client, headers)

    # project_id 为查询参数（端点签名是 project_id: str，非请求体）
    resp = await client.post(
        "/api/smart-home/matter/placement-plan",
        params={"project_id": project_id},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["protocol"] == "Matter 2.0"
    assert "rooms" in data
    assert data["total_device_count"] > 0


@pytest.mark.asyncio
async def test_matter_commission_not_enabled(client: AsyncClient):
    """Matter 配网：matter_enabled 默认 True，桥接为 stub 时诚实返回 501"""
    headers = await _auth_headers(client, "13920020012")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/smart-home/matter/commission",
        json={
            "project_id": project_id,
            "passcode": 12345678901,
            "discriminator": 3840,
        },
        headers=headers,
    )
    # matter_enabled 默认 True → 进入桥接层；真实配网未实现（stub）→ 501
    assert resp.status_code == 501


# ── 越权校验 ──


@pytest.mark.asyncio
async def test_smart_home_cross_user_access_blocked(client: AsyncClient):
    """用户不能访问他人的方案"""
    headers_a = await _auth_headers(client, "13920020013")
    headers_b = await _auth_headers(client, "13920020014")
    project_id_a = await _create_project(client, headers_a)
    scheme_a = await _create_scheme(client, headers_a, project_id_a, "客厅")

    resp = await client.get(
        f"/api/smart-home/schemes/{scheme_a['id']}",
        headers=headers_b,
    )
    assert resp.status_code == 403
