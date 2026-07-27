"""Tests for soft furnishing API endpoints.

覆盖端点:
- POST /api/soft-furnishing/schemes
- GET  /api/soft-furnishing/schemes/project/{id}
- GET  /api/soft-furnishing/schemes/{id}
- DELETE /api/soft-furnishing/schemes/{id}
- POST /api/soft-furnishing/schemes/{id}/ai-match
- GET  /api/soft-furnishing/schemes/{id}/color-harmony
- GET  /api/soft-furnishing/schemes/{id}/budget
- POST /api/soft-furnishing/schemes/{id}/items
- GET  /api/soft-furnishing/schemes/{id}/items
- DELETE /api/soft-furnishing/items/{id}
- PATCH /api/soft-furnishing/items/{id}/status
- POST /api/soft-furnishing/schemes/{id}/storage
- GET  /api/soft-furnishing/schemes/{id}/storage
- GET  /api/soft-furnishing/storage/{id}/capacity
- POST /api/soft-furnishing/storage/recommend
"""
import uuid

import pytest
from httpx import AsyncClient


async def _create_project(client: AsyncClient, headers: dict, name: str = "软装设计项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 100.0}, headers=headers,
    )
    return resp.json()["id"]


async def _register_user(client: AsyncClient, phone: str) -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "软装测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_soft_furnishing_requires_auth(client: AsyncClient):
    """未认证请求软装接口返回 401"""
    resp = await client.get("/api/soft-furnishing/schemes/project/fake-id")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_soft_scheme(client: AsyncClient, auth_headers: dict):
    """创建软装方案"""
    project_id = await _create_project(client, auth_headers)

    resp = await client.post(
        "/api/soft-furnishing/schemes",
        json={
            "project_id": project_id,
            "room_name": "客厅",
            "style": "北欧",
            "budget_total": 50000.0,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["style"] == "北欧"
    assert data["budget_total"] == 50000.0


@pytest.mark.asyncio
async def test_list_soft_schemes(client: AsyncClient, auth_headers: dict):
    """列出项目软装方案"""
    project_id = await _create_project(client, auth_headers)

    for style in ("北欧", "现代"):
        await client.post(
            "/api/soft-furnishing/schemes",
            json={
                "project_id": project_id,
                "room_name": style,
                "style": style,
                "budget_total": 30000.0,
            },
            headers=auth_headers,
        )

    resp = await client.get(
        f"/api/soft-furnishing/schemes/project/{project_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    schemes = resp.json()
    assert len(schemes) >= 2


@pytest.mark.asyncio
async def test_get_soft_scheme_detail(client: AsyncClient, auth_headers: dict):
    """获取软装方案详情"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/soft-furnishing/schemes",
        json={
            "project_id": project_id,
            "room_name": "主卧",
            "style": "现代",
            "budget_total": 40000.0,
        },
        headers=auth_headers,
    )
    scheme_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/soft-furnishing/schemes/{scheme_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == scheme_id
    assert resp.json()["style"] == "现代"


@pytest.mark.asyncio
async def test_soft_furnishing_foreign_project_blocked(
    client: AsyncClient, auth_headers: dict, auth_token: str
):
    """用户不能访问他人项目的软装方案"""
    project_id_a = await _create_project(client, auth_headers)

    phone_b = f"1395{str(uuid.uuid4().int)[:7]}"
    headers_b = await _register_user(client, phone_b)

    resp = await client.get(
        f"/api/soft-furnishing/schemes/project/{project_id_a}",
        headers=headers_b,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_soft_item_crud(client: AsyncClient, auth_headers: dict):
    """软装单品 CRUD"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/soft-furnishing/schemes",
        json={
            "project_id": project_id,
            "room_name": "客厅",
            "style": "现代",
            "budget_total": 50000.0,
        },
        headers=auth_headers,
    )
    scheme_id = create_resp.json()["id"]

    # 添加单品
    add_resp = await client.post(
        f"/api/soft-furnishing/schemes/{scheme_id}/items",
        json={
            "item_type": "sofa",
            "name": "布艺沙发",
            "price": 4280.0,
            "quantity": 1,
        },
        headers=auth_headers,
    )
    assert add_resp.status_code == 201
    item = add_resp.json()
    assert item["item_type"] == "sofa"
    assert item["name"] == "布艺沙发"

    # 列出单品
    list_resp = await client.get(
        f"/api/soft-furnishing/schemes/{scheme_id}/items",
        headers=auth_headers,
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # 删除单品
    del_resp = await client.delete(
        f"/api/soft-furnishing/items/{item['id']}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_soft_item_status_update(client: AsyncClient, auth_headers: dict):
    """单品状态更新"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/soft-furnishing/schemes",
        json={
            "project_id": project_id,
            "room_name": "客厅",
            "style": "现代",
            "budget_total": 50000.0,
        },
        headers=auth_headers,
    )
    scheme_id = create_resp.json()["id"]

    add_resp = await client.post(
        f"/api/soft-furnishing/schemes/{scheme_id}/items",
        json={
            "item_type": "lamp",
            "name": "落地灯",
            "price": 880.0,
        },
        headers=auth_headers,
    )
    item_id = add_resp.json()["id"]
    assert add_resp.json()["status"] == "planned"

    # 更新状态
    upd_resp = await client.patch(
        f"/api/soft-furnishing/items/{item_id}/status",
        json={"status": "purchased"},
        headers=auth_headers,
    )
    assert upd_resp.status_code == 200
    assert upd_resp.json()["status"] == "purchased"


@pytest.mark.asyncio
async def test_soft_color_harmony(client: AsyncClient, auth_headers: dict):
    """配色和谐度分析"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/soft-furnishing/schemes",
        json={
            "project_id": project_id,
            "room_name": "客厅",
            "style": "北欧",
            "budget_total": 50000.0,
        },
        headers=auth_headers,
    )
    scheme_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/soft-furnishing/schemes/{scheme_id}/color-harmony",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "score" in data
    assert 0 <= data["score"] <= 100


@pytest.mark.asyncio
async def test_soft_budget_usage(client: AsyncClient, auth_headers: dict):
    """预算使用情况"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/soft-furnishing/schemes",
        json={
            "project_id": project_id,
            "room_name": "客厅",
            "style": "北欧",
            "budget_total": 10000.0,
        },
        headers=auth_headers,
    )
    scheme_id = create_resp.json()["id"]

    # 添加单品
    await client.post(
        f"/api/soft-furnishing/schemes/{scheme_id}/items",
        json={
            "item_type": "sofa",
            "name": "沙发",
            "price": 6000.0,
            "quantity": 1,
        },
        headers=auth_headers,
    )

    resp = await client.get(
        f"/api/soft-furnishing/schemes/{scheme_id}/budget",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["budget_total"] == 10000.0
    assert data["budget_used"] == 6000.0
    assert data["budget_remaining"] == 4000.0
    assert "status" in data


@pytest.mark.asyncio
async def test_soft_storage_crud_and_capacity(client: AsyncClient, auth_headers: dict):
    """收纳系统 CRUD 及容量计算"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/soft-furnishing/schemes",
        json={
            "project_id": project_id,
            "room_name": "卧室",
            "style": "现代",
        },
        headers=auth_headers,
    )
    scheme_id = create_resp.json()["id"]

    # 添加收纳
    add_resp = await client.post(
        f"/api/soft-furnishing/schemes/{scheme_id}/storage",
        json={
            "room_name": "主卧",
            "storage_type": "衣柜",
            "total_capacity_l": 1000.0,
            "compartment_count": 6,
            "adjustable_shelves": True,
        },
        headers=auth_headers,
    )
    assert add_resp.status_code == 201
    storage = add_resp.json()
    assert storage["total_capacity_l"] == 1000.0

    # 列出收纳
    list_resp = await client.get(
        f"/api/soft-furnishing/schemes/{scheme_id}/storage",
        headers=auth_headers,
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # 容量计算
    cap_resp = await client.get(
        f"/api/soft-furnishing/storage/{storage['id']}/capacity",
        headers=auth_headers,
    )
    assert cap_resp.status_code == 200
    cdata = cap_resp.json()
    assert cdata["total_capacity_l"] == 1000.0
    assert "effective_capacity_l" in cdata


@pytest.mark.asyncio
async def test_soft_storage_recommend(client: AsyncClient, auth_headers: dict):
    """收纳方案推荐"""
    resp = await client.post(
        "/api/soft-furnishing/storage/recommend",
        json={
            "room_name": "主卧",
            "room_area": 20.0,
            "family_size": 3,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "recommended_capacity_l" in data
    assert "suggestions" in data


@pytest.mark.asyncio
async def test_delete_soft_scheme(client: AsyncClient, auth_headers: dict):
    """删除软装方案"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/soft-furnishing/schemes",
        json={
            "project_id": project_id,
            "room_name": "客厅",
            "style": "现代",
        },
        headers=auth_headers,
    )
    scheme_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/soft-furnishing/schemes/{scheme_id}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204

    get_resp = await client.get(
        f"/api/soft-furnishing/schemes/{scheme_id}",
        headers=auth_headers,
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_soft_scheme_not_found(client: AsyncClient, auth_headers: dict):
    """查询不存在的软装方案返回 404"""
    resp = await client.get(
        f"/api/soft-furnishing/schemes/non-existent-id",
        headers=auth_headers,
    )
    assert resp.status_code == 404
