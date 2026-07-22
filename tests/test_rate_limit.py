"""API 速率限制中间件测试。

覆盖场景：
- 正常请求通过（携带 RateLimit 响应头）
- 超过普通 API 60/min 限制返回 429
- 健康检查与 /metrics 端点不受限
- 认证端点使用更严格的 10/min 限制
- 认证配额与普通 API 配额相互独立
- rate_limit_enabled=False 时关闭限流
"""
import pytest
from httpx import AsyncClient

from app.config import get_settings
from app.middleware.rate_limit import reset_rate_limit_store


@pytest.fixture(autouse=True)
def enable_rate_limit(monkeypatch):
    """每个测试前启用限流、还原默认配额、清空存储；测试后再次清空。

    tests/conftest.py 默认通过环境变量 RATE_LIMIT_ENABLED=false 禁用限流，
    避免影响其他测试文件；此处通过 monkeypatch 显式启用以验证限流逻辑。
    """
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_per_minute", 60)
    monkeypatch.setattr(settings, "rate_limit_auth_per_minute", 10)
    reset_rate_limit_store()
    yield
    reset_rate_limit_store()


@pytest.mark.asyncio
async def test_normal_request_passes(client: AsyncClient):
    """未超限的普通请求应正常通过，并携带 X-RateLimit-* 响应头。"""
    # /api/auth/me 未携带 token → 401；但位于 /api 前缀下，受普通 API 限流（60/min）
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401  # 通过限流，被路由层拒绝认证
    assert resp.headers["X-RateLimit-Limit"] == "60"
    assert resp.headers["X-RateLimit-Remaining"] == "59"
    assert "X-RateLimit-Reset" in resp.headers


@pytest.mark.asyncio
async def test_exceed_limit_returns_429(client: AsyncClient):
    """超过 60 次/分钟限制后，第 61 次请求应返回 429。"""
    # 前 60 次请求通过限流（401 是认证失败，不影响限流判定）
    for i in range(60):
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401, f"第 {i + 1} 次请求应通过限流，实际: {resp.status_code}"

    # 第 61 次应被限流
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 429
    assert resp.headers["X-RateLimit-Limit"] == "60"
    assert resp.headers["X-RateLimit-Remaining"] == "0"
    assert "X-RateLimit-Reset" in resp.headers
    assert "Retry-After" in resp.headers
    assert int(resp.headers["Retry-After"]) >= 1

    body = resp.json()
    assert body["status_code"] == 429
    assert body["error"] is True
    assert "频繁" in body["detail"]


@pytest.mark.asyncio
async def test_health_check_not_limited(client: AsyncClient):
    """健康检查与指标端点不应受限流影响。"""
    # /health — 连续访问远超普通限制（70 次）
    for _ in range(70):
        resp = await client.get("/health")
        assert resp.status_code == 200
        # 不受限端点不携带 RateLimit 响应头
        assert "X-RateLimit-Limit" not in resp.headers

    # /api/health — 同样不受限
    for _ in range(70):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert "X-RateLimit-Limit" not in resp.headers

    # /metrics — Prometheus 指标端点不受限
    for _ in range(70):
        resp = await client.get("/metrics")
        assert resp.status_code != 429


@pytest.mark.asyncio
async def test_auth_endpoint_stricter_limit(client: AsyncClient):
    """认证端点 /api/auth/login 应使用更严格的 10 次/分钟限制。"""
    # 用不存在的手机号登录，每次返回 401（不创建用户，纯限流验证）
    for i in range(10):
        resp = await client.post(
            "/api/auth/login",
            json={"phone": f"13900000{i:03d}", "password": "test123456"},
        )
        # 第 1-10 次应通过限流（认证失败 401，而非限流 429）
        assert resp.status_code == 401, f"第 {i + 1} 次认证请求应通过限流，实际: {resp.status_code}"
        assert resp.headers["X-RateLimit-Limit"] == "10"

    # 第 11 次应被限流
    resp = await client.post(
        "/api/auth/login",
        json={"phone": "13900001111", "password": "test123456"},
    )
    assert resp.status_code == 429
    assert resp.headers["X-RateLimit-Limit"] == "10"
    assert resp.headers["X-RateLimit-Remaining"] == "0"
    assert int(resp.headers["Retry-After"]) >= 1


@pytest.mark.asyncio
async def test_register_endpoint_stricter_limit(client: AsyncClient):
    """/api/auth/register 同样使用 10 次/分钟限制。"""
    for i in range(10):
        resp = await client.post(
            "/api/auth/register",
            json={
                "phone": f"13910000{i:03d}",
                "name": f"用户{i}",
                "password": "test123456",
            },
        )
        # 前 10 次应通过限流（可能 201 创建成功或 409 重复，均非 429）
        assert resp.status_code in (201, 409), f"第 {i + 1} 次应通过限流，实际: {resp.status_code}"
        assert resp.headers["X-RateLimit-Limit"] == "10"

    # 第 11 次应被限流
    resp = await client.post(
        "/api/auth/register",
        json={
            "phone": "13910001111",
            "name": "超限用户",
            "password": "test123456",
        },
    )
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_auth_limit_independent_from_api_limit(client: AsyncClient):
    """认证端点与普通 API 配额相互独立 —— 用尽认证配额不应影响普通 API。"""
    # 用尽认证配额（10 次 + 1 次被拒）
    for _ in range(11):
        await client.post(
            "/api/auth/login",
            json={"phone": "13900000000", "password": "test123456"},
        )

    # 认证端点已被限流
    resp = await client.post(
        "/api/auth/login",
        json={"phone": "13900000000", "password": "test123456"},
    )
    assert resp.status_code == 429

    # 普通 API 仍可正常访问（不受认证配额耗尽影响）
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401  # 通过限流，认证失败
    assert resp.headers["X-RateLimit-Limit"] == "60"


@pytest.mark.asyncio
async def test_rate_limit_disabled(client: AsyncClient, monkeypatch):
    """rate_limit_enabled=False 时应直接放行，不应用任何限流。"""
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_enabled", False)

    # 发送远超普通限制的请求数（70 > 60），均应通过
    for _ in range(70):
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401  # 通过限流，认证失败
        # 关闭限流时不应有 RateLimit 响应头
        assert "X-RateLimit-Limit" not in resp.headers
        assert "X-RateLimit-Remaining" not in resp.headers
        assert "Retry-After" not in resp.headers
