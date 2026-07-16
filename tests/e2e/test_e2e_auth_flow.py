"""认证全流程端到端测试。

覆盖场景：
- 注册用户 → 登录 → 获取 token → 使用 token 访问受保护资源 → 验证 401 未授权访问
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_e2e_auth_full_flow(client: AsyncClient):
    """完整的认证端到端流程：注册 → 登录 → 获取 token → 访问受保护资源 → 验证 401。

    单个测试覆盖完整用户认证生命周期，确保各步骤衔接正确。
    """
    import uuid

    phone = f"139{str(uuid.uuid4().int)[:8]}"
    password = "test123456"

    # ── Step 1: 注册新用户 ──
    register_resp = await client.post(
        "/api/auth/register",
        json={
            "phone": phone,
            "name": "E2E 认证测试用户",
            "password": password,
            "role": "homeowner",
        },
    )
    assert register_resp.status_code == 201
    register_data = register_resp.json()
    assert "access_token" in register_data
    assert register_data["token_type"] == "Bearer"
    assert register_data["user"]["phone"] == phone
    assert register_data["user"]["name"] == "E2E 认证测试用户"
    user_id = register_data["user"]["id"]

    # ── Step 2: 使用注册返回的 token 访问受保护资源 /me ──
    token = register_data["access_token"]
    me_resp = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["id"] == user_id
    assert me_data["phone"] == phone
    assert me_data["name"] == "E2E 认证测试用户"
    assert me_data["role"] == "homeowner"

    # ── Step 3: 登出后使用旧 token 访问（确认 token 仍可用） ──
    # 注意：本项目为无状态 token，不存在服务端登出逻辑，
    # 合法 token 在有效期内始终可用。
    me_resp2 = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp2.status_code == 200

    # ── Step 4: 使用登录接口获取新 token ──
    login_resp = await client.post(
        "/api/auth/login",
        json={"phone": phone, "password": password},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert "access_token" in login_data
    login_token = login_data["access_token"]
    assert login_token != token  # 每次生成的 token 应不同

    # ── Step 5: 使用登录 token 访问受保护资源 ──
    me_resp3 = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {login_token}"},
    )
    assert me_resp3.status_code == 200
    assert me_resp3.json()["phone"] == phone

    # ── Step 6: 验证未认证访问返回 401 ──
    # 6a: 无 Authorization header
    resp_no_auth = await client.get("/api/auth/me")
    assert resp_no_auth.status_code == 401

    # 6b: 无效 token
    resp_invalid = await client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert resp_invalid.status_code == 401
    assert "无效的令牌" in resp_invalid.json()["detail"]

    # 6c: 空 token
    resp_empty = await client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer "},
    )
    assert resp_empty.status_code == 401

    # 6d: 错误 scheme
    resp_bad_scheme = await client.get(
        "/api/auth/me",
        headers={"Authorization": "Basic dGVzdDp0ZXN0"},
    )
    assert resp_bad_scheme.status_code in (401, 403)


@pytest.mark.asyncio
async def test_e2e_auth_login_then_register_same_phone(client: AsyncClient):
    """注册 → 尝试重复注册相同手机号应返回 409 → 用原密码成功登录。"""
    import uuid

    phone = f"139{str(uuid.uuid4().int)[:8]}"
    password = "test123456"

    # 首次注册
    resp1 = await client.post(
        "/api/auth/register",
        json={
            "phone": phone,
            "name": "首次用户",
            "password": password,
        },
    )
    assert resp1.status_code == 201

    # 重复注册
    resp2 = await client.post(
        "/api/auth/register",
        json={
            "phone": phone,
            "name": "重复用户",
            "password": password,
        },
    )
    assert resp2.status_code == 409

    # 依然可以使用原密码登录
    resp3 = await client.post(
        "/api/auth/login",
        json={"phone": phone, "password": password},
    )
    assert resp3.status_code == 200
    token = resp3.json()["access_token"]

    me_resp = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["phone"] == phone


@pytest.mark.asyncio
async def test_e2e_auth_protected_resource_requires_valid_token(client: AsyncClient):
    """验证受保护资源必须在有效认证下才能访问。

    覆盖多个受保护端点，确保认证中间件统一生效。
    """
    # 无 token 访问项目列表
    resp = await client.get("/api/projects")
    assert resp.status_code == 401

    # 无 token 创建项目
    resp = await client.post(
        "/api/projects",
        json={"name": "未认证项目", "total_area": 50.0},
    )
    assert resp.status_code == 401

    # 带有效 token 则可以正常访问
    import uuid

    phone = f"139{str(uuid.uuid4().int)[:8]}"
    register_resp = await client.post(
        "/api/auth/register",
        json={
            "phone": phone,
            "name": "受保护资源测试",
            "password": "test123456",
        },
    )
    token = register_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/projects", headers=headers)
    assert resp.status_code == 200
