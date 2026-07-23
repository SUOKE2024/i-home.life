import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": "13900000003", "name": "采购施工测试", "password": "test123456"},
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_list_suppliers(client: AsyncClient):
    # v1.2.1 P1-6：list_suppliers 现强制登录 + 手机号脱敏
    token = await _register_and_login(client)
    # 创建一个带手机号的供应商，验证列表脱敏
    await client.post(
        "/api/procurement/suppliers",
        json={
            "name": "测试供应商",
            "category": "flooring",
            "rating": 4.0,
            "phone": "13812345678",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    response = await client.get(
        "/api/procurement/suppliers",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    # 手机号应被脱敏（138****5678），不能出现明文
    phones = [s["phone"] for s in data if s.get("phone")]
    assert all("****" in p for p in phones), f"手机号未脱敏: {phones}"


@pytest.mark.asyncio
async def test_list_suppliers_requires_auth(client: AsyncClient):
    # v1.2.1 P1-6：匿名访问供应商列表应被拒绝（原为未鉴权可枚举 PII）
    response = await client.get("/api/procurement/suppliers")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_quotation(client: AsyncClient):
    token = await _register_and_login(client)
    cat_resp = await client.post(
        "/api/materials/categories",
        json={"name": "报价分类", "code": "quot_cat"},
        headers={"Authorization": f"Bearer {token}"},
    )
    cat_id = cat_resp.json()["id"]

    mat_resp = await client.post(
        "/api/materials",
        json={"category_id": cat_id, "name": "报价物料", "sku": "QUOT-001", "unit_price": 300.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    mat_id = mat_resp.json()["id"]

    sup_resp = await client.post(
        "/api/procurement/suppliers",
        json={"name": "测试供应商", "category": "flooring", "rating": 4.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    sup_id = sup_resp.json()["id"]

    proj_resp = await client.post(
        "/api/projects",
        json={"name": "报价项目"},
        headers={"Authorization": f"Bearer {token}"},
    )
    proj_id = proj_resp.json()["id"]

    response = await client.post(
        "/api/procurement/quotations",
        json={"supplier_id": sup_id, "material_id": mat_id, "project_id": proj_id, "quantity": 10, "unit_price": 280.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["total_price"] == 2800.0


@pytest.mark.asyncio
async def test_create_order(client: AsyncClient):
    token = await _register_and_login(client)
    cat_resp = await client.post(
        "/api/materials/categories",
        json={"name": "订单分类", "code": "ord_cat"},
        headers={"Authorization": f"Bearer {token}"},
    )
    cat_id = cat_resp.json()["id"]

    mat_resp = await client.post(
        "/api/materials",
        json={"category_id": cat_id, "name": "订单物料", "sku": "ORD-001", "unit_price": 500.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    mat_id = mat_resp.json()["id"]

    sup_resp = await client.post(
        "/api/procurement/suppliers",
        json={"name": "订单供应商", "category": "custom_furniture", "rating": 4.5},
        headers={"Authorization": f"Bearer {token}"},
    )
    sup_id = sup_resp.json()["id"]

    proj_resp = await client.post(
        "/api/projects",
        json={"name": "订单项目"},
        headers={"Authorization": f"Bearer {token}"},
    )
    proj_id = proj_resp.json()["id"]

    response = await client.post(
        "/api/procurement/orders",
        json={
            "project_id": proj_id,
            "supplier_id": sup_id,
            "lines": [{"material_id": mat_id, "quantity": 5, "unit_price": 480.0}],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["total_amount"] == 2400.0


@pytest.mark.asyncio
async def test_create_construction_task(client: AsyncClient):
    token = await _register_and_login(client)
    proj_resp = await client.post(
        "/api/projects",
        json={"name": "施工项目"},
        headers={"Authorization": f"Bearer {token}"},
    )
    proj_id = proj_resp.json()["id"]

    response = await client.post(
        "/api/construction/tasks",
        json={"project_id": proj_id, "name": "水电阶段", "phase": "mep", "priority": 1, "assigned_to": "李工"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "水电阶段"


@pytest.mark.asyncio
async def test_add_construction_log(client: AsyncClient):
    token = await _register_and_login(client)
    proj_resp = await client.post(
        "/api/projects",
        json={"name": "日志项目"},
        headers={"Authorization": f"Bearer {token}"},
    )
    proj_id = proj_resp.json()["id"]

    task_resp = await client.post(
        "/api/construction/tasks",
        json={"project_id": proj_id, "name": "拆改阶段", "phase": "demolition", "priority": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    task_id = task_resp.json()["id"]

    response = await client.post(
        "/api/construction/logs",
        json={"task_id": task_id, "content": "今日拆墙完成，垃圾已清运", "log_type": "daily"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["content"] == "今日拆墙完成，垃圾已清运"


@pytest.mark.asyncio
async def test_create_inspection(client: AsyncClient):
    token = await _register_and_login(client)
    proj_resp = await client.post(
        "/api/projects",
        json={"name": "质检项目"},
        headers={"Authorization": f"Bearer {token}"},
    )
    proj_id = proj_resp.json()["id"]

    task_resp = await client.post(
        "/api/construction/tasks",
        json={"project_id": proj_id, "name": "泥瓦阶段", "phase": "masonry", "priority": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    task_id = task_resp.json()["id"]

    response = await client.post(
        "/api/construction/inspections",
        json={"task_id": task_id, "inspector": "张监理", "result": "瓷砖空鼓率合格", "score": 95},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["score"] == 95
