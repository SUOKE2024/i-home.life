"""v1.8.1 认证安全修复回归测试

覆盖 P0-1/P0-2/P1-1 修复点：
- P0-1: PASETO verify_token fail-closed（exp 缺失/格式错 → TokenInvalidError）
- P0-2: logout 端点 + token 撤销列表（blacklist）
- P1-1: token 含 jti claim

测试组织：
- 单元测试（无 client/DB）：test_verify_token_missing_exp / _malformed_exp / _has_jti
  / _revoked_rejected / _invalidate_user_cache
- 集成测试（client + auth_token）：test_logout_invalidates_token / test_logout_audit_log
"""

import uuid

import pytest
from httpx import AsyncClient

from app.auth.paseto_handler import (
    TokenInvalidError,
    _revoked_tokens,
    create_token,
    revoke_token,
    verify_token,
)


@pytest.fixture(autouse=True)
def _clear_blacklist():
    """每个测试前后清空撤销列表，避免跨测试污染。"""
    _revoked_tokens.clear()
    yield
    _revoked_tokens.clear()


# ═══════════════════════════════════════════════════════════
#  P0-1: verify_token fail-closed
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_verify_token_missing_exp_raises_invalid():
    """P0-1: 缺少 exp 字段 → TokenInvalidError（原 fail-open 视为永不过期）"""
    import paseto
    from app.auth.paseto_handler import _get_key

    key = _get_key()
    # 直接构造无 exp 的 token
    token = paseto.create(
        key=key, purpose="local", claims={"sub": "u1", "role": "homeowner"}
    )
    with pytest.raises(TokenInvalidError, match="exp"):
        verify_token(token)


@pytest.mark.asyncio
async def test_verify_token_malformed_exp_raises_invalid():
    """P0-1: exp 格式错 → TokenInvalidError（fail-closed）

    注：paseto 库自身在 parse 阶段用 pendulum 解析 exp，格式错会先于
    我们代码的 fromisoformat 抛 ParserError，被 verify_token 的
    except Exception 捕获并转 TokenInvalidError。本测试只验证拒绝行为，
    不绑定具体错误消息（paseto 版本可能变化）。
    """
    import paseto
    from app.auth.paseto_handler import _get_key

    key = _get_key()
    token = paseto.create(
        key=key,
        purpose="local",
        claims={"sub": "u1", "role": "homeowner", "exp": "not-a-valid-date"},
    )
    with pytest.raises(TokenInvalidError):
        verify_token(token)


# ═══════════════════════════════════════════════════════════
#  P1-1: create_token 加 jti
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_token_has_jti():
    """P1-1: create_token 签发的 token 含 jti 唯一标识"""
    token = create_token("user-jti-test", "homeowner")
    payload = verify_token(token)
    assert "jti" in payload, "token 缺少 jti claim"
    assert isinstance(payload["jti"], str)
    assert len(payload["jti"]) > 0
    # jti 应为 UUID 格式
    uuid.UUID(payload["jti"])  # 无效 UUID 会 raise ValueError


@pytest.mark.asyncio
async def test_create_token_jti_unique():
    """P1-1: 每次签发的 jti 不同"""
    t1 = create_token("u", "homeowner")
    t2 = create_token("u", "homeowner")
    p1 = verify_token(t1)
    p2 = verify_token(t2)
    assert p1["jti"] != p2["jti"], "两次签发 jti 相同"


# ═══════════════════════════════════════════════════════════
#  P0-2: token 撤销列表（blacklist）
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_revoked_token_rejected():
    """P0-2: revoke_token 后，verify_token 拒绝该 token"""
    token = create_token("user-revoke", "homeowner")
    payload = verify_token(token)  # 先验证可用
    jti = payload["jti"]
    exp_iso = payload["exp"]

    revoke_token(jti, exp_iso)

    with pytest.raises(TokenInvalidError, match="撤销"):
        verify_token(token)


@pytest.mark.asyncio
async def test_revoke_expired_token_no_op():
    """P0-2: 撤销已过期 token 是 no-op（不报错，不污染 blacklist）"""
    token = create_token("user-expired", "homeowner")
    payload = verify_token(token)
    # 构造已过期的 exp（1 秒前）
    from datetime import datetime, timedelta, timezone
    past_exp = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    revoke_token(payload["jti"], past_exp)
    # blacklist 应为空
    assert len(_revoked_tokens) == 0


# ═══════════════════════════════════════════════════════════
#  P0-2: logout 端点（集成测试）
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_logout_invalidates_token(client: AsyncClient, auth_token: str):
    """P0-2: logout 端点撤销当前 token + 清用户缓存

    流程：me OK → logout → me 401
    """
    headers = {"Authorization": f"Bearer {auth_token}"}

    # logout 前 /me 可用
    r = await client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200, f"logout 前 /me 应可用: {r.status_code} {r.text}"

    # logout
    r = await client.post("/api/auth/logout", headers=headers)
    assert r.status_code == 200, f"logout 失败: {r.status_code} {r.text}"
    assert r.json()["detail"] == "登出成功"

    # logout 后 /me 应 401（token 被撤销）
    r = await client.get("/api/auth/me", headers=headers)
    assert r.status_code == 401, f"logout 后旧 token 仍可用: {r.status_code}"


@pytest.mark.asyncio
async def test_logout_requires_auth(client: AsyncClient):
    """P0-2: logout 端点必须认证"""
    r = await client.post("/api/auth/logout")
    assert r.status_code == 401, f"无 token logout 应 401: {r.status_code}"


