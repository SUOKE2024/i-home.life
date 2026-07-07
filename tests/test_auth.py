import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "i-home.life"


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    response = await client.post(
        "/api/auth/register",
        json={
            "phone": "13900001111",
            "name": "测试用户",
            "password": "test123456",
            "role": "homeowner",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["user"]["phone"] == "13900001111"
    assert data["user"]["name"] == "测试用户"
    assert data["token_type"] == "Bearer"


@pytest.mark.asyncio
async def test_register_duplicate_phone(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={
            "phone": "13900002222",
            "name": "重复用户",
            "password": "test123456",
        },
    )
    response = await client.post(
        "/api/auth/register",
        json={
            "phone": "13900002222",
            "name": "重复用户2",
            "password": "test123456",
        },
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={
            "phone": "13900003333",
            "name": "登录测试",
            "password": "test123456",
        },
    )
    response = await client.post(
        "/api/auth/login",
        json={"phone": "13900003333", "password": "test123456"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={
            "phone": "13900004444",
            "name": "密码测试",
            "password": "test123456",
        },
    )
    response = await client.post(
        "/api/auth/login",
        json={"phone": "13900004444", "password": "wrongpassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_with_token(client: AsyncClient):
    register_resp = await client.post(
        "/api/auth/register",
        json={
            "phone": "13900005555",
            "name": "个人信息测试",
            "password": "test123456",
        },
    )
    token = register_resp.json()["access_token"]

    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "个人信息测试"


@pytest.mark.asyncio
async def test_me_without_token(client: AsyncClient):
    response = await client.get("/api/auth/me")
    assert response.status_code == 401
