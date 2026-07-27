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
