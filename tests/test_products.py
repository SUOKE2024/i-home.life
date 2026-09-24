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


async def _supplier_headers(client: AsyncClient, db_session=None) -> dict:
    """注册供应商角色用户（v1.2.x 起创建产品要求 supplier 或已认证）。

    v1.17.x：POST /api/products 要求账号已绑定 suppliers 档案（手机号反查），
    无档案返回 422，故传入 db_session 时同步建档案（产品创建用例需走通）。
    """
    phone = f"1398801{uuid.uuid4().int % 10000:04d}"
    resp = await client.post(
        "/api/auth/register",
        json={
            "phone": phone,
            "name": "供应商", "password": "test123456", "role": "supplier",
        },
    )
    assert resp.status_code == 201
    if db_session is not None:
        from app.models.procurement import Supplier
        db_session.add(Supplier(name="测试供应商", phone=phone, category="flooring"))
        await db_session.commit()
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
async def test_create_product(client: AsyncClient, db_session):
    """创建产品（供应商角色，已绑定供应商档案）"""
    headers = await _supplier_headers(client, db_session)
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
async def test_get_product(client: AsyncClient, db_session):
    """获取单个产品"""
    headers = await _supplier_headers(client, db_session)
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
async def test_update_product(client: AsyncClient, db_session):
    """更新产品信息"""
    headers = await _supplier_headers(client, db_session)
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
async def test_delete_product(client: AsyncClient, db_session):
    """产品生命周期：v1.2.x 移除 DELETE（405），以下架/发布动作端点替代"""
    headers = await _supplier_headers(client, db_session)
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


async def _register_supplier(client: AsyncClient, phone: str) -> dict:
    """注册指定手机号的供应商账号（用于验证供应商档案手机号反查）"""
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "供应商", "password": "test123456", "role": "supplier"},
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_create_product_without_supplier_profile_422(client: AsyncClient):
    """供应商角色但无 suppliers 档案 → 422 且文案可诊断（不再回退空串撞外键）"""
    headers = await _register_supplier(client, "13700139001")
    resp = await client.post(
        "/api/products",
        json={"name": "无档案产品", "category": "flooring", "unit": "m2", "price_min": 100.0},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text
    assert "未绑定供应商档案" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_product_with_supplier_profile_ok(client: AsyncClient, db_session):
    """有 Supplier 档案（手机号匹配账号）→ 创建成功且 supplier_id 取档案 id"""
    from app.models.procurement import Supplier

    headers = await _register_supplier(client, "13700139002")
    supplier = Supplier(name="有档案供应商", phone="13700139002", category="flooring")
    db_session.add(supplier)
    await db_session.commit()
    await db_session.refresh(supplier)

    resp = await client.post(
        "/api/products",
        json={"name": "瓷砖现货", "category": "flooring", "unit": "m2", "price_min": 120.0},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["supplier_id"] == supplier.id
    assert body["status"] == "draft"
