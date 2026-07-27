"""产品管理 API 测试

覆盖端点:
- GET    /api/products
- POST   /api/products
- GET    /api/products/{id}
- PUT    /api/products/{id}
- DELETE /api/products/{id}
"""
import uuid
import pytest
from httpx import AsyncClient


async def _create_project(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": f"产品测试项目-{uuid.uuid4().hex[:6]}", "total_area": 100.0},
        headers=headers,
    )
    return resp.json()["id"]


async def _supplier_headers(client: AsyncClient) -> dict:
    """注册供应商角色用户（v1.2.x 起创建产品要求 supplier 或已认证）"""
    resp = await client.post(
        "/api/auth/register",
        json={
            "phone": f"1398801{uuid.uuid4().int % 10000:04d}",
            "name": "供应商", "password": "test123456", "role": "supplier",
        },
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_list_products_unauthorized(client: AsyncClient):
    """未认证用户无法获取产品列表"""
    resp = await client.get("/api/products")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_products(auth_headers: dict, client: AsyncClient):
    """已认证用户获取产品列表"""
    resp = await client.get("/api/products", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_create_product(client: AsyncClient):
    """创建产品（供应商角色）"""
    headers = await _supplier_headers(client)
    project_id = await _create_project(client, headers)
    resp = await client.post(
        "/api/products",
        json={
            "project_id": project_id,
            "name": "品牌瓷砖",
            "category": "flooring",
            "quantity": 50,
            "unit": "m2",
            "unit_price": 120.0,
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201)


@pytest.mark.asyncio
async def test_get_product_not_found(auth_headers: dict, client: AsyncClient):
    """获取不存在的产品返回 404"""
    resp = await client.get("/api/products/nonexistent-123", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_product(client: AsyncClient):
    """获取单个产品"""
    headers = await _supplier_headers(client)
    project_id = await _create_project(client, headers)
    create_resp = await client.post(
        "/api/products",
        json={
            "project_id": project_id,
            "name": "乳胶漆",
            "category": "paint",
            "quantity": 100,
            "unit": "L",
            "unit_price": 60.0,
        },
        headers=headers,
    )
    pid = create_resp.json()["id"]
    resp = await client.get(f"/api/products/{pid}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "乳胶漆"


@pytest.mark.asyncio
async def test_update_product(client: AsyncClient):
    """更新产品信息"""
    headers = await _supplier_headers(client)
    project_id = await _create_project(client, headers)
    create_resp = await client.post(
        "/api/products",
        json={
            "project_id": project_id,
            "name": "实木地板",
            "category": "flooring",
            "quantity": 30,
            "unit": "m2",
            "unit_price": 300.0,
        },
        headers=headers,
    )
    pid = create_resp.json()["id"]
    resp = await client.put(
        f"/api/products/{pid}",
        json={"unit_price": 280.0},
        headers=headers,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_product(client: AsyncClient):
    """产品生命周期：v1.2.x 移除 DELETE（405），以下架/发布动作端点替代"""
    headers = await _supplier_headers(client)
    project_id = await _create_project(client, headers)
    create_resp = await client.post(
        "/api/products",
        json={
            "project_id": project_id,
            "name": "测试产品-发布",
            "category": "lighting",
            "quantity": 1,
            "unit": "个",
            "unit_price": 50.0,
        },
        headers=headers,
    )
    pid = create_resp.json()["id"]
    # DELETE 已移除
    resp = await client.delete(f"/api/products/{pid}", headers=headers)
    assert resp.status_code == 405
    # 发布动作端点作为生命周期管理替代
    pub = await client.post(f"/api/products/{pid}/publish", headers=headers)
    assert pub.status_code == 200
