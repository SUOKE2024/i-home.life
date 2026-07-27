"""Tests for crews API endpoints.

覆盖端点:
- GET  /api/crews                    (列出施工队)
- POST /api/crews                    (创建施工队)
- GET  /api/crews/{crew_id}          (获取施工队详情)
- POST /api/crews/match              (智能匹配)
- GET  /api/crews/matches/{project_id}  (查询匹配记录)
- POST /api/crews/matches/{match_id}/status  (更新匹配状态)
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_crews_requires_auth(client: AsyncClient):
    """未认证请求施工队接口返回 401"""
    resp = await client.get("/api/crews")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_crews(client: AsyncClient, auth_headers: dict):
    """列出施工队"""
    resp = await client.get("/api/crews", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_create_crew(client: AsyncClient, auth_headers: dict):
    """创建施工队"""
    resp = await client.post(
        "/api/crews",
        json={
            "name": "精英施工队",
            "leader": "张工",
            "phone": "13800001111",
            "city": "北京",
            "district": "朝阳区",
            "qualification": "A",
            "specialties": ["mep", "masonry"],
            "rating": 4.5,
            "completed_projects": 20,
            "avg_duration": 45,
            "daily_rate": 1200,
            "status": "available",
            "introduction": "专业施工团队，经验丰富",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, f"创建失败: {resp.json()}"
    data = resp.json()
    assert data["name"] == "精英施工队"
    assert data["leader"] == "张工"
    assert "id" in data


@pytest.mark.asyncio
async def test_get_crew_not_found(client: AsyncClient, auth_headers: dict):
    """获取不存在的施工队返回 404"""
    resp = await client.get("/api/crews/nonexistent-crew-id", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_crews_with_city_filter(client: AsyncClient, auth_headers: dict):
    """按城市筛施工队"""
    # 先创建一个上海施工队
    await client.post(
        "/api/crews",
        json={
            "name": "上海施工一队",
            "leader": "李工",
            "city": "上海",
            "district": "浦东新区",
            "specialties": ["carpentry", "painting"],
        },
        headers=auth_headers,
    )
    # 按城市过滤
    resp = await client.get("/api/crews?city=上海", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all(c["city"] == "上海" for c in data if c.get("city"))


@pytest.mark.asyncio
async def test_create_crew_minimal_fields(client: AsyncClient, auth_headers: dict):
    """创建施工队只填必填字段（name + leader）"""
    resp = await client.post(
        "/api/crews",
        json={
            "name": "快速施工队",
            "leader": "王工",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, f"创建失败: {resp.json()}"
    data = resp.json()
    assert data["name"] == "快速施工队"
    assert data["qualification"] == "B"  # 默认值


@pytest.mark.asyncio
async def test_create_crew_empty_name_fails(client: AsyncClient, auth_headers: dict):
    """名称为空应返回 422"""
    resp = await client.post(
        "/api/crews",
        json={"name": "", "leader": "张工"},
        headers=auth_headers,
    )
    assert resp.status_code == 422
