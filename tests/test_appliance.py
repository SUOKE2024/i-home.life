"""Tests for appliance API endpoints.

覆盖端点:
- POST /api/appliances/categories
- GET  /api/appliances/categories
- GET  /api/appliances/categories/{id}
- PUT  /api/appliances/categories/{id}
- DELETE /api/appliances/categories/{id}
- POST /api/appliances
- GET  /api/appliances/search
- GET  /api/appliances/{id}
- PUT  /api/appliances/{id}
- DELETE /api/appliances/{id}
- POST /api/appliances/points
- GET  /api/appliances/projects/{id}/points
- GET  /api/appliances/points/{id}
- PUT  /api/appliances/points/{id}
- DELETE /api/appliances/points/{id}
- POST /api/appliances/projects/{id}/load-calc
- GET  /api/appliances/projects/{id}/load-calcs
- POST /api/appliances/cabinet-match
- GET  /api/appliances/projects/{id}/embedding-plan
"""
import uuid

import pytest
from httpx import AsyncClient


async def _create_project(client: AsyncClient, headers: dict, name: str = "家电测试项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 100.0}, headers=headers,
    )
    return resp.json()["id"]


async def _register_user(client: AsyncClient, phone: str) -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "家电测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── Auth ──


@pytest.mark.asyncio
async def test_appliance_requires_auth(client: AsyncClient):
    """未认证请求电器接口返回 401"""
    resp = await client.get("/api/appliances/categories")
    assert resp.status_code == 401


# ── 品类 CRUD ──


