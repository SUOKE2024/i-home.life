import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": "13900000001", "name": "物料测试", "password": "test123456"},
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_list_categories(client: AsyncClient):
    token = await _register_and_login(client)
    response = await client.get("/api/materials/categories")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_category(client: AsyncClient):
    token = await _register_and_login(client)
    response = await client.post(
        "/api/materials/categories",
        json={"name": "测试分类", "code": "test_cat"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "测试分类"


@pytest.mark.asyncio
async def test_list_materials(client: AsyncClient):
    token = await _register_and_login(client)
    response = await client.get("/api/materials?limit=10")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_material(client: AsyncClient):
    token = await _register_and_login(client)
    cat_resp = await client.post(
        "/api/materials/categories",
        json={"name": "临时分类", "code": "tmp_cat"},
        headers={"Authorization": f"Bearer {token}"},
    )
    cat_id = cat_resp.json()["id"]

    response = await client.post(
        "/api/materials",
        json={"category_id": cat_id, "name": "测试物料", "sku": "TEST-001", "unit_price": 100.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "测试物料"
    assert data["sku"] == "TEST-001"


@pytest.mark.asyncio
async def test_get_material_by_id(client: AsyncClient):
    token = await _register_and_login(client)
    cat_resp = await client.post(
        "/api/materials/categories",
        json={"name": "查找分类", "code": "find_cat"},
        headers={"Authorization": f"Bearer {token}"},
    )
    cat_id = cat_resp.json()["id"]

    create_resp = await client.post(
        "/api/materials",
        json={"category_id": cat_id, "name": "查找物料", "sku": "FIND-001", "unit_price": 50.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    mat_id = create_resp.json()["id"]

    response = await client.get(f"/api/materials/{mat_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "查找物料"


@pytest.mark.asyncio
async def test_add_bom_item(client: AsyncClient):
    token = await _register_and_login(client)
    cat_resp = await client.post(
        "/api/materials/categories",
        json={"name": "BOM分类", "code": "bom_cat"},
        headers={"Authorization": f"Bearer {token}"},
    )
    cat_id = cat_resp.json()["id"]

    mat_resp = await client.post(
        "/api/materials",
        json={"category_id": cat_id, "name": "BOM物料", "sku": "BOM-001", "unit_price": 200.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    mat_id = mat_resp.json()["id"]

    proj_resp = await client.post(
        "/api/projects",
        json={"name": "BOM项目", "address": "测试地址"},
        headers={"Authorization": f"Bearer {token}"},
    )
    proj_id = proj_resp.json()["id"]

    response = await client.post(
        "/api/materials/bom",
        json={"project_id": proj_id, "material_id": mat_id, "quantity": 5, "unit_price": 200.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["quantity"] == 5
    assert data["total_price"] == 1000.0


@pytest.mark.asyncio
async def test_get_project_bom(client: AsyncClient):
    token = await _register_and_login(client)
    cat_resp = await client.post(
        "/api/materials/categories",
        json={"name": "BOM2分类", "code": "bom2_cat"},
        headers={"Authorization": f"Bearer {token}"},
    )
    cat_id = cat_resp.json()["id"]

    mat_resp = await client.post(
        "/api/materials",
        json={"category_id": cat_id, "name": "BOM2", "sku": "BOM2-001", "unit_price": 100.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    mat_id = mat_resp.json()["id"]

    proj_resp = await client.post(
        "/api/projects",
        json={"name": "BOM2项目"},
        headers={"Authorization": f"Bearer {token}"},
    )
    proj_id = proj_resp.json()["id"]

    await client.post(
        "/api/materials/bom",
        json={"project_id": proj_id, "material_id": mat_id, "quantity": 3, "unit_price": 100.0},
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.get(
        f"/api/materials/bom/{proj_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_delete_bom_item(client: AsyncClient):
    token = await _register_and_login(client)
    cat_resp = await client.post(
        "/api/materials/categories",
        json={"name": "删除分类", "code": "del_cat"},
        headers={"Authorization": f"Bearer {token}"},
    )
    cat_id = cat_resp.json()["id"]

    mat_resp = await client.post(
        "/api/materials",
        json={"category_id": cat_id, "name": "删除物料", "sku": "DEL-001", "unit_price": 10.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    mat_id = mat_resp.json()["id"]

    proj_resp = await client.post(
        "/api/projects",
        json={"name": "删除测试"},
        headers={"Authorization": f"Bearer {token}"},
    )
    proj_id = proj_resp.json()["id"]

    bom_resp = await client.post(
        "/api/materials/bom",
        json={"project_id": proj_id, "material_id": mat_id, "quantity": 1, "unit_price": 10.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    bom_id = bom_resp.json()["id"]

    response = await client.delete(
        f"/api/materials/bom/{bom_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204
