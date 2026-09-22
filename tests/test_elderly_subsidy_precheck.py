"""F41 适老改造补贴资格预检 — 确定性估算测试

政策依据（2026-09-02 商务部等八部门《促进智能家居消费行动方案》+ 2026 消费品以旧换新
适老化补贴地方细则的媒体报道口径）：
- 各地普遍按产品成交价 15% 补贴，并设置单件补贴上限
- 补贴目录围绕老年人五大居家刚需场景：防跌倒安全防护 / 居家用火用水安防 /
  家务劳作减负 / 健康应急监护 / 行动康复辅助

覆盖端点:
- POST /api/elderly-adaptation/subsidy-precheck          (补贴资格预检)

诚实红线（断言锁定）：
- 输出必须标注 is_estimate=True，且不得宣称已获补贴/已通过核定
- 未接入地方官方目录时必须在 warnings 中标注，且不得省略
- 个人资格（年龄/失能等级/困难身份）不参与确定性判定，须在 warnings 中标注
"""
import pytest
from httpx import AsyncClient

from app.config import get_settings
from app.services import elderly_subsidy_service as subsidy

ALL_FIVE_CATEGORIES = [
    "fall_prevention",
    "fire_water_safety",
    "housework_relief",
    "health_emergency",
    "mobility_rehab",
]