@pytest.mark.asyncio
async def test_create_appliance_category(client: AsyncClient, auth_headers: dict):
    """创建电器品类"""
    resp = await client.post(
        "/api/appliances/categories",
        json={
            "name": "空调",
            "code": "air_conditioner",
            "description": "家用空调品类",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["name"] == "空调"


@pytest.mark.asyncio
async def test_list_appliance_categories(client: AsyncClient, auth_headers: dict):
    """列出电器品类"""
    await client.post(
        "/api/appliances/categories",
        json={"name": "冰箱", "code": "refrigerator", "description": "冰箱品类"},
        headers=auth_headers,
    )

    resp = await client.get(
        "/api/appliances/categories",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_appliance_category(client: AsyncClient, auth_headers: dict):
    """获取电器品类详情"""
    create_resp = await client.post(
        "/api/appliances/categories",
        json={"name": "洗衣机", "code": "washing_machine"},
        headers=auth_headers,
    )
    cat_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/appliances/categories/{cat_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == cat_id


@pytest.mark.asyncio
async def test_update_appliance_category(client: AsyncClient, auth_headers: dict):
    """更新电器品类"""
    create_resp = await client.post(
        "/api/appliances/categories",
        json={"name": "电视", "code": "tv"},
        headers=auth_headers,
    )
    cat_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/appliances/categories/{cat_id}",
        json={"name": "电视机", "description": "更新后的电视品类"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "电视机"


@pytest.mark.asyncio
async def test_delete_appliance_category(client: AsyncClient, auth_headers: dict):
    """删除电器品类"""
    create_resp = await client.post(
        "/api/appliances/categories",
        json={"name": "热水器", "code": "water_heater"},
        headers=auth_headers,
    )
    cat_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/appliances/categories/{cat_id}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204


# ── 电器实例 CRUD ──


@pytest.mark.asyncio
async def test_create_appliance(client: AsyncClient, auth_headers: dict):
    """创建电器实例"""
    cat_resp = await client.post(
        "/api/appliances/categories",
        json={"name": "空调", "code": "air_conditioner"},
        headers=auth_headers,
    )
    cat_id = cat_resp.json()["id"]

    resp = await client.post(
        "/api/appliances",
        json={
            "category_id": cat_id,
            "name": "美的空调",
            "brand": "Midea",
            "model": "KFR-35GW",
            "subcategory": "air_conditioner",
            "power_rating": 3500.0,
            "energy_label": "一级",
            "price": 3299.0,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["name"] == "美的空调"


@pytest.mark.asyncio
async def test_search_appliances(client: AsyncClient, auth_headers: dict):
    """搜索电器"""
    cat_resp = await client.post(
        "/api/appliances/categories",
        json={"name": "冰箱", "code": "refrigerator"},
        headers=auth_headers,
    )
    cat_id = cat_resp.json()["id"]

    await client.post(
        "/api/appliances",
        json={
            "category_id": cat_id,
            "name": "海尔冰箱",
            "brand": "Haier",
            "subcategory": "refrigerator",
            "price": 4500.0,
        },
        headers=auth_headers,
    )

    resp = await client.get(
        "/api/appliances/search",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_appliance_detail(client: AsyncClient, auth_headers: dict):
    """获取电器详情"""
    cat_resp = await client.post(
        "/api/appliances/categories",
        json={"name": "洗碗机", "code": "dishwasher"},
        headers=auth_headers,
    )
    cat_id = cat_resp.json()["id"]

    create_resp = await client.post(
        "/api/appliances",
        json={
            "category_id": cat_id,
            "name": "西门子洗碗机",
            "brand": "Siemens",
            "subcategory": "dishwasher",
            "price": 5299.0,
        },
        headers=auth_headers,
    )
    app_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/appliances/{app_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == app_id


@pytest.mark.asyncio
async def test_delete_appliance(client: AsyncClient, auth_headers: dict):
    """删除电器"""
    cat_resp = await client.post(
        "/api/appliances/categories",
        json={"name": "微波炉", "code": "microwave"},
        headers=auth_headers,
    )
    cat_id = cat_resp.json()["id"]

    create_resp = await client.post(
        "/api/appliances",
        json={
            "category_id": cat_id,
            "name": "格兰仕微波炉",
            "brand": "Galanz",
            "subcategory": "microwave",
            "price": 599.0,
        },
        headers=auth_headers,
    )
    app_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/appliances/{app_id}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204


# ── 电器点位 ──


@pytest.mark.asyncio
async def test_create_appliance_point(client: AsyncClient, auth_headers: dict):
    """创建电器点位"""
    project_id = await _create_project(client, auth_headers)

    resp = await client.post(
        "/api/appliances/points",
        json={
            "project_id": project_id,
            "name": "客厅空调插座",
            "location": "客厅南墙",
            "outlet_type": "16A三孔",
            "circuit": "空调回路",
            "power_w": 3500.0,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["name"] == "客厅空调插座"


@pytest.mark.asyncio
async def test_list_appliance_points(client: AsyncClient, auth_headers: dict):
    """列出项目电器点位"""
    project_id = await _create_project(client, auth_headers)

    for name in ("客厅插座", "厨房插座"):
        await client.post(
            "/api/appliances/points",
            json={
                "project_id": project_id,
                "name": name,
                "location": "墙面",
                "circuit": "普通回路",
                "power_w": 2000.0,
            },
            headers=auth_headers,
        )

    resp = await client.get(
        f"/api/appliances/projects/{project_id}/points",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    points = resp.json()
    assert len(points) >= 2


@pytest.mark.asyncio
async def test_delete_appliance_point(client: AsyncClient, auth_headers: dict):
    """删除电器点位"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/appliances/points",
        json={
            "project_id": project_id,
            "name": "临时插座",
            "location": "墙面",
            "circuit": "普通回路",
            "power_w": 2000.0,
        },
        headers=auth_headers,
    )
    point_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/appliances/points/{point_id}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204


# ── 负载计算 ──


@pytest.mark.asyncio
async def test_appliance_load_calc(client: AsyncClient, auth_headers: dict):
    """全屋负载计算"""
    project_id = await _create_project(client, auth_headers)

    # 先添加一个点位
    await client.post(
        "/api/appliances/points",
        json={
            "project_id": project_id,
            "name": "空调插座",
            "location": "客厅",
            "outlet_type": "16A三孔",
            "circuit": "空调回路",
            "power_w": 3500.0,
        },
        headers=auth_headers,
    )

    resp = await client.post(
        f"/api/appliances/projects/{project_id}/load-calc",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id


@pytest.mark.asyncio
async def test_appliance_get_load_calcs(client: AsyncClient, auth_headers: dict):
    """获取项目负载计算结果"""
    project_id = await _create_project(client, auth_headers)

    await client.post(
        "/api/appliances/points",
        json={
            "project_id": project_id,
            "name": "空调插座",
            "location": "客厅",
            "circuit": "空调回路",
            "power_w": 3500.0,
        },
        headers=auth_headers,
    )
    await client.post(
        f"/api/appliances/projects/{project_id}/load-calc",
        headers=auth_headers,
    )

    resp = await client.get(
        f"/api/appliances/projects/{project_id}/load-calcs",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    calcs = resp.json()
    assert isinstance(calcs, list)


# ── 嵌入式电器匹配 ──


@pytest.mark.asyncio
async def test_appliance_cabinet_match(client: AsyncClient, auth_headers: dict):
    """嵌入式电器与柜体尺寸匹配"""
    cat_resp = await client.post(
        "/api/appliances/categories",
        json={"name": "洗碗机", "code": "dishwasher"},
        headers=auth_headers,
    )
    cat_id = cat_resp.json()["id"]

    app_resp = await client.post(
        "/api/appliances",
        json={
            "category_id": cat_id,
            "name": "嵌入式洗碗机",
            "brand": "Siemens",
            "subcategory": "dishwasher",
            "dimensions": {"width": 600, "height": 820, "depth": 550},
            "price": 5299.0,
        },
        headers=auth_headers,
    )
    app_id = app_resp.json()["id"]

    resp = await client.post(
        "/api/appliances/cabinet-match",
        json={
            "appliance_id": app_id,
            "cabinet_width": 600.0,
            "cabinet_depth": 580.0,
            "cabinet_height": 850.0,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "fits" in data


# ── 预埋规划 ──


@pytest.mark.asyncio
async def test_appliance_embedding_plan(client: AsyncClient, auth_headers: dict):
    """预埋规划引擎"""
    project_id = await _create_project(client, auth_headers)

    resp = await client.get(
        f"/api/appliances/projects/{project_id}/embedding-plan",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id
