"""F18 厨卫水电 + F21 硬装模块 + F23 门窗/防水工程 测试

注意: 主代理负责在 app/main.py 中注册路由。
为保证测试可独立运行,此处将新路由与模型在本模块加载时挂载到 app 上。
"""

# ── 先导入模型,确保 Base.metadata 包含新表 ──
from app.models.kitchen_bath_mep import KitchenBathMEPPlan, MEPPoint  # noqa: F401
from app.models.hard_decoration import (  # noqa: F401
    HardDecorationScheme,
    HardDecorationFloor,
    WallFinish,
    CeilingDesign,
)
from app.models.door_window_waterproof import DoorWindowSpec, WaterproofPlan  # noqa: F401

# ── 注册路由到 app(若尚未注册) ──
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from app.main import app
from app.api import kitchen_bath_mep as mep_kb_api
from app.api import hard_decoration as hd_api
from app.api import door_window_waterproof as dww_api


def _ensure_routers_registered() -> None:
    _paths = {getattr(r, "path", "") for r in app.routes}
    prefixes = {
        "mep_kb": "/api/mep-kb",
        "hard_decoration": "/api/hard-decoration",
        "door_window_waterproof": "/api/door-window-waterproof",
    }
    already = {
        "mep_kb": any(p.startswith(prefixes["mep_kb"]) for p in _paths),
        "hard_decoration": any(p.startswith(prefixes["hard_decoration"]) for p in _paths),
        "door_window_waterproof": any(p.startswith(prefixes["door_window_waterproof"]) for p in _paths),
    }
    if all(already.values()):
        return
    # 找到根路径的 StaticFiles 挂载,临时移除,避免拦截新路由
    static_idx = None
    for i, r in enumerate(app.routes):
        if isinstance(r, Mount) and r.path in ("", "/") and isinstance(getattr(r, "app", None), StaticFiles):
            static_idx = i
            break
    static_mount = app.routes.pop(static_idx) if static_idx is not None else None
    if not already["mep_kb"]:
        app.include_router(mep_kb_api.router, prefix="/api")
    if not already["hard_decoration"]:
        app.include_router(hd_api.router, prefix="/api")
    if not already["door_window_waterproof"]:
        app.include_router(dww_api.router, prefix="/api")
    # 将静态挂载重新放回末尾,保持原有行为
    if static_mount is not None:
        app.routes.append(static_mount)


_ensure_routers_registered()


import pytest  # noqa: E402
from httpx import AsyncClient  # noqa: E402


async def _register_and_login(client: AsyncClient, phone: str, name: str) -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": name, "password": "test123456"},
    )
    return resp.json()["access_token"]


async def _create_project(client: AsyncClient, token: str, name: str) -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": name, "address": "测试地址"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp.json()["id"]


