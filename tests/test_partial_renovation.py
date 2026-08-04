"""F42 局部焕新 API 集成测试

覆盖端点:
- POST   /api/partial-renovation/plans                        (按模板创建计划)
- GET    /api/partial-renovation/plans/project/{project_id}   (按项目列计划)
- GET    /api/partial-renovation/plans/{plan_id}              (计划详情)
- GET    /api/partial-renovation/templates                    (模板列表)
- DELETE /api/partial-renovation/plans/{plan_id}              (删除计划)
"""
import pytest
from httpx import AsyncClient

ALL_SCOPE_TYPES = ["kitchen_refresh", "bathroom_refresh", "wall_refresh",
                   "single_room", "full_renovation"]

ALL_PACKAGE_CODES = ["PKG-48H-KITCHEN", "PKG-48H-BATHROOM", "PKG-7D-WALL"]


async def _auth_headers(client: AsyncClient, phone: str = "13960010001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "局部焕新测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "局部焕新测试项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 100.0}, headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_plan(
    client: AsyncClient, headers: dict, project_id: str,
    scope_type: str = "kitchen_refresh", budget_level: str = "comfort",
) -> dict:
    resp = await client.post(
        "/api/partial-renovation/plans",
        json={"project_id": project_id, "name": "局部焕新计划", "scope_type": scope_type,
              "budget_level": budget_level},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()


# ── Auth ──


@pytest.mark.asyncio
async def test_partial_renovation_unauthorized(client: AsyncClient):
    """未认证用户不能创建局部焕新计划"""
    resp = await client.post(
        "/api/partial-renovation/plans",
        json={"project_id": "fake", "name": "计划", "scope_type": "kitchen_refresh"},
    )
    assert resp.status_code == 401


# ── 模板列表 ──


@pytest.mark.asyncio
async def test_list_templates_contains_all_scope_types(client: AsyncClient):
    """模板列表包含全部 5 种 scope_type 及其摘要字段"""
    headers = await _auth_headers(client, "13960010002")

    resp = await client.get("/api/partial-renovation/templates", headers=headers)
    assert resp.status_code == 200
    templates = resp.json()
    scope_types = [t["scope_type"] for t in templates]
    assert set(scope_types) == set(ALL_SCOPE_TYPES)
    for t in templates:
        assert "name" in t and "duration_days" in t and "task_count" in t
        assert "budget_range" in t and set(t["budget_range"]) == {"economic", "comfort", "quality"}
        assert t["task_count"] >= 1


# ── 计划 CRUD ──


@pytest.mark.asyncio
async def test_create_and_get_plan_from_template(client: AsyncClient):
    """按 kitchen_refresh 舒适档模板创建计划，duration/budget 与模板一致"""
    headers = await _auth_headers(client, "13960010003")
    project_id = await _create_project(client, headers)

    created = await _create_plan(client, headers, project_id, "kitchen_refresh", "comfort")
    assert created["scope_type"] == "kitchen_refresh"
    assert created["budget_level"] == "comfort"
    assert created["duration_days"] == 7
    assert created["budget_lower"] == 1.5
    assert created["budget_upper"] == 4.0
    assert created["status"] == "draft"
    # 模板任务与干扰方案已填充
    assert isinstance(created["tasks"], list) and len(created["tasks"]) > 0
    assert isinstance(created["interference_plan"], dict)
    assert "noise_windows" in created["interference_plan"]

    resp = await client.get(f"/api/partial-renovation/plans/{created['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "局部焕新计划"


@pytest.mark.asyncio
async def test_create_plan_budget_level_and_scope_variants(client: AsyncClient):
    """不同 scope_type/budget_level 的组合按模板正确落库"""
    headers = await _auth_headers(client, "13960010004")
    project_id = await _create_project(client, headers)

    # wall_refresh 经济档: 3-5 天, 0.3-1.0 万
    wall = await _create_plan(client, headers, project_id, "wall_refresh", "economic")
    assert wall["duration_days"] == 5
    assert wall["budget_lower"] == 0.3
    assert wall["budget_upper"] == 1.0

    # full_renovation 舒适档: 60-90 天, 12-20 万
    full = await _create_plan(client, headers, project_id, "full_renovation", "comfort")
    assert full["duration_days"] == 90
    assert full["budget_lower"] == 12.0
    assert full["budget_upper"] == 20.0


@pytest.mark.asyncio
async def test_create_plan_invalid_scope_type(client: AsyncClient):
    """未知 scope_type 返回 400"""
    headers = await _auth_headers(client, "13960010005")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/partial-renovation/plans",
        json={"project_id": project_id, "name": "计划", "scope_type": "unknown_type"},
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_plans_by_project(client: AsyncClient):
    """按项目列出局部焕新计划"""
    headers = await _auth_headers(client, "13960010006")
    project_id = await _create_project(client, headers)

    await _create_plan(client, headers, project_id, "kitchen_refresh")
    await _create_plan(client, headers, project_id, "wall_refresh", "economic")

    resp = await client.get(f"/api/partial-renovation/plans/project/{project_id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_delete_plan(client: AsyncClient):
    """删除局部焕新计划"""
    headers = await _auth_headers(client, "13960010007")
    project_id = await _create_project(client, headers)
    created = await _create_plan(client, headers, project_id, "kitchen_refresh")

    resp = await client.delete(f"/api/partial-renovation/plans/{created['id']}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/partial-renovation/plans/{created['id']}", headers=headers)
    assert resp.status_code == 404


# ── 越权校验 ──


@pytest.mark.asyncio
async def test_partial_renovation_cross_user_access_blocked(client: AsyncClient):
    """用户不能访问他人的局部焕新计划"""
    headers_a = await _auth_headers(client, "13960010008")
    headers_b = await _auth_headers(client, "13960010009")
    project_id_a = await _create_project(client, headers_a)
    plan_a = await _create_plan(client, headers_a, project_id_a, "kitchen_refresh")

    resp = await client.get(
        f"/api/partial-renovation/plans/{plan_a['id']}",
        headers=headers_b,
    )
    assert resp.status_code == 403


# ── F49 局改快装产品化：标准化套餐（一口价 + 干法施工 + 0 搬家） ──


@pytest.mark.asyncio
async def test_quick_install_packages_list(client: AsyncClient):
    """标准快装套餐目录含 3 个套餐，均一口价 + 干法 + 0 搬家"""
    headers = await _auth_headers(client, "13960010010")
    resp = await client.get("/api/partial-renovation/quick-install/packages", headers=headers)
    assert resp.status_code == 200
    packages = resp.json()
    codes = [p["package_code"] for p in packages]
    assert set(codes) == set(ALL_PACKAGE_CODES)
    for p in packages:
        assert p["fixed_price"] > 0
        assert p["dry_construction"] is True
        assert p["zero_relocation"] is True
        assert p["duration_hours"] > 0
        assert isinstance(p["inclusions"], list) and len(p["inclusions"]) >= 1


@pytest.mark.asyncio
async def test_quick_install_package_detail(client: AsyncClient):
    """单个套餐详情：48h 厨房一口价 19800、7 天墙面 6800"""
    headers = await _auth_headers(client, "13960010011")
    resp = await client.get(
        "/api/partial-renovation/quick-install/packages/PKG-48H-KITCHEN", headers=headers
    )
    assert resp.status_code == 200
    pkg = resp.json()
    assert pkg["package_code"] == "PKG-48H-KITCHEN"
    assert pkg["name"] == "48h 厨房快装"
    assert pkg["duration_hours"] == 48
    assert pkg["fixed_price"] == 19800.0
    assert "warranty" in pkg and "excludes" in pkg

    resp = await client.get(
        "/api/partial-renovation/quick-install/packages/PKG-7D-WALL", headers=headers
    )
    assert resp.json()["fixed_price"] == 6800.0


@pytest.mark.asyncio
async def test_quick_install_package_not_found(client: AsyncClient):
    """未知套餐编码 → 404"""
    headers = await _auth_headers(client, "13960010012")
    resp = await client.get(
        "/api/partial-renovation/quick-install/packages/PKG-UNKNOWN", headers=headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_instantiate_quick_install_plan(client: AsyncClient):
    """实例化 48h 厨房套餐 → 计划落库（一口价/干法/0 搬家/package_code）"""
    headers = await _auth_headers(client, "13960010013")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/partial-renovation/quick-install/plans",
        json={"project_id": project_id, "package_code": "PKG-48H-KITCHEN"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    plan = resp.json()
    assert plan["package_code"] == "PKG-48H-KITCHEN"
    assert plan["fixed_price"] == 19800.0
    assert plan["dry_construction"] is True
    assert plan["zero_relocation"] is True
    assert plan["duration_days"] == 2
    assert plan["budget_lower"] == plan["budget_upper"] == 19800.0
    assert plan["scope_type"] == "kitchen_refresh"
    assert plan["status"] == "draft"

    # 入库后可读回（持久化）
    resp = await client.get(
        f"/api/partial-renovation/plans/{plan['id']}", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["package_code"] == "PKG-48H-KITCHEN"


@pytest.mark.asyncio
async def test_instantiate_quick_install_invalid_code(client: AsyncClient):
    """非法套餐编码 → 400"""
    headers = await _auth_headers(client, "13960010014")
    project_id = await _create_project(client, headers)
    resp = await client.post(
        "/api/partial-renovation/quick-install/plans",
        json={"project_id": project_id, "package_code": "PKG-UNKNOWN"},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "未知快装套餐" in resp.json()["detail"]
