"""演示账号登录边界测试 — 密码错误 / 网络超时 / 并发登录 / 认证限流

覆盖场景（对应「一键演示登录」健壮性）：
1. 密码错误 → 401（与 test_demo_seed 的断言互补：验证失败不产生 Token 副作用）
2. 网络超时 → 客户端抛 httpx.ReadTimeout（服务端慢响应时不误判登录成功）
3. 并发登录 → 同一演示账号并发多次全部成功，Token 互不相同（会话隔离）
4. 认证限流 → 认证端点 10 次/分钟/IP，第 11 次 429（防暴力破解边界）

说明：演示账号（13800138000/123456）由最小基础数据直接创建，不经 init_db 全量种子。
"""

import asyncio

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.database import async_session
from app.main import app
from app.models.user import User
from app.middleware.rate_limit import reset_rate_limit_store
from sqlalchemy import select

DEMO_PHONE = "13800138000"
DEMO_PASSWORD = "123456"


async def _ensure_demo_user() -> None:
    """创建演示业主账号（若不存在），对齐 scripts/seed.py 体验账户。"""
    from app.services.user_service import _hash_password

    async with async_session() as db:
        result = await db.execute(select(User).where(User.phone == DEMO_PHONE))
        if result.scalar_one_or_none():
            return
        db.add(User(
            phone=DEMO_PHONE,
            name="张先生",
            role="homeowner",
            hashed_password=_hash_password(DEMO_PASSWORD),
        ))
        await db.commit()


async def _login(client: AsyncClient) -> httpx.Response:
    return await client.post(
        "/api/auth/login",
        json={"phone": DEMO_PHONE, "password": DEMO_PASSWORD},
    )


# ═══════════════════════════════════════════
# 密码错误
# ═══════════════════════════════════════════

async def test_demo_login_wrong_password_no_token_side_effect(client):
    """密码错误：401 且响应不含 access_token（前端不会误置登录态）。"""
    await _ensure_demo_user()
    resp = await client.post(
        "/api/auth/login",
        json={"phone": DEMO_PHONE, "password": "wrong-password"},
    )
    assert resp.status_code == 401
    assert "access_token" not in resp.json()


# ═══════════════════════════════════════════
# 网络超时
# ═══════════════════════════════════════════

async def test_demo_login_network_timeout(monkeypatch):
    """网络超时：认证服务慢响应 → 调用方（模拟前端 fetch 超时语义）抛 TimeoutError。

    说明：httpx ASGITransport 为内存传输不触发客户端超时，故用 asyncio.wait_for
    包装请求模拟「请求发出后超过 N ms 未收到响应即判定超时」，等价于前端
    api.js 在 fetch 超时后走 catch 分支（网络错误），不会误报登录成功。
    """
    await _ensure_demo_user()

    # 让 authenticate_user 慢响应（模拟后端阻塞/网络拥塞）
    async def _slow_authenticate(*args, **kwargs):
        await asyncio.sleep(10)
        return None

    import app.api.auth as auth_module
    monkeypatch.setattr(auth_module, "authenticate_user", _slow_authenticate)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(_login(ac), timeout=0.2)


# ═══════════════════════════════════════════
# 并发登录
# ═══════════════════════════════════════════

async def test_demo_login_concurrent(client, monkeypatch):
    """并发登录：同一演示账号 8 个并发请求全部成功，Token 互不相同（会话隔离）。

    注意：测试库为 SQLite（StaticPool 单连接），并发写会锁冲突，故关闭
    audit_log 写（login 主路径仅读 + 内存 Token 生成），规避项目已知并发约束。
    """
    await _ensure_demo_user()
    monkeypatch.setattr(get_settings(), "audit_log_enabled", False)
    responses = await asyncio.gather(*[_login(client) for _ in range(8)])
    assert all(r.status_code == 200 for r in responses), [
        r.status_code for r in responses
    ]
    tokens = [r.json()["access_token"] for r in responses]
    assert len(set(tokens)) == 8, "并发登录应产生互不相同的 Token（jti 隔离）"


# ═══════════════════════════════════════════
# 认证限流（防暴力破解边界）
# ═══════════════════════════════════════════

async def test_demo_login_auth_rate_limit(client, monkeypatch):
    """认证限流：认证端点 10 次/分钟/IP，前 10 次 200、第 11 次 429。"""
    await _ensure_demo_user()
    # 显式启用限流（conftest 默认关闭）+ 清空滑动窗口存储；关闭审计写避免 SQLite 锁
    monkeypatch.setattr(get_settings(), "rate_limit_enabled", True)
    monkeypatch.setattr(get_settings(), "audit_log_enabled", False)
    reset_rate_limit_store()

    statuses = []
    for _ in range(11):
        resp = await _login(client)
        statuses.append(resp.status_code)

    assert statuses[:10] == [200] * 10, f"前 10 次应 200：{statuses}"
    assert statuses[10] == 429, f"第 11 次应 429（认证限流）：{statuses}"
    assert "Retry-After" in resp.headers, "429 应携带 Retry-After 响应头"
