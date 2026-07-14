import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.auth.paseto_handler import create_token
from app.models.user import User
from app.services.user_service import _hash_password


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] in ("i-home.life", "索克家居")


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


@pytest.mark.asyncio
async def test_login_nonexistent_phone(client: AsyncClient):
    """登录不存在的手机号应返回 401"""
    response = await client.post(
        "/api/auth/login",
        json={"phone": "13900000000", "password": "anypassword"},
    )
    assert response.status_code == 401
    assert "手机号或密码错误" in response.json()["detail"]


@pytest.mark.asyncio
async def test_me_with_invalid_token(client: AsyncClient):
    """无效格式的 token 应返回 401"""
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer not.a.valid.paseto.token"},
    )
    assert response.status_code == 401
    assert "无效的令牌" in response.json()["detail"]


@pytest.mark.asyncio
async def test_me_with_malformed_bearer_header(client: AsyncClient):
    """Authorization 头格式异常应返回 401/403"""
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": "InvalidScheme abc"},
    )
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_register_short_password(client: AsyncClient):
    """密码短于 6 位应返回 422 校验错误"""
    response = await client.post(
        "/api/auth/register",
        json={
            "phone": "13900006666",
            "name": "短密码",
            "password": "12345",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_phone(client: AsyncClient):
    """手机号长度不足 11 位应返回 422 校验错误"""
    response = await client.post(
        "/api/auth/register",
        json={
            "phone": "123",
            "name": "手机号格式错误",
            "password": "test123456",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_missing_password(client: AsyncClient):
    """缺少必填字段 password 应返回 422"""
    response = await client.post(
        "/api/auth/register",
        json={"phone": "13900007777", "name": "缺密码"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_missing_fields(client: AsyncClient):
    """登录缺少字段应返回 422"""
    response = await client.post(
        "/api/auth/login",
        json={"phone": "13900008888"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_token_works_for_me(client: AsyncClient):
    """注册返回的 token 可直接用于 /me（端到端）"""
    register_resp = await client.post(
        "/api/auth/register",
        json={
            "phone": "13900009999",
            "name": "端到端注册",
            "password": "test123456",
        },
    )
    assert register_resp.status_code == 201
    token = register_resp.json()["access_token"]

    me_resp = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["phone"] == "13900009999"
    assert me_resp.json()["name"] == "端到端注册"


@pytest.mark.asyncio
async def test_login_token_works_for_me(client: AsyncClient):
    """登录返回的 token 可直接用于 /me（端到端）"""
    await client.post(
        "/api/auth/register",
        json={
            "phone": "13900010000",
            "name": "端到端登录",
            "password": "test123456",
        },
    )
    login_resp = await client.post(
        "/api/auth/login",
        json={"phone": "13900010000", "password": "test123456"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    me_resp = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["phone"] == "13900010000"


@pytest.mark.asyncio
async def test_disabled_user_cannot_access_me(client: AsyncClient, db_session):
    """被禁用用户即使持有有效 token，访问 /me 也应返回 403"""
    hashed, _ = _hash_password("test123456")
    disabled_user = User(
        phone="13900011111",
        name="被禁用用户",
        role="homeowner",
        hashed_password=hashed,
        is_active=False,
    )
    db_session.add(disabled_user)
    await db_session.commit()
    await db_session.refresh(disabled_user)

    token = create_token(disabled_user.id, disabled_user.role)

    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert "账户已禁用" in response.json()["detail"]


@pytest.mark.asyncio
async def test_expired_token_rejected(client: AsyncClient, monkeypatch):
    """过期的 token 应被拒绝（返回 401）"""
    # 先注册拿到有效用户 id
    register_resp = await client.post(
        "/api/auth/register",
        json={
            "phone": "13900012121",
            "name": "过期测试",
            "password": "test123456",
        },
    )
    user_id = register_resp.json()["user"]["id"]

    # 将过期时间改为负数，使生成的 token 立即过期
    from app.auth import paseto_handler
    monkeypatch.setattr(
        paseto_handler.settings,
        "paseto_token_expire_minutes",
        -1,
    )
    expired_token = create_token(user_id, "homeowner")

    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_token_payload_contains_claims(client: AsyncClient):
    """令牌 payload 应包含 sub/role/iat/exp 声明"""
    from app.auth.paseto_handler import verify_token

    register_resp = await client.post(
        "/api/auth/register",
        json={
            "phone": "13900013131",
            "name": "Payload 测试",
            "password": "test123456",
        },
    )
    token = register_resp.json()["access_token"]
    payload = verify_token(token)
    assert payload is not None
    assert payload["sub"] == register_resp.json()["user"]["id"]
    assert payload["role"] == "homeowner"
    assert "iat" in payload
    assert "exp" in payload
