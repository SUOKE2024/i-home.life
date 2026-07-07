"""F33/F34 增强功能测试 — AI 比价 + 担保支付 + 物流追踪 + 样品索要"""

import pytest
from httpx import AsyncClient
from starlette.routing import Mount

# 显式导入增强模型，确保表会被 Base.metadata.create_all 创建
from app.models import procurement_enhanced  # noqa: F401
from app.main import app
from app.api import procurement_enhanced as procurement_enhanced_api

# 临时注册增强路由（主代理后续会在 app/main.py 中正式注册）
# 注意：必须注册在 StaticFiles mount 之前，否则会被静态文件拦截返回 405
_enhanced_registered = any(
    getattr(r, "path", "").startswith("/api/procurement-enhanced") for r in app.routes
)
if not _enhanced_registered:
    # 暂时移除根路径 StaticFiles mount（path 可能是 "/" 或 ""）
    _static_mounts = [
        r for r in app.router.routes
        if isinstance(r, Mount) and r.path in ("/", "")
    ]
    app.router.routes = [
        r for r in app.router.routes
        if not (isinstance(r, Mount) and r.path in ("/", ""))
    ]
    # 注册增强路由
    app.include_router(procurement_enhanced_api.router, prefix="/api")
    # 重新添加 StaticFiles mount 到末尾
    app.router.routes.extend(_static_mounts)


async def _register_and_login(client: AsyncClient, phone: str = "13900009001") -> tuple[str, dict]:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "采购增强测试用户", "password": "test123456"},
    )
    token = resp.json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "采购增强测试项目") -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": name, "total_area": 100.0},
        headers=headers,
    )
    return resp.json()["id"]


async def _create_category_material_and_bom(
    client: AsyncClient,
    headers: dict,
    project_id: str,
    category_code: str = "flooring",
    material_sku: str = "PE-MAT-001",
    material_name: str = "增强测试瓷砖",
) -> tuple[str, str]:
    """创建物料分类、物料、BOM 物料，返回 (material_id, bom_item_id)"""
    cat_resp = await client.post(
        "/api/materials/categories",
        json={"name": f"增强分类-{category_code}", "code": category_code},
        headers=headers,
    )
    cat_id = cat_resp.json()["id"]

    mat_resp = await client.post(
        "/api/materials",
        json={
            "category_id": cat_id,
            "name": material_name,
            "sku": material_sku,
            "unit": "㎡",
            "unit_price": 200.0,
            "brand": "测试品牌",
            "spec": "800×800mm",
        },
        headers=headers,
    )
    material_id = mat_resp.json()["id"]

    bom_resp = await client.post(
        "/api/materials/bom",
        json={
            "project_id": project_id,
            "material_id": material_id,
            "quantity": 50.0,
            "unit_price": 200.0,
        },
        headers=headers,
    )
    bom_item_id = bom_resp.json()["id"]
    return material_id, bom_item_id


async def _create_suppliers(client: AsyncClient, headers: dict, category: str = "flooring") -> list[str]:
    """创建多个供应商，返回 ID 列表"""
    supplier_ids = []
    for idx, (name, rating) in enumerate([
        ("比价供应商A", 4.8),
        ("比价供应商B", 4.2),
        ("比价供应商C", 3.8),
    ]):
        resp = await client.post(
            "/api/procurement/suppliers",
            json={"name": name, "category": category, "rating": rating, "address": "上海市"},
            headers=headers,
        )
        supplier_ids.append(resp.json()["id"])
    return supplier_ids


async def _create_order(
    client: AsyncClient,
    headers: dict,
    project_id: str,
    supplier_id: str,
    material_id: str,
) -> str:
    """创建采购订单，返回 order_id"""
    resp = await client.post(
        "/api/procurement/orders",
        json={
            "project_id": project_id,
            "supplier_id": supplier_id,
            "lines": [{"material_id": material_id, "quantity": 10, "unit_price": 180.0}],
        },
        headers=headers,
    )
    return resp.json()["id"]


# ── F33 比价报告 ──

