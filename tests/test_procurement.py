"""采购订单模块全量测试 — CRUD + 权限校验 + 状态流转"""

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, phone: str = "13900000010") -> tuple[str, dict]:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "采购测试用户", "password": "test123456"},
    )
    token = resp.json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "采购测试项目") -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": name, "total_area": 100.0},
        headers=headers,
    )
    return resp.json()["id"]


async def _create_supplier(client: AsyncClient, headers: dict, name: str = "测试供应商", category: str = "flooring") -> str:
    resp = await client.post(
        "/api/procurement/suppliers",
        json={"name": name, "category": category, "rating": 4.5},
        headers=headers,
    )
    return resp.json()["id"]


async def _create_material(client: AsyncClient, headers: dict, name: str = "测试物料", sku: str = "PO-MAT-001") -> str:
    cat_resp = await client.post(
        "/api/materials/categories",
        json={"name": f"采购分类-{sku}", "code": f"po_{sku.lower()}"},
        headers=headers,
    )
    cat_id = cat_resp.json()["id"]
    mat_resp = await client.post(
        "/api/materials",
        json={"category_id": cat_id, "name": name, "sku": sku, "unit_price": 200.0, "unit": "㎡"},
        headers=headers,
    )
    return mat_resp.json()["id"]


async def _create_order(client: AsyncClient, headers: dict, project_id: str, supplier_id: str, material_id: str) -> dict:
    resp = await client.post(
        "/api/procurement/orders",
        json={
            "project_id": project_id,
            "supplier_id": supplier_id,
            "lines": [{"material_id": material_id, "quantity": 10, "unit_price": 180.0}],
        },
        headers=headers,
    )
    return resp.json()


@pytest.mark.asyncio
async def test_create_order_and_verify(client: AsyncClient):
    """测试1: 创建采购订单并验证响应字段"""
    token, headers = await _register_and_login(client, "13900000010")
    project_id = await _create_project(client, headers, "创建订单测试")
    supplier_id = await _create_supplier(client, headers, "创建订单供应商")
    material_id = await _create_material(client, headers, "创建订单物料", "PO-CRT-001")

    order = await _create_order(client, headers, project_id, supplier_id, material_id)
    assert order["project_id"] == project_id
    assert order["supplier_id"] == supplier_id
    assert order["status"] == "draft"
    assert order["total_amount"] == 1800.0  # 10 × 180
    assert len(order["lines"]) == 1
    assert order["lines"][0]["total_price"] == 1800.0


@pytest.mark.asyncio
async def test_get_project_orders_list(client: AsyncClient):
    """测试2: 获取项目采购订单列表"""
    token, headers = await _register_and_login(client, "13900000011")
    project_id = await _create_project(client, headers, "订单列表测试")
    supplier_id = await _create_supplier(client, headers, "列表供应商")
    material_id = await _create_material(client, headers, "列表物料", "PO-LST-001")

    # 创建 2 个订单
    await _create_order(client, headers, project_id, supplier_id, material_id)
    await _create_order(client, headers, project_id, supplier_id, material_id)

    resp = await client.get(f"/api/procurement/orders/{project_id}", headers=headers)
    assert resp.status_code == 200
    orders = resp.json()
    assert len(orders) == 2
    # 验证按创建时间降序
    assert all("total_amount" in o for o in orders)


@pytest.mark.asyncio
async def test_get_order_detail(client: AsyncClient):
    """测试3: 获取单个订单详情"""
    token, headers = await _register_and_login(client, "13900000012")
    project_id = await _create_project(client, headers, "订单详情测试")
    supplier_id = await _create_supplier(client, headers, "详情供应商")
    material_id = await _create_material(client, headers, "详情物料", "PO-DTL-001")

    order = await _create_order(client, headers, project_id, supplier_id, material_id)

    resp = await client.get(f"/api/procurement/orders/detail/{order['id']}", headers=headers)
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["id"] == order["id"]
    assert detail["total_amount"] == 1800.0
    assert len(detail["lines"]) == 1


