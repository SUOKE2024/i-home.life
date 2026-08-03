"""预算模块全量测试 —— CRUD / F10 AI 分项预算 / F11 多方案对比 / F12 偏差预警 / F13 模板库"""

import json

import pytest
from httpx import AsyncClient

from app.agents.budget import (
    BUDGET_RATIOS,
    BUDGET_TEMPLATES,
    TIER_PRICES,
    BudgetAgent,
)


async def _register_and_login(client: AsyncClient, phone: str = "13900000010") -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "预算审计", "password": "test123456"},
    )
    return resp.json()["access_token"]


async def _create_project(client: AsyncClient, token: str, name: str = "预算项目") -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": name, "total_area": 100.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp.json()["id"]


# ── 预算 CRUD ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_budget(client: AsyncClient):
    token = await _register_and_login(client)
    proj_id = await _create_project(client, token)

    response = await client.post(
        "/api/budgets",
        json={
            "project_id": proj_id,
            "lines": [
                {
                    "category": "硬装", "name": "墙面处理",
                    "estimated_amount": 20000.0, "unit": "㎡",
                    "quantity": 100, "unit_price": 200,
                },
                {
                    "category": "软装", "name": "灯具",
                    "estimated_amount": 5000.0, "unit": "套",
                    "quantity": 1, "unit_price": 5000,
                },
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["total_estimated"] == 25000.0
    assert data["total_actual"] == 0.0
    assert data["status"] == "draft"
    assert len(data["lines"]) == 2
    assert data["project_id"] == proj_id


@pytest.mark.asyncio
async def test_create_budget_auto_calc_estimated(client: AsyncClient):
    """未显式提供 estimated_amount 时，按 quantity * unit_price 自动计算"""
    token = await _register_and_login(client, phone="13900000011")
    proj_id = await _create_project(client, token, "自动计算预算")

    response = await client.post(
        "/api/budgets",
        json={
            "project_id": proj_id,
            "lines": [
                {"category": "硬装", "name": "地板", "unit": "㎡", "quantity": 50, "unit_price": 300},
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["total_estimated"] == 15000.0
    assert data["lines"][0]["estimated_amount"] == 15000.0


@pytest.mark.asyncio
async def test_get_budget(client: AsyncClient):
    token = await _register_and_login(client, phone="13900000012")
    proj_id = await _create_project(client, token, "查询预算")

    await client.post(
        "/api/budgets",
        json={
            "project_id": proj_id,
            "lines": [
                {
                    "category": "测试", "name": "测试项",
                    "estimated_amount": 1000.0, "unit": "项",
                    "quantity": 1, "unit_price": 1000,
                },
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.get(
        f"/api/budgets/project/{proj_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_estimated"] == 1000.0
    assert len(data["lines"]) == 1


@pytest.mark.asyncio
async def test_get_budget_not_found(client: AsyncClient):
    token = await _register_and_login(client, phone="13900000013")
    proj_id = await _create_project(client, token, "无预算项目")

    response = await client.get(
        f"/api/budgets/project/{proj_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_budget(client: AsyncClient):
    token = await _register_and_login(client, phone="13900000014")
    proj_id = await _create_project(client, token, "重复预算")

    payload = {"project_id": proj_id, "lines": []}
    headers = {"Authorization": f"Bearer {token}"}
    first = await client.post("/api/budgets", json=payload, headers=headers)
    assert first.status_code == 201

    second = await client.post("/api/budgets", json=payload, headers=headers)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_update_budget_line(client: AsyncClient):
    token = await _register_and_login(client, phone="13900000015")
    proj_id = await _create_project(client, token, "更新预算行")

    create_resp = await client.post(
        "/api/budgets",
        json={
            "project_id": proj_id,
            "lines": [
                {
                    "category": "硬装", "name": "水电",
                    "estimated_amount": 10000.0, "unit": "项",
                    "quantity": 1, "unit_price": 10000,
                },
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    line_id = create_resp.json()["lines"][0]["id"]

    response = await client.patch(
        f"/api/budgets/lines/{line_id}",
        json={"actual_amount": 12000.0, "estimated_amount": 11000.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["actual_amount"] == 12000.0
    assert data["estimated_amount"] == 11000.0

    # 验证预算总额已重算
    budget_resp = await client.get(
        f"/api/budgets/project/{proj_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    budget = budget_resp.json()
    assert budget["total_estimated"] == 11000.0
    assert budget["total_actual"] == 12000.0


@pytest.mark.asyncio
async def test_update_budget_line_not_found(client: AsyncClient):
    token = await _register_and_login(client, phone="13900000016")

    response = await client.patch(
        "/api/budgets/lines/non-existent-line-id",
        json={"actual_amount": 1000.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_generate_budget_from_bom(client: AsyncClient):
    token = await _register_and_login(client, phone="13900000017")
    proj_id = await _create_project(client, token, "BOM 生成预算")

    # 创建物料分类
    cat_resp = await client.post(
        "/api/materials/categories",
        json={"name": "地面材料", "code": "flooring"},
        headers={"Authorization": f"Bearer {token}"},
    )
    cat_id = cat_resp.json()["id"]

    # 创建物料
    mat_resp = await client.post(
        "/api/materials",
        json={"category_id": cat_id, "name": "750×1500 大板砖", "sku": "TILE-750", "unit": "㎡", "unit_price": 180.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    mat_id = mat_resp.json()["id"]

    # 添加 BOM 项（quantity=100, unit_price=180 → BOM 采购总价 18000）
    # v1.1.31 FP-6：启用定额库后，预算 = BOM量 × 定额单价
    #   flooring @ comfort = 320元/㎡ → 100 × 320 = 32000（定额基准，非采购价）
    await client.post(
        "/api/materials/bom",
        json={"project_id": proj_id, "material_id": mat_id, "quantity": 100.0, "unit_price": 180.0},
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.post(
        f"/api/budgets/generate-from-bom/{proj_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    # 定额库启用：flooring comfort 档 320 元/㎡ × 100 = 32000
    assert data["total_estimated"] == 32000.0
    assert len(data["lines"]) == 1
    assert data["lines"][0]["name"] == "750×1500 大板砖"
    assert data["lines"][0]["category"] == "地面工程"
    # 定价来源标记（note 含 pricing_source=quota）
    assert "pricing_source=quota" in (data["lines"][0].get("note") or "")


@pytest.mark.asyncio
async def test_generate_budget_from_bom_no_materials(client: AsyncClient):
    token = await _register_and_login(client, phone="13900000018")
    proj_id = await _create_project(client, token, "空 BOM 项目")

    response = await client.post(
        f"/api/budgets/generate-from-bom/{proj_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_generate_budget_from_bom_conflict(client: AsyncClient):
    token = await _register_and_login(client, phone="13900000019")
    proj_id = await _create_project(client, token, "BOM 冲突项目")

    # 先创建一个预算
    await client.post(
        "/api/budgets",
        json={"project_id": proj_id, "lines": []},
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.post(
        f"/api/budgets/generate-from-bom/{proj_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


# ── F10 AI 分项预算 ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_f10_generate_budget_plan_default(client: AsyncClient):
    token = await _register_and_login(client, phone="13900000020")

    response = await client.post(
        "/api/budgets/generate-plan",
        json={"message": "126㎡ 舒适型"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tier"] == "comfort"
    assert data["tier_name"] == "舒适型"
    assert data["area"] == 126.0
    low, high = TIER_PRICES["comfort"]
    mid = (low + high) / 2
    assert data["total_estimated"] == round(126.0 * mid, 2)
    assert data["unit_price_range"] == [low, high]
    assert len(data["lines"]) == 8
    # 分项预算合计应等于总预算（round 容差）
    total_lines = round(sum(line["estimated_amount"] for line in data["lines"]), 2)
    assert abs(total_lines - data["total_estimated"]) <= 0.05
    # 8 类拆分 + 三费 + 价格来源
    categories = {line["category"] for line in data["lines"]}
    assert categories == {
        "土建改造", "硬装工程", "软装工程", "厨卫工程",
        "家具采购", "灯具照明", "家电设备", "智能家居",
    }
    for line in data["lines"]:
        assert "material_cost" in line and "labor_cost" in line and "management_cost" in line
        assert line["price_source"] == "市场价格库（估算）"
        assert abs(line["material_cost"] + line["labor_cost"] + line["management_cost"]
                   - line["estimated_amount"]) <= 0.05
    # 旧 5 类聚合字段向后兼容
    assert "legacy_5cat" in data
    assert set(data["legacy_5cat"].keys()) == {"hard_fit", "custom_cabinet", "soft_decor", "appliance", "other"}
    # 诚实标注：预算由规则引擎生成，未调用 LLM
    assert data["engine"] == "rule_based"
    assert "规则引擎" in data["source_note"]


@pytest.mark.asyncio
async def test_f10_generate_budget_plan_tier_detection(client: AsyncClient):
    token = await _register_and_login(client, phone="13900000021")
    cases = [
        ("90㎡ 经济型简装", "economy", 90.0),
        ("160㎡ 轻奢品质装修", "premium", 160.0),
        ("200㎡ 豪华高端大平层", "luxury", 200.0),
    ]
    for message, tier, area in cases:
        response = await client.post(
            "/api/budgets/generate-plan",
            json={"message": message},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == tier, f"消息「{message}」应识别为 {tier}"
        assert data["area"] == area


@pytest.mark.asyncio
async def test_f10_generate_budget_plan_ratios(client: AsyncClient):
    """验证分项预算比例合计为 1.0"""
    token = await _register_and_login(client, phone="13900000022")
    response = await client.post(
        "/api/budgets/generate-plan",
        json={"message": "126㎡ 舒适型"},
        headers={"Authorization": f"Bearer {token}"},
    )
    data = response.json()
    ratio_sum = round(sum(line["estimated_amount"] for line in data["lines"]) / data["total_estimated"], 4)
    assert abs(ratio_sum - 1.0) < 0.01


# ── F11 多方案预算对比 ───────────────────────────────────────


@pytest.mark.asyncio
async def test_f11_compare_budget_plans(client: AsyncClient):
    token = await _register_and_login(client, phone="13900000023")

    response = await client.post(
        "/api/budgets/compare-plans",
        json={"message": "126㎡"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["area"] == 126.0
    assert len(data["plans"]) == 3
    # 三档应递增
    totals = [p["total_estimated"] for p in data["plans"]]
    assert totals[0] < totals[1] < totals[2]
    assert data["plans"][0]["tier"] == "economy"
    assert data["plans"][1]["tier"] == "comfort"
    assert data["plans"][2]["tier"] == "premium"
    # 差异分析
    assert data["differences"]["economy_to_comfort"] == round(totals[1] - totals[0], 2)
    assert data["differences"]["comfort_to_premium"] == round(totals[2] - totals[1], 2)
    assert "推荐" in data["recommendation"]


@pytest.mark.asyncio
async def test_f11_compare_budget_plans_area_detection(client: AsyncClient):
    token = await _register_and_login(client, phone="13900000024")
    response = await client.post(
        "/api/budgets/compare-plans",
        json={"message": "90㎡ 小户型"},
        headers={"Authorization": f"Bearer {token}"},
    )
    data = response.json()
    assert data["area"] == 90.0
    for plan in data["plans"]:
        low, high = TIER_PRICES[plan["tier"]]
        assert plan["total_range"] == [round(90.0 * low, 2), round(90.0 * high, 2)]


# ── F12 预算偏差预警 ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_f12_variance_ok(client: AsyncClient):
    token = await _register_and_login(client, phone="13900000025")
    response = await client.post(
        "/api/budgets/variance-check",
        json={"total_estimated": 100000.0, "total_actual": 103000.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["variance_pct"] == 3.0
    assert data["alert"] is None


@pytest.mark.asyncio
async def test_f12_variance_warning(client: AsyncClient):
    token = await _register_and_login(client, phone="13900000026")
    response = await client.post(
        "/api/budgets/variance-check",
        json={"total_estimated": 100000.0, "total_actual": 106000.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    data = response.json()
    assert data["status"] == "warning"
    assert data["variance_pct"] == 6.0
    assert "5% 预警阈值" in data["alert"]


@pytest.mark.asyncio
async def test_f12_variance_critical(client: AsyncClient):
    token = await _register_and_login(client, phone="13900000027")
    response = await client.post(
        "/api/budgets/variance-check",
        json={"total_estimated": 100000.0, "total_actual": 115000.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    data = response.json()
    assert data["status"] == "critical"
    assert data["variance_pct"] == 15.0
    assert "停工复盘" in data["alert"]


@pytest.mark.asyncio
async def test_f12_variance_saving(client: AsyncClient):
    token = await _register_and_login(client, phone="13900000028")
    response = await client.post(
        "/api/budgets/variance-check",
        json={"total_estimated": 100000.0, "total_actual": 85000.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    data = response.json()
    assert data["status"] == "saving"
    assert data["variance_pct"] == -15.0
    assert "节约" in data["alert"]


@pytest.mark.asyncio
async def test_f12_variance_zero_estimated(client: AsyncClient):
    token = await _register_and_login(client, phone="13900000029")
    response = await client.post(
        "/api/budgets/variance-check",
        json={"total_estimated": 0.0, "total_actual": 5000.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    data = response.json()
    assert data["status"] == "ok"
    assert data["variance_pct"] == 0


# ── F13 预算模板库 ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_f13_list_templates(client: AsyncClient):
    token = await _register_and_login(client, phone="13900000030")

    response = await client.get(
        "/api/budgets/templates",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == len(BUDGET_TEMPLATES)
    assert len(data["templates"]) == len(BUDGET_TEMPLATES)
    for tpl in data["templates"]:
        assert "code" in tpl
        assert "name" in tpl
        assert "area" in tpl
        assert "tier" in tpl
        assert "total_range" in tpl
        assert tpl["line_count"] > 0


@pytest.mark.asyncio
async def test_f13_apply_template_default_area(client: AsyncClient):
    token = await _register_and_login(client, phone="13900000031")
    code = "126_comfort_modern"
    tpl = BUDGET_TEMPLATES[code]

    response = await client.post(
        "/api/budgets/templates/apply",
        json={"template_code": code},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["template_code"] == code
    assert data["scale"] == 1.0
    assert data["applied_area"] == tpl["area"]
    # 验算总价
    expected_total = round(sum(line["unit_price"] * line["quantity"] for line in tpl["lines"]), 2)
    assert data["total_estimated"] == expected_total
    assert len(data["lines"]) == len(tpl["lines"])


@pytest.mark.asyncio
async def test_f13_apply_template_with_scaling(client: AsyncClient):
    token = await _register_and_login(client, phone="13900000032")
    code = "90_economy_modern"
    tpl = BUDGET_TEMPLATES[code]
    target_area = 120.0
    expected_scale = target_area / tpl["area"]

    response = await client.post(
        "/api/budgets/templates/apply",
        json={"template_code": code, "area": target_area},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["scale"] == round(expected_scale, 3)
    assert data["applied_area"] == target_area
    # 验算缩放后首行数量
    first_line = tpl["lines"][0]
    expected_qty = round(first_line["quantity"] * expected_scale, 2)
    assert data["lines"][0]["quantity"] == expected_qty


@pytest.mark.asyncio
async def test_f13_apply_template_not_found(client: AsyncClient):
    token = await _register_and_login(client, phone="13900000033")

    response = await client.post(
        "/api/budgets/templates/apply",
        json={"template_code": "non_existent_template"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert "available" in data


# ── F13 预算模板 AI 自动填充（LLM 优先 + 诚实回退）─────────────


@pytest.mark.asyncio
async def test_f13_apply_template_llm_success(client: AsyncClient, monkeypatch):
    """LLM 可用（返回有效 JSON lines）时 filling_source=llm 且按 unit_price×quantity 计算"""
    token = await _register_and_login(client, phone="13900000050")

    async def fake_chat(self, messages, **kwargs):
        return json.dumps({
            "lines": [
                {"category": "硬装", "name": "水电改造", "unit_price": 250, "quantity": 126, "unit": "㎡"},
                {"category": "软装", "name": "全屋窗帘", "unit_price": 8000, "quantity": 1, "unit": "套"},
            ]
        }, ensure_ascii=False)

    monkeypatch.setattr(BudgetAgent, "_chat", fake_chat)

    response = await client.post(
        "/api/budgets/templates/apply",
        json={"template_code": "126_comfort_modern"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filling_source"] == "llm"
    assert "llm" in data["note"]
    assert data["total_estimated"] == round(250 * 126 + 8000, 2)
    assert len(data["lines"]) == 2
    for line in data["lines"]:
        assert line["estimated_amount"] == round(line["unit_price"] * line["quantity"], 2)


@pytest.mark.asyncio
async def test_f13_apply_template_llm_fallback_rule(client: AsyncClient, monkeypatch):
    """LLM 抛异常时回退线性缩放，filling_source=rule 且 note 标注降级"""
    token = await _register_and_login(client, phone="13900000051")

    async def fake_chat(self, messages, **kwargs):
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(BudgetAgent, "_chat", fake_chat)

    code = "90_economy_modern"
    tpl = BUDGET_TEMPLATES[code]
    target_area = 120.0
    response = await client.post(
        "/api/budgets/templates/apply",
        json={"template_code": code, "area": target_area},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filling_source"] == "rule"
    assert "降级" in data["note"]
    assert data["applied_area"] == target_area
    expected_scale = target_area / tpl["area"]
    assert data["scale"] == round(expected_scale, 3)
    # 缩放逻辑与规则路径一致
    expected_total = round(sum(line["unit_price"] * round(line["quantity"] * expected_scale, 2)
                               for line in tpl["lines"]), 2)
    assert data["total_estimated"] == expected_total


@pytest.mark.asyncio
async def test_f13_apply_template_llm_non_json_fallback_rule(client: AsyncClient, monkeypatch):
    """LLM 返回非 JSON 时回退线性缩放（诚实降级，不伪装 LLM 能力）"""
    token = await _register_and_login(client, phone="13900000052")

    async def fake_chat(self, messages, **kwargs):
        return "抱歉，我只能给出文字建议。"

    monkeypatch.setattr(BudgetAgent, "_chat", fake_chat)

    response = await client.post(
        "/api/budgets/templates/apply",
        json={"template_code": "126_comfort_modern"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filling_source"] == "rule"
    assert "降级" in data["note"]


# ── F12 采购订单 → 预算科目自动扣减联动 ─────────────────────


@pytest.mark.asyncio
async def test_f12_purchase_order_deducts_budget(client: AsyncClient):
    """F12 联动：创建采购订单后，对应预算科目 actual_amount 自动扣减"""
    token = await _register_and_login(client, phone="13900000040")
    headers = {"Authorization": f"Bearer {token}"}
    proj_id = await _create_project(client, token, "F12联动项目")

    # 创建预算（含「地面工程」科目）
    budget_resp = await client.post(
        "/api/budgets",
        json={
            "project_id": proj_id,
            "lines": [
                {
                    "category": "地面工程", "name": "大板砖",
                    "estimated_amount": 50000.0, "unit": "㎡",
                    "quantity": 100, "unit_price": 500,
                },
            ],
        },
        headers=headers,
    )
    assert budget_resp.status_code == 201

    # 供应商 + 物料（flooring 品类 → 预算科目「地面工程」）
    sup_resp = await client.post(
        "/api/procurement/suppliers",
        json={"name": "F12供应商", "category": "flooring", "rating": 4.5},
        headers=headers,
    )
    supplier_id = sup_resp.json()["id"]
    cat_resp = await client.post(
        "/api/materials/categories",
        json={"name": "地面材料", "code": "flooring"},
        headers=headers,
    )
    mat_resp = await client.post(
        "/api/materials",
        json={
            "category_id": cat_resp.json()["id"], "name": "大板瓷砖",
            "sku": "F12-TILE-001", "unit": "㎡", "unit_price": 180.0,
        },
        headers=headers,
    )
    material_id = mat_resp.json()["id"]

    # 创建采购订单（10 × 180 = 1800）
    order_resp = await client.post(
        "/api/procurement/orders",
        json={
            "project_id": proj_id,
            "supplier_id": supplier_id,
            "lines": [{"material_id": material_id, "quantity": 10, "unit_price": 180.0}],
        },
        headers=headers,
    )
    assert order_resp.status_code == 201
    order_id = order_resp.json()["id"]

    # 预算科目已被自动扣减
    budget_resp = await client.get(f"/api/budgets/project/{proj_id}", headers=headers)
    budget = budget_resp.json()
    assert budget["total_actual"] == 1800.0
    floor_line = next(ln for ln in budget["lines"] if ln["category"] == "地面工程")
    assert floor_line["actual_amount"] == 1800.0

    # 订单 note 体现预算联动审计
    detail_resp = await client.get(
        f"/api/procurement/orders/detail/{order_id}", headers=headers
    )
    assert "预算联动" in (detail_resp.json().get("note") or "")

    # 联动记录可查
    links_resp = await client.get(f"/api/budgets/{proj_id}/linked-purchases", headers=headers)
    assert links_resp.status_code == 200
    links = links_resp.json()
    assert links["has_budget"] is True
    assert links["linked_count"] == 1
    assert links["linked_purchases"][0]["order_id"] == order_id
    assert links["linked_purchases"][0]["category"] == "地面工程"
    assert links["linked_purchases"][0]["status"] == "draft"
    assert links["linked_purchases"][0]["total_amount"] == 1800.0


@pytest.mark.asyncio
async def test_f12_purchase_order_without_budget(client: AsyncClient):
    """F12 联动：项目无预算时下单不报错（预算联动不阻塞采购主流程）"""
    token = await _register_and_login(client, phone="13900000041")
    headers = {"Authorization": f"Bearer {token}"}
    proj_id = await _create_project(client, token, "F12无预算项目")

    sup_resp = await client.post(
        "/api/procurement/suppliers",
        json={"name": "F12供应商2", "category": "flooring", "rating": 4.0},
        headers=headers,
    )
    cat_resp = await client.post(
        "/api/materials/categories",
        json={"name": "地面材料2", "code": "flooring"},
        headers=headers,
    )
    mat_resp = await client.post(
        "/api/materials",
        json={
            "category_id": cat_resp.json()["id"], "name": "瓷砖2",
            "sku": "F12-TILE-002", "unit_price": 100.0,
        },
        headers=headers,
    )
    order_resp = await client.post(
        "/api/procurement/orders",
        json={
            "project_id": proj_id,
            "supplier_id": sup_resp.json()["id"],
            "lines": [
                {"material_id": mat_resp.json()["id"], "quantity": 5, "unit_price": 100.0},
            ],
        },
        headers=headers,
    )
    assert order_resp.status_code == 201
    assert order_resp.json()["total_amount"] == 500.0

    # 无预算 → 联动记录为空且不报错
    links_resp = await client.get(f"/api/budgets/{proj_id}/linked-purchases", headers=headers)
    assert links_resp.status_code == 200
    assert links_resp.json()["has_budget"] is False
    assert links_resp.json()["linked_count"] == 0


# ── Agent 单元测试（不依赖 HTTP，直接测业务逻辑）──────────────


class TestBudgetAgentUnit:
    """BudgetAgent 纯逻辑单元测试"""

    def setup_method(self):
        self.agent = BudgetAgent()

    def test_detect_tier(self):
        assert self.agent.detect_tier("豪华大平层") == "luxury"
        assert self.agent.detect_tier("轻奢品质装修") == "premium"
        assert self.agent.detect_tier("经济简装出租房") == "economy"
        assert self.agent.detect_tier("126㎡ 三室两厅") == "comfort"

    def test_detect_area(self):
        assert self.agent.detect_area("126㎡") == 126.0
        assert self.agent.detect_area("90 平方") == 90.0
        assert self.agent.detect_area("大平层") == 160.0
        assert self.agent.detect_area("小户型") == 90.0
        assert self.agent.detect_area("无面积信息") == 126.0

    def test_generate_budget_plan_lines_cover_all_categories(self):
        plan = self.agent.generate_budget_plan("126㎡ 舒适型")
        categories = {line["category"] for line in plan["lines"]}
        assert categories == {
            "土建改造", "硬装工程", "软装工程", "厨卫工程",
            "家具采购", "灯具照明", "家电设备", "智能家居",
        }

    def test_generate_budget_plan_ratio_match(self):
        for tier in TIER_PRICES:
            msg = {"economy": "经济型", "comfort": "舒适型", "premium": "品质型", "luxury": "豪华型"}[tier]
            plan = self.agent.generate_budget_plan(f"100㎡ {msg}")
            ratios = BUDGET_RATIOS[tier]
            for line in plan["lines"]:
                cat_key = {
                    "土建改造": "structural", "硬装工程": "hard_fit", "软装工程": "soft_decor",
                    "厨卫工程": "kitchen_bath", "家具采购": "furniture", "灯具照明": "lighting",
                    "家电设备": "appliance", "智能家居": "smart_home",
                }[line["category"]]
                expected = round(plan["total_estimated"] * ratios[cat_key], 2)
                assert line["estimated_amount"] == expected

    def test_generate_budget_plan_cost_split_and_price_source(self):
        """每项预算行含材料/人工/管理费拆分（60/30/10）与价格来源（规则路径标市场价格库估算）"""
        plan = self.agent.generate_budget_plan("126㎡ 舒适型")
        assert len(plan["lines"]) == 8
        for line in plan["lines"]:
            assert line["material_cost"] == round(line["estimated_amount"] * 0.6, 2)
            assert line["labor_cost"] == round(line["estimated_amount"] * 0.3, 2)
            assert line["management_cost"] == round(line["estimated_amount"] * 0.1, 2)
            assert line["price_source"] == "市场价格库（估算）"
            assert "估算" in line["cost_split_note"]
        # 旧 5 类聚合合计应等于总预算
        legacy_total = round(sum(plan["legacy_5cat"].values()), 2)
        assert abs(legacy_total - plan["total_estimated"]) <= 0.05

    def test_compare_budget_plans_returns_three_tiers(self):
        result = self.agent.compare_budget_plans("126㎡")
        assert len(result["plans"]) == 3
        tiers = [p["tier"] for p in result["plans"]]
        assert tiers == ["economy", "comfort", "premium"]

    def test_check_budget_variance_thresholds(self):
        assert self.agent.check_budget_variance(100000, 100000)["status"] == "ok"
        assert self.agent.check_budget_variance(100000, 103000)["status"] == "ok"
        assert self.agent.check_budget_variance(100000, 106000)["status"] == "warning"
        assert self.agent.check_budget_variance(100000, 115000)["status"] == "critical"
        assert self.agent.check_budget_variance(100000, 85000)["status"] == "saving"

    def test_list_templates_matches_registry(self):
        result = self.agent.list_templates()
        assert result["total"] == len(BUDGET_TEMPLATES)
        codes = {t["code"] for t in result["templates"]}
        assert codes == set(BUDGET_TEMPLATES.keys())

    @pytest.mark.asyncio
    async def test_apply_template_invalid_code(self):
        result = await self.agent.apply_template("invalid_code")
        assert "error" in result
        assert result["available"] == list(BUDGET_TEMPLATES.keys())
