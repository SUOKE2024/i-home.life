"""F26 家具品类库 + F31 智能家居方案 + F32 场景编辑 测试

注意: 主代理负责在 app/main.py 中注册路由。
为保证测试可独立运行,此处将新路由与模型在本模块加载时挂载到 app 上。
"""

# ── 先导入模型,确保 Base.metadata 包含新表 ──
from app.models.furniture_catalog import FurnitureCatalogItem  # noqa: F401
from app.models.smart_home import SmartHomeScheme, SmartDevice  # noqa: F401
from app.models.scene_automation import SceneAutomation, EcosystemIntegration  # noqa: F401

# ── 注册路由到 app(若尚未注册) ──
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from app.main import app
from app.api import furniture_catalog as fc_api
from app.api import smart_home as sh_api
from app.api import scene_automation as sa_api


def _ensure_routers_registered() -> None:
    _paths = {getattr(r, "path", "") for r in app.routes}
    targets = [
        ("/api/furniture-catalog", fc_api.router),
        ("/api/smart-home", sh_api.router),
        ("/api/scene-automation", sa_api.router),
    ]
    pending = [(prefix, router) for prefix, router in targets if not any(p.startswith(prefix) for p in _paths)]
    if not pending:
        return
    # 找到根路径的 StaticFiles 挂载,临时移除,避免拦截新路由
    static_idx = None
    for i, r in enumerate(app.routes):
        if isinstance(r, Mount) and r.path in ("", "/") and isinstance(getattr(r, "app", None), StaticFiles):
            static_idx = i
            break
    static_mount = app.routes.pop(static_idx) if static_idx is not None else None
    for prefix, router in pending:
        app.include_router(router, prefix="/api")
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


async def _create_project(client: AsyncClient, token: str, name: str = "测试项目") -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": name, "address": "测试地址"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp.json()["id"]


