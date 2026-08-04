"""F44 环保材料库标签 API 集成测试

覆盖端点:
- POST /api/eco-materials/certs                                  (分配环保认证标签)
- GET  /api/eco-materials/certs/{material_id}                   (材料环保认证详情)
- GET  /api/eco-materials/materials?grade=ENF                   (按环保等级筛选)
- GET  /api/eco-materials/grades                                (环保等级统计)
- POST /api/eco-materials/validate                              (环保合规校验报告)
- GET  /api/eco-materials/materials/{material_id}/alternatives  (环保同级/更优替代)
- F44 AI 选材强制提示环保等级：BOM 生成 / AI 推荐链路 eco_grade + eco_notice
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.budget import Budget
from app.models.material import Material, MaterialCategory
from app.models.project import Floor, Room
from app.services import eco_material_service
from app.services.material_service import generate_bom_for_project, recommend_materials


async def _auth_headers(client: AsyncClient, phone: str = "13930050001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "环保标签测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_category_and_material(
    client: AsyncClient, headers: dict, cat_name: str, cat_code: str,
    mat_name: str, mat_sku: str, unit_price: float = 100.0,
) -> tuple[str, str]:
    """创建物料分类 + 材料，返回 (cat_id, mat_id)"""
    cat_resp = await client.post(
        "/api/materials/categories",
        json={"name": cat_name, "code": cat_code},
        headers=headers,
    )
    assert cat_resp.status_code == 201
    cat_id = cat_resp.json()["id"]
    mat_resp = await client.post(
        "/api/materials",
        json={
            "category_id": cat_id, "name": mat_name, "sku": mat_sku,
            "unit": "㎡", "unit_price": unit_price, "brand": "测试品牌",
        },
        headers=headers,
    )
    assert mat_resp.status_code == 201, mat_resp.text
    return cat_id, mat_resp.json()["id"]


async def _assign_cert(
    client: AsyncClient, headers: dict, material_id: str, eco_grade: str,
    certification: str = "绿色建材产品认证", source: str = "third_party",
) -> dict:
    resp = await client.post(
        "/api/eco-materials/certs",
        json={
            "material_id": material_id,
            "eco_grade": eco_grade,
            "certification": certification,
            "source": source,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Auth ──


@pytest.mark.asyncio
async def test_eco_materials_unauthorized(client: AsyncClient):
    """未认证用户不能分配环保认证标签"""
    resp = await client.post(
        "/api/eco-materials/certs",
        json={"material_id": "fake", "eco_grade": "ENF"},
    )
    assert resp.status_code == 401


# ── 标签分配 ──


@pytest.mark.asyncio
async def test_assign_and_get_cert(client: AsyncClient):
    """分配环保标签并读取"""
    headers = await _auth_headers(client, "13930050002")
    _, mat_id = await _create_category_and_material(
        client, headers, "环保分类A", "eco_cat_a", "环保板材", "ECO-001",
    )

    cert = await _assign_cert(client, headers, mat_id, "ENF")
    assert cert["eco_grade"] == "ENF"
    assert cert["certification"] == "绿色建材产品认证"
    assert cert["source"] == "third_party"

    resp = await client.get(f"/api/eco-materials/certs/{mat_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["eco_grade"] == "ENF"


@pytest.mark.asyncio
async def test_reassign_updates(client: AsyncClient):
    """重复分配为更新而非报错"""
    headers = await _auth_headers(client, "13930050003")
    _, mat_id = await _create_category_and_material(
        client, headers, "环保分类B", "eco_cat_b", "环保板材B", "ECO-002",
    )
    await _assign_cert(client, headers, mat_id, "ENF")

    resp = await client.post(
        "/api/eco-materials/certs",
        json={
            "material_id": mat_id,
            "eco_grade": "E0",
            "certification": "中国环境标志(十环)",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["eco_grade"] == "E0"
    assert resp.json()["certification"] == "中国环境标志(十环)"

    resp = await client.get(f"/api/eco-materials/certs/{mat_id}", headers=headers)
    assert resp.json()["eco_grade"] == "E0"


@pytest.mark.asyncio
async def test_invalid_grade_422(client: AsyncClient):
    """非法环保等级 → 422"""
    headers = await _auth_headers(client, "13930050004")
    _, mat_id = await _create_category_and_material(
        client, headers, "环保分类C", "eco_cat_c", "环保板材C", "ECO-003",
    )
    resp = await client.post(
        "/api/eco-materials/certs",
        json={"material_id": mat_id, "eco_grade": "E2"},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_assign_missing_material_404(client: AsyncClient):
    """材料不存在 → 404"""
    headers = await _auth_headers(client, "13930050005")
    resp = await client.post(
        "/api/eco-materials/certs",
        json={"material_id": "non-existent-id", "eco_grade": "ENF"},
        headers=headers,
    )
    assert resp.status_code == 404
    assert "材料不存在" in resp.json()["detail"]


# ── 筛选与统计 ──


@pytest.mark.asyncio
async def test_list_by_grade(client: AsyncClient):
    """按环保等级筛选 + 缺省返回全部"""
    headers = await _auth_headers(client, "13930050006")
    _, m1 = await _create_category_and_material(
        client, headers, "环保分类D", "eco_cat_d", "板材D1", "ECO-004",
    )
    _, m2 = await _create_category_and_material(
        client, headers, "环保分类E", "eco_cat_e", "板材E1", "ECO-005",
    )
    await _assign_cert(client, headers, m1, "ENF")
    await _assign_cert(client, headers, m2, "E0")

    resp = await client.get("/api/eco-materials/materials?grade=ENF", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["material_name"] == "板材D1"
    assert data[0]["sku"] == "ECO-004"
    assert data[0]["eco_grade"] == "ENF"

    resp = await client.get("/api/eco-materials/materials", headers=headers)
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_grades_stats(client: AsyncClient):
    """各环保等级数量统计"""
    headers = await _auth_headers(client, "13930050007")
    _, m1 = await _create_category_and_material(
        client, headers, "环保分类F", "eco_cat_f", "板材F1", "ECO-006",
    )
    _, m2 = await _create_category_and_material(
        client, headers, "环保分类G", "eco_cat_g", "板材G1", "ECO-007",
    )
    _, m3 = await _create_category_and_material(
        client, headers, "环保分类H", "eco_cat_h", "板材H1", "ECO-008",
    )
    await _assign_cert(client, headers, m1, "ENF")
    await _assign_cert(client, headers, m2, "E0")
    await _assign_cert(client, headers, m3, "E1")

    resp = await client.get("/api/eco-materials/grades", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ENF"] == 1
    assert data["E0"] == 1
    assert data["E1"] == 1


# ── 合规校验 ──


@pytest.mark.asyncio
async def test_validate_compliance(client: AsyncClient):
    """ENF+第三方认证合规；E1 或无认证不合规"""
    headers = await _auth_headers(client, "13930050008")
    _, m_enf = await _create_category_and_material(
        client, headers, "环保分类I", "eco_cat_i", "合规板材", "ECO-009",
    )
    _, m_e1 = await _create_category_and_material(
        client, headers, "环保分类J", "eco_cat_j", "E1板材", "ECO-010",
    )
    _, m_none = await _create_category_and_material(
        client, headers, "环保分类K", "eco_cat_k", "无认证板材", "ECO-011",
    )
    await _assign_cert(client, headers, m_enf, "ENF", certification="绿色建材产品认证")
    await _assign_cert(client, headers, m_e1, "E1", certification="绿色建材产品认证")
    # m_none 无环保标签（默认 E1 / 无认证）

    resp = await client.post(
        "/api/eco-materials/validate",
        json={"material_ids": [m_enf, m_e1, m_none]},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert data["compliant_count"] == 1
    assert data["non_compliant_count"] == 2
    by_id = {item["material_id"]: item for item in data["items"]}
    assert by_id[m_enf]["compliant"] is True
    assert by_id[m_enf]["requirement"] == "HC-003 环保等级硬约束"
    assert by_id[m_e1]["compliant"] is False
    assert by_id[m_none]["compliant"] is False
    assert by_id[m_none]["eco_grade"] == "E1"
    assert by_id[m_none]["certification"] == "无认证"


@pytest.mark.asyncio
async def test_validate_missing_material_404(client: AsyncClient):
    """校验不存在的材料 → 404"""
    headers = await _auth_headers(client, "13930050009")
    resp = await client.post(
        "/api/eco-materials/validate",
        json={"material_ids": ["non-existent-id"]},
        headers=headers,
    )
    assert resp.status_code == 404


# ── 替代推荐 ──


@pytest.mark.asyncio
async def test_alternatives(client: AsyncClient):
    """同分类环保同级/更优替代推荐"""
    headers = await _auth_headers(client, "13930050010")
    cat_resp = await client.post(
        "/api/materials/categories",
        json={"name": "环保分类-替代", "code": "eco_cat_alt"},
        headers=headers,
    )
    assert cat_resp.status_code == 201
    cat_id = cat_resp.json()["id"]
    material_ids: dict[str, str] = {}
    for name, sku, price in [
        ("目标板材", "ALT-001", 80.0),
        ("ENF板材", "ALT-002", 150.0),
        ("E0板材", "ALT-003", 120.0),
        ("E1板材", "ALT-004", 60.0),
    ]:
        resp = await client.post(
            "/api/materials",
            json={
                "category_id": cat_id, "name": name, "sku": sku,
                "unit": "㎡", "unit_price": price,
            },
            headers=headers,
        )
        assert resp.status_code == 201
        material_ids[sku] = resp.json()["id"]
    await _assign_cert(client, headers, material_ids["ALT-001"], "E0")
    await _assign_cert(client, headers, material_ids["ALT-002"], "ENF")
    await _assign_cert(client, headers, material_ids["ALT-003"], "E0")
    await _assign_cert(client, headers, material_ids["ALT-004"], "E1")

    resp = await client.get(
        f"/api/eco-materials/materials/{material_ids['ALT-001']}/alternatives",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    names = {item["material_name"] for item in data}
    assert "ENF板材" in names   # 更优等级
    assert "E0板材" in names    # 同级
    assert "E1板材" not in names  # 更低等级不推荐
    for item in data:
        assert item["sku"] in ("ALT-002", "ALT-003")
        assert "eco_grade" in item
        assert "unit_price" in item


# ── F44 AI 选材强制提示环保等级（BOM 生成 / AI 推荐链路） ──


@pytest.mark.asyncio
async def test_generate_bom_attaches_eco_grade(client: AsyncClient, db_session: AsyncSession):
    """BOM 生成强制提示环保等级：已认证材料 eco_grade=ENF；
    未认证材料 eco_grade=unverified + HC-003 提示（诚实标注不伪装）"""
    headers = await _auth_headers(client, "13930050011")
    proj_resp = await client.post(
        "/api/projects", json={"name": "BOM环保项目", "total_area": 100.0}, headers=headers,
    )
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]

    # ORM 建楼层 + 房间
    floor = Floor(project_id=proj_id, name="1F", floor_number=1, area=60.0)
    db_session.add(floor)
    await db_session.commit()
    await db_session.refresh(floor)
    db_session.add(Room(floor_id=floor.id, name="主卧", room_type="bedroom", area=15.0))
    await db_session.commit()

    # ORM 建分类 + 材料：flooring 将分配 ENF 认证；wall 无认证
    cat_flooring = MaterialCategory(name="地面材料", code="flooring")
    cat_wall = MaterialCategory(name="墙面材料", code="wall")
    db_session.add_all([cat_flooring, cat_wall])
    await db_session.commit()
    m_cert = Material(
        category_id=cat_flooring.id, name="ENF强化地板", sku="ECO-BOM-ENF",
        unit="㎡", unit_price=200.0,
    )
    m_plain = Material(
        category_id=cat_wall.id, name="普通乳胶漆", sku="ECO-BOM-PLAIN",
        unit="桶", unit_price=300.0,
    )
    db_session.add_all([m_cert, m_plain])
    await db_session.commit()

    # 为 m_cert 分配 ENF 环保认证
    await eco_material_service.assign_cert(
        db_session, m_cert.id, "ENF", "绿色建材产品认证", "third_party",
    )

    items = await generate_bom_for_project(db_session, proj_id)
    by_mat = {item.material_id: item for item in items}
    assert m_cert.id in by_mat and m_plain.id in by_mat

    # 已认证材料：如实标注 eco_grade=ENF，note 附带环保提示
    cert_item = by_mat[m_cert.id]
    assert cert_item.eco_grade == "ENF"
    assert "绿色建材产品认证" in cert_item.eco_notice
    assert "环保等级 ENF" in cert_item.note

    # 未认证材料：unverified 诚实标注 + HC-003 提示，不伪装成 E1/ENF
    plain_item = by_mat[m_plain.id]
    assert plain_item.eco_grade == "unverified"
    assert "未登记环保等级" in plain_item.eco_notice
    assert "HC-003" in plain_item.eco_notice
    assert "HC-003" in plain_item.note


@pytest.mark.asyncio
async def test_recommend_materials_attaches_eco_grade(
    client: AsyncClient, db_session: AsyncSession,
):
    """AI 选材推荐链路补充 eco_grade/eco_notice：有认证如实标注，无认证 unverified"""
    headers = await _auth_headers(client, "13930050012")
    proj_resp = await client.post(
        "/api/projects", json={"name": "AI选材环保项目", "total_area": 100.0}, headers=headers,
    )
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]

    db_session.add(Budget(project_id=proj_id, total_estimated=200000.0))
    await db_session.commit()

    cat = MaterialCategory(name="地面材料", code="flooring")
    db_session.add(cat)
    await db_session.commit()
    m_cert = Material(
        category_id=cat.id, name="ENF实木地板", sku="ECO-AI-ENF",
        unit="㎡", unit_price=300.0, description="零甲醛实木地板",
    )
    m_plain = Material(
        category_id=cat.id, name="普通瓷砖", sku="ECO-AI-PLAIN",
        unit="㎡", unit_price=80.0,
    )
    db_session.add_all([m_cert, m_plain])
    await db_session.commit()
    await eco_material_service.assign_cert(
        db_session, m_cert.id, "ENF", "中国环境标志(十环)", "third_party",
    )

    result = await recommend_materials(db_session, proj_id)
    recommendations = result["recommendations"]
    by_mat = {r["material_id"]: r for r in recommendations}
    assert m_cert.id in by_mat and m_plain.id in by_mat

    assert by_mat[m_cert.id]["eco_grade"] == "ENF"
    assert "十环" in by_mat[m_cert.id]["eco_notice"]
    assert by_mat[m_plain.id]["eco_grade"] == "unverified"
    assert "未登记环保等级" in by_mat[m_plain.id]["eco_notice"]
    assert "HC-003" in by_mat[m_plain.id]["eco_notice"]


# ── F50 一板一码溯源 ──


@pytest.mark.asyncio
async def test_board_trace_create_and_get(client: AsyncClient):
    """创建一板一码溯源记录并查询（含 HENF 等级）"""
    headers = await _auth_headers(client, "13930050020")
    _, mat_id = await _create_category_and_material(
        client, headers, "溯源分类A", "trace_cat_a", "板材A", "TRACE-001",
    )
    resp = await client.post(
        "/api/eco-materials/boards",
        json={
            "board_code": "B202607-001",
            "material_id": mat_id,
            "batch_no": "BATCH-2026-07",
            "origin": "佛山",
            "vendor": "大自然家居",
            "produced_at": "2026-07-01T00:00:00Z",
            "logistics": {"stages": [{"stage": "出厂", "location": "佛山"}]},
            "henf_grade": "HENF",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["board_code"] == "B202607-001"
    assert data["henf_grade"] == "HENF"
    assert data["origin"] == "佛山"
    assert data["material_name"] == "板材A"

    # 查询
    get_resp = await client.get("/api/eco-materials/boards/B202607-001", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["board_code"] == "B202607-001"
    assert get_resp.json()["henf_grade"] == "HENF"


@pytest.mark.asyncio
async def test_board_trace_duplicate_409(client: AsyncClient):
    """重复创建同一板材编码 → 404（valueerror 映射）"""
    headers = await _auth_headers(client, "13930050021")
    _, mat_id = await _create_category_and_material(
        client, headers, "溯源分类B", "trace_cat_b", "板材B", "TRACE-002",
    )
    payload = {"board_code": "B202607-DUP", "material_id": mat_id}
    r1 = await client.post("/api/eco-materials/boards", json=payload, headers=headers)
    assert r1.status_code == 201
    r2 = await client.post("/api/eco-materials/boards", json=payload, headers=headers)
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_board_trace_list_and_filter(client: AsyncClient):
    """列出板材溯源记录，可按材料筛选"""
    headers = await _auth_headers(client, "13930050022")
    _, mat_id = await _create_category_and_material(
        client, headers, "溯源分类C", "trace_cat_c", "板材C", "TRACE-003",
    )
    for code in ("B202607-01", "B202607-02"):
        await client.post(
            "/api/eco-materials/boards",
            json={"board_code": code, "material_id": mat_id},
            headers=headers,
        )
    resp = await client.get("/api/eco-materials/boards", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 2
    filtered = await client.get(
        f"/api/eco-materials/boards?material_id={mat_id}", headers=headers
    )
    assert filtered.status_code == 200
    assert {b["board_code"] for b in filtered.json()} == {"B202607-01", "B202607-02"}


@pytest.mark.asyncio
async def test_board_trace_not_found(client: AsyncClient):
    """查询不存在的板材编码 → 404"""
    headers = await _auth_headers(client, "13930050023")
    resp = await client.get("/api/eco-materials/boards/NO-SUCH-CODE", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cert_henf_grade_field(client: AsyncClient):
    """环保认证标签支持 HENF 等级预埋字段"""
    headers = await _auth_headers(client, "13930050024")
    _, mat_id = await _create_category_and_material(
        client, headers, "溯源分类D", "trace_cat_d", "板材D", "TRACE-004",
    )
    resp = await client.post(
        "/api/eco-materials/certs",
        json={
            "material_id": mat_id,
            "eco_grade": "ENF",
            "certification": "绿色建材产品认证",
            "henf_grade": "HENF",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["henf_grade"] == "HENF"
    # 查询详情也带 henf_grade
    detail = await client.get(f"/api/eco-materials/certs/{mat_id}", headers=headers)
    assert detail.json()["henf_grade"] == "HENF"