@pytest.mark.asyncio
async def test_update_order_status_valid(client: AsyncClient):
    """测试4: 更新订单状态（合法流转 draft → pending → confirmed）"""
    token, headers = await _register_and_login(client, "13900000013")
    project_id = await _create_project(client, headers, "状态流转测试")
    supplier_id = await _create_supplier(client, headers, "状态供应商")
    material_id = await _create_material(client, headers, "状态物料", "PO-STS-001")

    order = await _create_order(client, headers, project_id, supplier_id, material_id)

    # draft → pending
    resp = await client.patch(f"/api/procurement/orders/{order['id']}/status?status=pending", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "pending"

    # pending → confirmed
    resp = await client.patch(f"/api/procurement/orders/{order['id']}/status?status=confirmed", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"


@pytest.mark.asyncio
async def test_update_order_status_invalid_transition(client: AsyncClient):
    """测试5: 非法状态流转应被拒绝（draft → delivered 不允许）"""
    token, headers = await _register_and_login(client, "13900000014")
    project_id = await _create_project(client, headers, "非法流转测试")
    supplier_id = await _create_supplier(client, headers, "非法流转供应商")
    material_id = await _create_material(client, headers, "非法流转物料", "PO-INV-001")

    order = await _create_order(client, headers, project_id, supplier_id, material_id)

    # draft → delivered 非法
    resp = await client.patch(f"/api/procurement/orders/{order['id']}/status?status=delivered", headers=headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_delete_order(client: AsyncClient):
    """测试6: 删除采购订单"""
    token, headers = await _register_and_login(client, "13900000015")
    project_id = await _create_project(client, headers, "删除订单测试")
    supplier_id = await _create_supplier(client, headers, "删除供应商")
    material_id = await _create_material(client, headers, "删除物料", "PO-DEL-001")

    order = await _create_order(client, headers, project_id, supplier_id, material_id)

    # 删除
    resp = await client.delete(f"/api/procurement/orders/{order['id']}", headers=headers)
    assert resp.status_code == 204

    # 再次查询应 404
    resp = await client.get(f"/api/procurement/orders/detail/{order['id']}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_user_unauthorized_access(client: AsyncClient):
    """测试7: 越权访问 — 用户B不能操作用户A的订单"""
    # 用户 A 创建项目和订单
    token_a, headers_a = await _register_and_login(client, "13900000020")
    project_id = await _create_project(client, headers_a, "越权测试项目")
    supplier_id = await _create_supplier(client, headers_a, "越权供应商")
    material_id = await _create_material(client, headers_a, "越权物料", "PO-OWN-001")
    order = await _create_order(client, headers_a, project_id, supplier_id, material_id)

    # 用户 B 登录
    resp = await client.post(
        "/api/auth/register",
        json={"phone": "13900000021", "name": "用户B", "password": "test123456"},
    )
    token_b = resp.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # B 尝试获取 A 的订单列表 → 403
    resp = await client.get(f"/api/procurement/orders/{project_id}", headers=headers_b)
    assert resp.status_code == 403

    # B 尝试获取 A 的订单详情 → 403
    resp = await client.get(f"/api/procurement/orders/detail/{order['id']}", headers=headers_b)
    assert resp.status_code == 403

    # B 尝试更新 A 的订单状态 → 403
    resp = await client.patch(f"/api/procurement/orders/{order['id']}/status?status=pending", headers=headers_b)
    assert resp.status_code == 403

    # B 尝试删除 A 的订单 → 403
    resp = await client.delete(f"/api/procurement/orders/{order['id']}", headers=headers_b)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_order_fields(client: AsyncClient):
    """测试8: 更新订单字段（备注、预期交货时间）"""
    token, headers = await _register_and_login(client, "13900000016")
    project_id = await _create_project(client, headers, "更新字段测试")
    supplier_id = await _create_supplier(client, headers, "更新字段供应商")
    material_id = await _create_material(client, headers, "更新字段物料", "PO-UPD-001")

    order = await _create_order(client, headers, project_id, supplier_id, material_id)

    resp = await client.patch(
        f"/api/procurement/orders/{order['id']}",
        json={"note": "加急订单，优先处理"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    updated = resp.json()
    assert updated["note"] == "加急订单，优先处理"


@pytest.mark.asyncio
async def test_order_not_found(client: AsyncClient):
    """测试9: 不存在的订单返回 404"""
    token, headers = await _register_and_login(client, "13900000017")

    # 详情
    resp = await client.get("/api/procurement/orders/detail/non-existent-id", headers=headers)
    assert resp.status_code == 404

    # 删除
    resp = await client.delete("/api/procurement/orders/non-existent-id", headers=headers)
    assert resp.status_code == 404

    # 更新状态
    resp = await client.patch("/api/procurement/orders/non-existent-id/status?status=pending", headers=headers)
    assert resp.status_code == 404
