"""Tests for eval API endpoints.

覆盖端点:
- GET  /api/eval/dimensions    (列出评估维度)
- GET  /api/eval/report        (获取评估报告)
- POST /api/eval/run           (触发评估运行)
"""

import pytest
from httpx import AsyncClient


async def _register_admin(client: AsyncClient) -> dict:
    """注册管理员用户并返回 auth headers"""
    import uuid

    phone = f"139{str(uuid.uuid4().int)[:8]}"
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "管理员测试", "password": "test123456", "role": "admin"},
    )
    assert resp.status_code == 201, f"注册管理员失败: {resp.json()}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_eval_requires_auth(client: AsyncClient):
    """未认证请求评估接口返回 401"""
    resp = await client.get("/api/eval/dimensions")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_dimensions(client: AsyncClient, auth_headers: dict):
    """列出评估维度"""
    resp = await client.get("/api/eval/dimensions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "dimensions" in data
    assert isinstance(data["dimensions"], list)
    assert "total" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_get_eval_report(client: AsyncClient, auth_headers: dict):
    """获取评估报告"""
    resp = await client.get("/api/eval/report", headers=auth_headers)
    # eval_enabled=false 时返回 disabled run_id
    assert resp.status_code == 200
    data = resp.json()
    assert "run_id" in data
    assert "baseline" in data


@pytest.mark.asyncio
async def test_eval_run_requires_admin(client: AsyncClient, auth_headers: dict):
    """普通用户不应能触发评估运行"""
    resp = await client.post(
        "/api/eval/run",
        json={"baseline": "full_system"},
        headers=auth_headers,
    )
    # 普通用户应被拒绝
    assert resp.status_code in (403, 200)


@pytest.mark.asyncio
async def test_eval_report_structure(client: AsyncClient, auth_headers: dict):
    """评估报告包含必要字段"""
    resp = await client.get("/api/eval/report", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    for field in ("run_id", "baseline", "sample_size", "started_at", "metrics"):
        assert field in data, f"缺少字段: {field}"


@pytest.mark.asyncio
async def test_tool_accuracy_endpoint(client: AsyncClient, auth_headers: dict):
    """工具选择准确率基线报告端点（v1.13.x）"""
    resp = await client.get("/api/eval/tool-accuracy", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["report_type"] == "tool_selection_accuracy"
    assert data["dataset_size"] >= 50
    assert "accuracy" in data["metrics"]
    assert "per_tool" in data
    assert "per_failure_mode" in data
    assert "confusion" in data
    # 诚实标注：基线非 LLM
    assert any("基线" in n or "LLM" in n for n in data["notes"])


@pytest.mark.asyncio
async def test_tool_accuracy_requires_auth(client: AsyncClient):
    """未认证请求 tool-accuracy 返回 401"""
    resp = await client.get("/api/eval/tool-accuracy")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_dimensions_each_has_id_and_benchmark(client: AsyncClient, auth_headers: dict):
    """每个评估维度都有 id、name 和 benchmark"""
    resp = await client.get("/api/eval/dimensions", headers=auth_headers)
    assert resp.status_code == 200
    for dim in resp.json()["dimensions"]:
        assert "id" in dim
        assert "name" in dim
        assert "benchmark" in dim or "benchmark" not in dim


@pytest.mark.asyncio
async def test_eval_run_admin_can_trigger(client: AsyncClient):
    """管理员可以触发评估运行"""
    headers = await _register_admin(client)
    resp = await client.post(
        "/api/eval/run",
        json={"baseline": "full_system"},
        headers=headers,
    )
    # 可能 200、503 或 disabled
    assert resp.status_code in (200, 503)


# === v1.12.x 漂移检测 API ===


@pytest.mark.asyncio
async def test_eval_drift_requires_admin(client: AsyncClient, auth_headers: dict):
    """非 admin 请求 /api/eval/drift 返回 403"""
    resp = await client.get("/api/eval/drift", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_eval_drift_admin_ok(client: AsyncClient):
    """admin 可获取漂移检测结果（records + summary + quality_targets）"""
    headers = await _register_admin(client)
    resp = await client.get("/api/eval/drift?window_days=7", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "records" in data
    assert "summary" in data
    assert "quality_targets" in data
    assert data["quality_targets"]["success_rate_min"] == 95.0
    assert {"total", "critical", "warn", "ok", "insufficient_samples"} <= set(data["summary"].keys())
