"""采购服务层单元测试 — 供应商比价 / 到货核验 / 物料库存查询"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    User, Project, MaterialCategory, Material,
    Supplier, Quotation, ProcurementOrder, OrderLine,
)
from app.services.procurement_service import (
    compare_suppliers,
    verify_delivery,
    get_material_availability,
)


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """创建一个测试用户"""
    user = User(
        phone="13900000102",
        name="采购测试用户",
        hashed_password="hashed_test_password",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_project(db_session: AsyncSession, test_user: User):
    """创建一个测试项目"""
    project = Project(
        name="采购测试项目",
        total_area=100.0,
        owner_id=test_user.id,
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest.fixture
async def test_material(db_session: AsyncSession):
    """创建一个测试物料（含分类）"""
    cat = MaterialCategory(name="地面材料", code="flooring")
    db_session.add(cat)
    await db_session.commit()
    await db_session.refresh(cat)

    mat = Material(
        category_id=cat.id,
        name="大板瓷砖",
        sku="COMP-TILE-001",
        unit="㎡",
        unit_price=198.0,
        brand="马可波罗",
    )
    db_session.add(mat)
    await db_session.commit()
    await db_session.refresh(mat)
    return mat


@pytest.fixture
async def test_suppliers(db_session: AsyncSession):
    """创建多个测试供应商"""
    suppliers = [
        Supplier(name="优质供应商A", category="flooring", rating=4.8),
        Supplier(name="经济供应商B", category="flooring", rating=3.5),
        Supplier(name="靠谱供应商C", category="flooring", rating=4.2),
    ]
    for s in suppliers:
        db_session.add(s)
    await db_session.commit()
    for s in suppliers:
        await db_session.refresh(s)
    return suppliers


@pytest.fixture
async def test_quotations(db_session: AsyncSession, test_suppliers, test_material, test_project):
    """为不同供应商创建同一物料的报价"""
    quotes = [
        Quotation(
            supplier_id=test_suppliers[0].id,
            material_id=test_material.id,
            project_id=test_project.id,
            quantity=100.0,
            unit_price=180.0,
            total_price=18000.0,
            delivery_days=5,
            status="pending",
        ),
        Quotation(
            supplier_id=test_suppliers[1].id,
            material_id=test_material.id,
            project_id=test_project.id,
            quantity=100.0,
            unit_price=150.0,
            total_price=15000.0,
            delivery_days=10,
            status="pending",
        ),
        Quotation(
            supplier_id=test_suppliers[2].id,
            material_id=test_material.id,
            project_id=test_project.id,
            quantity=100.0,
            unit_price=195.0,
            total_price=19500.0,
            delivery_days=7,
            status="pending",
        ),
    ]
    for q in quotes:
        db_session.add(q)
    await db_session.commit()
    for q in quotes:
        await db_session.refresh(q)
    return quotes


# ── compare_suppliers 测试 ──


@pytest.mark.asyncio
async def test_compare_suppliers(db_session: AsyncSession, test_quotations, test_material):
    """测试供应商比价 — 返回按总价排序的比较结果"""
    result = await compare_suppliers(db_session, test_material.id, quantity=50.0)

    assert result["material_id"] == test_material.id
    assert result["material_name"] == test_material.name
    assert result["material_sku"] == test_material.sku
    assert result["requested_quantity"] == 50.0
    assert result["total_suppliers"] == 3

    comparisons = result["comparisons"]
    assert len(comparisons) == 3

    # 验证按 total_cost 升序排列
    for i in range(len(comparisons) - 1):
        assert comparisons[i]["total_cost"] <= comparisons[i + 1]["total_cost"]

    # 验证每条记录包含必要字段
    for c in comparisons:
        assert "supplier_id" in c
        assert "supplier_name" in c
        assert "supplier_rating" in c
        assert "unit_price" in c
        assert "total_cost" in c
        assert "delivery_days" in c
        # total_cost = quantity * unit_price
        assert c["total_cost"] == pytest.approx(50.0 * c["unit_price"], rel=1e-9)


@pytest.mark.asyncio
async def test_compare_suppliers_no_quotations(db_session: AsyncSession, test_material, test_suppliers, test_user):
    """测试比价 — 无报价时返回供应商基础信息"""
    result = await compare_suppliers(db_session, test_material.id, quantity=30.0)

    assert result["material_id"] == test_material.id
    assert result["total_suppliers"] == 3  # 有 3 个活跃供应商
    comparisons = result["comparisons"]

    for c in comparisons:
        assert c["quotation_status"] == "no_quotation"
        assert "note" in c


@pytest.mark.asyncio
async def test_compare_suppliers_material_not_found(db_session: AsyncSession):
    """测试比价 — 物料不存在应抛出 ValueError"""
    with pytest.raises(ValueError, match="物料不存在"):
        await compare_suppliers(db_session, "non-existent-material-id", 10.0)


# ── verify_delivery 测试 ──


@pytest.fixture
async def test_order_with_lines(db_session: AsyncSession, test_project, test_material, test_suppliers):
    """创建含多行明细的采购订单（用于核验测试）"""
    order = ProcurementOrder(
        project_id=test_project.id,
        supplier_id=test_suppliers[0].id,
        status="shipped",
        total_amount=5000.0,
    )
    db_session.add(order)
    await db_session.commit()
    await db_session.refresh(order)

    # 创建两条 OrderLine
    lines = [
        OrderLine(
            order_id=order.id,
            material_id=test_material.id,
            quantity=20.0,
            unit_price=198.0,
            total_price=3960.0,
            delivered_quantity=20.0,  # 完全匹配
        ),
        OrderLine(
            order_id=order.id,
            material_id=test_material.id,
            quantity=10.0,
            unit_price=104.0,
            total_price=1040.0,
            delivered_quantity=7.0,  # 短缺 3
        ),
    ]
    for line in lines:
        db_session.add(line)
    await db_session.commit()
    for line in lines:
        await db_session.refresh(line)

    # 刷新 order 以加载 lines
    await db_session.refresh(order)
    return order


@pytest.mark.asyncio
async def test_verify_delivery(db_session: AsyncSession, test_order_with_lines):
    """测试到货核验 — 检测差异并返回完整报告"""
    result = await verify_delivery(db_session, test_order_with_lines.id)

    assert result["order_id"] == test_order_with_lines.id
    assert "verified_at" in result
    assert result["total_lines"] == 2
    assert result["all_matched"] is False  # 有短缺
    assert result["discrepancy_count"] > 0

    discrepancies = result["discrepancies"]
    assert len(discrepancies) == 2

    # 第一条：数量匹配
    matched_line = next(d for d in discrepancies if d["status"] == "matched")
    assert matched_line["ordered_quantity"] == 20.0
    assert matched_line["delivered_quantity"] == 20.0
    assert matched_line["difference"] == 0.0

    # 第二条：短缺
    short_line = next(d for d in discrepancies if d["status"] == "short")
    assert short_line["ordered_quantity"] == 10.0
    assert short_line["delivered_quantity"] == 7.0
    assert short_line["difference"] == 3.0


@pytest.mark.asyncio
async def test_verify_delivery_all_matched(db_session: AsyncSession, test_project, test_material, test_suppliers):
    """测试到货核验 — 全部匹配的场景"""
    order = ProcurementOrder(
        project_id=test_project.id,
        supplier_id=test_suppliers[0].id,
        status="delivered",
        total_amount=1980.0,
    )
    db_session.add(order)
    await db_session.commit()
    await db_session.refresh(order)

    line = OrderLine(
        order_id=order.id,
        material_id=test_material.id,
        quantity=10.0,
        unit_price=198.0,
        total_price=1980.0,
        delivered_quantity=10.0,  # 完全匹配
    )
    db_session.add(line)
    await db_session.commit()
    await db_session.refresh(line)
    await db_session.refresh(order)

    result = await verify_delivery(db_session, order.id)

    assert result["all_matched"] is True
    assert result["discrepancy_count"] == 0
    assert result["total_lines"] == 1

    # 唯一一条记录状态应为 matched
    assert result["discrepancies"][0]["status"] == "matched"


@pytest.mark.asyncio
async def test_verify_delivery_order_not_found(db_session: AsyncSession):
    """测试核验 — 订单不存在应抛出 ValueError"""
    with pytest.raises(ValueError, match="采购订单不存在"):
        await verify_delivery(db_session, "non-existent-order-id")


# ── get_material_availability 测试 ──


@pytest.mark.asyncio
async def test_get_material_availability(db_session: AsyncSession, test_quotations, test_material):
    """测试物料库存查询 — 返回各供应商的可用库存和交货信息"""
    result = await get_material_availability(db_session, test_material.id)

    assert result["material_id"] == test_material.id
    assert result["material_name"] == test_material.name
    assert result["material_sku"] == test_material.sku
    assert "total_available" in result
    assert result["supplier_count"] > 0

    suppliers = result["suppliers"]
    assert len(suppliers) > 0

    for s in suppliers:
        assert "supplier_id" in s
        assert "supplier_name" in s
        assert "supplier_rating" in s
        assert "available_quantity" in s
        assert "lead_time_days" in s
        assert "unit_price" in s
        assert "in_transit_quantity" in s
        assert s["available_quantity"] >= 0


@pytest.mark.asyncio
async def test_get_material_availability_no_quotations(db_session: AsyncSession, test_material):
    """测试库存查询 — 无报价物料"""
    result = await get_material_availability(db_session, test_material.id)

    assert result["material_id"] == test_material.id
    assert result["supplier_count"] == 0
    assert result["total_available"] == 0.0
    assert result["suppliers"] == []


@pytest.mark.asyncio
async def test_get_material_availability_material_not_found(db_session: AsyncSession):
    """测试库存查询 — 物料不存在应抛出 ValueError"""
    with pytest.raises(ValueError, match="物料不存在"):
        await get_material_availability(db_session, "non-existent-material-id")
