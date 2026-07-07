"""F27 定制家具设计器 + F24/F25 软装搭配 + 收纳系统 测试

注意: 主代理负责在 app/main.py 中注册路由。
为保证测试可独立运行,此处将新路由与模型在本模块加载时挂载到 app 上。
"""

# ── 先导入模型,确保 Base.metadata 包含新表 ──
from app.models.custom_furniture import CustomFurnitureDesign, FurnitureModule, FurnitureBOM  # noqa: F401
from app.models.soft_furnishing import SoftFurnishingScheme, SoftFurnishingItem, StorageSystem  # noqa: F401

# ── 注册路由到 app(若尚未注册) ──
# 注意: app.py 末尾 app.mount("/", StaticFiles(...)) 会拦截所有未被匹配的请求,
# StaticFiles 对 POST 返回 405。因此必须把新路由插入到静态挂载之前。
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from app.main import app
from app.api import custom_furniture as cf_api
from app.api import soft_furnishing as sf_api


def _ensure_routers_registered() -> None:
    _paths = {getattr(r, "path", "") for r in app.routes}
    already_cf = any(p.startswith("/api/custom-furniture") for p in _paths)
    already_sf = any(p.startswith("/api/soft-furnishing") for p in _paths)
    if already_cf and already_sf:
        return
    # 找到根路径的 StaticFiles 挂载,临时移除,避免拦截新路由
    # 注意: app.mount("/", StaticFiles(...)) 实际产生的 Mount.path 为空字符串
    static_idx = None
    for i, r in enumerate(app.routes):
        if isinstance(r, Mount) and r.path in ("", "/") and isinstance(getattr(r, "app", None), StaticFiles):
            static_idx = i
            break
    static_mount = app.routes.pop(static_idx) if static_idx is not None else None
    if not already_cf:
        app.include_router(cf_api.router, prefix="/api")
    if not already_sf:
        app.include_router(sf_api.router, prefix="/api")
    # 将静态挂载重新放回末尾,保持原有行为
    if static_mount is not None:
        app.routes.append(static_mount)


_ensure_routers_registered()


import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, phone: str = "13900270001", name: str = "家具软装测试") -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": name, "password": "test123456"},
    )
    return resp.json()["access_token"]


async def _create_project(client: AsyncClient, token: str, name: str = "家具软装项目") -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": name, "address": "测试地址"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp.json()["id"]


