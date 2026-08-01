"""analytics API 端点测试 — 前端埋点采集 /api/analytics/collect

v1.2.10 补齐：此前 analytics 是唯一无对应 test_*.py 的 API 模块。
该端点为公开端点（前端 analytics.js 不带 token，且需登录前采集），
仅接收事件并返回 204，不持久化。测试覆盖：
- 标准事件批量上报
- 单事件对象上报
- 非 JSON 体容错
- 空体容错
- 未认证可访问（公开端点）
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_collect_events_batch(client: AsyncClient):
    """标准事件批量上报返回 204"""
    resp = await client.post(
        "/api/analytics/collect",
        json={"events": [{"type": "page_view", "path": "/"}, {"type": "click"}], "v": "1.0.0"},
    )
    assert resp.status_code == 204
    assert resp.content == b""


@pytest.mark.asyncio
async def test_collect_single_event_object(client: AsyncClient):
    """单事件对象（非数组包装）也能正常接收"""
    resp = await client.post(
        "/api/analytics/collect",
        json={"type": "page_view", "path": "/login"},
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_collect_array_body(client: AsyncClient):
    """裸数组体也能接收"""
    resp = await client.post(
        "/api/analytics/collect",
        json=[{"type": "page_view"}, {"type": "scroll"}],
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_collect_non_json_body(client: AsyncClient):
    """非 JSON 体容错，仍返回 204（埋点不应阻塞前端）"""
    resp = await client.post(
        "/api/analytics/collect",
        content=b"not-a-json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_collect_empty_body(client: AsyncClient):
    """空体容错，返回 204"""
    resp = await client.post("/api/analytics/collect")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_collect_no_auth_required(client: AsyncClient):
    """公开端点：无需 Authorization 头即可访问

    analytics.js 在登录前采集页面访问，不附带 token。
    """
    resp = await client.post(
        "/api/analytics/collect",
        json={"events": [{"type": "page_view", "path": "/login"}]},
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_collect_invalid_json_structure(client: AsyncClient):
    """JSON 但非对象/数组结构（如字符串、数字）也容错返回 204"""
    resp = await client.post(
        "/api/analytics/collect",
        json="just-a-string",
    )
    assert resp.status_code == 204
