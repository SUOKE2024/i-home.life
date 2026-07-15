"""通知设备令牌注册 API 测试"""
import pytest
from httpx import AsyncClient


async def _register_and_get_token(client: AsyncClient, phone: str = "13900999001") -> str:
    """注册用户并返回 PASETO token"""
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "通知测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_register_device(client: AsyncClient):
    """注册设备推送令牌"""
    token = await _register_and_get_token(client)
    resp = await client.post(
        "/api/notifications/register-device",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "user_id": "placeholder",
            "device_token": "ios_device_123456",
            "platform": "ios",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["device_token"] == "ios_device_123456"
    assert data["platform"] == "ios"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_register_device_updates_existing(client: AsyncClient):
    """重复注册同平台设备应更新 token 而非新建"""
    token = await _register_and_get_token(client, "13900999002")
    headers = {"Authorization": f"Bearer {token}"}

    # 第一次注册
    resp1 = await client.post(
        "/api/notifications/register-device",
        headers=headers,
        json={"user_id": "x", "device_token": "android_old_token", "platform": "android"},
    )
    assert resp1.status_code == 200

    # 第二次注册（同平台，新 token）
    resp2 = await client.post(
        "/api/notifications/register-device",
        headers=headers,
        json={"user_id": "x", "device_token": "android_new_token", "platform": "android"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["device_token"] == "android_new_token"
    assert resp2.json()["id"] == resp1.json()["id"]  # 同一条记录


@pytest.mark.asyncio
async def test_list_devices(client: AsyncClient):
    """列出用户设备"""
    token = await _register_and_get_token(client, "13900999003")
    headers = {"Authorization": f"Bearer {token}"}

    # 注册两个平台
    await client.post(
        "/api/notifications/register-device",
        headers=headers,
        json={"user_id": "x", "device_token": "ios_tok", "platform": "ios"},
    )
    await client.post(
        "/api/notifications/register-device",
        headers=headers,
        json={"user_id": "x", "device_token": "android_tok", "platform": "android"},
    )

    resp = await client.get("/api/notifications/devices", headers=headers)
    assert resp.status_code == 200
    devices = resp.json()
    assert len(devices) == 2
    platforms = {d["platform"] for d in devices}
    assert platforms == {"ios", "android"}


@pytest.mark.asyncio
async def test_unregister_device(client: AsyncClient):
    """注销设备（软删除）"""
    token = await _register_and_get_token(client, "13900999004")
    headers = {"Authorization": f"Bearer {token}"}

    reg_resp = await client.post(
        "/api/notifications/register-device",
        headers=headers,
        json={"user_id": "x", "device_token": "tok_to_remove", "platform": "ios"},
    )
    device_id = reg_resp.json()["id"]

    # 注销
    del_resp = await client.delete(
        f"/api/notifications/devices/{device_id}",
        headers=headers,
    )
    assert del_resp.status_code == 200

    # 列表中应无活跃设备
    list_resp = await client.get("/api/notifications/devices", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 0


@pytest.mark.asyncio
async def test_register_device_unauthorized(client: AsyncClient):
    """未认证应返回 401"""
    resp = await client.post(
        "/api/notifications/register-device",
        json={"user_id": "x", "device_token": "tok", "platform": "ios"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_device_invalid_platform(client: AsyncClient):
    """非法平台应返回 422"""
    token = await _register_and_get_token(client, "13900999005")
    resp = await client.post(
        "/api/notifications/register-device",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": "x", "device_token": "tok", "platform": "windows"},
    )
    assert resp.status_code == 422
