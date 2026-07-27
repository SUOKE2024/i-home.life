"""Tests for workers API endpoints.

覆盖端点:
- GET  /api/workers                     (列出服务者)
- POST /api/workers                     (创建服务者)
- GET  /api/workers/{worker_id}         (获取服务者详情)
- POST /api/workers/match               (智能匹配)
- GET  /api/workers/matches/{project_id}   (查询匹配记录)
- PATCH /api/workers/matches/{match_id}/status  (更新匹配状态)
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_workers_requires_auth(client: AsyncClient):
    """未认证请求服务者接口返回 401"""
    resp = await client.get("/api/workers")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_workers(client: AsyncClient, auth_headers: dict):
    """列出服务者"""
    resp = await client.get("/api/workers", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_create_worker(client: AsyncClient, auth_headers: dict):
    """创建服务者档案"""
    resp = await client.post(
        "/api/workers",
        json={
            "name": "李明",
            "phone": "13800002222",
            "city": "上海",
            "district": "徐汇区",
            "role": "designer",
            "qualification": "A",
            "rating": 4.8,
            "completed_projects": 30,
            "years_of_experience": 10,
            "hourly_rate": 300,
            "daily_rate": 1500,
            "status": "available",
            "introduction": "资深室内设计师",
            "certifications": ["高级室内设计师"],
            "portfolio_urls": ["https://example.com/portfolio"],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, f"创建失败: {resp.json()}"
    data = resp.json()
    assert data["name"] == "李明"
    assert data["role"] == "designer"
    assert "id" in data


@pytest.mark.asyncio
async def test_get_worker_not_found(client: AsyncClient, auth_headers: dict):
    """获取不存在的服务者返回 404"""
    resp = await client.get("/api/workers/nonexistent-worker-id", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_workers_with_role_filter(client: AsyncClient, auth_headers: dict):
    """按角色筛选服务者"""
    # 创建一个木工
    await client.post(
        "/api/workers",
        json={
            "name": "赵木工",
            "role": "carpenter",
            "city": "北京",
        },
        headers=auth_headers,
    )
    resp = await client.get("/api/workers?role=carpenter", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all(w["role"] == "carpenter" for w in data)


@pytest.mark.asyncio
async def test_create_worker_minimal_fields(client: AsyncClient, auth_headers: dict):
    """创建服务者只填必填字段"""
    resp = await client.post(
        "/api/workers",
        json={
            "name": "快速工人",
            "role": "supervisor",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, f"创建失败: {resp.json()}"
    data = resp.json()
    assert data["name"] == "快速工人"
    assert data["role"] == "supervisor"


@pytest.mark.asyncio
async def test_create_worker_missing_role_fails(client: AsyncClient, auth_headers: dict):
    """缺少必填字段 role 应返回 422"""
    resp = await client.post(
        "/api/workers",
        json={"name": "张三"},
        headers=auth_headers,
    )
    assert resp.status_code == 422
