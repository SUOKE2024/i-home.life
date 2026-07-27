"""Agent Harness 管理 API 测试

覆盖端点:
- GET /api/harness/metrics
- GET /api/harness/traces
- GET /api/harness/eval
- GET /api/harness/health
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_harness_health_public(client: AsyncClient):
    """Harness 健康检查无需认证"""
    resp = await client.get("/api/harness/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_harness_metrics_requires_auth(client: AsyncClient):
    """获取指标需要认证"""
    resp = await client.get("/api/harness/metrics")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_harness_metrics_authenticated(auth_headers: dict, client: AsyncClient):
    """已认证用户可获取指标"""
    resp = await client.get("/api/harness/metrics", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_runs" in data
    assert "registered_agents" in data


@pytest.mark.asyncio
async def test_harness_traces_requires_admin(auth_headers: dict, client: AsyncClient):
    """查询轨迹需要管理员权限（普通用户 403）"""
    resp = await client.get("/api/harness/traces", headers=auth_headers)
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_harness_eval_requires_admin(auth_headers: dict, client: AsyncClient):
    """运行评估需要管理员权限（普通用户 403）"""
    resp = await client.get("/api/harness/eval", headers=auth_headers)
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_harness_health_structure(client: AsyncClient):
    """健康检查响应结构正确"""
    resp = await client.get("/api/harness/health")
    data = resp.json()
    assert "registered_agents" in data
    assert "trace_count" in data
    assert "total_runs" in data