@pytest.mark.asyncio
async def test_generate_comparison_from_bom(client: AsyncClient):
    """F33 从 BOM 生成比价报告"""
    token, headers = await _register_and_login(client, "13900009001")
    project_id = await _create_project(client, headers, "比价报告测试")
    await _create_suppliers(client, headers, "flooring")
    material_id, bom_item_id = await _create_category_material_and_bom(
        client, headers, project_id,
        material_sku="PE-CMP-001", material_name="比价瓷砖",
    )

    # 生成比价报告
    resp = await client.post(
        "/api/procurement-enhanced/comparisons",
        json={"project_id": project_id, "bom_id": None},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["status"] == "completed"
    assert data["item_count"] == 1
    assert data["supplier_count"] >= 1
    assert data["total_quotes"] >= 1
    assert data["total_savings"] >= 0.0
    assert data["report_no"].startswith("PC-")
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["material_name"] == "比价瓷砖"
    assert item["quantity"] == 50.0
    assert len(item["quotations"]) >= 1
    assert item["recommended_supplier_id"] is not None
    assert item["recommended_price"] > 0


@pytest.mark.asyncio
async def test_ai_match_suppliers(client: AsyncClient):
    """F33 AI 供应商匹配"""
    token, headers = await _register_and_login(client, "13900009002")
    project_id = await _create_project(client, headers, "AI 匹配测试")
    await _create_suppliers(client, headers, "wall")
    _, bom_item_id = await _create_category_material_and_bom(
        client, headers, project_id,
        category_code="wall",
        material_sku="PE-AI-001",
        material_name="AI 匹配涂料",
    )

    resp = await client.post(
        "/api/procurement-enhanced/ai-match",
        json={"bom_item_id": bom_item_id, "location": "上海"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["bom_item_id"] == bom_item_id
    assert data["material_name"] == "AI 匹配涂料"
    assert len(data["matched_suppliers"]) >= 1
    # 综合评分最高的应排第一
    top = data["matched_suppliers"][0]
    assert "score" in top
    assert top["score"] > 0
    assert data["recommended_supplier_id"] == top["supplier_id"]
    assert data["reason"]


@pytest.mark.asyncio
async def test_comparison_rank_and_savings(client: AsyncClient):
    """F33 报价排名 + 节省金额计算"""
    token, headers = await _register_and_login(client, "13900009003")
    project_id = await _create_project(client, headers, "排名节省测试")
    await _create_suppliers(client, headers, "mep")
    _, _ = await _create_category_material_and_bom(
        client, headers, project_id,
        category_code="mep",
        material_sku="PE-RANK-001",
        material_name="排名测试电线",
    )

    resp = await client.post(
        "/api/procurement-enhanced/comparisons",
        json={"project_id": project_id},
        headers=headers,
    )
    assert resp.status_code == 201
    comparison = resp.json()

    # 验证报价按综合评分降序排列
    items_resp = await client.get(
        f"/api/procurement-enhanced/comparisons/{comparison['id']}/items",
        headers=headers,
    )
    assert items_resp.status_code == 200
    items = items_resp.json()
    assert len(items) == 1
    quotes = items[0]["quotations"]
    # 至少有 3 个供应商报价
    assert len(quotes) >= 3
    # 验证评分降序
    scores = [q["score"] for q in quotes]
    assert scores == sorted(scores, reverse=True)
    # 推荐供应商应等于排名第一的供应商
    assert items[0]["recommended_supplier_id"] == quotes[0]["supplier_id"]

    # 节省金额：推荐价 vs 最高价
    prices = [q["price"] for q in quotes]
    max_price = max(prices)
    recommended_price = items[0]["recommended_price"]
    expected_savings = round((max_price - recommended_price) * 50.0, 2)
    assert items[0]["savings_per_item"] == expected_savings
    # 总节省金额 ≥ 0（推荐价 ≤ 最高价）
    assert comparison["total_savings"] >= 0


@pytest.mark.asyncio
async def test_comparison_list_get_delete(client: AsyncClient):
    """F33 比价报告列表 + 详情 + 删除"""
    token, headers = await _register_and_login(client, "13900009004")
    project_id = await _create_project(client, headers, "列表删除测试")
    await _create_suppliers(client, headers, "doors_windows")
    await _create_category_material_and_bom(
        client, headers, project_id,
        category_code="doors_windows",
        material_sku="PE-LST-001",
        material_name="列表测试门",
    )

    # 创建报告
    resp = await client.post(
        "/api/procurement-enhanced/comparisons",
        json={"project_id": project_id},
        headers=headers,
    )
    assert resp.status_code == 201
    comparison_id = resp.json()["id"]

    # 列表查询
    list_resp = await client.get(
        f"/api/procurement-enhanced/comparisons/project/{project_id}",
        headers=headers,
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # 详情查询
    detail_resp = await client.get(
        f"/api/procurement-enhanced/comparisons/{comparison_id}",
        headers=headers,
    )
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == comparison_id

    # 删除
    del_resp = await client.delete(
        f"/api/procurement-enhanced/comparisons/{comparison_id}",
        headers=headers,
    )
    assert del_resp.status_code == 204

    # 再次查询应 404
    not_found = await client.get(
        f"/api/procurement-enhanced/comparisons/{comparison_id}",
        headers=headers,
    )
    assert not_found.status_code == 404


@pytest.mark.asyncio
async def test_comparison_empty_bom(client: AsyncClient):
    """F33 空 BOM 生成比价报告应失败"""
    token, headers = await _register_and_login(client, "13900009005")
    project_id = await _create_project(client, headers, "空 BOM 测试")

    resp = await client.post(
        "/api/procurement-enhanced/comparisons",
        json={"project_id": project_id},
        headers=headers,
    )
    assert resp.status_code == 400


# ── F34 担保支付 ──

@pytest.mark.asyncio
async def test_escrow_full_lifecycle(client: AsyncClient):
    """F34 担保支付完整生命周期: 创建 → 付款 → 释放"""
    token, headers = await _register_and_login(client, "13900009010")
    project_id = await _create_project(client, headers, "担保支付测试")
    supplier_ids = await _create_suppliers(client, headers, "kitchen_bath")
    material_id, _ = await _create_category_material_and_bom(
        client, headers, project_id,
        category_code="kitchen_bath",
        material_sku="PE-ESC-001",
        material_name="担保支付马桶",
    )
    order_id = await _create_order(client, headers, project_id, supplier_ids[0], material_id)

    # 1. 创建担保支付
    resp = await client.post(
        "/api/procurement-enhanced/escrow",
        json={"order_id": order_id},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    payment = resp.json()
    assert payment["status"] == "pending"
    assert payment["buyer_paid"] is False
    assert payment["supplier_received"] is False
    assert payment["total_amount"] == 1800.0  # 10 × 180
    # 担保手续费 0.5%
    assert payment["escrow_fee"] == round(1800.0 * 0.005, 2)
    assert payment["escrow_no"].startswith("ES-")
    escrow_id = payment["id"]

    # 2. 买家付款
    resp = await client.post(
        f"/api/procurement-enhanced/escrow/{escrow_id}/pay",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "buyer_paid"
    assert resp.json()["buyer_paid"] is True
    assert resp.json()["buyer_paid_at"] is not None

    # 3. 释放资金给供应商
    resp = await client.post(
        f"/api/procurement-enhanced/escrow/{escrow_id}/release",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "supplier_received"
    assert resp.json()["supplier_received"] is True
    assert resp.json()["supplier_received_at"] is not None


@pytest.mark.asyncio
async def test_escrow_refund(client: AsyncClient):
    """F34 担保支付退款流程"""
    token, headers = await _register_and_login(client, "13900009011")
    project_id = await _create_project(client, headers, "退款测试")
    supplier_ids = await _create_suppliers(client, headers, "ceiling")
    material_id, _ = await _create_category_material_and_bom(
        client, headers, project_id,
        category_code="ceiling",
        material_sku="PE-RFD-001",
        material_name="退款测试吊顶",
    )
    order_id = await _create_order(client, headers, project_id, supplier_ids[0], material_id)

    # 创建担保支付
    resp = await client.post(
        "/api/procurement-enhanced/escrow",
        json={"order_id": order_id},
        headers=headers,
    )
    escrow_id = resp.json()["id"]

    # 买家付款
    resp = await client.post(
        f"/api/procurement-enhanced/escrow/{escrow_id}/pay",
        headers=headers,
    )
    assert resp.status_code == 200

    # 申请退款
    resp = await client.post(
        f"/api/procurement-enhanced/escrow/{escrow_id}/refund",
        json={"reason": "货物与样品不符"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "refunded"
    assert resp.json()["dispute_reason"] == "货物与样品不符"


@pytest.mark.asyncio
async def test_escrow_invalid_state_transitions(client: AsyncClient):
    """F34 担保支付非法状态流转"""
    token, headers = await _register_and_login(client, "13900009012")
    project_id = await _create_project(client, headers, "状态流转测试")
    supplier_ids = await _create_suppliers(client, headers, "appliances")
    material_id, _ = await _create_category_material_and_bom(
        client, headers, project_id,
        category_code="appliances",
        material_sku="PE-INV-001",
        material_name="状态流转空调",
    )
    order_id = await _create_order(client, headers, project_id, supplier_ids[0], material_id)

    # 创建担保支付
    resp = await client.post(
        "/api/procurement-enhanced/escrow",
        json={"order_id": order_id},
        headers=headers,
    )
    escrow_id = resp.json()["id"]

    # 在 pending 状态下直接释放应失败
    resp = await client.post(
        f"/api/procurement-enhanced/escrow/{escrow_id}/release",
        headers=headers,
    )
    assert resp.status_code == 400

    # 在 pending 状态下退款应失败
    resp = await client.post(
        f"/api/procurement-enhanced/escrow/{escrow_id}/refund",
        json={"reason": "测试"},
        headers=headers,
    )
    assert resp.status_code == 400

    # 付款
    await client.post(f"/api/procurement-enhanced/escrow/{escrow_id}/pay", headers=headers)

    # 已付款后再次付款应失败
    resp = await client.post(
        f"/api/procurement-enhanced/escrow/{escrow_id}/pay",
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_escrow_not_found(client: AsyncClient):
    """F34 不存在的担保支付"""
    token, headers = await _register_and_login(client, "13900009013")
    resp = await client.get(
        "/api/procurement-enhanced/escrow/non-existent-id",
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_escrow_order_not_found(client: AsyncClient):
    """F34 不存在的订单创建担保支付"""
    token, headers = await _register_and_login(client, "13900009014")
    resp = await client.post(
        "/api/procurement-enhanced/escrow",
        json={"order_id": "non-existent-order"},
        headers=headers,
    )
    assert resp.status_code == 400


# ── F34 物流追踪 ──

@pytest.mark.asyncio
async def test_logistics_create_and_track(client: AsyncClient):
    """F34 物流单创建 + 轨迹更新 + ETA"""
    token, headers = await _register_and_login(client, "13900009020")
    project_id = await _create_project(client, headers, "物流追踪测试")
    supplier_ids = await _create_suppliers(client, headers, "soft_decor")
    material_id, _ = await _create_category_material_and_bom(
        client, headers, project_id,
        category_code="soft_decor",
        material_sku="PE-LOG-001",
        material_name="物流测试沙发",
    )
    order_id = await _create_order(client, headers, project_id, supplier_ids[0], material_id)

    # 1. 创建物流单
    resp = await client.post(
        "/api/procurement-enhanced/logistics",
        json={
            "order_id": order_id,
            "carrier": "sf_express",
            "ship_from": "广东深圳市",
            "ship_to": "上海市浦东新区",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    tracking = resp.json()
    assert tracking["status"] == "pending"
    assert tracking["carrier"] == "sf_express"
    assert tracking["tracking_no"].startswith("LG-")
    assert tracking["estimated_arrival"] is not None  # ETA 已计算
    assert tracking["ship_from"] == "广东深圳市"
    assert tracking["ship_to"] == "上海市浦东新区"
    tracking_id = tracking["id"]

    # 2. 更新轨迹：已发货
    resp = await client.patch(
        f"/api/procurement-enhanced/logistics/{tracking_id}",
        json={"status": "shipped", "location": "深圳转运中心", "description": "已揽收"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "shipped"
    assert len(data["tracking_history"]) == 1
    assert data["tracking_history"][0]["location"] == "深圳转运中心"

    # 3. 更新轨迹：运输中
    resp = await client.patch(
        f"/api/procurement-enhanced/logistics/{tracking_id}",
        json={"status": "in_transit", "location": "上海中转场", "description": "运输中"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()["tracking_history"]) == 2

    # 4. 更新轨迹：已签收
    resp = await client.patch(
        f"/api/procurement-enhanced/logistics/{tracking_id}",
        json={"status": "delivered", "location": "上海浦东", "description": "客户已签收"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "delivered"
    assert data["actual_arrival"] is not None
    assert len(data["tracking_history"]) == 3


@pytest.mark.asyncio
async def test_logistics_eta_computation(client: AsyncClient):
    """F34 ETA 计算 — 不同承运商和起止地"""
    from app.services.procurement_enhanced_service import compute_eta, CARRIER_BASE_DAYS
    from app.models.procurement_enhanced import LogisticsTracking

    # 顺丰，同省份
    t1 = LogisticsTracking(
        tracking_no="T1", carrier="sf_express",
        ship_from="上海市闵行区", ship_to="上海市浦东新区",
    )
    eta1 = compute_eta(t1)
    base1 = CARRIER_BASE_DAYS["sf_express"]  # 2 天
    assert eta1 is not None

    # 德邦，跨省份（额外 1 天）
    t2 = LogisticsTracking(
        tracking_no="T2", carrier="debon",
        ship_from="北京市朝阳区", ship_to="上海市浦东新区",
    )
    eta2 = compute_eta(t2)
    assert eta2 is not None

    # 自送，无起止地
    t3 = LogisticsTracking(
        tracking_no="T3", carrier="self_delivery",
        ship_from=None, ship_to=None,
    )
    eta3 = compute_eta(t3)
    assert eta3 is not None


@pytest.mark.asyncio
async def test_logistics_order_query(client: AsyncClient):
    """F34 按订单查询物流"""
    token, headers = await _register_and_login(client, "13900009021")
    project_id = await _create_project(client, headers, "物流查询测试")
    supplier_ids = await _create_suppliers(client, headers, "custom_furniture")
    material_id, _ = await _create_category_material_and_bom(
        client, headers, project_id,
        category_code="custom_furniture",
        material_sku="PE-LQ-001",
        material_name="物流查询衣柜",
    )
    order_id = await _create_order(client, headers, project_id, supplier_ids[0], material_id)

    # 创建 2 个物流单
    for carrier in ["sf_express", "jd_logistics"]:
        resp = await client.post(
            "/api/procurement-enhanced/logistics",
            json={"order_id": order_id, "carrier": carrier, "ship_from": "广州", "ship_to": "上海"},
            headers=headers,
        )
        assert resp.status_code == 201

    # 按订单查询
    resp = await client.get(
        f"/api/procurement-enhanced/logistics/order/{order_id}",
        headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_logistics_not_found(client: AsyncClient):
    """F34 不存在的物流单"""
    token, headers = await _register_and_login(client, "13900009022")
    resp = await client.get(
        "/api/procurement-enhanced/logistics/non-existent-id",
        headers=headers,
    )
    assert resp.status_code == 404


# ── F34 样品索要 ──

@pytest.mark.asyncio
async def test_sample_full_lifecycle(client: AsyncClient):
    """F34 样品索要完整流程"""
    token, headers = await _register_and_login(client, "13900009030")
    project_id = await _create_project(client, headers, "样品索要测试")
    supplier_ids = await _create_suppliers(client, headers, "wall")
    material_id, _ = await _create_category_material_and_bom(
        client, headers, project_id,
        category_code="wall",
        material_sku="PE-SMP-001",
        material_name="样品测试涂料",
    )

    # 1. 索要样品
    resp = await client.post(
        "/api/procurement-enhanced/samples",
        json={
            "project_id": project_id,
            "supplier_id": supplier_ids[0],
            "material_id": material_id,
            "sample_type": "色卡",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    sample = resp.json()
    assert sample["status"] == "requested"
    assert sample["sample_type"] == "色卡"
    assert sample["shipped_at"] is None
    assert sample["received_at"] is None
    sample_id = sample["id"]

    # 2. 更新状态：已寄出
    resp = await client.patch(
        f"/api/procurement-enhanced/samples/{sample_id}",
        json={"status": "shipped"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "shipped"
    assert resp.json()["shipped_at"] is not None

    # 3. 更新状态：已收到
    resp = await client.patch(
        f"/api/procurement-enhanced/samples/{sample_id}",
        json={"status": "received", "notes": "样品质量良好"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "received"
    assert data["received_at"] is not None
    assert data["notes"] == "样品质量良好"


@pytest.mark.asyncio
async def test_sample_list_by_project(client: AsyncClient):
    """F34 项目样品列表"""
    token, headers = await _register_and_login(client, "13900009031")
    project_id = await _create_project(client, headers, "样品列表测试")
    supplier_ids = await _create_suppliers(client, headers, "flooring")

    # 创建 2 个样品索要
    for idx in range(2):
        resp = await client.post(
            "/api/procurement-enhanced/samples",
            json={
                "project_id": project_id,
                "supplier_id": supplier_ids[idx],
                "sample_type": "小样",
            },
            headers=headers,
        )
        assert resp.status_code == 201

    # 列表查询
    resp = await client.get(
        f"/api/procurement-enhanced/samples/project/{project_id}",
        headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_sample_not_found(client: AsyncClient):
    """F34 不存在的样品"""
    token, headers = await _register_and_login(client, "13900009032")
    resp = await client.patch(
        "/api/procurement-enhanced/samples/non-existent-id",
        json={"status": "shipped"},
        headers=headers,
    )
    assert resp.status_code == 404


# ── 服务层直接测试 ──

@pytest.mark.asyncio
async def test_rank_quotations_algorithm():
    """F33 评分算法: 价格 40% + 交期 25% + 库存 15% + 评分 20%"""
    from app.services.procurement_enhanced_service import rank_quotations

    quotations = [
        {"supplier_id": "A", "supplier_name": "A", "price": 100.0, "delivery_days": 5, "in_stock": True, "rating": 4.5},
        {"supplier_id": "B", "supplier_name": "B", "price": 120.0, "delivery_days": 3, "in_stock": True, "rating": 4.8},
        {"supplier_id": "C", "supplier_name": "C", "price": 90.0, "delivery_days": 10, "in_stock": False, "rating": 3.5},
    ]
    ranked = rank_quotations(quotations)
    assert len(ranked) == 3
    # 所有都应有 score 字段
    for q in ranked:
        assert "score" in q
        assert 0 <= q["score"] <= 100
    # 应按 score 降序排列
    scores = [q["score"] for q in ranked]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_compute_savings_algorithm():
    """F33 节省金额计算"""
    from app.services.procurement_enhanced_service import compute_savings

    class FakeItem:
        def __init__(self, quotations, recommended_price, quantity):
            self.quotations = quotations
            self.recommended_price = recommended_price
            self.quantity = quantity

    items = [
        # 最高价 120, 推荐价 100, 数量 10 → 节省 200
        FakeItem(
            quotations=[{"price": 100.0}, {"price": 120.0}, {"price": 110.0}],
            recommended_price=100.0,
            quantity=10.0,
        ),
        # 最高价 200, 推荐价 150, 数量 5 → 节省 250
        FakeItem(
            quotations=[{"price": 150.0}, {"price": 200.0}],
            recommended_price=150.0,
            quantity=5.0,
        ),
    ]
    total = compute_savings(items)
    assert total == 450.0


@pytest.mark.asyncio
async def test_rank_quotations_empty():
    """F33 空报价列表"""
    from app.services.procurement_enhanced_service import rank_quotations
    assert rank_quotations([]) == []
