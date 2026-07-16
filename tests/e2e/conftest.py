"""e2e 测试专用 fixtures —— 提供已认证的 HTTP 客户端 headers 等。"""

import pytest_asyncio
from httpx import AsyncClient

from app.auth.paseto_handler import create_token


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict:
    """注册新用户，返回已认证的 Authorization headers。

    每次调用都会注册一个唯一的用户，确保测试隔离。
    """
    import uuid

    phone = f"139{str(uuid.uuid4().int)[:8]}"
    resp = await client.post(
        "/api/auth/register",
        json={
            "phone": phone,
            "name": "E2E 测试用户",
            "password": "test123456",
        },
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def registered_user(client: AsyncClient) -> dict:
    """注册用户并返回用户信息（含 token）。"""
    import uuid

    phone = f"139{str(uuid.uuid4().int)[:8]}"
    resp = await client.post(
        "/api/auth/register",
        json={
            "phone": phone,
            "name": "E2E 测试用户",
            "password": "test123456",
        },
    )
    data = resp.json()
    return {
        "phone": phone,
        "user_id": data["user"]["id"],
        "token": data["access_token"],
        "role": data["user"].get("role", "homeowner"),
    }


@pytest_asyncio.fixture
async def registered_user_and_headers(registered_user: dict) -> tuple[dict, dict]:
    """返回 (user_info, auth_headers)。"""
    headers = {"Authorization": f"Bearer {registered_user['token']}"}
    return registered_user, headers


@pytest_asyncio.fixture
async def token_for_user() -> callable:
    """返回一个工厂函数，用于为指定用户生成 PASETO token。

    用法: token = await token_for_user(user_id, role)
    """
    async def _factory(user_id: str, role: str = "homeowner") -> str:
        return create_token(user_id, role)
    return _factory
