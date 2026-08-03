"""F26 家具品类库 API 测试

覆盖端点:
- GET  /api/furniture-catalog
- POST /api/furniture-catalog
- GET  /api/furniture-catalog/{id}
- PUT  /api/furniture-catalog/{id}
- DELETE /api/furniture-catalog/{id}
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_catalog_unauthorized(client: AsyncClient):
    """未认证用户无法访问家具品类库"""
    resp = await client.get("/api/furniture-catalog")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_catalog(auth_headers: dict, client: AsyncClient):
    """已认证用户获取家具品类列表"""
    resp = await client.get("/api/furniture-catalog", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_catalog_by_category(auth_headers: dict, client: AsyncClient):
    """按品类过滤家具"""
    resp = await client.get("/api/furniture-catalog?category=sofa", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_catalog_item(auth_headers: dict, client: AsyncClient):
    """创建家具品类条目"""
    resp = await client.post(
        "/api/furniture-catalog",
        json={
            "name": "北欧沙发",
            "category": "living_room",
            "subcategory": "sofa",
            "brand": "测试品牌",
            "price": 5000.0,
            "material": "科技布",
            "width": 200, "depth": 90, "height": 85,
        },
        headers=auth_headers,
    )
    assert resp.status_code in (200, 201)


@pytest.mark.asyncio
async def test_get_catalog_item_not_found(auth_headers: dict, client: AsyncClient):
    """获取不存在的家具品类返回 404"""
    resp = await client.get("/api/furniture-catalog/nonexistent-123", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_catalog_item(auth_headers: dict, client: AsyncClient):
    """更新家具品类"""
    create_resp = await client.post(
        "/api/furniture-catalog",
        json={
            "name": "实木餐桌",
            "category": "dining_room",
            "subcategory": "dining_table",
            "brand": "测试品牌",
            "price": 3000.0,
            "material": "橡木",
            "width": 160, "depth": 80, "height": 75,
        },
        headers=auth_headers,
    )
    item_id = create_resp.json()["id"]
    resp = await client.patch(
        f"/api/furniture-catalog/{item_id}",
        json={"price": 2800.0},
        headers=auth_headers,
    )
    assert resp.status_code == 200