# ════════════════════════════════════════════════════════════════
# F27 定制家具设计器
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_furniture_create_and_get_design(client: AsyncClient):
    token = await _register_and_login(client, "13900270010", "家具CRUD")
    project_id = await _create_project(client, token, "家具项目1")

    resp = await client.post(
        "/api/custom-furniture/designs",
        json={
            "project_id": project_id,
            "room_name": "主卧",
            "furniture_type": "wardrobe",
            "total_width": 1800,
            "total_height": 2400,
            "total_depth": 600,
            "panel_material": "颗粒板",
            "style": "北欧",
            "color": "白色",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["furniture_type"] == "wardrobe"
    assert data["total_width"] == 1800
    assert data["panel_material"] == "颗粒板"
    design_id = data["id"]

    # 查询单个
    get_resp = await client.get(f"/api/custom-furniture/designs/{design_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == design_id

    # 列表
    list_resp = await client.get(f"/api/custom-furniture/designs/project/{project_id}")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


@pytest.mark.asyncio
async def test_furniture_parametric_design(client: AsyncClient):
    token = await _register_and_login(client, "13900270011", "参数化测试")
    project_id = await _create_project(client, token, "参数化项目")
    create = await client.post(
        "/api/custom-furniture/designs",
        json={
            "project_id": project_id,
            "room_name": "主卧",
            "furniture_type": "wardrobe",
            "total_width": 1800,
            "total_height": 2400,
            "total_depth": 600,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    design_id = create.json()["id"]

    resp = await client.post(
        f"/api/custom-furniture/designs/{design_id}/parametric",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    modules = resp.json()
    # 衣柜至少应包含: 顶板/底板/侧板×2/背板/层板/挂衣杆/抽屉/门板
    assert len(modules) >= 8
    types = {m["module_type"] for m in modules}
    assert "top" in types
    assert "side" in types
    assert "shelf" in types
    assert "hanging_rod" in types
    assert "drawer" in types

    # 列出模块
    list_resp = await client.get(f"/api/custom-furniture/designs/{design_id}/modules")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == len(modules)


@pytest.mark.asyncio
async def test_furniture_compute_panels_and_price(client: AsyncClient):
    token = await _register_and_login(client, "13900270012", "板材价格测试")
    project_id = await _create_project(client, token, "板材项目")
    create = await client.post(
        "/api/custom-furniture/designs",
        json={
            "project_id": project_id,
            "room_name": "书房",
            "furniture_type": "bookshelf",
            "total_width": 1200,
            "total_height": 2100,
            "total_depth": 300,
            "panel_material": "多层板",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    design_id = create.json()["id"]
    await client.post(
        f"/api/custom-furniture/designs/{design_id}/parametric",
        headers={"Authorization": f"Bearer {token}"},
    )

    # 板材计算
    panels = await client.get(f"/api/custom-furniture/designs/{design_id}/panels")
    assert panels.status_code == 200
    pdata = panels.json()
    assert pdata["total_panel_area_m2"] > 0
    assert pdata["panel_sheets"] > 0

    # 价格估算
    price = await client.get(f"/api/custom-furniture/designs/{design_id}/price")
    assert price.status_code == 200
    price_data = price.json()
    assert price_data["total_price"] > 0
    assert price_data["panel_cost"] > 0
    assert price_data["process_cost"] > 0


@pytest.mark.asyncio
async def test_furniture_generate_and_query_bom(client: AsyncClient):
    token = await _register_and_login(client, "13900270013", "BOM测试")
    project_id = await _create_project(client, token, "BOM项目")
    create = await client.post(
        "/api/custom-furniture/designs",
        json={
            "project_id": project_id,
            "room_name": "客厅",
            "furniture_type": "tv_cabinet",
            "total_width": 1800,
            "total_height": 400,
            "total_depth": 350,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    design_id = create.json()["id"]
    await client.post(
        f"/api/custom-furniture/designs/{design_id}/parametric",
        headers={"Authorization": f"Bearer {token}"},
    )

    # 生成 BOM
    gen = await client.post(
        f"/api/custom-furniture/designs/{design_id}/bom",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert gen.status_code == 200, gen.text
    boms = gen.json()
    # 应包含 panel / hardware / accessory / door 中至少 3 类
    types = {b["item_type"] for b in boms}
    assert "panel" in types
    assert "accessory" in types
    assert "door" in types

    # 总价更新
    design = await client.get(f"/api/custom-furniture/designs/{design_id}")
    assert design.json()["total_price"] > 0
    assert design.json()["status"] == "quoted"

    # 查询 BOM
    query = await client.get(f"/api/custom-furniture/designs/{design_id}/bom")
    assert query.status_code == 200
    assert len(query.json()) == len(boms)


@pytest.mark.asyncio
async def test_furniture_bom_requires_modules(client: AsyncClient):
    token = await _register_and_login(client, "13900270014", "BOM校验")
    project_id = await _create_project(client, token, "BOM校验项目")
    create = await client.post(
        "/api/custom-furniture/designs",
        json={
            "project_id": project_id,
            "room_name": "客厅",
            "furniture_type": "wardrobe",
            "total_width": 1500,
            "total_height": 2200,
            "total_depth": 580,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    design_id = create.json()["id"]
    # 未先生成模块直接生成 BOM 应 400
    gen = await client.post(
        f"/api/custom-furniture/designs/{design_id}/bom",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert gen.status_code == 400


@pytest.mark.asyncio
async def test_furniture_validation_wardrobe_depth(client: AsyncClient):
    token = await _register_and_login(client, "13900270015", "校验测试")
    project_id = await _create_project(client, token, "校验项目")
    create = await client.post(
        "/api/custom-furniture/designs",
        json={
            "project_id": project_id,
            "room_name": "卧室",
            "furniture_type": "wardrobe",
            "total_width": 1500,
            "total_height": 2200,
            "total_depth": 400,  # 不达标
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    design_id = create.json()["id"]
    await client.post(
        f"/api/custom-furniture/designs/{design_id}/parametric",
        headers={"Authorization": f"Bearer {token}"},
    )
    v = await client.get(f"/api/custom-furniture/designs/{design_id}/validation")
    assert v.status_code == 200
    vdata = v.json()
    assert vdata["valid"] is False
    assert any("衣柜深度" in i["message"] for i in vdata["issues"])


@pytest.mark.asyncio
async def test_furniture_validation_door_width(client: AsyncClient):
    token = await _register_and_login(client, "13900270016", "门宽校验")
    project_id = await _create_project(client, token, "门宽项目")
    create = await client.post(
        "/api/custom-furniture/designs",
        json={
            "project_id": project_id,
            "room_name": "客厅",
            "furniture_type": "tv_cabinet",
            "total_width": 1500,
            "total_height": 400,
            "total_depth": 350,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    design_id = create.json()["id"]
    await client.post(
        f"/api/custom-furniture/designs/{design_id}/parametric",
        headers={"Authorization": f"Bearer {token}"},
    )
    v = await client.get(f"/api/custom-furniture/designs/{design_id}/validation")
    assert v.status_code == 200
    # tv_cabinet 宽 1500 → door_count = max(2, 1500//500)=3, 单门宽 500, 应通过
    vdata = v.json()
    assert vdata["valid"] is True


@pytest.mark.asyncio
async def test_furniture_add_and_delete_module(client: AsyncClient):
    token = await _register_and_login(client, "13900270017", "模块测试")
    project_id = await _create_project(client, token, "模块项目")
    create = await client.post(
        "/api/custom-furniture/designs",
        json={
            "project_id": project_id,
            "room_name": "卧室",
            "furniture_type": "wardrobe",
            "total_width": 1200,
            "total_height": 2200,
            "total_depth": 580,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    design_id = create.json()["id"]

    add = await client.post(
        f"/api/custom-furniture/designs/{design_id}/modules",
        json={"module_type": "mirror", "position_index": 99, "width": 400, "height": 1500, "depth": 5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert add.status_code == 201
    module_id = add.json()["id"]

    # 删除
    dele = await client.delete(
        f"/api/custom-furniture/modules/{module_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dele.status_code == 204


@pytest.mark.asyncio
async def test_furniture_delete_design(client: AsyncClient):
    token = await _register_and_login(client, "13900270018", "删除设计")
    project_id = await _create_project(client, token, "删除设计项目")
    create = await client.post(
        "/api/custom-furniture/designs",
        json={
            "project_id": project_id,
            "room_name": "卧室",
            "furniture_type": "wardrobe",
            "total_width": 1000,
            "total_height": 2000,
            "total_depth": 580,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    design_id = create.json()["id"]
    dele = await client.delete(
        f"/api/custom-furniture/designs/{design_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dele.status_code == 204
    # 再次查询应 404
    get = await client.get(f"/api/custom-furniture/designs/{design_id}")
    assert get.status_code == 404


# ════════════════════════════════════════════════════════════════
# F24/F25 软装搭配 + 收纳系统
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_soft_create_and_get_scheme(client: AsyncClient):
    token = await _register_and_login(client, "13900270020", "软装CRUD")
    project_id = await _create_project(client, token, "软装项目1")
    resp = await client.post(
        "/api/soft-furnishing/schemes",
        json={
            "project_id": project_id,
            "room_name": "客厅",
            "style": "北欧",
            "budget_total": 50000,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["style"] == "北欧"
    assert data["budget_total"] == 50000
    scheme_id = data["id"]

    # 查询
    get = await client.get(f"/api/soft-furnishing/schemes/{scheme_id}")
    assert get.status_code == 200
    assert get.json()["id"] == scheme_id

    # 列表
    lst = await client.get(f"/api/soft-furnishing/schemes/project/{project_id}")
    assert lst.status_code == 200
    assert len(lst.json()) == 1


@pytest.mark.asyncio
async def test_soft_ai_match(client: AsyncClient):
    token = await _register_and_login(client, "13900270021", "AI搭配")
    project_id = await _create_project(client, token, "AI项目")
    create = await client.post(
        "/api/soft-furnishing/schemes",
        json={"project_id": project_id, "room_name": "客厅", "style": "北欧", "budget_total": 60000},
        headers={"Authorization": f"Bearer {token}"},
    )
    scheme_id = create.json()["id"]

    resp = await client.post(
        f"/api/soft-furnishing/schemes/{scheme_id}/ai-match",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["style"] == "北欧"
    assert "color_scheme" in data
    assert data["color_scheme"]["primary"]
    assert len(data["recommended_items"]) > 0

    # 校验已写入配色 + 单品
    scheme = await client.get(f"/api/soft-furnishing/schemes/{scheme_id}")
    sdata = scheme.json()
    assert sdata["color_scheme"] is not None

    items = await client.get(f"/api/soft-furnishing/schemes/{scheme_id}/items")
    assert items.status_code == 200
    assert len(items.json()) > 0


@pytest.mark.asyncio
async def test_soft_color_harmony(client: AsyncClient):
    token = await _register_and_login(client, "13900270022", "配色测试")
    project_id = await _create_project(client, token, "配色项目")
    create = await client.post(
        "/api/soft-furnishing/schemes",
        json={"project_id": project_id, "room_name": "客厅", "style": "现代", "budget_total": 50000},
        headers={"Authorization": f"Bearer {token}"},
    )
    scheme_id = create.json()["id"]
    await client.post(
        f"/api/soft-furnishing/schemes/{scheme_id}/ai-match",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.get(f"/api/soft-furnishing/schemes/{scheme_id}/color-harmony")
    assert resp.status_code == 200
    data = resp.json()
    assert "score" in data
    assert "primary_pct" in data
    assert 0 <= data["score"] <= 100


@pytest.mark.asyncio
async def test_soft_color_harmony_no_scheme_color(client: AsyncClient):
    """未设置配色时应返回低分 + 提示"""
    token = await _register_and_login(client, "13900270023", "配色空")
    project_id = await _create_project(client, token, "配色空项目")
    create = await client.post(
        "/api/soft-furnishing/schemes",
        json={"project_id": project_id, "room_name": "客厅", "style": "法式", "budget_total": 50000},
        headers={"Authorization": f"Bearer {token}"},
    )
    scheme_id = create.json()["id"]
    resp = await client.get(f"/api/soft-furnishing/schemes/{scheme_id}/color-harmony")
    assert resp.status_code == 200
    assert resp.json()["score"] == 0.0


@pytest.mark.asyncio
async def test_soft_budget_usage(client: AsyncClient):
    token = await _register_and_login(client, "13900270024", "预算测试")
    project_id = await _create_project(client, token, "预算项目")
    create = await client.post(
        "/api/soft-furnishing/schemes",
        json={"project_id": project_id, "room_name": "客厅", "style": "北欧", "budget_total": 10000},
        headers={"Authorization": f"Bearer {token}"},
    )
    scheme_id = create.json()["id"]
    # 添加单品
    await client.post(
        f"/api/soft-furnishing/schemes/{scheme_id}/items",
        json={"item_type": "sofa", "name": "布艺沙发", "price": 4280, "quantity": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        f"/api/soft-furnishing/schemes/{scheme_id}/items",
        json={"item_type": "rug", "name": "羊毛地毯", "price": 1680, "quantity": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.get(f"/api/soft-furnishing/schemes/{scheme_id}/budget")
    assert resp.status_code == 200
    data = resp.json()
    # 4280 + 1680*2 = 7640
    assert data["budget_used"] == 7640.0
    assert data["budget_total"] == 10000
    assert data["budget_remaining"] == 2360.0
    assert data["status"] == "normal"


@pytest.mark.asyncio
async def test_soft_budget_warning_and_over(client: AsyncClient):
    token = await _register_and_login(client, "13900270025", "预算超")
    project_id = await _create_project(client, token, "预算超项目")
    create = await client.post(
        "/api/soft-furnishing/schemes",
        json={"project_id": project_id, "room_name": "客厅", "style": "北欧", "budget_total": 5000},
        headers={"Authorization": f"Bearer {token}"},
    )
    scheme_id = create.json()["id"]
    # 超预算
    await client.post(
        f"/api/soft-furnishing/schemes/{scheme_id}/items",
        json={"item_type": "sofa", "name": "真皮沙发", "price": 6000, "quantity": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.get(f"/api/soft-furnishing/schemes/{scheme_id}/budget")
    assert resp.json()["status"] == "over"


@pytest.mark.asyncio
async def test_soft_item_status_and_delete(client: AsyncClient):
    token = await _register_and_login(client, "13900270026", "单品状态")
    project_id = await _create_project(client, token, "单品项目")
    create = await client.post(
        "/api/soft-furnishing/schemes",
        json={"project_id": project_id, "room_name": "客厅", "style": "现代"},
        headers={"Authorization": f"Bearer {token}"},
    )
    scheme_id = create.json()["id"]
    item = await client.post(
        f"/api/soft-furnishing/schemes/{scheme_id}/items",
        json={"item_type": "lamp", "name": "落地灯", "price": 880},
        headers={"Authorization": f"Bearer {token}"},
    )
    item_id = item.json()["id"]
    assert item.json()["status"] == "planned"

    # 更新状态
    upd = await client.patch(
        f"/api/soft-furnishing/items/{item_id}/status",
        json={"status": "purchased"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upd.status_code == 200
    assert upd.json()["status"] == "purchased"

    # 删除
    dele = await client.delete(
        f"/api/soft-furnishing/items/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dele.status_code == 204


@pytest.mark.asyncio
async def test_soft_storage_crud_and_capacity(client: AsyncClient):
    token = await _register_and_login(client, "13900270027", "收纳CRUD")
    project_id = await _create_project(client, token, "收纳项目")
    create = await client.post(
        "/api/soft-furnishing/schemes",
        json={"project_id": project_id, "room_name": "卧室", "style": "现代"},
        headers={"Authorization": f"Bearer {token}"},
    )
    scheme_id = create.json()["id"]
    add = await client.post(
        f"/api/soft-furnishing/schemes/{scheme_id}/storage",
        json={
            "room_name": "主卧",
            "storage_type": "衣柜",
            "total_capacity_l": 1000,
            "compartment_count": 6,
            "adjustable_shelves": True,
            "smart_features": {"auto_light": True, "smart_lock": False},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert add.status_code == 201, add.text
    storage_id = add.json()["id"]
    assert add.json()["total_capacity_l"] == 1000

    # 列表
    lst = await client.get(f"/api/soft-furnishing/schemes/{scheme_id}/storage")
    assert lst.status_code == 200
    assert len(lst.json()) == 1

    # 容量计算
    cap = await client.get(f"/api/soft-furnishing/storage/{storage_id}/capacity")
    assert cap.status_code == 200
    cdata = cap.json()
    assert cdata["total_capacity_l"] == 1000
    assert cdata["utilization_rate"] == 0.7
    assert cdata["effective_capacity_l"] == 700.0


@pytest.mark.asyncio
async def test_soft_storage_recommend(client: AsyncClient):
    token = await _register_and_login(client, "13900270028", "收纳推荐")
    resp = await client.post(
        "/api/soft-furnishing/storage/recommend",
        json={"room_name": "主卧", "room_area": 20, "family_size": 3},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # 3 人 × 200L = 600L
    assert data["recommended_capacity_l"] == 600.0
    assert data["family_size"] == 3
    assert len(data["suggestions"]) > 0


@pytest.mark.asyncio
async def test_soft_delete_scheme(client: AsyncClient):
    token = await _register_and_login(client, "13900270029", "删除方案")
    project_id = await _create_project(client, token, "删除方案项目")
    create = await client.post(
        "/api/soft-furnishing/schemes",
        json={"project_id": project_id, "room_name": "客厅", "style": "现代"},
        headers={"Authorization": f"Bearer {token}"},
    )
    scheme_id = create.json()["id"]
    dele = await client.delete(
        f"/api/soft-furnishing/schemes/{scheme_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dele.status_code == 204
    get = await client.get(f"/api/soft-furnishing/schemes/{scheme_id}")
    assert get.status_code == 404
