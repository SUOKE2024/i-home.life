"""预算模块全量测试 —— CRUD / F10 AI 分项预算 / F11 多方案对比 / F12 偏差预警 / F13 模板库"""

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

    # 添加 BOM 项（quantity=100, unit_price=180 → total=18000）
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
    assert data["total_estimated"] == 18000.0
    assert len(data["lines"]) == 1
    assert data["lines"][0]["name"] == "750×1500 大板砖"
    assert data["lines"][0]["category"] == "地面工程"


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
    assert len(data["lines"]) == 5
    # 分项预算合计应等于总预算
    total_lines = round(sum(line["estimated_amount"] for line in data["lines"]), 2)
    assert total_lines == data["total_estimated"]


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
        assert categories == {"硬装工程", "定制柜体", "软装工程", "家电设备", "其他费用"}

    def test_generate_budget_plan_ratio_match(self):
        for tier in TIER_PRICES:
            msg = {"economy": "经济型", "comfort": "舒适型", "premium": "品质型", "luxury": "豪华型"}[tier]
            plan = self.agent.generate_budget_plan(f"100㎡ {msg}")
            ratios = BUDGET_RATIOS[tier]
            for line in plan["lines"]:
                cat_key = {
                    "硬装工程": "hard_fit", "定制柜体": "custom_cabinet",
                    "软装工程": "soft_decor", "家电设备": "appliance", "其他费用": "other",
                }[line["category"]]
                expected = round(plan["total_estimated"] * ratios[cat_key], 2)
                assert line["estimated_amount"] == expected

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

    def test_apply_template_invalid_code(self):
        result = self.agent.apply_template("invalid_code")
        assert "error" in result
        assert result["available"] == list(BUDGET_TEMPLATES.keys())