# ════════════════════════════════════════════════════════════════
# F18 厨卫水电
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_mep_kb_create_and_get_plan(client: AsyncClient):
    """厨卫水电 CRUD"""
    token = await _register_and_login(client, "13900300001", "厨卫水电CRUD")
    project_id = await _create_project(client, token, "厨卫水电项目1")

    resp = await client.post(
        "/api/mep-kb/plans",
        json={
            "project_id": project_id,
            "room_name": "厨房",
            "room_type": "kitchen",
            "water_heater_type": "gas",
            "water_heater_capacity_l": 16,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["room_name"] == "厨房"
    assert data["room_type"] == "kitchen"
    assert data["water_heater_type"] == "gas"
    plan_id = data["id"]

    # 查询单个
    get_resp = await client.get(f"/api/mep-kb/plans/{plan_id}", headers={"Authorization": f"Bearer {token}"})
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == plan_id

    # 列表
    list_resp = await client.get(
        f"/api/mep-kb/plans/project/{project_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


@pytest.mark.asyncio
async def test_mep_kb_auto_generate(client: AsyncClient):
    """厨卫水电自动生成水电点位"""
    token = await _register_and_login(client, "13900300002", "自动生成")
    project_id = await _create_project(client, token, "自动生成项目")
    create = await client.post(
        "/api/mep-kb/plans",
        json={
            "project_id": project_id,
            "room_name": "厨房",
            "room_type": "kitchen",
            "water_heater_type": "gas",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    plan_id = create.json()["id"]

    resp = await client.post(
        f"/api/mep-kb/plans/{plan_id}/auto-generate",
        json={"devices": ["热水器", "洗碗机", "净水器", "智能马桶", "洗衣机"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # 热水器(2进水+1燃气) + 洗碗机(1进水+1排水) + 净水器(1进水+1排水) + 智能马桶(1进水) + 洗衣机(1进水+1排水)
    # = 6 进水 + 3 排水 = 9 点位
    assert data["total"] >= 6
    assert len(data["water_inlets"]) >= 5
    assert len(data["drains"]) >= 2

    # 点位已写入
    points = await client.get(f"/api/mep-kb/plans/{plan_id}/points", headers={"Authorization": f"Bearer {token}"})
    assert points.status_code == 200
    assert len(points.json()) == data["total"]


@pytest.mark.asyncio
async def test_mep_kb_circuits(client: AsyncClient):
    """厨房回路设计"""
    token = await _register_and_login(client, "13900300003", "回路设计")
    project_id = await _create_project(client, token, "回路项目")
    create = await client.post(
        "/api/mep-kb/plans",
        json={"project_id": project_id, "room_name": "厨房", "room_type": "kitchen"},
        headers={"Authorization": f"Bearer {token}"},
    )
    plan_id = create.json()["id"]

    resp = await client.get(
        f"/api/mep-kb/plans/{plan_id}/circuits",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_circuits"] >= 2  # 至少包含照明 + 普通插座
    assert "main_breaker_recommended" in data
    # 检查有大功率回路
    types = [c["type"] for c in data["circuits"]]
    assert "照明回路" in types
    assert "普通插座回路" in types


@pytest.mark.asyncio
async def test_mep_kb_equipotential_compliant(client: AsyncClient):
    """等电位校验 - 合规"""
    token = await _register_and_login(client, "13900300004", "等电位合规")
    project_id = await _create_project(client, token, "等电位项目1")
    create = await client.post(
        "/api/mep-kb/plans",
        json={
            "project_id": project_id,
            "room_name": "卫生间",
            "room_type": "bathroom",
            "equipotential_bonding": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    plan_id = create.json()["id"]
    resp = await client.get(
        f"/api/mep-kb/plans/{plan_id}/equipotential",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["compliant"] is True


@pytest.mark.asyncio
async def test_mep_kb_equipotential_non_compliant(client: AsyncClient):
    """等电位校验 - 不合规 (卫生间未做等电位)"""
    token = await _register_and_login(client, "13900300005", "等电位不合规")
    project_id = await _create_project(client, token, "等电位项目2")
    create = await client.post(
        "/api/mep-kb/plans",
        json={
            "project_id": project_id,
            "room_name": "卫生间",
            "room_type": "bathroom",
            "equipotential_bonding": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    plan_id = create.json()["id"]
    resp = await client.get(
        f"/api/mep-kb/plans/{plan_id}/equipotential",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["compliant"] is False


@pytest.mark.asyncio
async def test_mep_kb_gas_plan(client: AsyncClient):
    """燃气管道规划"""
    token = await _register_and_login(client, "13900300006", "燃气规划")
    project_id = await _create_project(client, token, "燃气项目")
    create = await client.post(
        "/api/mep-kb/plans",
        json={
            "project_id": project_id,
            "room_name": "厨房",
            "room_type": "kitchen",
            "water_heater_type": "gas",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    plan_id = create.json()["id"]
    resp = await client.get(
        f"/api/mep-kb/plans/{plan_id}/gas",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["needed"] is True
    assert len(data["outlets"]) >= 1
    # 灶台 + 热水器
    devices = [o["device"] for o in data["outlets"]]
    assert "燃气灶" in devices
    assert "燃气热水器" in devices


@pytest.mark.asyncio
async def test_mep_kb_add_and_delete_point(client: AsyncClient):
    """厨卫水电点位增删"""
    token = await _register_and_login(client, "13900300007", "点位增删")
    project_id = await _create_project(client, token, "点位项目")
    create = await client.post(
        "/api/mep-kb/plans",
        json={"project_id": project_id, "room_name": "厨房", "room_type": "kitchen"},
        headers={"Authorization": f"Bearer {token}"},
    )
    plan_id = create.json()["id"]

    add = await client.post(
        f"/api/mep-kb/plans/{plan_id}/points",
        json={
            "plan_id": plan_id,
            "point_type": "socket",
            "device": "油烟机",
            "position_x": 500,
            "position_y": 300,
            "position_z": 2100,
            "voltage": "220V",
            "power_w": 200,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert add.status_code == 201
    point_id = add.json()["id"]

    # 删除点位
    dele = await client.delete(
        f"/api/mep-kb/points/{point_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dele.status_code == 204


@pytest.mark.asyncio
async def test_mep_kb_delete_plan(client: AsyncClient):
    """删除厨卫水电方案"""
    token = await _register_and_login(client, "13900300008", "删除方案")
    project_id = await _create_project(client, token, "删除方案项目")
    create = await client.post(
        "/api/mep-kb/plans",
        json={"project_id": project_id, "room_name": "厨房", "room_type": "kitchen"},
        headers={"Authorization": f"Bearer {token}"},
    )
    plan_id = create.json()["id"]
    dele = await client.delete(
        f"/api/mep-kb/plans/{plan_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dele.status_code == 204
    get = await client.get(f"/api/mep-kb/plans/{plan_id}", headers={"Authorization": f"Bearer {token}"})
    assert get.status_code == 404


# ════════════════════════════════════════════════════════════════
# F21 硬装模块
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_hd_create_and_get_scheme(client: AsyncClient):
    """硬装模块 CRUD"""
    token = await _register_and_login(client, "13900300010", "硬装CRUD")
    project_id = await _create_project(client, token, "硬装项目1")
    resp = await client.post(
        "/api/hard-decoration/schemes",
        json={
            "project_id": project_id,
            "room_name": "客厅",
            "scheme_type": "floor",
            "floor_area": 25.0,
            "wall_area": 60.0,
            "ceiling_area": 25.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["room_name"] == "客厅"
    assert data["floor_area"] == 25.0
    scheme_id = data["id"]

    # 查询
    get = await client.get(f"/api/hard-decoration/schemes/{scheme_id}", headers={"Authorization": f"Bearer {token}"})
    assert get.status_code == 200
    assert get.json()["id"] == scheme_id

    # 列表
    lst = await client.get(
        f"/api/hard-decoration/schemes/project/{project_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert lst.status_code == 200
    assert len(lst.json()) == 1


@pytest.mark.parametrize(
    "pattern",
    ["直铺", "人字拼", "鱼骨拼", "工字铺", "菱形"],
)
@pytest.mark.asyncio
async def test_hd_tile_layout_patterns(client: AsyncClient, pattern: str):
    """瓷砖排版 - 5 种 pattern"""
    token = await _register_and_login(client, "13900300011", f"瓷砖{pattern}")
    project_id = await _create_project(client, token, f"瓷砖项目{pattern}")
    create = await client.post(
        "/api/hard-decoration/schemes",
        json={"project_id": project_id, "room_name": "客厅", "scheme_type": "floor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    scheme_id = create.json()["id"]

    resp = await client.post(
        f"/api/hard-decoration/schemes/{scheme_id}/tile-layout",
        json={
            "room_width": 5.0,
            "room_length": 6.0,
            "tile_width": 800,
            "tile_length": 800,
            "pattern": pattern,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["pattern"] == pattern
    assert data["full_tiles"] > 0
    assert data["final_total_tiles"] >= data["full_tiles"]
    assert data["material_area_m2"] > 0
    # 不同 pattern 损耗不同
    assert data["waste_percent"] >= 5.0


@pytest.mark.asyncio
async def test_hd_tile_layout_unit_compat(client: AsyncClient):
    """瓷砖排版 - 单位兼容：瓷砖尺寸误传 m 应自动换算为 mm

    回归测试：前端误传 tile_width=0.6 (m) 而非 600 (mm) 时，
    服务层应自动识别并换算，避免 full_tiles 异常膨胀到千万级。
    """
    token = await _register_and_login(client, "13900300021", "单位兼容")
    project_id = await _create_project(client, token, "单位兼容项目")
    create = await client.post(
        "/api/hard-decoration/schemes",
        json={"project_id": project_id, "room_name": "客厅", "scheme_type": "floor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    scheme_id = create.json()["id"]

    # 传 m 单位（0.6）应自动换算为 600 mm
    resp_m = await client.post(
        f"/api/hard-decoration/schemes/{scheme_id}/tile-layout",
        json={"room_width": 4.0, "room_length": 5.0, "tile_width": 0.6, "tile_length": 0.6, "pattern": "直铺"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_m.status_code == 200, resp_m.text
    data_m = resp_m.json()
    # 4m × 5m = 20㎡，0.6m × 0.6m = 0.36㎡，整砖数应在 50 块量级
    assert data_m["full_tiles"] < 100, f"瓷砖数异常: {data_m['full_tiles']}（应自动换算 m→mm）"
    assert data_m["tile_area_m2"] == 0.36, f"单砖面积应为 0.36㎡，实际: {data_m['tile_area_m2']}"

    # 传 mm 单位（600）应正常工作，结果与 m 单位一致
    resp_mm = await client.post(
        f"/api/hard-decoration/schemes/{scheme_id}/tile-layout",
        json={"room_width": 4.0, "room_length": 5.0, "tile_width": 600, "tile_length": 600, "pattern": "直铺"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_mm.status_code == 200
    data_mm = resp_mm.json()
    assert data_m["full_tiles"] == data_mm["full_tiles"], "m 单位与 mm 单位结果应一致"


@pytest.mark.asyncio
async def test_hd_scheme_create_accept_name_alias(client: AsyncClient):
    """硬装方案创建 - 支持传 name 作为 room_name 的别名

    回归测试：前端传 name 字段应被接受并映射到 room_name。
    """
    token = await _register_and_login(client, "13900300022", "别名测试")
    project_id = await _create_project(client, token, "别名项目")
    # 传 name 而非 room_name
    resp = await client.post(
        "/api/hard-decoration/schemes",
        json={"project_id": project_id, "name": "主卧", "scheme_type": "floor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["room_name"] == "主卧", f"name 别名未映射到 room_name，实际: {data['room_name']}"


@pytest.mark.asyncio
async def test_hd_paint_usage(client: AsyncClient):
    """涂料用量计算"""
    token = await _register_and_login(client, "13900300012", "涂料用量")
    project_id = await _create_project(client, token, "涂料项目")
    create = await client.post(
        "/api/hard-decoration/schemes",
        json={"project_id": project_id, "room_name": "卧室", "scheme_type": "wall", "wall_area": 50.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    scheme_id = create.json()["id"]
    resp = await client.post(
        f"/api/hard-decoration/schemes/{scheme_id}/paint-usage",
        json={"wall_area": 50.0, "coats": 2, "coverage_per_l": 9.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # 50 * 2 / 9 = 11.11 L, +5% = 11.67 L, 18L桶 = 1桶
    assert data["paint_liters"] > 0
    assert data["total_liters"] > data["paint_liters"]
    assert data["buckets_18l"] >= 1


@pytest.mark.asyncio
async def test_hd_ceiling_design(client: AsyncClient):
    """吊顶设计"""
    token = await _register_and_login(client, "13900300013", "吊顶设计")
    project_id = await _create_project(client, token, "吊顶项目")
    create = await client.post(
        "/api/hard-decoration/schemes",
        json={"project_id": project_id, "room_name": "客厅", "scheme_type": "ceiling"},
        headers={"Authorization": f"Bearer {token}"},
    )
    scheme_id = create.json()["id"]

    # 客厅吊顶
    resp = await client.post(
        f"/api/hard-decoration/schemes/{scheme_id}/ceiling-design",
        json={"room_type": "living", "height": 2.8},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ceiling_type"] == "gypsum_perimeter"
    assert data["light_strip"] is True
    assert data["height_drop_mm"] > 0

    # 卧室平顶
    resp2 = await client.post(
        f"/api/hard-decoration/schemes/{scheme_id}/ceiling-design",
        json={"room_type": "bedroom", "height": 2.8},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["ceiling_type"] == "flat"
    assert data2["light_strip"] is False


@pytest.mark.asyncio
async def test_hd_budget_summary(client: AsyncClient):
    """预算汇总"""
    token = await _register_and_login(client, "13900300014", "预算汇总")
    project_id = await _create_project(client, token, "预算项目")
    create = await client.post(
        "/api/hard-decoration/schemes",
        json={
            "project_id": project_id,
            "room_name": "客厅",
            "scheme_type": "floor",
            "floor_area": 25.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    scheme_id = create.json()["id"]

    # 添加地面方案
    await client.post(
        f"/api/hard-decoration/schemes/{scheme_id}/floors",
        json={
            "scheme_id": scheme_id,
            "material_type": "tile",
            "material_spec": "800×800 抛釉砖",
            "pattern": "直铺",
            "coverage_area": 25.0,
            "unit_price": 128.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    # 添加墙面方案
    await client.post(
        f"/api/hard-decoration/schemes/{scheme_id}/walls",
        json={
            "scheme_id": scheme_id,
            "finish_type": "paint",
            "color_code": "#FFFFFF",
            "color_name": "纯白",
            "coverage_area": 60.0,
            "coats": 2,
            "unit_price": 38.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    # 添加吊顶方案
    await client.post(
        f"/api/hard-decoration/schemes/{scheme_id}/ceilings",
        json={
            "scheme_id": scheme_id,
            "ceiling_type": "gypsum_perimeter",
            "height_drop_mm": 200,
            "light_strip": True,
            "material": "石膏板",
            "total_area": 25.0,
            "unit_price": 220.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        f"/api/hard-decoration/schemes/{scheme_id}/budget",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["floor_count"] == 1
    assert data["wall_count"] == 1
    assert data["ceiling_count"] == 1
    assert data["total_budget"] > 0
    # 地面 25 * 1.05(损耗) * 128 = 3360
    assert data["floor_budget"] == 3360.0


@pytest.mark.asyncio
async def test_hd_delete_scheme(client: AsyncClient):
    """删除硬装方案"""
    token = await _register_and_login(client, "13900300015", "删除硬装")
    project_id = await _create_project(client, token, "删除硬装项目")
    create = await client.post(
        "/api/hard-decoration/schemes",
        json={"project_id": project_id, "room_name": "客厅", "scheme_type": "floor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    scheme_id = create.json()["id"]
    dele = await client.delete(
        f"/api/hard-decoration/schemes/{scheme_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dele.status_code == 204
    get = await client.get(f"/api/hard-decoration/schemes/{scheme_id}", headers={"Authorization": f"Bearer {token}"})
    assert get.status_code == 404


@pytest.mark.asyncio
async def test_hd_list_floors_walls_ceilings(client: AsyncClient):
    """硬装方案子资源列表：地面/墙面/吊顶 GET 端点（v1.0.16 新增）"""
    token = await _register_and_login(client, "13900300016", "硬装子资源")
    project_id = await _create_project(client, token, "硬装子资源项目")
    create = await client.post(
        "/api/hard-decoration/schemes",
        json={"project_id": project_id, "room_name": "客厅", "scheme_type": "floor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create.status_code == 201, create.text
    scheme_id = create.json()["id"]

    # 添加地面方案
    floor_resp = await client.post(
        f"/api/hard-decoration/schemes/{scheme_id}/floors",
        json={
            "scheme_id": scheme_id,
            "material_type": "tile",
            "coverage_area": 25.0,
            "unit_price": 80.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert floor_resp.status_code == 201, floor_resp.text
    floor_id = floor_resp.json()["id"]

    # 添加墙面方案
    wall_resp = await client.post(
        f"/api/hard-decoration/schemes/{scheme_id}/walls",
        json={
            "scheme_id": scheme_id,
            "finish_type": "paint",
            "coverage_area": 60.0,
            "unit_price": 35.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert wall_resp.status_code == 201, wall_resp.text
    wall_id = wall_resp.json()["id"]

    # 添加吊顶方案
    ceiling_resp = await client.post(
        f"/api/hard-decoration/schemes/{scheme_id}/ceilings",
        json={
            "scheme_id": scheme_id,
            "ceiling_type": "flat",
            "total_area": 25.0,
            "unit_price": 120.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ceiling_resp.status_code == 201, ceiling_resp.text
    ceiling_id = ceiling_resp.json()["id"]

    # 列出地面方案
    floors_list = await client.get(
        f"/api/hard-decoration/schemes/{scheme_id}/floors",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert floors_list.status_code == 200, floors_list.text
    floors_data = floors_list.json()
    assert len(floors_data) == 1
    assert floors_data[0]["id"] == floor_id
    assert floors_data[0]["material_type"] == "tile"

    # 列出墙面方案
    walls_list = await client.get(
        f"/api/hard-decoration/schemes/{scheme_id}/walls",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert walls_list.status_code == 200, walls_list.text
    walls_data = walls_list.json()
    assert len(walls_data) == 1
    assert walls_data[0]["id"] == wall_id
    assert walls_data[0]["finish_type"] == "paint"

    # 列出吊顶方案
    ceilings_list = await client.get(
        f"/api/hard-decoration/schemes/{scheme_id}/ceilings",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ceilings_list.status_code == 200, ceilings_list.text
    ceilings_data = ceilings_list.json()
    assert len(ceilings_data) == 1
    assert ceilings_data[0]["id"] == ceiling_id
    assert ceilings_data[0]["ceiling_type"] == "flat"

    # 空列表场景：新建一个 scheme 验证返回 []
    empty_create = await client.post(
        "/api/hard-decoration/schemes",
        json={"project_id": project_id, "room_name": "空房间", "scheme_type": "floor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    empty_scheme_id = empty_create.json()["id"]
    empty_list = await client.get(
        f"/api/hard-decoration/schemes/{empty_scheme_id}/floors",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert empty_list.status_code == 200
    assert empty_list.json() == []

    # 不存在的 scheme → 404
    not_found = await client.get(
        "/api/hard-decoration/schemes/nonexistent-scheme-id/floors",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert not_found.status_code == 404


# ════════════════════════════════════════════════════════════════
# F23 门窗/防水工程
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_dw_create_and_get(client: AsyncClient):
    """门窗选型 CRUD"""
    token = await _register_and_login(client, "13900300020", "门窗CRUD")
    project_id = await _create_project(client, token, "门窗项目1")
    resp = await client.post(
        "/api/door-window-waterproof/door-windows",
        json={
            "project_id": project_id,
            "room_name": "入户",
            "location": "入户大门",
            "spec_type": "entry_door",
            "material": "steel",
            "width": 950,
            "height": 2050,
            "thickness": 90,
            "opening_direction": "inward",
            "has_lock": True,
            "price": 3980,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["spec_type"] == "entry_door"
    assert data["material"] == "steel"
    spec_id = data["id"]

    # 查询
    get = await client.get(
        f"/api/door-window-waterproof/door-windows/{spec_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get.status_code == 200
    assert get.json()["id"] == spec_id

    # 列表
    lst = await client.get(
        f"/api/door-window-waterproof/door-windows/project/{project_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert lst.status_code == 200
    assert len(lst.json()) == 1


@pytest.mark.asyncio
async def test_dw_recommend_entry_door(client: AsyncClient):
    """门窗推荐 - 入户门"""
    token = await _register_and_login(client, "13900300021", "门窗推荐1")
    resp = await client.post(
        "/api/door-window-waterproof/door-windows/recommend",
        json={"spec_type": "entry_door"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["recommended_material"] == "steel"
    assert data["thickness_mm"] >= 90
    assert data["has_lock"] is True
    assert "C 级" in data["lock_grade"]


@pytest.mark.asyncio
async def test_dw_recommend_bathroom_door(client: AsyncClient):
    """门窗推荐 - 卫生间门"""
    token = await _register_and_login(client, "13900300022", "门窗推荐2")
    resp = await client.post(
        "/api/door-window-waterproof/door-windows/recommend",
        json={"spec_type": "interior_door", "room_type": "bathroom"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # 卫生间门推荐铝合金 (防潮)
    assert data["recommended_material"] == "aluminum"


@pytest.mark.asyncio
async def test_dw_recommend_window(client: AsyncClient):
    """门窗推荐 - 窗户"""
    token = await _register_and_login(client, "13900300023", "门窗推荐3")
    resp = await client.post(
        "/api/door-window-waterproof/door-windows/recommend",
        json={"spec_type": "window"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["recommended_material"] == "aluminum"
    assert data["glass_type"] == "double"
    assert data["has_screen"] is True


@pytest.mark.asyncio
async def test_dw_delete(client: AsyncClient):
    """删除门窗选型"""
    token = await _register_and_login(client, "13900300024", "删除门窗")
    project_id = await _create_project(client, token, "删除门窗项目")
    create = await client.post(
        "/api/door-window-waterproof/door-windows",
        json={
            "project_id": project_id,
            "room_name": "卧室",
            "spec_type": "interior_door",
            "material": "wood_composite",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    spec_id = create.json()["id"]
    dele = await client.delete(
        f"/api/door-window-waterproof/door-windows/{spec_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dele.status_code == 204
    get = await client.get(
        f"/api/door-window-waterproof/door-windows/{spec_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get.status_code == 404


@pytest.mark.asyncio
async def test_wp_create_and_get(client: AsyncClient):
    """防水方案 CRUD"""
    token = await _register_and_login(client, "13900300025", "防水CRUD")
    project_id = await _create_project(client, token, "防水项目1")
    resp = await client.post(
        "/api/door-window-waterproof/waterproof",
        json={
            "project_id": project_id,
            "room_name": "卫生间",
            "room_type": "bathroom",
            "wall_height_mm": 1800,
            "floor_area": 6.0,
            "wall_area": 15.0,
            "waterproof_material": "polyurethane",
            "coating_layers": 2,
            "thickness_mm": 1.5,
            "closure_test_hours": 24,
            "unit_price": 45.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["room_type"] == "bathroom"
    assert data["wall_height_mm"] == 1800
    plan_id = data["id"]

    # 查询
    get = await client.get(
        f"/api/door-window-waterproof/waterproof/{plan_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get.status_code == 200
    assert get.json()["id"] == plan_id

    # 列表
    lst = await client.get(
        f"/api/door-window-waterproof/waterproof/project/{project_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert lst.status_code == 200
    assert len(lst.json()) == 1


@pytest.mark.asyncio
async def test_wp_compute_area_bathroom(client: AsyncClient):
    """防水面积计算 - 卫生间"""
    token = await _register_and_login(client, "13900300026", "防水面积1")
    project_id = await _create_project(client, token, "防水面积项目1")
    create = await client.post(
        "/api/door-window-waterproof/waterproof",
        json={
            "project_id": project_id,
            "room_name": "卫生间",
            "room_type": "bathroom",
            "wall_height_mm": 1800,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    plan_id = create.json()["id"]
    resp = await client.post(
        f"/api/door-window-waterproof/waterproof/{plan_id}/compute-area",
        json={"room_width": 2.0, "room_length": 3.0, "wall_height_mm": 1800},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # 地面 = 2*3 = 6 m²
    assert data["floor_area_m2"] == 6.0
    # 墙面 > 0 (淋浴区 1.8m + 其他 0.3m)
    assert data["wall_area_m2"] > 0
    assert data["total_area_m2"] > data["floor_area_m2"]
    assert data["standard_height_mm"] == 1800


@pytest.mark.asyncio
async def test_wp_compute_area_kitchen(client: AsyncClient):
    """防水面积计算 - 厨房"""
    token = await _register_and_login(client, "13900300027", "防水面积2")
    project_id = await _create_project(client, token, "防水面积项目2")
    create = await client.post(
        "/api/door-window-waterproof/waterproof",
        json={
            "project_id": project_id,
            "room_name": "厨房",
            "room_type": "kitchen",
            "wall_height_mm": 300,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    plan_id = create.json()["id"]
    resp = await client.post(
        f"/api/door-window-waterproof/waterproof/{plan_id}/compute-area",
        json={"room_width": 3.0, "room_length": 4.0, "wall_height_mm": 300},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # 地面 = 3*4 = 12 m²
    assert data["floor_area_m2"] == 12.0
    assert data["standard_height_mm"] == 300


@pytest.mark.asyncio
async def test_wp_validation_compliant(client: AsyncClient):
    """防水规范校验 - 合规"""
    token = await _register_and_login(client, "13900300028", "防水合规")
    project_id = await _create_project(client, token, "防水合规项目")
    create = await client.post(
        "/api/door-window-waterproof/waterproof",
        json={
            "project_id": project_id,
            "room_name": "卫生间",
            "room_type": "bathroom",
            "wall_height_mm": 1800,
            "coating_layers": 2,
            "thickness_mm": 1.5,
            "closure_test_hours": 24,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    plan_id = create.json()["id"]
    resp = await client.get(
        f"/api/door-window-waterproof/waterproof/{plan_id}/validation",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["compliant"] is True
    assert data["passed_checks"] == data["total_checks"]


@pytest.mark.asyncio
async def test_wp_validation_non_compliant_height(client: AsyncClient):
    """防水规范校验 - 不合规 (卫生间防水高度不足)"""
    token = await _register_and_login(client, "13900300029", "防水高度不足")
    project_id = await _create_project(client, token, "防水不合规项目1")
    create = await client.post(
        "/api/door-window-waterproof/waterproof",
        json={
            "project_id": project_id,
            "room_name": "卫生间",
            "room_type": "bathroom",
            "wall_height_mm": 1500,  # 不足 1800
            "coating_layers": 2,
            "thickness_mm": 1.5,
            "closure_test_hours": 24,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    plan_id = create.json()["id"]
    resp = await client.get(
        f"/api/door-window-waterproof/waterproof/{plan_id}/validation",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["compliant"] is False
    # 高度校验失败
    height_check = [c for c in data["checks"] if "1800" in c["item"]][0]
    assert height_check["passed"] is False


@pytest.mark.asyncio
async def test_wp_validation_non_compliant_thickness(client: AsyncClient):
    """防水规范校验 - 不合规 (涂膜厚度不足)"""
    token = await _register_and_login(client, "13900300030", "防水厚度不足")
    project_id = await _create_project(client, token, "防水不合规项目2")
    create = await client.post(
        "/api/door-window-waterproof/waterproof",
        json={
            "project_id": project_id,
            "room_name": "卫生间",
            "room_type": "bathroom",
            "wall_height_mm": 1800,
            "coating_layers": 2,
            "thickness_mm": 1.0,  # 不足 1.5
            "closure_test_hours": 24,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    plan_id = create.json()["id"]
    resp = await client.get(
        f"/api/door-window-waterproof/waterproof/{plan_id}/validation",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["compliant"] is False
    thickness_check = [c for c in data["checks"] if "厚度" in c["item"]][0]
    assert thickness_check["passed"] is False


@pytest.mark.asyncio
async def test_wp_validation_non_compliant_closure(client: AsyncClient):
    """防水规范校验 - 不合规 (闭水试验时长不足)"""
    token = await _register_and_login(client, "13900300031", "闭水不足")
    project_id = await _create_project(client, token, "防水不合规项目3")
    create = await client.post(
        "/api/door-window-waterproof/waterproof",
        json={
            "project_id": project_id,
            "room_name": "卫生间",
            "room_type": "bathroom",
            "wall_height_mm": 1800,
            "coating_layers": 2,
            "thickness_mm": 1.5,
            "closure_test_hours": 12,  # 不足 24
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    plan_id = create.json()["id"]
    resp = await client.get(
        f"/api/door-window-waterproof/waterproof/{plan_id}/validation",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["compliant"] is False
    closure_check = [c for c in data["checks"] if "闭水" in c["item"]][0]
    assert closure_check["passed"] is False


@pytest.mark.asyncio
async def test_wp_delete(client: AsyncClient):
    """删除防水方案"""
    token = await _register_and_login(client, "13900300032", "删除防水")
    project_id = await _create_project(client, token, "删除防水项目")
    create = await client.post(
        "/api/door-window-waterproof/waterproof",
        json={
            "project_id": project_id,
            "room_name": "卫生间",
            "room_type": "bathroom",
            "wall_height_mm": 1800,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    plan_id = create.json()["id"]
    dele = await client.delete(
        f"/api/door-window-waterproof/waterproof/{plan_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dele.status_code == 204
    get = await client.get(
        f"/api/door-window-waterproof/waterproof/{plan_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get.status_code == 404
