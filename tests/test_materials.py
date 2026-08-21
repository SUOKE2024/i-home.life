import pytest
from httpx import AsyncClient

from app.models import Floor, Room, MaterialCategory, Material


async def _register_and_login(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": "13900000001", "name": "物料测试", "password": "test123456"},
    )
    return resp.json()["access_token"]


async def _create_category_and_material(
    client: AsyncClient, token: str, cat_name: str, cat_code: str,
    mat_name: str, mat_sku: str, unit_price: float = 100.0, unit: str = "㎡",
):
    """工具：创建分类+物料，返回 (cat_id, mat_id)"""
    cat_resp = await client.post(
        "/api/materials/categories",
        json={"name": cat_name, "code": cat_code},
        headers={"Authorization": f"Bearer {token}"},
    )
    cat_id = cat_resp.json()["id"]
    mat_resp = await client.post(
        "/api/materials",
        json={"category_id": cat_id, "name": mat_name, "sku": mat_sku, "unit_price": unit_price, "unit": unit},
        headers={"Authorization": f"Bearer {token}"},
    )
    return cat_id, mat_resp.json()["id"]


async def _create_project(client: AsyncClient, token: str, name: str = "测试项目"):
    proj_resp = await client.post(
        "/api/projects",
        json={"name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    return proj_resp.json()["id"]


@pytest.mark.asyncio
async def test_list_categories(client: AsyncClient):
    token = await _register_and_login(client)
    response = await client.get(
        "/api/materials/categories",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_category(client: AsyncClient):
    token = await _register_and_login(client)
    response = await client.post(
        "/api/materials/categories",
        json={"name": "测试分类", "code": "test_cat"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "测试分类"


@pytest.mark.asyncio
async def test_list_materials(client: AsyncClient):
    token = await _register_and_login(client)
    response = await client.get(
        "/api/materials?limit=10",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_material(client: AsyncClient):
    token = await _register_and_login(client)
    cat_resp = await client.post(
        "/api/materials/categories",
        json={"name": "临时分类", "code": "tmp_cat"},
        headers={"Authorization": f"Bearer {token}"},
    )
    cat_id = cat_resp.json()["id"]

    response = await client.post(
        "/api/materials",
        json={"category_id": cat_id, "name": "测试物料", "sku": "TEST-001", "unit_price": 100.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "测试物料"
    assert data["sku"] == "TEST-001"


@pytest.mark.asyncio
async def test_get_material_by_id(client: AsyncClient):
    token = await _register_and_login(client)
    cat_resp = await client.post(
        "/api/materials/categories",
        json={"name": "查找分类", "code": "find_cat"},
        headers={"Authorization": f"Bearer {token}"},
    )
    cat_id = cat_resp.json()["id"]

    create_resp = await client.post(
        "/api/materials",
        json={"category_id": cat_id, "name": "查找物料", "sku": "FIND-001", "unit_price": 50.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    mat_id = create_resp.json()["id"]

    response = await client.get(
        f"/api/materials/{mat_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "查找物料"


@pytest.mark.asyncio
async def test_add_bom_item(client: AsyncClient):
    token = await _register_and_login(client)
    cat_resp = await client.post(
        "/api/materials/categories",
        json={"name": "BOM分类", "code": "bom_cat"},
        headers={"Authorization": f"Bearer {token}"},
    )
    cat_id = cat_resp.json()["id"]

    mat_resp = await client.post(
        "/api/materials",
        json={"category_id": cat_id, "name": "BOM物料", "sku": "BOM-001", "unit_price": 200.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    mat_id = mat_resp.json()["id"]

    proj_resp = await client.post(
        "/api/projects",
        json={"name": "BOM项目", "address": "测试地址"},
        headers={"Authorization": f"Bearer {token}"},
    )
    proj_id = proj_resp.json()["id"]

    response = await client.post(
        "/api/materials/bom",
        json={"project_id": proj_id, "material_id": mat_id, "quantity": 5, "unit_price": 200.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["quantity"] == 5
    assert data["total_price"] == 1000.0


@pytest.mark.asyncio
async def test_add_bom_item_material_not_found_404(client: AsyncClient):
    """生产验证 ISSUE-001（2026-08-20）：不存在的 material_id 应 404 而非 500。

    此前 FK 冲突未捕获 → IntegrityError 500；边界校验先行返回 404 诚实报错。
    """
    token = await _register_and_login(client)
    proj_resp = await client.post(
        "/api/projects",
        json={"name": "BOM物料不存在项目", "address": "测试地址"},
        headers={"Authorization": f"Bearer {token}"},
    )
    proj_id = proj_resp.json()["id"]

    response = await client.post(
        "/api/materials/bom",
        json={"project_id": proj_id, "material_id": "NO-SUCH-MATERIAL-999", "quantity": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert "物料不存在" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_project_bom(client: AsyncClient):
    token = await _register_and_login(client)
    cat_resp = await client.post(
        "/api/materials/categories",
        json={"name": "BOM2分类", "code": "bom2_cat"},
        headers={"Authorization": f"Bearer {token}"},
    )
    cat_id = cat_resp.json()["id"]

    mat_resp = await client.post(
        "/api/materials",
        json={"category_id": cat_id, "name": "BOM2", "sku": "BOM2-001", "unit_price": 100.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    mat_id = mat_resp.json()["id"]

    proj_resp = await client.post(
        "/api/projects",
        json={"name": "BOM2项目"},
        headers={"Authorization": f"Bearer {token}"},
    )
    proj_id = proj_resp.json()["id"]

    await client.post(
        "/api/materials/bom",
        json={"project_id": proj_id, "material_id": mat_id, "quantity": 3, "unit_price": 100.0},
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.get(
        f"/api/materials/bom/{proj_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_delete_bom_item(client: AsyncClient):
    token = await _register_and_login(client)
    cat_resp = await client.post(
        "/api/materials/categories",
        json={"name": "删除分类", "code": "del_cat"},
        headers={"Authorization": f"Bearer {token}"},
    )
    cat_id = cat_resp.json()["id"]

    mat_resp = await client.post(
        "/api/materials",
        json={"category_id": cat_id, "name": "删除物料", "sku": "DEL-001", "unit_price": 10.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    mat_id = mat_resp.json()["id"]

    proj_resp = await client.post(
        "/api/projects",
        json={"name": "删除测试"},
        headers={"Authorization": f"Bearer {token}"},
    )
    proj_id = proj_resp.json()["id"]

    bom_resp = await client.post(
        "/api/materials/bom",
        json={"project_id": proj_id, "material_id": mat_id, "quantity": 1, "unit_price": 10.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    bom_id = bom_resp.json()["id"]

    response = await client.delete(
        f"/api/materials/bom/{bom_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204


# ============ 新增审计补全测试 ============


@pytest.mark.asyncio
async def test_get_material_not_found(client: AsyncClient):
    """查询不存在的物料应返回 404"""
    token = await _register_and_login(client)
    response = await client.get(
        "/api/materials/non-existent-id",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert "物料不存在" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_bom_item_not_found(client: AsyncClient):
    """删除不存在的 BOM 项应返回 404"""
    token = await _register_and_login(client)
    response = await client.delete(
        "/api/materials/bom/non-existent-bom-id",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert "BOM项不存在" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_materials_by_category(client: AsyncClient):
    """按品类筛选物料"""
    token = await _register_and_login(client)
    cat_a_id, _ = await _create_category_and_material(client, token, "品类A", "cat_a", "物料A1", "CAT_A_001")
    cat_b_id, _ = await _create_category_and_material(client, token, "品类B", "cat_b", "物料B1", "CAT_B_001")
    # 再加一个 A 品类的物料
    await client.post(
        "/api/materials",
        json={"category_id": cat_a_id, "name": "物料A2", "sku": "CAT_A_002", "unit_price": 50.0},
        headers={"Authorization": f"Bearer {token}"},
    )

    headers = {"Authorization": f"Bearer {token}"}
    resp_a = await client.get(
        f"/api/materials?category_id={cat_a_id}",
        headers=headers,
    )
    assert resp_a.status_code == 200
    data_a = resp_a.json()
    assert len(data_a) == 2
    assert all(m["category_id"] == cat_a_id for m in data_a)

    resp_b = await client.get(
        f"/api/materials?category_id={cat_b_id}",
        headers=headers,
    )
    assert len(resp_b.json()) == 1


@pytest.mark.asyncio
async def test_search_materials_by_keyword(client: AsyncClient):
    """关键字搜索物料（名称/SKU/品牌）"""
    token = await _register_and_login(client)
    await _create_category_and_material(
        client, token, "搜索分类", "search_cat", "立邦净味乳胶漆", "SEARCH-PAINT-001", 680.0, "桶"
    )
    await _create_category_and_material(
        client, token, "搜索分类2", "search_cat2", "东鹏瓷砖", "SEARCH-TILE-001", 198.0, "㎡"
    )

    # 按名称搜索
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get("/api/materials?keyword=立邦", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert "立邦" in data[0]["name"]

    # 按 SKU 搜索
    resp_sku = await client.get("/api/materials?keyword=SEARCH-TILE", headers=headers)
    assert len(resp_sku.json()) == 1

    # 按品牌搜索
    await client.post(
        "/api/materials",
        json={
            "category_id": data[0]["category_id"], "name": "搜索品牌物料",
            "sku": "SEARCH-BRAND-001", "brand": "多乐士", "unit_price": 1.0,
        },
        headers=headers,
    )
    resp_brand = await client.get("/api/materials?keyword=多乐士", headers=headers)
    assert len(resp_brand.json()) == 1


@pytest.mark.asyncio
async def test_generate_bom_no_rooms(client: AsyncClient):
    """F6 BOM 自动生成 — 项目无房间应返回 404"""
    token = await _register_and_login(client)
    proj_id = await _create_project(client, token, "无房间项目")

    response = await client.post(
        f"/api/materials/bom/generate/{proj_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert "房间" in response.json()["detail"]


@pytest.mark.asyncio
async def test_generate_bom_floorplan_placeholder_fallback(client: AsyncClient):
    """生产验证观察项（2026-08-20）：有户型占位（room_count/room_status）但无 Room 行，
    应经验法兜底 201 而非 404；quantity_source=empirical + 户型占位 fallback_note 诚实标注。"""
    token = await _register_and_login(client)
    # 建分类与物料（覆盖 flooring/wall/ceiling）
    cat_ids = {}
    for code, name in (("flooring", "地面材料"), ("wall", "墙面材料"), ("ceiling", "顶面材料")):
        cat = await client.post(
            "/api/materials/categories",
            json={"name": name, "code": code},
            headers={"Authorization": f"Bearer {token}"},
        )
        cat_ids[code] = cat.json()["id"]
    for code, mat_name in (("flooring", "地板"), ("wall", "乳胶漆"), ("ceiling", "石膏板")):
        await client.post(
            "/api/materials",
            json={"category_id": cat_ids[code], "name": mat_name, "sku": f"SKU-{code}",
                  "unit_price": 100.0, "unit": "桶" if code == "wall" else "㎡"},
            headers={"Authorization": f"Bearer {token}"},
        )
    proj_id = await _create_project(client, token, "户型占位项目")
    # 仅建户型占位（room_status 有房间名，不建 Floor/Room 行）
    fp_resp = await client.post(
        "/api/floorplans",
        json={"project_id": proj_id, "name": "占位户型", "total_area": 118.0,
              "room_count": 5,
              "room_status": {"客厅": "in_progress", "主卧": "in_progress",
                              "次卧": "pending", "厨房": "pending", "卫生间": "pending"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert fp_resp.status_code == 201

    resp = await client.post(
        f"/api/materials/bom/generate/{proj_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["quantity_source"] == "empirical"
    assert "户型占位" in data["fallback_note"]
    assert len(data["items"]) > 0
    for item in data["items"]:
        assert item["quantity_source"] == "empirical"
        assert "户型占位" in item["fallback_note"]


@pytest.mark.asyncio
async def test_generate_bom_placeholder_no_area(client: AsyncClient):
    """生产验证观察项（2026-08-20 二轮 QA）：有户型占位但无几何 data（room_count>0、
    total_area=0、room_status 为空）时，应经验法兜底 201 而非 404；
    quantity_source=empirical + fallback_note 诚实标注（QA 建议 P3-2 回归锁定）。"""
    token = await _register_and_login(client)
    cat_ids = {}
    for code, name in (("flooring", "地面材料"), ("wall", "墙面材料"), ("ceiling", "顶面材料")):
        cat = await client.post(
            "/api/materials/categories",
            json={"name": name, "code": code},
            headers={"Authorization": f"Bearer {token}"},
        )
        cat_ids[code] = cat.json()["id"]
    for code, mat_name in (("flooring", "地板"), ("wall", "乳胶漆"), ("ceiling", "石膏板")):
        await client.post(
            "/api/materials",
            json={"category_id": cat_ids[code], "name": mat_name, "sku": f"SKU-NOAREA-{code}",
                  "unit_price": 100.0, "unit": "桶" if code == "wall" else "㎡"},
            headers={"Authorization": f"Bearer {token}"},
        )
    proj_id = await _create_project(client, token, "户型占位无面积项目")
    # 与生产 QA 一致：仅 room_count>0，无 total_area/room_status/几何 data
    fp_resp = await client.post(
        "/api/floorplans",
        json={"project_id": proj_id, "name": "占位户型", "room_count": 5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert fp_resp.status_code == 201

    resp = await client.post(
        f"/api/materials/bom/generate/{proj_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["quantity_source"] == "empirical"
    assert "户型占位" in data["fallback_note"]
    assert len(data["items"]) > 0
    for item in data["items"]:
        assert item["quantity_source"] == "empirical"


@pytest.mark.asyncio
async def test_generate_bom_auto(client: AsyncClient, db_session):
    """F6 BOM 自动生成 — 基于房间面积生成 BOM"""
    token = await _register_and_login(client)
    proj_id = await _create_project(client, token, "BOM自动生成项目")

    # 直接通过 ORM 创建楼层和房间
    floor = Floor(project_id=proj_id, name="1F", floor_number=1, area=80.0)
    db_session.add(floor)
    await db_session.commit()
    await db_session.refresh(floor)

    rooms = [
        Room(floor_id=floor.id, name="主卧", room_type="bedroom", area=15.0),
        Room(floor_id=floor.id, name="客厅", room_type="living", area=30.0),
        Room(floor_id=floor.id, name="厨房", room_type="kitchen", area=8.0),
        Room(floor_id=floor.id, name="卫生间", room_type="bathroom", area=5.0),
    ]
    for r in rooms:
        db_session.add(r)
    await db_session.commit()

    # 创建物料分类与物料（覆盖自动生成会用到的品类）
    cat_flooring = MaterialCategory(name="地面材料", code="flooring")
    cat_wall = MaterialCategory(name="墙面材料", code="wall")
    cat_ceiling = MaterialCategory(name="顶面材料", code="ceiling")
    cat_doors = MaterialCategory(name="门窗", code="doors_windows")
    cat_kb = MaterialCategory(name="厨卫", code="kitchen_bath")
    cat_cf = MaterialCategory(name="定制家具", code="custom_furniture")
    for c in [cat_flooring, cat_wall, cat_ceiling, cat_doors, cat_kb, cat_cf]:
        db_session.add(c)
    await db_session.commit()

    materials = [
        Material(category_id=cat_flooring.id, name="大板砖", sku="GEN-FLR-001", unit="㎡", unit_price=198.0),
        Material(category_id=cat_wall.id, name="乳胶漆", sku="GEN-WLL-001", unit="桶", unit_price=680.0),
        Material(category_id=cat_ceiling.id, name="石膏板吊顶", sku="GEN-CEL-001", unit="㎡", unit_price=95.0),
        Material(category_id=cat_doors.id, name="实木复合门", sku="GEN-DW-001", unit="扇", unit_price=1880.0),
        Material(category_id=cat_kb.id, name="智能马桶", sku="GEN-KB-001", unit="个", unit_price=3980.0),
        Material(category_id=cat_cf.id, name="定制衣柜", sku="GEN-CF-001", unit="㎡", unit_price=1280.0),
    ]
    for m in materials:
        db_session.add(m)
    await db_session.commit()

    # 调用 F6 自动生成
    response = await client.post(
        f"/api/materials/bom/generate/{proj_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["project_id"] == proj_id
    assert data["generated_count"] > 0
    assert data["total_price"] > 0
    # 至少应包含地面、墙面、顶面物料
    item_cats = {item["material"]["category"]["code"] for item in data["items"]}
    assert "flooring" in item_cats
    assert "wall" in item_cats
    assert "ceiling" in item_cats
    # 自动生成状态
    assert all(item["status"] == "auto_generated" for item in data["items"])


@pytest.mark.asyncio
async def test_generate_bom_conflict(client: AsyncClient, db_session):
    """F6 BOM 自动生成 — 已有 BOM 应返回 409"""
    token = await _register_and_login(client)
    proj_id = await _create_project(client, token, "BOM冲突项目")

    floor = Floor(project_id=proj_id, name="1F", floor_number=1, area=50.0)
    db_session.add(floor)
    await db_session.commit()
    await db_session.refresh(floor)
    db_session.add(Room(floor_id=floor.id, name="卧室", room_type="bedroom", area=15.0))
    await db_session.commit()

    cat = MaterialCategory(name="地面材料", code="flooring")
    db_session.add(cat)
    await db_session.commit()
    db_session.add(Material(category_id=cat.id, name="地板", sku="CONF-FLR-001", unit="㎡", unit_price=200.0))
    await db_session.commit()

    # 第一次生成
    resp1 = await client.post(
        f"/api/materials/bom/generate/{proj_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 201

    # 第二次应冲突
    resp2 = await client.post(
        f"/api/materials/bom/generate/{proj_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 409
    assert "已有 BOM" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_get_bom_summary(client: AsyncClient):
    """BOM 汇总按品类聚合"""
    token = await _register_and_login(client)
    cat_id, mat_id = await _create_category_and_material(client, token, "汇总分类", "sum_cat", "汇总物料", "SUM-001", 100.0)
    proj_id = await _create_project(client, token, "BOM汇总项目")

    await client.post(
        "/api/materials/bom",
        json={"project_id": proj_id, "material_id": mat_id, "quantity": 3, "unit_price": 100.0},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        f"/api/materials/bom/{proj_id}/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == proj_id
    assert data["total_items"] == 1
    assert data["total_price"] == 300.0
    assert len(data["categories"]) == 1
    assert data["categories"][0]["category_code"] == "sum_cat"
    assert data["categories"][0]["item_count"] == 1
    assert data["categories"][0]["total_price"] == 300.0


@pytest.mark.asyncio
async def test_get_bom_summary_empty(client: AsyncClient):
    """BOM 汇总 — 无数据应返回 404"""
    token = await _register_and_login(client)
    proj_id = await _create_project(client, token, "空BOM项目")
    resp = await client.get(
        f"/api/materials/bom/{proj_id}/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_bom_excel(client: AsyncClient):
    """F7 BOM Excel 导出"""
    token = await _register_and_login(client)
    cat_id, mat_id = await _create_category_and_material(client, token, "导出分类", "exp_cat", "导出物料", "EXP-001", 100.0)
    proj_id = await _create_project(client, token, "BOM导出项目")

    await client.post(
        "/api/materials/bom",
        json={"project_id": proj_id, "material_id": mat_id, "quantity": 2, "unit_price": 100.0},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        f"/api/materials/bom/{proj_id}/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "spreadsheet" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]
    # 检查返回的是二进制 Excel
    body = resp.content
    assert len(body) > 0
    # xlsx 文件的魔数（PK 头）
    assert body[:2] == b"PK"


@pytest.mark.asyncio
async def test_export_bom_empty(client: AsyncClient):
    """F7 BOM Excel 导出 — 无数据应返回 404"""
    token = await _register_and_login(client)
    proj_id = await _create_project(client, token, "空BOM导出项目")
    resp = await client.get(
        f"/api/materials/bom/{proj_id}/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_project_bom_with_material_info(client: AsyncClient):
    """BOM 列表返回时应包含物料及品类信息"""
    token = await _register_and_login(client)
    cat_id, mat_id = await _create_category_and_material(
        client, token, "BOM详情分类", "bom_detail_cat", "BOM详情物料", "BOMD-001", 250.0,
    )
    proj_id = await _create_project(client, token, "BOM详情项目")

    await client.post(
        "/api/materials/bom",
        json={"project_id": proj_id, "material_id": mat_id, "quantity": 4, "unit_price": 250.0, "note": "测试备注"},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        f"/api/materials/bom/{proj_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    item = items[0]
    assert item["material"] is not None
    assert item["material"]["name"] == "BOM详情物料"
    assert item["material"]["category"] is not None
    assert item["total_price"] == 1000.0
    assert item["note"] == "测试备注"


# ============ F7 BOM 版本管理与差异标注 ============


@pytest.mark.asyncio
async def test_bom_version_snapshot_and_diff(client: AsyncClient, db_session):
    """F7 版本快照 + 差异对比：新增/删除/价格变化三类标注"""
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    proj_id = await _create_project(client, token, "BOM版本项目")

    _, mat_a = await _create_category_and_material(
        client, token, "品类A", "cat_a", "物料A", "VER-A-001", 100.0,
    )
    _, mat_b = await _create_category_and_material(
        client, token, "品类B", "cat_b", "物料B", "VER-B-001", 200.0,
    )

    # v1：添加 A、B 两项
    await client.post(
        "/api/materials/bom",
        json={"project_id": proj_id, "material_id": mat_a, "quantity": 2, "unit_price": 100.0},
        headers=headers,
    )
    await client.post(
        "/api/materials/bom",
        json={"project_id": proj_id, "material_id": mat_b, "quantity": 1, "unit_price": 200.0},
        headers=headers,
    )

    # 版本列表：只有 v1
    versions = (await client.get(f"/api/materials/bom/{proj_id}/versions", headers=headers)).json()
    assert versions["current_version"] == 1
    assert versions["versions"][0]["version"] == 1
    assert versions["versions"][0]["item_count"] == 2

    # 打版本快照 → v2（复制工作集）
    snap = (await client.post(f"/api/materials/bom/{proj_id}/version", headers=headers)).json()
    assert snap["snapshot_version"] == 1
    assert snap["new_version"] == 2
    assert snap["copied_items"] == 2

    # v2 工作集改造：删除 B 副本、修改 A 单价（模拟设计变更）
    from sqlalchemy import select as sa_select
    from app.models.material import BOMItem

    v2_items = (
        await db_session.execute(
            sa_select(BOMItem).where(BOMItem.project_id == proj_id, BOMItem.version == 2)
        )
    ).scalars().all()
    b_v2 = next(i for i in v2_items if i.material_id == mat_b)
    a_v2 = next(i for i in v2_items if i.material_id == mat_a)
    await db_session.delete(b_v2)
    a_v2.unit_price = 180.0
    a_v2.total_price = round(a_v2.quantity * 180.0, 2)
    await db_session.commit()

    # 新增：物料 C
    _, mat_c = await _create_category_and_material(
        client, token, "品类C", "cat_c", "物料C", "VER-C-001", 50.0,
    )
    await client.post(
        "/api/materials/bom",
        json={"project_id": proj_id, "material_id": mat_c, "quantity": 5, "unit_price": 50.0},
        headers=headers,
    )

    # 差异对比 from=1&to=2
    diff = (await client.get(f"/api/materials/bom/{proj_id}/diff?from=1&to=2", headers=headers)).json()
    assert diff["from_version"] == 1
    assert diff["to_version"] == 2
    added_ids = {d["material_id"] for d in diff["added"]}
    removed_ids = {d["material_id"] for d in diff["removed"]}
    assert mat_c in added_ids
    assert mat_b in removed_ids
    price_change = next(c for c in diff["changed"] if c["material_id"] == mat_a)
    assert price_change["from_unit_price"] == 100.0
    assert price_change["to_unit_price"] == 180.0
    assert price_change["change_type"] == "price"
    # 汇总
    assert diff["summary"]["added"] == 1
    assert diff["summary"]["removed"] == 1
    assert diff["summary"]["changed"] == 1

    # 打快照后工作集视图 = v2（不含历史 v1 快照）
    current = (await client.get(f"/api/materials/bom/{proj_id}", headers=headers)).json()
    assert len(current) == 2  # A、C


@pytest.mark.asyncio
async def test_bom_snapshot_no_bom_404(client: AsyncClient):
    """F7 无 BOM 时打版本快照应返回 404"""
    token = await _register_and_login(client)
    proj_id = await _create_project(client, token, "空BOM快照项目")
    resp = await client.post(
        f"/api/materials/bom/{proj_id}/version",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ============ F6 BOM 接入几何算量 ============


async def _create_geometric_project(
    client: AsyncClient, db_session, token: str, name: str, with_floorplan: bool
) -> str:
    """工具：创建含房间（可选 active floorplan）的项目与三类物料"""
    proj_id = await _create_project(client, token, name)

    floor = Floor(project_id=proj_id, name="1F", floor_number=1, area=20.0)
    db_session.add(floor)
    await db_session.commit()
    await db_session.refresh(floor)
    db_session.add(Room(floor_id=floor.id, name="客厅", room_type="living", area=20.0))
    await db_session.commit()

    if with_floorplan:
        import json as _json
        from app.models.floorplan import FloorPlan

        plan = FloorPlan(
            project_id=proj_id, name="户型A",
            data=_json.dumps({
                "walls": [
                    {"name": "W1", "start": {"x": 0, "y": 0}, "end": {"x": 5000, "y": 0}, "thickness": 240},
                    {"name": "W2", "start": {"x": 0, "y": 0}, "end": {"x": 0, "y": 4000}, "thickness": 240},
                ],
                "doors": [], "windows": [],
                "rooms": [{"name": "客厅", "area": 20.0, "type": "living", "tile_size": "600x600"}],
            }),
            wall_height=2.8, total_area=20.0, room_count=1, is_active=True,
        )
        db_session.add(plan)
        await db_session.commit()

    cat_flooring = MaterialCategory(name="地面材料", code="flooring")
    cat_wall = MaterialCategory(name="墙面材料", code="wall")
    cat_ceiling = MaterialCategory(name="顶面材料", code="ceiling")
    for c in [cat_flooring, cat_wall, cat_ceiling]:
        db_session.add(c)
    await db_session.commit()

    materials = [
        Material(category_id=cat_flooring.id, name="大板砖", sku=f"GEO-FLR-{name[:4]}", unit="㎡", unit_price=198.0),
        Material(category_id=cat_wall.id, name="乳胶漆", sku=f"GEO-WLL-{name[:4]}", unit="桶", unit_price=680.0),
        Material(category_id=cat_ceiling.id, name="石膏板吊顶", sku=f"GEO-CEL-{name[:4]}", unit="㎡", unit_price=95.0),
    ]
    for m in materials:
        db_session.add(m)
    await db_session.commit()
    return proj_id


@pytest.mark.asyncio
async def test_generate_bom_geometric_takeoff(client: AsyncClient, db_session):
    """F6 几何算量接入：有 active floorplan 时 BOM 项 quantity_source=geometric_takeoff"""
    token = await _register_and_login(client)
    proj_id = await _create_geometric_project(client, db_session, token, "几何算量项目", with_floorplan=True)

    resp = await client.post(
        f"/api/materials/bom/generate/{proj_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["quantity_source"] == "geometric_takeoff"
    assert data["fallback_note"] is None
    assert len(data["items"]) == 3  # flooring / wall / ceiling 均由几何算量填充
    for item in data["items"]:
        assert item["quantity_source"] == "geometric_takeoff"
        # 几何量应为 floorplan 派生量（地面 20㎡ 而非经验法 20×1.05）
        if item["material"]["category"]["code"] == "flooring":
            assert item["quantity"] == 20.0


@pytest.mark.asyncio
async def test_generate_bom_empirical_fallback(client: AsyncClient, db_session):
    """F6 无 floorplan 时回退经验法并标注 empirical + fallback_note"""
    token = await _register_and_login(client)
    proj_id = await _create_geometric_project(client, db_session, token, "经验回退项目", with_floorplan=False)

    resp = await client.post(
        f"/api/materials/bom/generate/{proj_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["quantity_source"] == "empirical"
    assert data["fallback_note"] == "无可用户型几何数据，采用面积×标准用量经验估算"
    assert len(data["items"]) == 3
    for item in data["items"]:
        assert item["quantity_source"] == "empirical"
        assert item["fallback_note"] == "无可用户型几何数据，采用面积×标准用量经验估算"
