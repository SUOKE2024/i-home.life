"""F29/F30 灯光设计器 + F16 厨房设计器 + F17 卫生间设计器 测试"""

import pytest
from httpx import AsyncClient

# 导入模型以注册到 Base.metadata (确保 create_all 创建表)
from app.models.lighting import LightingScheme, LightingFixture  # noqa: F401
from app.models.kitchen import KitchenDesign, KitchenComponent  # noqa: F401
from app.models.bathroom import BathroomDesign, BathroomFixture  # noqa: F401

# 注册路由 (主代理后续会集成到 main.py，这里仅测试用)
# 需要将路由插入到 StaticFiles 挂载之前，否则静态文件会拦截请求
from app.main import app
from app.api import lighting as lighting_api, kitchen as kitchen_api, bathroom as bathroom_api
from starlette.routing import Mount

_existing_paths = {getattr(r, "path", "") for r in app.routes}
_needs_lighting = not any("/lighting/schemes" in p for p in _existing_paths)
_needs_kitchen = not any("/kitchen/designs" in p for p in _existing_paths)
_needs_bathroom = not any("/bathroom/designs" in p for p in _existing_paths)

if _needs_lighting or _needs_kitchen or _needs_bathroom:
    # 临时移除 StaticFiles 挂载 (最后一个路由)
    _static_mounts = []
    while app.routes and isinstance(app.routes[-1], Mount):
        _static_mounts.append(app.routes.pop())

    if _needs_lighting:
        app.include_router(lighting_api.router, prefix="/api")
    if _needs_kitchen:
        app.include_router(kitchen_api.router, prefix="/api")
    if _needs_bathroom:
        app.include_router(bathroom_api.router, prefix="/api")

    # 重新挂载 StaticFiles
    for mount in reversed(_static_mounts):
        app.routes.append(mount)


async def _register_and_login(client: AsyncClient, phone: str = "13900007001") -> tuple[str, dict]:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "垂直设计器测试用户", "password": "test123456"},
    )
    token = resp.json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "垂直设计器测试项目") -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": name, "total_area": 120.0},
        headers=headers,
    )
    return resp.json()["id"]


# ── F29/F30 灯光设计器 ──

