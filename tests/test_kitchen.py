"""Tests for kitchen API endpoints.

覆盖端点:
- POST /api/kitchen/designs              (创建厨房设计)
- GET  /api/kitchen/designs/project/{id}
- GET  /api/kitchen/designs/{id}
- POST /api/kitchen/designs/{id}/auto-layout
- GET  /api/kitchen/designs/{id}/workflow
- GET  /api/kitchen/designs/{id}/compliance
- POST /api/kitchen/designs/{id}/components
- GET  /api/kitchen/designs/{id}/components
- DELETE /api/kitchen/components/{id}
- DELETE /api/kitchen/designs/{id}
"""
import uuid

import pytest
from httpx import AsyncClient


async def _create_project(client: AsyncClient, headers: dict, name: str = "厨房设计项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 100.0}, headers=headers,
    )
    return resp.json()["id"]


async def _register_user(client: AsyncClient, phone: str) -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "厨房测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_kitchen_requires_auth(client: AsyncClient):
    """未认证请求厨房设计接口返回 401"""
    resp = await client.get("/api/kitchen/designs/project/fake-id")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_kitchen_design(client: AsyncClient, auth_headers: dict):
    """创建厨房设计方案"""
    project_id = await _create_project(client, auth_headers)

    resp = await client.post(
        "/api/kitchen/designs",
        json={
            "project_id": project_id,
            "room_name": "厨房",
            "layout_type": "L",
            "room_width": 3.0,
            "room_length": 4.0,
            "design_style": "modern",
            "ceiling_height": 2.5,
            "counter_height": 0.85,
            "counter_depth": 0.6,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["layout_type"] == "L"
    assert data["room_name"] == "厨房"


@pytest.mark.asyncio
async def test_list_kitchen_designs(client: AsyncClient, auth_headers: dict):
    """列出项目厨房设计"""
    project_id = await _create_project(client, auth_headers)

    for layout in ("L", "U"):
        await client.post(
            "/api/kitchen/designs",
            json={
                "project_id": project_id,
                "room_name": f"厨房-{layout}",
                "layout_type": layout,
                "room_width": 3.0,
                "room_length": 3.0,
            },
            headers=auth_headers,
        )

    resp = await client.get(
        f"/api/kitchen/designs/project/{project_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    designs = resp.json()
    assert len(designs) >= 2


@pytest.mark.asyncio
async def test_get_kitchen_design_detail(client: AsyncClient, auth_headers: dict):
    """获取厨房设计详情"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/kitchen/designs",
        json={
            "project_id": project_id,
            "room_name": "厨房",
            "layout_type": "I",
            "room_width": 2.5,
            "room_length": 5.0,
        },
        headers=auth_headers,
    )
    design_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/kitchen/designs/{design_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == design_id
    assert resp.json()["layout_type"] == "I"


@pytest.mark.asyncio
async def test_kitchen_foreign_project_blocked(client: AsyncClient, auth_headers: dict, auth_token: str):
    """用户不能访问他人项目的厨房设计"""
    project_id_a = await _create_project(client, auth_headers)

    phone_b = f"1391{str(uuid.uuid4().int)[:7]}"
    headers_b = await _register_user(client, phone_b)

    resp = await client.get(
        f"/api/kitchen/designs/project/{project_id_a}",
        headers=headers_b,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_kitchen_auto_layout(client: AsyncClient, auth_headers: dict):
    """自动布局生成厨房组件"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/kitchen/designs",
        json={
            "project_id": project_id,
            "room_name": "厨房",
            "layout_type": "L",
            "room_width": 3.0,
            "room_length": 4.0,
        },
        headers=auth_headers,
    )
    design_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/kitchen/designs/{design_id}/auto-layout",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["design_id"] == design_id
    assert "components" in data
    assert data["total"] > 0


@pytest.mark.asyncio
async def test_kitchen_workflow_analysis(client: AsyncClient, auth_headers: dict):
    """厨房动线分析"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/kitchen/designs",
        json={
            "project_id": project_id,
            "room_name": "厨房",
            "layout_type": "U",
            "room_width": 3.5,
            "room_length": 4.5,
        },
        headers=auth_headers,
    )
    design_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/kitchen/designs/{design_id}/workflow",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["design_id"] == design_id


@pytest.mark.asyncio
async def test_kitchen_compliance_check(client: AsyncClient, auth_headers: dict):
    """厨房规范校验"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/kitchen/designs",
        json={
            "project_id": project_id,
            "room_name": "厨房",
            "layout_type": "L",
            "room_width": 3.0,
            "room_length": 4.0,
            "ceiling_height": 2.6,
        },
        headers=auth_headers,
    )
    design_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/kitchen/designs/{design_id}/compliance",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["design_id"] == design_id


@pytest.mark.asyncio
async def test_kitchen_component_crud(client: AsyncClient, auth_headers: dict):
    """厨房组件 CRUD"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/kitchen/designs",
        json={
            "project_id": project_id,
            "room_name": "厨房",
            "layout_type": "L",
            "room_width": 3.0,
            "room_length": 4.0,
        },
        headers=auth_headers,
    )
    design_id = create_resp.json()["id"]

    # 添加组件
    add_resp = await client.post(
        f"/api/kitchen/designs/{design_id}/components",
        json={
            "design_id": design_id,
            "component_type": "cabinet_base",
            "width": 800.0,
            "depth": 600.0,
            "height": 720.0,
            "brand": "测试品牌",
            "model": "KB-800",
        },
        headers=auth_headers,
    )
    assert add_resp.status_code == 201
    component = add_resp.json()
    assert component["component_type"] == "cabinet_base"

    # 列出组件
    list_resp = await client.get(
        f"/api/kitchen/designs/{design_id}/components",
        headers=auth_headers,
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # 删除组件
    del_resp = await client.delete(
        f"/api/kitchen/components/{component['id']}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_kitchen_design(client: AsyncClient, auth_headers: dict):
    """删除厨房设计"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/kitchen/designs",
        json={
            "project_id": project_id,
            "room_name": "厨房",
            "layout_type": "I",
            "room_width": 2.0,
            "room_length": 3.0,
        },
        headers=auth_headers,
    )
    design_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/kitchen/designs/{design_id}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204

    # 确认已删除
    get_resp = await client.get(
        f"/api/kitchen/designs/{design_id}",
        headers=auth_headers,
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_kitchen_design_not_found(client: AsyncClient, auth_headers: dict):
    """查询不存在的厨房设计返回 404"""
    resp = await client.get(
        "/api/kitchen/designs/non-existent-id",
        headers=auth_headers,
    )
    assert resp.status_code == 404
