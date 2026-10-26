"""小程序只读数据链路契约测试。

小程序页面不直接读后端字段，而是经 `miniapp/src/services/adapters.ts` 从 DTO 取固定键名。
后端一旦改名（此前 `quick-install/packages` 的 `code` → `package_code` 就踩过一次），
TypeScript 不会报错，线上表现是页面某个值静默变空 —— 这类问题只有契约测试能拦住。

本文件按「适配层真正读了哪些字段」逐项断言，新增字段不 breaking，改名/删字段立即失败。
"""
import pytest
from httpx import AsyncClient

# adapters.ts toSpace() 读取的字段
SPACE_ASSET_FIELDS = {
    "id",
    "name",
    "project_id",
    "province",
    "city",
    "district",
    "building_area_sqm",
    "business_format",
    "renovation_status",
    "smart_readiness_score",
    "matter_device_count",
    "sensor_count",
    "scene_automation_count",
    "fire_safety_status",
    "accessibility_status",
    "retrofit_package_code",
    "created_at",
}

# adapters.ts toProject() 读取的字段
PROJECT_FIELDS = {
    "id",
    "name",
    "address",
    "total_area",
    "house_type",
    "project_type",
    "status",
    "phase",
    "updated_at",
}


async def _register(client: AsyncClient, phone: str) -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "小程序契约测试", "password": "test123456"},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _seed_project_and_asset(client: AsyncClient, token: str) -> tuple[str, str]:
    """造一条真实项目 + 空间资产，用于断言列表字段。"""
    headers = _headers(token)
    project = await client.post(
        "/api/projects",
        json={
            "name": "契约测试项目",
            "project_type": "bathroom",
            "address": "昆明市五华区测试路 1 号",
            "total_area": 96.5,
        },
        headers=headers,
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    asset = await client.post(
        "/api/space-assets",
        json={
            "name": "契约测试空间",
            "asset_holder": "索克(昆明)联合科技有限责任公司",
            "province": "云南省",
            "city": "昆明市",
            "district": "五华区",
            "building_area_sqm": 96.5,
            "asset_category": "kangyang",
            "business_format": "elderly_home",
            "matter_device_count": 6,
            "sensor_count": 3,
            "scene_automation_count": 2,
            "fire_safety_status": "pass",
            "accessibility_status": "warning",
            "project_id": project_id,
            "retrofit_package_code": "PKG-ELDERLY-BATH",
        },
        headers=headers,
    )
    assert asset.status_code in (200, 201), asset.text
    return project_id, asset.json()["id"]


@pytest.mark.asyncio
async def test_space_asset_fields_match_miniprogram_adapter(client: AsyncClient):
    """空间台账字段必须齐：首页健康分、四维就绪度、空间详情全靠它。"""
    token = await _register(client, "13900003001")
    await _seed_project_and_asset(client, token)

    resp = await client.get("/api/space-assets", headers=_headers(token))
    assert resp.status_code == 200
    assets = resp.json()
    assert len(assets) == 1, "新建资产必须对本人可见"

    missing = SPACE_ASSET_FIELDS - set(assets[0])
    assert not missing, f"小程序适配层读取的字段缺失：{missing}"

    asset = assets[0]
    # 枚举值必须落在前端映射表内，否则 toSpaceFormat 会静默回落成「其他」
    assert asset["business_format"] == "elderly_home"
    assert 0 <= asset["smart_readiness_score"] <= 100
    assert asset["retrofit_package_code"] == "PKG-ELDERLY-BATH"


@pytest.mark.asyncio
async def test_project_fields_match_miniprogram_adapter(client: AsyncClient):
    """项目列表字段必须齐：阶段、进度、面积、更新时间都从这些键推。"""
    token = await _register(client, "13900003002")
    await _seed_project_and_asset(client, token)

    resp = await client.get("/api/projects", headers=_headers(token))
    assert resp.status_code == 200
    projects = resp.json()
    assert projects, "新建项目必须对本人可见"

    missing = PROJECT_FIELDS - set(projects[0])
    assert not missing, f"小程序适配层读取的字段缺失：{missing}"

    # phase 是前端唯一阶段口径来源；initiation 会被显示成「待勘测」而非「设计」
    assert projects[0]["phase"] in {
        "initiation",
        "design",
        "budget",
        "procurement",
        "construction",
        "quality",
        "settlement",
        "completed",
    }


@pytest.mark.asyncio
async def test_quick_install_packages_expose_package_code(client: AsyncClient):
    """套餐主键是 package_code 而非 code —— 曾因此让补贴预检 404。"""
    token = await _register(client, "13900003003")
    resp = await client.get(
        "/api/partial-renovation/quick-install/packages", headers=_headers(token)
    )
    assert resp.status_code == 200, resp.text
    packages = resp.json()
    assert packages, "套餐目录不应为空：适老页与详情页都依赖它"

    first = packages[0]
    assert "package_code" in first, "套餐主键字段名变更，小程序会读不到编码"
    assert first["package_code"]
    assert first.get("name"), "套餐名缺失，页面无法展示"


@pytest.mark.asyncio
async def test_subsidy_precheck_returns_deterministic_single_value(client: AsyncClient):
    """补贴预检必须给确定性单值：小程序据此只展示一个数，不渲染假区间。"""
    token = await _register(client, "13900003004")
    headers = _headers(token)
    packages = (
        await client.get("/api/partial-renovation/quick-install/packages", headers=headers)
    ).json()
    code = packages[0]["package_code"]

    resp = await client.post(
        "/api/elderly-adaptation/subsidy-precheck",
        json={"package_code": code},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    for key in ("total_subsidy", "net_payable", "subsidy_rate", "disclaimer"):
        assert key in data, f"适配层读取的 {key} 缺失"

    # 单值：不得出现 min/max 区间字段，否则前端可能被诱导渲染区间
    assert isinstance(data["total_subsidy"], (int, float))
    assert data["total_subsidy"] >= 0
    assert data["net_payable"] <= data["total_price"] + 0.01


@pytest.mark.asyncio
async def test_smart_home_and_scene_endpoints_reachable(client: AsyncClient):
    """智控页对新项目必须返回空集而不是 404（否则整页降级为演示数据）。"""
    token = await _register(client, "13900003005")
    project_id, _ = await _seed_project_and_asset(client, token)
    headers = _headers(token)

    schemes = await client.get(f"/api/smart-home/schemes/project/{project_id}", headers=headers)
    assert schemes.status_code == 200, schemes.text
    assert isinstance(schemes.json(), list)

    scenes = await client.get(f"/api/scene-automation/scenes/project/{project_id}", headers=headers)
    assert scenes.status_code == 200, scenes.text
    assert isinstance(scenes.json(), list)

    health = await client.get(f"/api/health-monitor/records/project/{project_id}", headers=headers)
    assert health.status_code == 200, health.text
    assert isinstance(health.json(), list)


@pytest.mark.asyncio
async def test_read_endpoints_require_auth(client: AsyncClient):
    """只读接口也要求登录：小程序未登录时必须走「演示数据」标识，而不是拿到他人数据。"""
    for path in ("/api/space-assets", "/api/projects"):
        resp = await client.get(path)
        assert resp.status_code == 401, f"{path} 未鉴权，存在越权风险"