@pytest.mark.asyncio
async def test_logout_writes_audit_log(
    client: AsyncClient, auth_token: str, db_session
):
    """P0-2: logout 写入 LOGOUT 审计日志"""
    from sqlalchemy import select

    from app.models.audit_log import AuditLog

    headers = {"Authorization": f"Bearer {auth_token}"}

    # 先调 /me 触发用户缓存（取 user_id）
    r = await client.get("/api/auth/me", headers=headers)
    user_id = r.json()["id"]

    # logout
    r = await client.post("/api/auth/logout", headers=headers)
    assert r.status_code == 200

    # 查询 LOGOUT 审计日志
    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.user_id == user_id,
            AuditLog.action == "LOGOUT",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None, "未找到 LOGOUT 审计日志"
    assert entry.resource_type == "user"
    assert entry.resource_id == user_id


# ═══════════════════════════════════════════════════════════
#  P0-2: 用户缓存失效（invalidate_user_cache）
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_invalidate_user_cache_clears_entry():
    """P0-2: invalidate_user_cache 直接清缓存（被 logout 调用）"""
    import time

    from app.auth import _user_cache, invalidate_user_cache

    fake_id = "test-invalidate-user-id"
    # 构造 fake user 对象（仅需 is_active + id 属性）
    fake_user = type("FakeUser", (), {"is_active": True, "id": fake_id})()
    _user_cache[fake_id] = (time.monotonic() + 30, fake_user)
    assert fake_id in _user_cache, "缓存写入失败"

    invalidate_user_cache(fake_id)

    assert fake_id not in _user_cache, "缓存未清除"


@pytest.mark.asyncio
async def test_invalidate_user_cache_all():
    """P0-2: invalidate_user_cache(user_id=None) 清空整个缓存"""
    import time

    from app.auth import _user_cache, invalidate_user_cache

    # 写入 2 条
    for i in range(2):
        fake_id = f"test-bulk-{i}"
        fake_user = type("FakeUser", (), {"is_active": True, "id": fake_id})()
        _user_cache[fake_id] = (time.monotonic() + 30, fake_user)
    assert len(_user_cache) >= 2

    invalidate_user_cache()  # 清空

    assert len(_user_cache) == 0, "缓存未完全清空"


# ═══════════════════════════════════════════════════════════
#  端到端冒烟测试：register → login → me → projects → logout → me 401
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_e2e_auth_smoke(client: AsyncClient):
    """Step 7 冒烟测试：全链路认证流程

    覆盖：
    1. POST /api/auth/register → 201 + token
    2. POST /api/auth/login → 200 + token（与 register token 不同）
    3. GET /api/auth/me 带 token → 200
    4. GET /api/projects 无 token → 401
    5. GET /api/projects 带 token → 200
    6. POST /api/auth/logout → 200
    7. GET /api/auth/me 带旧 token → 401（被撤销）
    """
    import uuid

    phone = f"139{str(uuid.uuid4().int)[:8]}"
    password = "test123456"

    # 1. 注册
    r = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "冒烟测试", "password": password},
    )
    assert r.status_code == 201, f"注册失败: {r.status_code} {r.text}"
    register_token = r.json()["access_token"]

    # 2. 登录
    r = await client.post(
        "/api/auth/login",
        json={"phone": phone, "password": password},
    )
    assert r.status_code == 200, f"登录失败: {r.status_code} {r.text}"
    login_token = r.json()["access_token"]
    assert login_token != register_token, "登录 token 应不同于注册 token"

    # 3. /me 带 token
    headers = {"Authorization": f"Bearer {login_token}"}
    r = await client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200, f"/me 应返回 200: {r.status_code}"
    assert r.json()["phone"] == phone

    # 4. /api/projects 无 token → 401
    r = await client.get("/api/projects")
    assert r.status_code == 401, f"无 token 应 401: {r.status_code}"

    # 5. /api/projects 带 token → 200
    r = await client.get("/api/projects", headers=headers)
    assert r.status_code == 200, f"带 token 应 200: {r.status_code} {r.text}"
    # 新用户项目列表应为空 list
    assert isinstance(r.json(), list)

    # 6. logout
    r = await client.post("/api/auth/logout", headers=headers)
    assert r.status_code == 200, f"logout 应 200: {r.status_code}"

    # 7. /me 带旧 token → 401（被撤销）
    r = await client.get("/api/auth/me", headers=headers)
    assert r.status_code == 401, f"logout 后旧 token 应 401: {r.status_code}"


# ═══════════════════════════════════════════════════════════
#  注册角色白名单：禁止自注册 admin / 非法角色
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_register_rejects_admin_role(client: AsyncClient):
    """注册端点拒绝自注册 admin（防权限提升）"""
    phone = f"139{str(uuid.uuid4().int)[:8]}"
    r = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "越权管理员", "password": "test123456", "role": "admin"},
    )
    assert r.status_code == 400
    assert "无效角色" in r.json()["detail"]


@pytest.mark.asyncio
async def test_register_rejects_unknown_role(client: AsyncClient):
    """注册端点拒绝非法角色"""
    phone = f"139{str(uuid.uuid4().int)[:8]}"
    r = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "非法角色", "password": "test123456", "role": "superadmin"},
    )
    assert r.status_code == 400
    assert "无效角色" in r.json()["detail"]
