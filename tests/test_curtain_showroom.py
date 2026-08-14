"""窗帘智能展厅 API 集成测试

覆盖端点:
- GET /api/curtain-showroom/overview   (展厅总览)
- GET /api/curtain-showroom/products    (展品筛选)
"""

import pytest
from httpx import AsyncClient

from app.models.curtain_showroom import (
    CurtainInstallation,
    CurtainLightingPreset,
    CurtainProduct,
    CurtainSeries,
    CurtainShowroom,
    CurtainShowroomArea,
)
from app.models.material import Material, MaterialCategory


async def _seed_showroom(db) -> None:
    """在测试库中注入最小可用的单店铺展厅数据。"""
    category = MaterialCategory(name="窗帘布艺", code="curtain_fabric")
    db.add(category)
    await db.flush()
    material = Material(
        category_id=category.id, name="高精密提花 · 米白", sku="TEST-CUR-001",
        unit="米", unit_price=168.0, brand="帘享自营", spec="提花 · 米白",
    )
    db.add(material)
    await db.flush()

    showroom = CurtainShowroom(name="官渡区帘享空间窗帘布艺经营部", description="测试展厅")
    db.add(showroom)
    await db.flush()

    series = CurtainSeries(showroom_id=showroom.id, name="轻奢提花系列")
    db.add(series)
    installation = CurtainInstallation(code="roman_rod", name="罗马杆", render_type="roman_rod")
    db.add(installation)
    lighting = CurtainLightingPreset(
        code="morning", name="晨光", time_of_day="morning",
        light_color="#ffe3c2", ambient_intensity=1.0,
    )
    db.add(lighting)
    await db.flush()

    product = CurtainProduct(
        showroom_id=showroom.id, series_id=series.id, material_id=material.id,
        name="高精密提花 · 米白", sku="TEST-CUR-001", brand="帘享自营",
        fabric="提花", color="米白", unit="米", unit_price=168.0,
    )
    db.add(product)
    await db.flush()

    area = CurtainShowroomArea(
        showroom_id=showroom.id, name="客厅飘窗区",
        installation_id=installation.id, default_product_id=product.id,
    )
    db.add(area)
    await db.commit()


@pytest.mark.asyncio
async def test_curtain_showroom_unauthorized(client: AsyncClient):
    """未认证用户不可访问窗帘展厅"""
    resp = await client.get("/api/curtain-showroom/overview")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_curtain_showroom_overview_unconfigured(client: AsyncClient, auth_headers):
    """未配置展厅时诚实返回 404"""
    resp = await client.get("/api/curtain-showroom/overview", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_curtain_showroom_overview_with_data(client: AsyncClient, auth_headers, db_session):
    """展厅总览返回系列/安装方式/灯光预设/展示区域"""
    await _seed_showroom(db_session)
    resp = await client.get("/api/curtain-showroom/overview", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["showroom"]["name"] == "官渡区帘享空间窗帘布艺经营部"
    assert len(data["series"]) == 1
    assert len(data["installations"]) == 1
    assert len(data["lighting_presets"]) == 1
    assert len(data["areas"]) == 1
    assert data["areas"][0]["name"] == "客厅飘窗区"
    assert data["areas"][0]["installation"]["render_type"] == "roman_rod"
    assert data["areas"][0]["default_product"]["sku"] == "TEST-CUR-001"


@pytest.mark.asyncio
async def test_curtain_showroom_products_filter(client: AsyncClient, auth_headers, db_session):
    """展品列表按材质筛选"""
    await _seed_showroom(db_session)

    resp = await client.get("/api/curtain-showroom/products", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    hit = await client.get("/api/curtain-showroom/products?fabric=提花", headers=auth_headers)
    assert len(hit.json()) == 1

    miss = await client.get("/api/curtain-showroom/products?fabric=绒布", headers=auth_headers)
    assert len(miss.json()) == 0
