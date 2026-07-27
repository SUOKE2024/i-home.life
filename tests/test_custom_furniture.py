"""Tests for custom furniture API endpoints.

覆盖端点:
- POST /api/custom-furniture/designs
- GET  /api/custom-furniture/designs/project/{id}
- GET  /api/custom-furniture/designs/{id}
- DELETE /api/custom-furniture/designs/{id}
- POST /api/custom-furniture/designs/{id}/parametric
- POST /api/custom-furniture/designs/{id}/modules
- GET  /api/custom-furniture/designs/{id}/modules
- DELETE /api/custom-furniture/modules/{id}
- POST /api/custom-furniture/designs/{id}/bom
- GET  /api/custom-furniture/designs/{id}/bom
- GET  /api/custom-furniture/designs/{id}/price
- GET  /api/custom-furniture/designs/{id}/panels
- GET  /api/custom-furniture/designs/{id}/validation
"""
import uuid

import pytest
from httpx import AsyncClient


async def _create_project(client: AsyncClient, headers: dict, name: str = "定制家具项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 100.0}, headers=headers,
    )
    return resp.json()["id"]


async def _register_user(client: AsyncClient, phone: str) -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "定制家具测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_custom_furniture_requires_auth(client: AsyncClient):
    """未认证请求定制家具接口返回 401"""
    resp = await client.get("/api/custom-furniture/designs/project/fake-id")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_custom_furniture_design(client: AsyncClient, auth_headers: dict):
    """创建定制家具设计"""
    project_id = await _create_project(client, auth_headers)

    resp = await client.post(
        "/api/custom-furniture/designs",
        json={
            "project_id": project_id,
            "room_name": "主卧",
            "furniture_type": "wardrobe",
            "total_width": 1800.0,
            "total_height": 2400.0,
            "total_depth": 600.0,
            "panel_material": "颗粒板",
            "style": "北欧",
            "color": "白色",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["furniture_type"] == "wardrobe"
    assert data["total_width"] == 1800.0


@pytest.mark.asyncio
async def test_list_custom_furniture_designs(client: AsyncClient, auth_headers: dict):
    """列出项目定制家具设计"""
    project_id = await _create_project(client, auth_headers)

    for ftype in ("wardrobe", "bookshelf"):
        await client.post(
            "/api/custom-furniture/designs",
            json={
                "project_id": project_id,
                "room_name": f"{ftype}房间",
                "furniture_type": ftype,
                "total_width": 1500.0,
                "total_height": 2200.0,
                "total_depth": 600.0,
            },
            headers=auth_headers,
        )

    resp = await client.get(
        f"/api/custom-furniture/designs/project/{project_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    designs = resp.json()
    assert len(designs) >= 2


@pytest.mark.asyncio
async def test_get_custom_furniture_design_detail(client: AsyncClient, auth_headers: dict):
    """获取定制家具设计详情"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/custom-furniture/designs",
        json={
            "project_id": project_id,
            "room_name": "书房",
            "furniture_type": "bookshelf",
            "total_width": 1200.0,
            "total_height": 2100.0,
            "total_depth": 300.0,
            "panel_material": "多层板",
        },
        headers=auth_headers,
    )
    design_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/custom-furniture/designs/{design_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == design_id
    assert resp.json()["furniture_type"] == "bookshelf"


@pytest.mark.asyncio
async def test_custom_furniture_foreign_project_blocked(
    client: AsyncClient, auth_headers: dict, auth_token: str
):
    """用户不能访问他人项目的定制家具设计"""
    project_id_a = await _create_project(client, auth_headers)

    phone_b = f"1394{str(uuid.uuid4().int)[:7]}"
    headers_b = await _register_user(client, phone_b)

    resp = await client.get(
        f"/api/custom-furniture/designs/project/{project_id_a}",
        headers=headers_b,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_custom_furniture_parametric_design(client: AsyncClient, auth_headers: dict):
    """参数化设计生成家具模块"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/custom-furniture/designs",
        json={
            "project_id": project_id,
            "room_name": "主卧",
            "furniture_type": "wardrobe",
            "total_width": 1800.0,
            "total_height": 2400.0,
            "total_depth": 600.0,
        },
        headers=auth_headers,
    )
    design_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/custom-furniture/designs/{design_id}/parametric",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    modules = resp.json()
    assert len(modules) >= 1


@pytest.mark.asyncio
async def test_custom_furniture_module_crud(client: AsyncClient, auth_headers: dict):
    """定制家具模块 CRUD"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/custom-furniture/designs",
        json={
            "project_id": project_id,
            "room_name": "客厅",
            "furniture_type": "tv_cabinet",
            "total_width": 1800.0,
            "total_height": 400.0,
            "total_depth": 350.0,
        },
        headers=auth_headers,
    )
    design_id = create_resp.json()["id"]

    # 添加模块
    add_resp = await client.post(
        f"/api/custom-furniture/designs/{design_id}/modules",
        json={
            "module_type": "drawer",
            "position_index": 1,
            "width": 600.0,
            "height": 200.0,
            "depth": 350.0,
            "quantity": 2,
        },
        headers=auth_headers,
    )
    assert add_resp.status_code == 201
    module = add_resp.json()
    assert module["module_type"] == "drawer"

    # 列出模块
    list_resp = await client.get(
        f"/api/custom-furniture/designs/{design_id}/modules",
        headers=auth_headers,
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # 删除模块
    del_resp = await client.delete(
        f"/api/custom-furniture/modules/{module['id']}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_custom_furniture_bom_generation(client: AsyncClient, auth_headers: dict):
    """BOM 物料清单生成"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/custom-furniture/designs",
        json={
            "project_id": project_id,
            "room_name": "客厅",
            "furniture_type": "tv_cabinet",
            "total_width": 1800.0,
            "total_height": 400.0,
            "total_depth": 350.0,
        },
        headers=auth_headers,
    )
    design_id = create_resp.json()["id"]

    # 先执行参数化设计
    await client.post(
        f"/api/custom-furniture/designs/{design_id}/parametric",
        headers=auth_headers,
    )

    # 生成 BOM
    resp = await client.post(
        f"/api/custom-furniture/designs/{design_id}/bom",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    boms = resp.json()
    assert len(boms) > 0

    # 查询 BOM
    get_resp = await client.get(
        f"/api/custom-furniture/designs/{design_id}/bom",
        headers=auth_headers,
    )
    assert get_resp.status_code == 200
    assert len(get_resp.json()) == len(boms)


@pytest.mark.asyncio
async def test_custom_furniture_bom_without_modules(client: AsyncClient, auth_headers: dict):
    """未生成模块时 BOM 生成应返回 400"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/custom-furniture/designs",
        json={
            "project_id": project_id,
            "room_name": "卧室",
            "furniture_type": "wardrobe",
            "total_width": 1500.0,
            "total_height": 2200.0,
            "total_depth": 580.0,
        },
        headers=auth_headers,
    )
    design_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/custom-furniture/designs/{design_id}/bom",
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_custom_furniture_price_estimate(client: AsyncClient, auth_headers: dict):
    """价格估算"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/custom-furniture/designs",
        json={
            "project_id": project_id,
            "room_name": "书房",
            "furniture_type": "bookshelf",
            "total_width": 1200.0,
            "total_height": 2100.0,
            "total_depth": 300.0,
            "panel_material": "多层板",
        },
        headers=auth_headers,
    )
    design_id = create_resp.json()["id"]

    # 参数化设计
    await client.post(
        f"/api/custom-furniture/designs/{design_id}/parametric",
        headers=auth_headers,
    )

    resp = await client.get(
        f"/api/custom-furniture/designs/{design_id}/price",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_price"] > 0


@pytest.mark.asyncio
async def test_custom_furniture_panel_compute(client: AsyncClient, auth_headers: dict):
    """板材计算"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/custom-furniture/designs",
        json={
            "project_id": project_id,
            "room_name": "书房",
            "furniture_type": "bookshelf",
            "total_width": 1200.0,
            "total_height": 2100.0,
            "total_depth": 300.0,
        },
        headers=auth_headers,
    )
    design_id = create_resp.json()["id"]

    await client.post(
        f"/api/custom-furniture/designs/{design_id}/parametric",
        headers=auth_headers,
    )

    resp = await client.get(
        f"/api/custom-furniture/designs/{design_id}/panels",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_panel_area_m2"] > 0
    assert data["panel_sheets"] > 0


@pytest.mark.asyncio
async def test_custom_furniture_validation(client: AsyncClient, auth_headers: dict):
    """规格校验"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/custom-furniture/designs",
        json={
            "project_id": project_id,
            "room_name": "卧室",
            "furniture_type": "wardrobe",
            "total_width": 1500.0,
            "total_height": 2200.0,
            "total_depth": 580.0,
        },
        headers=auth_headers,
    )
    design_id = create_resp.json()["id"]

    await client.post(
        f"/api/custom-furniture/designs/{design_id}/parametric",
        headers=auth_headers,
    )

    resp = await client.get(
        f"/api/custom-furniture/designs/{design_id}/validation",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "valid" in data
    assert "issues" in data


@pytest.mark.asyncio
async def test_delete_custom_furniture_design(client: AsyncClient, auth_headers: dict):
    """删除定制家具设计"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/custom-furniture/designs",
        json={
            "project_id": project_id,
            "room_name": "卧室",
            "furniture_type": "wardrobe",
            "total_width": 1000.0,
            "total_height": 2000.0,
            "total_depth": 580.0,
        },
        headers=auth_headers,
    )
    design_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/custom-furniture/designs/{design_id}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204

    get_resp = await client.get(
        f"/api/custom-furniture/designs/{design_id}",
        headers=auth_headers,
    )
    assert get_resp.status_code == 404