@pytest.mark.asyncio
async def test_lighting_scheme_crud(client: AsyncClient):
    """灯光方案 CRUD"""
    token, headers = await _register_and_login(client, "13900007001")
    project_id = await _create_project(client, headers, "灯光测试")

    # 创建
    resp = await client.post(
        "/api/lighting/schemes",
        json={
            "project_id": project_id,
            "room_name": "客厅",
            "scheme_type": "none_main",
            "room_area": 20.0,
            "ceiling_height": 2.8,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    scheme = resp.json()
    scheme_id = scheme["id"]
    assert scheme["room_name"] == "客厅"
    assert scheme["scheme_type"] == "none_main"
    assert scheme["room_area"] == 20.0

    # 列表
    resp = await client.get(f"/api/lighting/schemes/project/{project_id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # 详情
    resp = await client.get(f"/api/lighting/schemes/{scheme_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == scheme_id

    # 删除
    resp = await client.delete(f"/api/lighting/schemes/{scheme_id}", headers=headers)
    assert resp.status_code == 204

    # 确认已删除
    resp = await client.get(f"/api/lighting/schemes/{scheme_id}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_lighting_ai_design(client: AsyncClient):
    """AI 灯光方案设计"""
    token, headers = await _register_and_login(client, "13900007002")
    project_id = await _create_project(client, headers, "AI 灯光测试")

    # 创建方案
    resp = await client.post(
        "/api/lighting/schemes",
        json={
            "project_id": project_id,
            "room_name": "主卧",
            "scheme_type": "main_light",
            "room_area": 15.0,
            "ceiling_height": 2.8,
        },
        headers=headers,
    )
    scheme_id = resp.json()["id"]

    # AI 设计
    resp = await client.post(
        f"/api/lighting/schemes/{scheme_id}/ai-design",
        json={"room_type": "bedroom", "style": "warm"},
        headers=headers,
    )
    assert resp.status_code == 200
    result = resp.json()
    # 卧室推荐无主灯
    assert result["scheme_type"] == "none_main"
    # 卧室色温 2700K
    assert result["color_temp_k"] == 2700
    assert result["cri"] == 90.0
    assert result["total_lumens"] > 0
    assert result["total_power_w"] > 0

    # 验证灯具已创建
    resp = await client.get(f"/api/lighting/schemes/{scheme_id}/fixtures", headers=headers)
    assert resp.status_code == 200
    fixtures = resp.json()
    assert len(fixtures) > 0
    # 应该有筒灯/射灯/灯带
    fixture_types = {f["fixture_type"] for f in fixtures}
    assert "spot" in fixture_types or "strip" in fixture_types


@pytest.mark.asyncio
async def test_lighting_illuminance(client: AsyncClient):
    """照度计算"""
    token, headers = await _register_and_login(client, "13900007003")
    project_id = await _create_project(client, headers, "照度测试")

    # 创建方案
    resp = await client.post(
        "/api/lighting/schemes",
        json={
            "project_id": project_id,
            "room_name": "书房",
            "scheme_type": "main_light",
            "room_area": 12.0,
            "ceiling_height": 2.8,
        },
        headers=headers,
    )
    scheme_id = resp.json()["id"]

    # 添加灯具
    resp = await client.post(
        f"/api/lighting/schemes/{scheme_id}/fixtures",
        json={
            "scheme_id": scheme_id,
            "fixture_type": "panel",
            "brand": "欧普",
            "wattage_w": 48.0,
            "lumens": 3840.0,
            "color_temp_k": 5000,
            "quantity": 2,
            "dimmable": True,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    fixture_id = resp.json()["id"]

    # 照度计算
    resp = await client.get(f"/api/lighting/schemes/{scheme_id}/illuminance", headers=headers)
    assert resp.status_code == 200
    result = resp.json()
    # 总光通量 = 3840 × 2 = 7680
    assert result["total_lumens"] == 7680.0
    # 照度 = 7680 × 0.7 × 0.8 / 12 = 358.4
    assert result["illuminance"] > 0
    assert result["rating"] in ("optimal", "bright", "excessive", "low", "insufficient")

    # 删除灯具
    resp = await client.delete(f"/api/lighting/fixtures/{fixture_id}", headers=headers)
    assert resp.status_code == 204

    # 确认已删除
    resp = await client.get(f"/api/lighting/schemes/{scheme_id}/fixtures", headers=headers)
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_lighting_color_temp_planning():
    """色温规划 (直接测试服务层)"""
    from app.services.lighting_service import plan_color_temp

    # 客厅 3000K
    result = plan_color_temp("none_main", "living_room")
    assert result["color_temp_k"] == 3000
    assert "客厅" in result["description"]

    # 厨房 4000K
    result = plan_color_temp("main_light", "kitchen")
    assert result["color_temp_k"] == 4000

    # 卧室 2700K
    result = plan_color_temp("none_main", "bedroom")
    assert result["color_temp_k"] == 2700

    # 书房 5000K
    result = plan_color_temp("main_light", "study")
    assert result["color_temp_k"] == 5000


# ── F16 厨房设计器 ──

@pytest.mark.asyncio
async def test_kitchen_design_crud(client: AsyncClient):
    """厨房设计 CRUD"""
    token, headers = await _register_and_login(client, "13900007004")
    project_id = await _create_project(client, headers, "厨房测试")

    # 创建
    resp = await client.post(
        "/api/kitchen/designs",
        json={
            "project_id": project_id,
            "room_name": "厨房",
            "layout_type": "L",
            "room_width": 3.0,
            "room_length": 3.0,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    design = resp.json()
    design_id = design["id"]
    assert design["layout_type"] == "L"
    assert design["counter_height"] == 850.0
    assert design["counter_depth"] == 600.0

    # 列表
    resp = await client.get(f"/api/kitchen/designs/project/{project_id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # 详情
    resp = await client.get(f"/api/kitchen/designs/{design_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == design_id

    # 删除
    resp = await client.delete(f"/api/kitchen/designs/{design_id}", headers=headers)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_kitchen_auto_layout(client: AsyncClient):
    """厨房自动布局"""
    token, headers = await _register_and_login(client, "13900007005")
    project_id = await _create_project(client, headers, "厨房布局测试")

    # 创建设计
    resp = await client.post(
        "/api/kitchen/designs",
        json={
            "project_id": project_id,
            "room_name": "厨房",
            "layout_type": "I",
            "room_width": 3.5,
            "room_length": 2.5,
        },
        headers=headers,
    )
    design_id = resp.json()["id"]

    # 自动布局
    resp = await client.post(f"/api/kitchen/designs/{design_id}/auto-layout", headers=headers)
    assert resp.status_code == 200
    result = resp.json()
    assert result["layout_type"] == "I"
    assert result["total"] > 0
    # 应包含冰箱、水槽、灶台等关键设备
    comp_types = {c["component_type"] for c in result["components"]}
    assert "fridge" in comp_types
    assert "sink" in comp_types
    assert "stove" in comp_types
    assert "range_hood" in comp_types

    # 验证组件已保存
    resp = await client.get(f"/api/kitchen/designs/{design_id}/components", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == result["total"]


@pytest.mark.asyncio
async def test_kitchen_workflow_analysis(client: AsyncClient):
    """厨房动线分析"""
    token, headers = await _register_and_login(client, "13900007006")
    project_id = await _create_project(client, headers, "厨房动线测试")

    # 创建设计并自动布局
    resp = await client.post(
        "/api/kitchen/designs",
        json={
            "project_id": project_id,
            "room_name": "厨房",
            "layout_type": "L",
            "room_width": 3.0,
            "room_length": 3.0,
        },
        headers=headers,
    )
    design_id = resp.json()["id"]

    await client.post(f"/api/kitchen/designs/{design_id}/auto-layout", headers=headers)

    # 动线分析
    resp = await client.get(f"/api/kitchen/designs/{design_id}/workflow", headers=headers)
    assert resp.status_code == 200
    result = resp.json()
    assert result["status"] == "complete"
    assert "fridge_to_sink" in result["distances"]
    assert "sink_to_stove" in result["distances"]
    assert "stove_to_fridge" in result["distances"]
    assert result["total_distance"] > 0
    assert result["rating"] in ("optimal", "too_compact", "too_spread")


@pytest.mark.asyncio
async def test_kitchen_compliance_valid(client: AsyncClient):
    """厨房规范校验 - 合规用例"""
    token, headers = await _register_and_login(client, "13900007007")
    project_id = await _create_project(client, headers, "厨房合规测试")

    # 创建设计并自动布局
    resp = await client.post(
        "/api/kitchen/designs",
        json={
            "project_id": project_id,
            "room_name": "厨房",
            "layout_type": "I",
            "room_width": 4.0,
            "room_length": 3.0,
        },
        headers=headers,
    )
    design_id = resp.json()["id"]

    await client.post(f"/api/kitchen/designs/{design_id}/auto-layout", headers=headers)

    # 规范校验
    resp = await client.get(f"/api/kitchen/designs/{design_id}/compliance", headers=headers)
    assert resp.status_code == 200
    result = resp.json()
    assert "compliant" in result
    assert "checks" in result
    assert result["total_checks"] == 6
    # 检查所有校验项都有 passed 字段
    for check in result["checks"]:
        assert "item" in check
        assert "passed" in check


@pytest.mark.asyncio
async def test_kitchen_compliance_non_compliant(client: AsyncClient):
    """厨房规范校验 - 不合规用例 (灶台距水槽过近)"""
    token, headers = await _register_and_login(client, "13900007008")
    project_id = await _create_project(client, headers, "厨房不合规测试")

    # 创建设计
    resp = await client.post(
        "/api/kitchen/designs",
        json={
            "project_id": project_id,
            "room_name": "厨房",
            "layout_type": "I",
            "room_width": 4.0,
            "room_length": 3.0,
        },
        headers=headers,
    )
    design_id = resp.json()["id"]

    # 手动添加组件 - 灶台距水槽过近 (违反 ≥ 600mm 规范)
    # 水槽在 x=600, 灶台在 x=620 (几乎重叠)
    await client.post(
        f"/api/kitchen/designs/{design_id}/components",
        json={
            "design_id": design_id,
            "component_type": "fridge",
            "width": 600, "depth": 600, "height": 1800,
            "position_x": 0, "position_y": 0, "position_z": 0,
        },
        headers=headers,
    )
    await client.post(
        f"/api/kitchen/designs/{design_id}/components",
        json={
            "design_id": design_id,
            "component_type": "sink",
            "width": 760, "depth": 450, "height": 200,
            "position_x": 600, "position_y": 0, "position_z": 850,
        },
        headers=headers,
    )
    await client.post(
        f"/api/kitchen/designs/{design_id}/components",
        json={
            "design_id": design_id,
            "component_type": "stove",
            "width": 720, "depth": 420, "height": 50,
            "position_x": 620, "position_y": 0, "position_z": 850,
        },
        headers=headers,
    )
    # 抽油烟机距灶台过近 (违反 650-750mm 规范)
    await client.post(
        f"/api/kitchen/designs/{design_id}/components",
        json={
            "design_id": design_id,
            "component_type": "range_hood",
            "width": 900, "depth": 520, "height": 700,
            "position_x": 530, "position_y": 0, "position_z": 1400,
        },
        headers=headers,
    )

    # 规范校验 - 应不合规
    resp = await client.get(f"/api/kitchen/designs/{design_id}/compliance", headers=headers)
    assert resp.status_code == 200
    result = resp.json()
    assert result["compliant"] is False
    # 至少有一项不通过
    failed_checks = [c for c in result["checks"] if not c["passed"]]
    assert len(failed_checks) > 0


# ── F17 卫生间设计器 ──

@pytest.mark.asyncio
async def test_bathroom_design_crud(client: AsyncClient):
    """卫生间设计 CRUD"""
    token, headers = await _register_and_login(client, "13900007009")
    project_id = await _create_project(client, headers, "卫生间测试")

    # 创建
    resp = await client.post(
        "/api/bathroom/designs",
        json={
            "project_id": project_id,
            "room_name": "主卫",
            "layout_type": "dry_wet_separation",
            "room_width": 2.0,
            "room_length": 3.0,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    design = resp.json()
    design_id = design["id"]
    assert design["layout_type"] == "dry_wet_separation"
    assert design["waterproof_height_mm"] == 1800
    assert design["drain_slope_percent"] == 1.5

    # 列表
    resp = await client.get(f"/api/bathroom/designs/project/{project_id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # 详情
    resp = await client.get(f"/api/bathroom/designs/{design_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == design_id

    # 删除
    resp = await client.delete(f"/api/bathroom/designs/{design_id}", headers=headers)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_bathroom_auto_layout(client: AsyncClient):
    """卫生间自动布局"""
    token, headers = await _register_and_login(client, "13900007010")
    project_id = await _create_project(client, headers, "卫生间布局测试")

    # 创建设计
    resp = await client.post(
        "/api/bathroom/designs",
        json={
            "project_id": project_id,
            "room_name": "客卫",
            "layout_type": "dry_wet_separation",
            "room_width": 2.5,
            "room_length": 3.0,
        },
        headers=headers,
    )
    design_id = resp.json()["id"]

    # 自动布局
    resp = await client.post(f"/api/bathroom/designs/{design_id}/auto-layout", headers=headers)
    assert resp.status_code == 200
    result = resp.json()
    assert result["layout_type"] == "dry_wet_separation"
    assert result["total"] > 0
    # 应包含马桶、洗手盆、淋浴等
    fixture_types = {f["fixture_type"] for f in result["fixtures"]}
    assert "toilet" in fixture_types
    assert "basin" in fixture_types
    assert "shower" in fixture_types

    # 验证设备已保存
    resp = await client.get(f"/api/bathroom/designs/{design_id}/fixtures", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == result["total"]


@pytest.mark.asyncio
async def test_bathroom_drain_slope(client: AsyncClient):
    """地漏坡度计算"""
    token, headers = await _register_and_login(client, "13900007011")
    project_id = await _create_project(client, headers, "地漏坡度测试")

    # 创建设计 - 默认坡度 1.5%
    resp = await client.post(
        "/api/bathroom/designs",
        json={
            "project_id": project_id,
            "room_name": "卫生间",
            "layout_type": "dry_wet_separation",
            "room_width": 2.0,
            "room_length": 3.0,
        },
        headers=headers,
    )
    design_id = resp.json()["id"]

    # 地漏坡度计算
    resp = await client.get(f"/api/bathroom/designs/{design_id}/drain", headers=headers)
    assert resp.status_code == 200
    result = resp.json()
    assert result["slope_percent"] == 1.5
    assert result["distance"] > 0
    assert result["height_diff_mm"] > 0
    assert result["recommended_range"] == [1.0, 2.0]
    # 1.5% 在推荐范围内
    assert result["rating"] == "optimal"


@pytest.mark.asyncio
async def test_bathroom_waterproof(client: AsyncClient):
    """防水规范校验"""
    token, headers = await _register_and_login(client, "13900007012")
    project_id = await _create_project(client, headers, "防水校验测试")

    # 创建设计 - 默认防水高度 1800mm (合规)
    resp = await client.post(
        "/api/bathroom/designs",
        json={
            "project_id": project_id,
            "room_name": "卫生间",
            "layout_type": "dry_wet_separation",
            "room_width": 2.0,
            "room_length": 3.0,
            "waterproof_height_mm": 1800,
        },
        headers=headers,
    )
    design_id = resp.json()["id"]

    # 防水校验
    resp = await client.get(f"/api/bathroom/designs/{design_id}/waterproof", headers=headers)
    assert resp.status_code == 200
    result = resp.json()
    assert result["compliant"] is True
    assert result["waterproof_height_mm"] == 1800
    assert result["total_checks"] > 0
    # 所有项通过
    assert result["passed_checks"] == result["total_checks"]

    # 测试不合规情况 - 防水高度不足
    resp2 = await client.post(
        "/api/bathroom/designs",
        json={
            "project_id": project_id,
            "room_name": "卫生间2",
            "layout_type": "traditional",
            "room_width": 2.0,
            "room_length": 3.0,
            "waterproof_height_mm": 1500,  # 不足 1.8m
        },
        headers=headers,
    )
    design_id2 = resp2.json()["id"]

    resp2 = await client.get(f"/api/bathroom/designs/{design_id2}/waterproof", headers=headers)
    assert resp2.status_code == 200
    result2 = resp2.json()
    assert result2["compliant"] is False


@pytest.mark.asyncio
async def test_bathroom_ventilation(client: AsyncClient):
    """通风分析"""
    token, headers = await _register_and_login(client, "13900007013")
    project_id = await _create_project(client, headers, "通风分析测试")

    # 创建设计
    resp = await client.post(
        "/api/bathroom/designs",
        json={
            "project_id": project_id,
            "room_name": "卫生间",
            "layout_type": "dry_wet_separation",
            "room_width": 2.0,
            "room_length": 3.0,
            "ceiling_height": 2.6,
            # v1.2.2：FP-2 通风真校验需显式声明窗户与机械通风参数
            # （create schema 已补齐这些字段）。0.54 m² > 0.3 m² 必要面积 → 自然通风合规
            "has_natural_window": True,
            "window_area_m2": 0.54,
            "mechanical_vent_airflow": 80.0,
        },
        headers=headers,
    )
    design_id = resp.json()["id"]

    # 通风分析
    resp = await client.get(f"/api/bathroom/designs/{design_id}/ventilation", headers=headers)
    assert resp.status_code == 200
    result = resp.json()
    assert result["floor_area"] == 6.0  # 2.0 × 3.0
    assert "natural_ventilation" in result
    assert "mechanical_ventilation" in result
    # 自然通风要求面积 = 6.0 / 20 = 0.3 m²
    assert result["natural_ventilation"]["required_area"] == 0.3
    # 假设窗户面积 0.54 m² > 0.3，应合规
    assert result["natural_ventilation"]["compliant"] is True
    # 机械通风 ≥ 80 m³/h
    assert result["mechanical_ventilation"]["required_airflow"] == 80.0
    assert result["mechanical_ventilation"]["compliant"] is True
    # 综合评级
    assert result["rating"] == "good"
