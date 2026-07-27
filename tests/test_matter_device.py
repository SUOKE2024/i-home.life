"""A7 Matter 协议桥接 API 集成测试

覆盖端点:
- GET  /api/smart-home/matter/device-types     (设备类型列表)
- POST /api/smart-home/matter/placement-plan   (点位规划)
- POST /api/smart-home/matter/commission       (设备配网 — stub 返 501)
"""
import pytest
from httpx import AsyncClient


async def _auth_headers(client: AsyncClient, phone: str = "13900030001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "Matter 测试", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "Matter 测试项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 100.0}, headers=headers,
    )
    return resp.json()["id"]


# ── 设备类型列表 ──


@pytest.mark.asyncio
async def test_get_matter_device_types(client: AsyncClient):
    """获取 Matter 设备类型列表（无需认证）"""
    resp = await client.get("/api/smart-home/matter/device-types")
    assert resp.status_code == 200
    data = resp.json()
    assert data["protocol"] == "Matter 2.0"
    assert len(data["categories"]) >= 4
    # 验证包含安防类别
    categories = [c["category"] for c in data["categories"]]
    assert "安防" in categories
    # 每个类别有 types
    for category in data["categories"]:
        assert len(category["types"]) > 0
    # 包含配网说明
    assert "commissioning_note" in data
    assert "ecosystem_compatibility" in data


# ── 点位规划 ──


@pytest.mark.asyncio
async def test_generate_placement_plan(client: AsyncClient):
    """生成 Matter 设备点位规划"""
    headers = await _auth_headers(client, "13900030011")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        f"/api/smart-home/matter/placement-plan?project_id={project_id}",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["protocol"] == "Matter 2.0"
    assert data["total_device_count"] > 0
    assert data["estimated_power_w"] > 0
    assert len(data["rooms"]) > 0
    assert "commissioning_guide" in data
    assert "commissioned_devices" in data
    # 验证房间设备结构
    for room in data["rooms"]:
        assert "name" in room
        assert "devices" in room
        for dev in room["devices"]:
            assert "type" in dev
            assert "count" in dev
            assert "position" in dev


@pytest.mark.asyncio
async def test_placement_plan_unauthorized(client: AsyncClient):
    """未认证不能生成点位规划"""
    resp = await client.post(
        "/api/smart-home/matter/placement-plan?project_id=fake",
    )
    assert resp.status_code == 401


# ── Matter Commissioning (stub 返 501) ──


@pytest.mark.asyncio
async def test_commission_matter_device_stub(client: AsyncClient):
    """Matter 配网 — 桥接层未就绪时返 501 (stub)"""
    headers = await _auth_headers(client, "13900030012")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/smart-home/matter/commission",
        json={
            "project_id": project_id,
            "passcode": 12345678901,
            "discriminator": 3840,
            "device_type_id": 256,   # 0x0100 On/Off Light
            "vendor_id": 0x1385,
            "product_id": 0x0001,
        },
        headers=headers,
    )
    # 桥接层未就绪 → 501
    assert resp.status_code == 501


@pytest.mark.asyncio
async def test_commission_invalid_passcode(client: AsyncClient):
    """passcode 格式错误返 422"""
    headers = await _auth_headers(client, "13900030013")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/smart-home/matter/commission",
        json={
            "project_id": project_id,
            "passcode": -1,   # 无效
            "discriminator": 100,
        },
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_commission_invalid_discriminator(client: AsyncClient):
    """discriminator 超出范围返 422"""
    headers = await _auth_headers(client, "13900030014")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/smart-home/matter/commission",
        json={
            "project_id": project_id,
            "passcode": 12345678901,
            "discriminator": 5000,   # 超出 0-4095
        },
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_commission_unauthorized(client: AsyncClient):
    """未认证不能配网"""
    resp = await client.post(
        "/api/smart-home/matter/commission",
        json={
            "project_id": "fake",
            "passcode": 12345678901,
            "discriminator": 100,
        },
    )
    assert resp.status_code == 401