async def _auth_headers(client: AsyncClient, phone: str = "13950020001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "补贴预检测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── 服务层：确定性计算 ──


def test_subsidy_categories_cover_five_scenarios():
    """补贴目录覆盖政策五大居家刚需场景"""
    for code in ALL_FIVE_CATEGORIES:
        assert code in subsidy.SUBSIDY_CATEGORIES
    assert "other" in subsidy.SUBSIDY_CATEGORIES


def test_national_baseline_profile_matches_reported_terms():
    """全国基准档案：15% 比例 + 五大场景可补贴 + 未设定单件上限（诚实留空）"""
    profile = subsidy.SUBSIDY_POLICY_PROFILES["national_baseline"]
    assert profile["subsidy_rate"] == 0.15
    assert profile["max_subsidy_per_unit"] is None
    assert set(profile["eligible_categories"]) == set(ALL_FIVE_CATEGORIES)
    assert profile["version"]
    assert profile["disclaimer"]


def test_precheck_estimates_eligible_and_ineligible_items():
    """可补贴品类按 15% 估算；不在目录内的品类计 0 并给出原因"""
    result = subsidy.precheck_subsidy(
        items=[
            {"name": "毫米波跌倒监测雷达", "category": "fall_prevention",
             "unit_price": 1200.0, "quantity": 1},
            {"name": "全屋软装布艺", "category": "other",
             "unit_price": 500.0, "quantity": 2},
        ],
        policy_profile="national_baseline",
    )

    assert result["is_estimate"] is True
    assert result["total_price"] == 2200.0
    assert result["total_subsidy"] == 180.0
    assert result["net_payable"] == 2020.0

    first, second = result["items"]
    assert first["eligible"] is True
    assert first["subsidy_amount"] == 180.0
    assert first["category_label"] == subsidy.SUBSIDY_CATEGORIES["fall_prevention"]
    assert second["eligible"] is False
    assert second["subsidy_amount"] == 0.0
    assert second["reason"]


def test_precheck_quantity_applies_per_unit():
    """补贴额按「单价 × 数量」的小计估算"""
    result = subsidy.precheck_subsidy(
        items=[{"name": "防干烧灶具", "category": "fire_water_safety",
                "unit_price": 2000.0, "quantity": 2}],
        policy_profile="national_baseline",
    )
    assert result["items"][0]["subtotal"] == 4000.0
    assert result["total_subsidy"] == 600.0


def test_precheck_warns_when_cap_not_configured():
    """基准未设单件上限时必须警告（不得默认按无上限冒充最终结果）"""
    result = subsidy.precheck_subsidy(
        items=[{"name": "护理床", "category": "health_emergency",
                "unit_price": 8000.0, "quantity": 1}],
        policy_profile="national_baseline",
    )
    assert any("单件" in w for w in result["warnings"])


def test_precheck_warns_when_region_absent():
    """未指定地区 → 警告未接入地方补贴目录"""
    result = subsidy.precheck_subsidy(
        items=[{"name": "夜间感应照明", "category": "fall_prevention",
                "unit_price": 300.0, "quantity": 1}],
    )
    assert result["region"] is None
    assert any("地方" in w for w in result["warnings"])


def test_precheck_warns_region_not_verified():
    """指定地区但未接入官方目录 → 明确标注需以当地政策为准"""
    result = subsidy.precheck_subsidy(
        items=[{"name": "夜间感应照明", "category": "fall_prevention",
                "unit_price": 300.0, "quantity": 1}],
        region="昆明市",
    )
    assert result["region"] == "昆明市"
    assert any("昆明市" in w for w in result["warnings"])


def test_precheck_never_claims_personal_eligibility():
    """个人资格（年龄/失能等级）不参与判定 → 必须警告不得据此认定资格"""
    result = subsidy.precheck_subsidy(
        items=[{"name": "扶手安装", "category": "mobility_rehab",
                "unit_price": 800.0, "quantity": 1}],
    )
    assert any("个人资格" in w for w in result["warnings"])


def test_precheck_unknown_profile_raises():
    """未知政策档案 → ValueError"""
    with pytest.raises(ValueError):
        subsidy.precheck_subsidy(
            items=[{"name": "扶手", "category": "mobility_rehab",
                    "unit_price": 100.0, "quantity": 1}],
            policy_profile="unknown-profile",
        )


def test_precheck_empty_items_raises():
    """空清单 → ValueError（不得返回 0 补贴冒充结论）"""
    with pytest.raises(ValueError):
        subsidy.precheck_subsidy(items=[])


def test_precheck_from_package_code_uses_fixed_price():
    """按套餐编码预检：取套餐一口价作为清单行"""
    result = subsidy.precheck_subsidy(package_code="PKG-ELDERLY-BATH")
    assert result["total_price"] > 0
    item = result["items"][0]
    assert "适老" in item["name"]
    assert item["eligible"] is True
    assert result["total_subsidy"] == round(result["total_price"] * 0.15, 2)


def test_precheck_unknown_package_code_raises():
    """未知套餐编码 → ValueError"""
    with pytest.raises(ValueError):
        subsidy.precheck_subsidy(package_code="PKG-UNKNOWN")


def test_precheck_requires_items_or_package():
    """既无清单也无套餐编码 → ValueError"""
    with pytest.raises(ValueError):
        subsidy.precheck_subsidy()


# ── API：认证 ──


@pytest.mark.asyncio
async def test_subsidy_precheck_unauthorized(client: AsyncClient):
    """未认证用户不能调用补贴预检"""
    resp = await client.post(
        "/api/elderly-adaptation/subsidy-precheck",
        json={"items": [{"name": "扶手", "category": "mobility_rehab", "unit_price": 100.0}]},
    )
    assert resp.status_code == 401


# ── API：正常路径 ──


@pytest.mark.asyncio
async def test_subsidy_precheck_by_items(client: AsyncClient):
    """按拟购清单预检 → 返回逐项补贴与落地价"""
    headers = await _auth_headers(client, "13950020002")
    resp = await client.post(
        "/api/elderly-adaptation/subsidy-precheck",
        json={
            "region": "昆明市",
            "items": [
                {"name": "毫米波跌倒监测雷达", "category": "fall_prevention",
                 "unit_price": 1200.0, "quantity": 1},
                {"name": "全屋软装布艺", "category": "other",
                 "unit_price": 500.0, "quantity": 2},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_estimate"] is True
    assert body["policy_profile"] == "national_baseline"
    assert body["total_price"] == 2200.0
    assert body["total_subsidy"] == 180.0
    assert body["net_payable"] == 2020.0
    assert len(body["items"]) == 2
    assert body["warnings"]
    assert body["disclaimer"]


@pytest.mark.asyncio
async def test_subsidy_precheck_by_package_code(client: AsyncClient):
    """按适老套餐编码预检 → 一口价参与估算"""
    headers = await _auth_headers(client, "13950020003")
    resp = await client.post(
        "/api/elderly-adaptation/subsidy-precheck",
        json={"package_code": "PKG-ELDERLY-BATH"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_price"] > 0
    assert body["total_subsidy"] == round(body["total_price"] * 0.15, 2)


# ── API：参数校验 ──


@pytest.mark.asyncio
async def test_subsidy_precheck_missing_input(client: AsyncClient):
    """既无 items 也无 package_code → 400"""
    headers = await _auth_headers(client, "13950020004")
    resp = await client.post(
        "/api/elderly-adaptation/subsidy-precheck", json={}, headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_subsidy_precheck_unknown_profile(client: AsyncClient):
    """未知政策档案 → 400"""
    headers = await _auth_headers(client, "13950020005")
    resp = await client.post(
        "/api/elderly-adaptation/subsidy-precheck",
        json={"policy_profile": "unknown", "items": [
            {"name": "扶手", "category": "mobility_rehab", "unit_price": 100.0}]},
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_subsidy_precheck_unknown_package(client: AsyncClient):
    """未知套餐编码 → 400"""
    headers = await _auth_headers(client, "13950020006")
    resp = await client.post(
        "/api/elderly-adaptation/subsidy-precheck",
        json={"package_code": "PKG-UNKNOWN"},
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_subsidy_precheck_invalid_quantity(client: AsyncClient):
    """数量 < 1 → 422（schema 约束）"""
    headers = await _auth_headers(client, "13950020007")
    resp = await client.post(
        "/api/elderly-adaptation/subsidy-precheck",
        json={"items": [{"name": "扶手", "category": "mobility_rehab",
                         "unit_price": 100.0, "quantity": 0}]},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_subsidy_precheck_negative_price(client: AsyncClient):
    """负单价 → 422（schema 约束）"""
    headers = await _auth_headers(client, "13950020008")
    resp = await client.post(
        "/api/elderly-adaptation/subsidy-precheck",
        json={"items": [{"name": "扶手", "category": "mobility_rehab",
                         "unit_price": -1.0, "quantity": 1}]},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_subsidy_profiles_lists_baseline(client: AsyncClient):
    """政策档案列表：含全国基准 + 口径来源 + 免责声明"""
    headers = await _auth_headers(client, "13950020010")
    resp = await client.get("/api/elderly-adaptation/subsidy-profiles", headers=headers)
    assert resp.status_code == 200
    profiles = {p["policy_profile"]: p for p in resp.json()}
    baseline = profiles["national_baseline"]
    assert baseline["subsidy_rate"] == 0.15
    assert baseline["max_subsidy_per_unit"] is None
    assert set(baseline["eligible_categories"]) == set(ALL_FIVE_CATEGORIES)
    assert baseline["source"] and baseline["disclaimer"]


@pytest.mark.asyncio
async def test_subsidy_precheck_disabled_by_flag(client: AsyncClient, monkeypatch):
    """feature flag 关闭 → 404（诚实不可用，不返回假数据）"""
    headers = await _auth_headers(client, "13950020009")
    monkeypatch.setattr(get_settings(), "elderly_subsidy_precheck_enabled", False)
    resp = await client.post(
        "/api/elderly-adaptation/subsidy-precheck",
        json={"items": [{"name": "扶手", "category": "mobility_rehab", "unit_price": 100.0}]},
        headers=headers,
    )
    assert resp.status_code == 404

    resp = await client.get("/api/elderly-adaptation/subsidy-profiles", headers=headers)
    assert resp.status_code == 404