# ════════════════════════════════════════════════════════════════
# F26 家具品类库
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_furniture_catalog_crud(client: AsyncClient):
    token = await _register_and_login(client, "13900300001", "家具库CRUD")
    # 创建
    resp = await client.post(
        "/api/furniture-catalog",
        json={
            "category": "living_room",
            "subcategory": "sofa",
            "name": "北欧布艺三人沙发",
            "brand": "芝华仕",
            "width": 2100,
            "depth": 900,
            "height": 850,
            "material": "科技布",
            "color": "深灰",
            "style": "nordic",
            "price": 4980.0,
            "sale_price": 4280.0,
            "ar_preview_supported": True,
            "stock_count": 50,
            "rating": 4.5,
            "tags": ["热销", "新品"],
            "specs": {"材质": "科技布", "产地": "中国"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "北欧布艺三人沙发"
    assert data["style"] == "nordic"
    assert data["ar_preview_supported"] is True
    item_id = data["id"]

    # 查询
    get = await client.get(f"/api/furniture-catalog/{item_id}", headers={"Authorization": f"Bearer {token}"})
    assert get.status_code == 200
    assert get.json()["id"] == item_id
    # 浏览量应 +1
    assert get.json()["view_count"] == 1

    # 更新
    upd = await client.patch(
        f"/api/furniture-catalog/{item_id}",
        json={"price": 4680.0, "stock_count": 30},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upd.status_code == 200
    assert upd.json()["price"] == 4680.0
    assert upd.json()["stock_count"] == 30

    # 删除
    dele = await client.delete(
        f"/api/furniture-catalog/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dele.status_code == 204
    # 再次查询应 404
    get2 = await client.get(f"/api/furniture-catalog/{item_id}", headers={"Authorization": f"Bearer {token}"})
    assert get2.status_code == 404


@pytest.mark.asyncio
async def test_furniture_catalog_search(client: AsyncClient):
    token = await _register_and_login(client, "13900300002", "家具库筛选")
    # 批量创建不同品类的家具
    items = [
        {
            "category": "living_room", "subcategory": "sofa",
            "name": "现代沙发A", "style": "modern", "price": 5000,
            "brand": "A牌", "material": "布艺", "color": "灰",
        },
        {
            "category": "living_room", "subcategory": "coffee_table",
            "name": "现代茶几", "style": "modern", "price": 2000,
            "brand": "B牌", "material": "岩板", "color": "黑",
        },
        {
            "category": "bedroom", "subcategory": "bed",
            "name": "北欧床", "style": "nordic", "price": 4000,
            "brand": "A牌", "material": "实木", "color": "原木",
        },
        {
            "category": "bedroom", "subcategory": "wardrobe",
            "name": "中式衣柜", "style": "chinese", "price": 8000,
            "brand": "C牌", "material": "实木", "color": "红木",
        },
    ]
    for it in items:
        await client.post("/api/furniture-catalog", json=it, headers={"Authorization": f"Bearer {token}"})

    # 按品类筛选
    resp = await client.get("/api/furniture-catalog?category=living_room", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    # 按风格筛选
    resp = await client.get("/api/furniture-catalog?style=modern", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    # 按品牌筛选
    resp = await client.get("/api/furniture-catalog?brand=A牌", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    # 按价格区间筛选
    resp = await client.get(
        "/api/furniture-catalog?price_min=3000&price_max=6000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    prices = [i["price"] for i in resp.json()]
    assert all(3000 <= p <= 6000 for p in prices)

    # 按材质筛选
    resp = await client.get("/api/furniture-catalog?material=实木", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    # 关键词搜索
    resp = await client.get("/api/furniture-catalog?keyword=沙发", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_furniture_catalog_recommend(client: AsyncClient):
    token = await _register_and_login(client, "13900300003", "家具推荐")
    # 创建匹配的家具
    await client.post(
        "/api/furniture-catalog",
        json={
            "category": "bedroom", "subcategory": "bed", "name": "1.8m北欧床",
            "style": "nordic", "price": 4980,
            "width": 1800, "depth": 2000, "height": 400,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        "/api/furniture-catalog",
        json={
            "category": "bedroom", "subcategory": "nightstand", "name": "北欧床头柜",
            "style": "nordic", "price": 680,
            "width": 500, "depth": 400, "height": 500,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        "/api/furniture-catalog",
        json={
            "category": "bedroom", "subcategory": "wardrobe", "name": "北欧衣柜",
            "style": "nordic", "price": 4280,
            "width": 1800, "depth": 600, "height": 2200,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    # 推荐卧室组合
    resp = await client.get(
        "/api/furniture-catalog/recommend?room_type=bedroom&room_area=20&style=nordic&budget=20000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["room_type"] == "bedroom"
    assert data["style"] == "nordic"
    assert len(data["combos"]) == 3  # 床 + 床头柜×2 + 衣柜
    # 床头柜数量应为 2
    nightstand = [c for c in data["combos"] if c["subcategory"] == "nightstand"][0]
    assert nightstand["quantity"] == 2
    assert data["within_budget"] is True
    assert data["total_estimate"] > 0


@pytest.mark.asyncio
async def test_furniture_catalog_ar_placement(client: AsyncClient):
    token = await _register_and_login(client, "13900300004", "AR摆放")
    create = await client.post(
        "/api/furniture-catalog",
        json={
            "category": "living_room",
            "subcategory": "sofa",
            "name": "三人沙发",
            "style": "modern",
            "price": 5000,
            "width": 2100,
            "depth": 900,
            "height": 850,
            "ar_preview_supported": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    item_id = create.json()["id"]

    # 正常摆放
    resp = await client.get(
        f"/api/furniture-catalog/{item_id}/ar-placement?room_width=4000&room_length=5000&room_height=2800",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["scale"] == 1.0
    assert data["item_dimensions"]["width"] == 2100
    assert data["room_dimensions"]["width"] == 4000
    assert "x" in data["recommended_position"]
    assert "y" in data["recommended_position"]
    assert "z" in data["recommended_position"]
    assert data["fit_warning"] is None

    # 尺寸过大警告
    resp2 = await client.get(
        f"/api/furniture-catalog/{item_id}/ar-placement?room_width=1500&room_length=5000&room_height=2800",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["fit_warning"] is not None
    assert "超过房间宽度" in resp2.json()["fit_warning"]


@pytest.mark.asyncio
async def test_furniture_catalog_similar(client: AsyncClient):
    token = await _register_and_login(client, "13900300005", "相似推荐")
    # 创建同品类同风格的家具
    await client.post(
        "/api/furniture-catalog",
        json={
            "category": "living_room", "subcategory": "sofa",
            "name": "沙发A", "style": "modern", "price": 5000, "rating": 4.5,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        "/api/furniture-catalog",
        json={
            "category": "living_room", "subcategory": "coffee_table",
            "name": "茶几B", "style": "modern", "price": 2000, "rating": 4.2,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    create_c = await client.post(
        "/api/furniture-catalog",
        json={
            "category": "living_room", "subcategory": "sofa",
            "name": "沙发C", "style": "modern", "price": 4500, "rating": 4.8,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    item_id = create_c.json()["id"]

    resp = await client.get(
        f"/api/furniture-catalog/{item_id}/similar?limit=5",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # 应返回同 category + 同 style 的其他家具(沙发A)
    assert len(data) >= 1
    assert all(d["category"] == "living_room" for d in data)
    assert all(d["style"] == "modern" for d in data)
    # 不应包含自身
    assert all(d["id"] != item_id for d in data)


# ════════════════════════════════════════════════════════════════
# F31 智能家居方案设计器
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_smart_home_scheme_crud(client: AsyncClient):
    token = await _register_and_login(client, "13900300010", "智家CRUD")
    project_id = await _create_project(client, token, "智家项目")

    # 创建方案
    resp = await client.post(
        "/api/smart-home/schemes",
        json={
            "project_id": project_id,
            "room_name": "客厅",
            "room_type": "living_room",
            "protocol": "zigbee",
            "hub_brand": "xiaomi",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["room_name"] == "客厅"
    assert data["protocol"] == "zigbee"
    assert data["hub_brand"] == "xiaomi"
    assert data["device_count"] == 0
    scheme_id = data["id"]

    # 查询
    get = await client.get(f"/api/smart-home/schemes/{scheme_id}", headers={"Authorization": f"Bearer {token}"})
    assert get.status_code == 200
    assert get.json()["id"] == scheme_id

    # 列表
    lst = await client.get(
        f"/api/smart-home/schemes/project/{project_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert lst.status_code == 200
    assert len(lst.json()) == 1

    # 删除
    dele = await client.delete(f"/api/smart-home/schemes/{scheme_id}", headers={"Authorization": f"Bearer {token}"})
    assert dele.status_code == 204
    get2 = await client.get(f"/api/smart-home/schemes/{scheme_id}", headers={"Authorization": f"Bearer {token}"})
    assert get2.status_code == 404


@pytest.mark.asyncio
async def test_smart_home_auto_recommend(client: AsyncClient):
    token = await _register_and_login(client, "13900300011", "智家推荐")
    project_id = await _create_project(client, token, "智家推荐项目")
    create = await client.post(
        "/api/smart-home/schemes",
        json={
            "project_id": project_id, "room_name": "客厅", "room_type": "living_room",
            "protocol": "zigbee", "hub_brand": "xiaomi",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    scheme_id = create.json()["id"]

    # 自动推荐设备
    resp = await client.post(
        f"/api/smart-home/schemes/{scheme_id}/auto-recommend",
        json={"room_type": "living_room", "room_area": 30, "protocol": "zigbee", "hub_brand": "xiaomi"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["room_type"] == "living_room"
    # 客厅应包含: 灯/开关/窗帘/音箱/传感器/摄像头 (面积>25 多一盏灯)
    assert len(data["recommended_devices"]) >= 6
    types = {d["device_type"] for d in data["recommended_devices"]}
    assert "light" in types
    assert "switch" in types
    assert "curtain" in types
    assert "speaker" in types
    assert "sensor" in types
    assert "camera" in types
    assert data["total_estimate"] > 0

    # 方案 device_count 与 total_price 应同步更新
    scheme = await client.get(f"/api/smart-home/schemes/{scheme_id}", headers={"Authorization": f"Bearer {token}"})
    assert scheme.json()["device_count"] == len(data["recommended_devices"])

    # 设备列表
    devices = await client.get(
        f"/api/smart-home/schemes/{scheme_id}/devices",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert devices.status_code == 200
    assert len(devices.json()) == len(data["recommended_devices"])


@pytest.mark.asyncio
async def test_smart_home_wiring_plan(client: AsyncClient):
    token = await _register_and_login(client, "13900300012", "布线规划")
    project_id = await _create_project(client, token, "布线项目")
    create = await client.post(
        "/api/smart-home/schemes",
        json={
            "project_id": project_id, "room_name": "客厅", "room_type": "living_room",
            "protocol": "zigbee", "hub_brand": "xiaomi",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    scheme_id = create.json()["id"]
    await client.post(
        f"/api/smart-home/schemes/{scheme_id}/auto-recommend",
        json={"room_type": "living_room", "room_area": 20, "protocol": "zigbee", "hub_brand": "xiaomi"},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(f"/api/smart-home/schemes/{scheme_id}/wiring", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["wiring_items"]) > 0
    # 应包含零火线 / 电源预留 / 网线等布线说明
    notes_text = " ".join(data["notes"])
    assert "零线" in notes_text or any("零火线" in str(w["wiring_spec"]) for w in data["wiring_items"])


@pytest.mark.asyncio
async def test_smart_home_protocol_advice(client: AsyncClient):
    token = await _register_and_login(client, "13900300013", "协议选型")
    project_id = await _create_project(client, token, "协议项目")
    # Apple 生态
    create = await client.post(
        "/api/smart-home/schemes",
        json={
            "project_id": project_id, "room_name": "客厅", "room_type": "living_room",
            "protocol": "matter", "hub_brand": "apple",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    scheme_id = create.json()["id"]
    await client.post(
        f"/api/smart-home/schemes/{scheme_id}/devices",
        json={"device_type": "lock", "device_name": "智能门锁", "price": 1980, "wiring_required": False},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        f"/api/smart-home/schemes/{scheme_id}/protocol-advice",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["hub_brand"] == "apple"
    assert data["recommended_protocol"] == "matter"
    assert len(data["compatibility"]) > 0


@pytest.mark.asyncio
async def test_smart_home_total_price(client: AsyncClient):
    token = await _register_and_login(client, "13900300014", "总价计算")
    project_id = await _create_project(client, token, "总价项目")
    create = await client.post(
        "/api/smart-home/schemes",
        json={
            "project_id": project_id, "room_name": "客厅", "room_type": "living_room",
            "protocol": "zigbee", "hub_brand": "xiaomi",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    scheme_id = create.json()["id"]
    await client.post(
        f"/api/smart-home/schemes/{scheme_id}/devices",
        json={
            "device_type": "light", "device_name": "智能灯", "price": 880,
            "wiring_required": True, "wiring_spec": {"零火线": True},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        f"/api/smart-home/schemes/{scheme_id}/devices",
        json={
            "device_type": "switch", "device_name": "智能开关", "price": 280,
            "wiring_required": True, "wiring_spec": {"零火线": True},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(f"/api/smart-home/schemes/{scheme_id}/price", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["device_count"] == 2
    assert data["device_total"] == 1160.0
    assert data["hub_estimate"] > 0  # xiaomi 网关估价
    assert data["total_price"] == data["device_total"] + data["hub_estimate"]


@pytest.mark.asyncio
async def test_smart_home_device_delete(client: AsyncClient):
    token = await _register_and_login(client, "13900300015", "设备删除")
    project_id = await _create_project(client, token, "设备删除项目")
    create = await client.post(
        "/api/smart-home/schemes",
        json={"project_id": project_id, "room_name": "客厅", "room_type": "living_room"},
        headers={"Authorization": f"Bearer {token}"},
    )
    scheme_id = create.json()["id"]
    dev = await client.post(
        f"/api/smart-home/schemes/{scheme_id}/devices",
        json={"device_type": "light", "device_name": "智能灯", "price": 880},
        headers={"Authorization": f"Bearer {token}"},
    )
    device_id = dev.json()["id"]

    # 删除前 device_count=1
    scheme = await client.get(f"/api/smart-home/schemes/{scheme_id}", headers={"Authorization": f"Bearer {token}"})
    assert scheme.json()["device_count"] == 1

    dele = await client.delete(f"/api/smart-home/devices/{device_id}", headers={"Authorization": f"Bearer {token}"})
    assert dele.status_code == 204

    # 删除后 device_count=0
    scheme2 = await client.get(f"/api/smart-home/schemes/{scheme_id}", headers={"Authorization": f"Bearer {token}"})
    assert scheme2.json()["device_count"] == 0


# ════════════════════════════════════════════════════════════════
# F32 场景编辑
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_scene_crud(client: AsyncClient):
    token = await _register_and_login(client, "13900300020", "场景CRUD")
    project_id = await _create_project(client, token, "场景项目")

    # 创建场景
    resp = await client.post(
        "/api/scene-automation/scenes",
        json={
            "project_id": project_id,
            "scene_name": "回家模式",
            "scene_type": "triggered",
            "trigger_condition": {"type": "device", "device_id": "lock", "state": "unlock"},
            "actions": [{"device_id": "light", "action": "turn_on", "params": {"brightness": 80}}],
            "enabled": True,
            "priority": 10,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["scene_name"] == "回家模式"
    assert data["scene_type"] == "triggered"
    assert data["enabled"] is True
    assert data["priority"] == 10
    scene_id = data["id"]

    # 查询
    get = await client.get(f"/api/scene-automation/scenes/{scene_id}", headers={"Authorization": f"Bearer {token}"})
    assert get.status_code == 200
    assert get.json()["id"] == scene_id

    # 列表
    lst = await client.get(
        f"/api/scene-automation/scenes/project/{project_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert lst.status_code == 200
    assert len(lst.json()) == 1

    # 更新(禁用)
    upd = await client.patch(
        f"/api/scene-automation/scenes/{scene_id}",
        json={"enabled": False, "priority": 5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upd.status_code == 200
    assert upd.json()["enabled"] is False
    assert upd.json()["priority"] == 5

    # 删除
    dele = await client.delete(f"/api/scene-automation/scenes/{scene_id}", headers={"Authorization": f"Bearer {token}"})
    assert dele.status_code == 204
    get2 = await client.get(f"/api/scene-automation/scenes/{scene_id}", headers={"Authorization": f"Bearer {token}"})
    assert get2.status_code == 404


@pytest.mark.asyncio
async def test_scene_trigger_validation_invalid_cron(client: AsyncClient):
    token = await _register_and_login(client, "13900300021", "触发校验")
    project_id = await _create_project(client, token, "触发校验项目")
    # 无效 cron
    create = await client.post(
        "/api/scene-automation/scenes",
        json={
            "project_id": project_id,
            "scene_name": "定时场景",
            "scene_type": "scheduled",
            "trigger_condition": {"type": "time", "cron": "invalid"},
            "actions": [{"device_id": "light", "action": "turn_on"}],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    scene_id = create.json()["id"]

    resp = await client.post(
        f"/api/scene-automation/scenes/{scene_id}/simulate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["would_execute"] is False
    assert any("cron" in n for n in data["notes"])


@pytest.mark.asyncio
async def test_scene_trigger_validation_valid_cron(client: AsyncClient):
    token = await _register_and_login(client, "13900300022", "有效定时")
    project_id = await _create_project(client, token, "有效定时项目")
    create = await client.post(
        "/api/scene-automation/scenes",
        json={
            "project_id": project_id,
            "scene_name": "起床模式",
            "scene_type": "scheduled",
            "trigger_condition": {"type": "time", "cron": "0 7 * * *"},
            "actions": [],  # 无动作时也会校验失败
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    scene_id = create.json()["id"]

    resp = await client.post(
        f"/api/scene-automation/scenes/{scene_id}/simulate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # 动作列表为空 → 不会执行
    assert data["would_execute"] is False


@pytest.mark.asyncio
async def test_scene_action_validation_with_devices(client: AsyncClient):
    """动作校验: 设备存在性 + 动作合法性"""
    token = await _register_and_login(client, "13900300023", "动作校验")
    project_id = await _create_project(client, token, "动作校验项目")
    # 创建智能家居方案 + 设备
    scheme = await client.post(
        "/api/smart-home/schemes",
        json={
            "project_id": project_id, "room_name": "客厅", "room_type": "living_room",
            "protocol": "zigbee", "hub_brand": "xiaomi",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    scheme_id = scheme.json()["id"]
    dev = await client.post(
        f"/api/smart-home/schemes/{scheme_id}/devices",
        json={"device_type": "light", "device_name": "客厅灯", "price": 880},
        headers={"Authorization": f"Bearer {token}"},
    )
    device_id = dev.json()["id"]

    # 创建场景: 动作合法
    create = await client.post(
        "/api/scene-automation/scenes",
        json={
            "project_id": project_id,
            "scheme_id": scheme_id,
            "scene_name": "回家模式",
            "scene_type": "triggered",
            "trigger_condition": {"type": "device", "device_id": "lock", "state": "unlock"},
            "actions": [{"device_id": device_id, "action": "turn_on", "params": {"brightness": 80}}],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    scene_id = create.json()["id"]

    resp = await client.post(
        f"/api/scene-automation/scenes/{scene_id}/simulate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["would_execute"] is True
    assert len(data["actions_preview"]) == 1

    # 创建场景: 动作不合法(灯不支持 open)
    create2 = await client.post(
        "/api/scene-automation/scenes",
        json={
            "project_id": project_id,
            "scheme_id": scheme_id,
            "scene_name": "错误场景",
            "scene_type": "manual",
            "actions": [{"device_id": device_id, "action": "open"}],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    scene_id2 = create2.json()["id"]
    resp2 = await client.post(
        f"/api/scene-automation/scenes/{scene_id2}/simulate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["would_execute"] is False
    assert any("不支持动作" in n for n in data2["notes"])


@pytest.mark.asyncio
async def test_scene_recommend(client: AsyncClient):
    token = await _register_and_login(client, "13900300026", "场景推荐")
    resp = await client.get(
        "/api/scene-automation/scenes/recommend?room_type=bedroom&lifestyle=睡眠",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["room_type"] == "bedroom"
    assert len(data["recommended_scenes"]) > 0
    # lifestyle 过滤应返回睡眠相关场景
    names = [s["scene_name"] for s in data["recommended_scenes"]]
    assert any("睡眠" in n for n in names)


@pytest.mark.asyncio
async def test_scene_parse_natural_language(client: AsyncClient):
    # 定时 + 动作
    resp = await client.post(
        "/api/scene-automation/scenes/parse",
        json={"text": "每天早上 7 点打开客厅灯"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["parsed"] is True
    assert data["scene_type"] == "scheduled"
    assert data["trigger_condition"]["type"] == "time"
    assert data["trigger_condition"]["cron"] == "0 7 * * *"
    assert data["actions"] is not None
    assert data["actions"][0]["action"] == "turn_on"

    # 回家模式
    resp2 = await client.post(
        "/api/scene-automation/scenes/parse",
        json={"text": "回家时打开灯"},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["parsed"] is True
    assert data2["scene_type"] == "triggered"

    # 空文本
    resp3 = await client.post(
        "/api/scene-automation/scenes/parse",
        json={"text": ""},
    )
    assert resp3.status_code == 200
    assert resp3.json()["parsed"] is False


@pytest.mark.asyncio
async def test_scene_sync_to_ecosystem(client: AsyncClient):
    token = await _register_and_login(client, "13900300024", "生态同步")
    project_id = await _create_project(client, token, "生态同步项目")
    create = await client.post(
        "/api/scene-automation/scenes",
        json={
            "project_id": project_id,
            "scene_name": "回家模式",
            "scene_type": "manual",
            "actions": [{"device_id": "light", "action": "turn_on"}],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    scene_id = create.json()["id"]

    resp = await client.post(
        f"/api/scene-automation/scenes/{scene_id}/sync",
        json={"ecosystem": "mijia"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["synced"] is True
    assert "米家" in data["message"]

    # 验证生态对接记录已创建
    ecos = await client.get(
        f"/api/scene-automation/ecosystems/project/{project_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ecos.status_code == 200
    assert len(ecos.json()) == 1
    assert ecos.json()[0]["ecosystem"] == "mijia"
    assert ecos.json()[0]["auth_status"] == "connected"


@pytest.mark.asyncio
async def test_ecosystem_crud(client: AsyncClient):
    token = await _register_and_login(client, "13900300025", "生态CRUD")
    project_id = await _create_project(client, token, "生态CRUD项目")

    # 创建生态对接
    resp = await client.post(
        "/api/scene-automation/ecosystems",
        json={"project_id": project_id, "ecosystem": "homekit", "auth_status": "disconnected", "notes": "HomeKit 对接"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["ecosystem"] == "homekit"
    assert data["auth_status"] == "disconnected"
    eco_id = data["id"]

    # 列表
    lst = await client.get(
        f"/api/scene-automation/ecosystems/project/{project_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert lst.status_code == 200
    assert len(lst.json()) == 1

    # 删除
    dele = await client.delete(
        f"/api/scene-automation/ecosystems/{eco_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dele.status_code == 204
    lst2 = await client.get(
        f"/api/scene-automation/ecosystems/project/{project_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert len(lst2.json()) == 0
