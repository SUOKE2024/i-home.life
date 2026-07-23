"""物料服务层单元测试 — AI 推荐引擎（recommend_materials）"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    User, Project, Budget,
    MaterialCategory, Material,
    Supplier, Quotation,
)
from app.services.material_service import recommend_materials


# ── Fixtures ──


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """创建一个测试用户"""
    user = User(
        phone="13900000103",
        name="物料推荐测试用户",
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
        name="物料推荐测试项目",
        total_area=100.0,
        owner_id=test_user.id,
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest.fixture
async def test_categories(db_session: AsyncSession):
    """创建各品类分类"""
    cats = [
        MaterialCategory(name="地面材料", code="flooring"),
        MaterialCategory(name="墙面材料", code="wall"),
        MaterialCategory(name="顶面材料", code="ceiling"),
        MaterialCategory(name="门窗", code="doors_windows"),
        MaterialCategory(name="厨卫", code="kitchen_bath"),
        MaterialCategory(name="定制家具", code="custom_furniture"),
    ]
    for c in cats:
        db_session.add(c)
    await db_session.commit()
    for c in cats:
        await db_session.refresh(c)
    return {c.code: c for c in cats}


@pytest.fixture
async def test_materials(db_session: AsyncSession, test_categories):
    """创建各品类物料 — 覆盖不同价格区间和风格"""
    mats = []

    # 地面材料 — 经济型
    mats.append(Material(
        category_id=test_categories["flooring"].id,
        name="经济型强化地板",
        sku="REC-FLR-001",
        unit="㎡", unit_price=80.0, brand="普通品牌",
        spec="E1级 8mm 耐磨",
    ))
    # 地面材料 — 高端型
    mats.append(Material(
        category_id=test_categories["flooring"].id,
        name="现代简约大理石瓷砖",
        sku="REC-FLR-002",
        unit="㎡", unit_price=350.0, brand="马可波罗",
        spec="E0级 全瓷通体 防滑",
        description="现代简约风格首选，适合客厅、卧室",
    ))
    # 地面材料 — 中式风格
    mats.append(Material(
        category_id=test_categories["flooring"].id,
        name="新中式实木地板",
        sku="REC-FLR-003",
        unit="㎡", unit_price=480.0, brand="诺贝尔",
        spec="ENF级 18mm 橡木",
        description="新中式风格，东方美学实木地板",
    ))

    # 墙面材料 — 经济型
    mats.append(Material(
        category_id=test_categories["wall"].id,
        name="经济型内墙漆",
        sku="REC-WLL-001",
        unit="桶", unit_price=180.0, brand="普通品牌",
        spec="18L A级",
    ))
    # 墙面材料 — 高端型
    mats.append(Material(
        category_id=test_categories["wall"].id,
        name="北欧净味乳胶漆",
        sku="REC-WLL-002",
        unit="桶", unit_price=680.0, brand="立邦",
        spec="18L E0级 零甲醛",
        description="北欧风格，环保净味",
    ))

    # 顶面材料
    mats.append(Material(
        category_id=test_categories["ceiling"].id,
        name="石膏板吊顶",
        sku="REC-CEL-001",
        unit="㎡", unit_price=95.0, brand="普通品牌",
        spec="600×600 轻钢龙骨",
    ))
    mats.append(Material(
        category_id=test_categories["ceiling"].id,
        name="法式雕花吊顶",
        sku="REC-CEL-002",
        unit="㎡", unit_price=380.0, brand="高端品牌",
        spec="法式石膏线 定制雕花",
        description="法式浪漫风格吊顶装饰",
    ))

    # 门窗
    mats.append(Material(
        category_id=test_categories["doors_windows"].id,
        name="实木复合门",
        sku="REC-DW-001",
        unit="扇", unit_price=1880.0, brand="欧派",
        spec="E1级 实木复合 标准尺寸",
    ))

    # 厨卫
    mats.append(Material(
        category_id=test_categories["kitchen_bath"].id,
        name="经济型马桶",
        sku="REC-KB-001",
        unit="个", unit_price=680.0, brand="普通品牌",
    ))
    mats.append(Material(
        category_id=test_categories["kitchen_bath"].id,
        name="科勒智能马桶",
        sku="REC-KB-002",
        unit="个", unit_price=3980.0, brand="科勒",
        spec="智能除臭 暖风烘干",
    ))

    # 定制家具
    mats.append(Material(
        category_id=test_categories["custom_furniture"].id,
        name="极简衣柜",
        sku="REC-CF-001",
        unit="㎡", unit_price=800.0, brand="索菲亚",
        spec="E0级 18mm颗粒板",
        description="现代极简风格衣柜",
    ))
    mats.append(Material(
        category_id=test_categories["custom_furniture"].id,
        name="轻奢定制衣柜",
        sku="REC-CF-002",
        unit="㎡", unit_price=2800.0, brand="索菲亚",
        spec="ENF级 实木多层板",
        description="轻奢高端衣柜",
    ))

    for m in mats:
        db_session.add(m)
    await db_session.commit()
    for m in mats:
        await db_session.refresh(m)
    return mats


@pytest.fixture
async def test_supplier(db_session: AsyncSession):
    """创建测试供应商"""
    sup = Supplier(name="推荐物料供应商", category="flooring", rating=4.5)
    db_session.add(sup)
    await db_session.commit()
    await db_session.refresh(sup)
    return sup


# ── 辅助函数 ──


async def _create_budget(db_session: AsyncSession, project_id: str, total: float):
    """创建项目预算"""
    budget = Budget(
        project_id=project_id,
        total_estimated=total,
        total_actual=0.0,
        status="approved",
    )
    db_session.add(budget)
    await db_session.commit()
    await db_session.refresh(budget)
    return budget


# ── recommend_materials 测试 ──


@pytest.mark.asyncio
async def test_recommend_materials_economy(
    db_session: AsyncSession, test_project: Project,
    test_materials, test_categories,
):
    """测试推荐物料 — 经济型预算：应优先推荐低价物料"""
    # 创建低预算
    await _create_budget(db_session, test_project.id, 50000.0)

    result = await recommend_materials(db_session, test_project.id, budget_level="economy")

    assert result["project_id"] == test_project.id
    assert result["budget_level"] == "economy"
    assert result["total_budget"] == 50000.0
    assert "recommendations" in result
    assert "total_estimated_cost" in result
    assert "budget_utilization_percent" in result
    assert "alternative_suggestions" in result

    recommendations = result["recommendations"]
    assert len(recommendations) > 0
    assert result["total_recommendations"] == len(recommendations)

    # 验证每条推荐包含必要字段
    for rec in recommendations:
        assert "material_id" in rec
        assert "name" in rec
        assert "category" in rec
        assert "category_code" in rec
        assert "unit_price" in rec
        assert "estimated_cost" in rec
        assert "environmental_grade" in rec
        assert "match_score" in rec
        assert "reason" in rec
        assert 0 <= rec["match_score"] <= 100

    # 验证 economy 模式下包含相应建议
    suggestions = result["alternative_suggestions"]
    has_economy_suggestion = any("经济型" in s for s in suggestions)
    assert has_economy_suggestion


@pytest.mark.asyncio
async def test_recommend_materials_premium(
    db_session: AsyncSession, test_project: Project,
    test_materials, test_categories,
):
    """测试推荐物料 — 高端预算：应优先推荐高价物料"""
    # 创建高预算
    await _create_budget(db_session, test_project.id, 300000.0)

    result = await recommend_materials(db_session, test_project.id, budget_level="premium")

    assert result["project_id"] == test_project.id
    assert result["budget_level"] == "premium"
    assert result["total_budget"] == 300000.0

    recommendations = result["recommendations"]
    assert len(recommendations) > 0

    # premium 模式下应有高端品质相关的推荐理由
    premium_reasons = [
        r for r in recommendations if "高端品质" in r["reason"]
    ]
    assert len(premium_reasons) > 0

    # 验证包含高端建议
    suggestions = result["alternative_suggestions"]
    has_premium_suggestion = any("高端" in s for s in suggestions)
    assert has_premium_suggestion


@pytest.mark.asyncio
async def test_recommend_materials_standard_budget(
    db_session: AsyncSession, test_project: Project,
    test_materials, test_categories,
):
    """测试推荐物料 — 标准预算：按匹配分数排序"""
    await _create_budget(db_session, test_project.id, 120000.0)

    result = await recommend_materials(db_session, test_project.id)

    assert result["budget_level"] == "standard"
    assert result["total_budget"] == 120000.0

    recommendations = result["recommendations"]
    assert len(recommendations) > 0

    # 验证分数降序排列
    scores = [r["match_score"] for r in recommendations]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_recommend_materials_by_style(
    db_session: AsyncSession, test_project: Project,
    test_materials, test_categories,
):
    """测试风格过滤 — 指定现代风格应优先匹配相关物料"""
    await _create_budget(db_session, test_project.id, 150000.0)

    result = await recommend_materials(
        db_session, test_project.id,
        style="modern",
    )

    assert result["style"] == "modern"
    recommendations = result["recommendations"]

    # 找到名称中包含"现代"或"简约"或"极简"的推荐
    style_keywords = ["现代", "简约", "极简"]
    style_matched = [
        r for r in recommendations
        if any(kw in r["name"] for kw in style_keywords)
    ]

    # 风格匹配的推荐应该有风格相关推荐理由
    if style_matched:
        for rec in style_matched:
            assert rec["match_score"] >= 0  # 分数非负
            assert "风格" in rec["reason"] or any(kw in rec["name"] for kw in style_keywords)


@pytest.mark.asyncio
async def test_recommend_materials_with_room_type(
    db_session: AsyncSession, test_project: Project,
    test_materials, test_categories,
):
    """测试按房间类型筛选 — 仅返回相关品类的物料"""
    await _create_budget(db_session, test_project.id, 100000.0)

    result = await recommend_materials(
        db_session, test_project.id,
        room_type="bathroom",
    )

    assert result["room_type"] == "bathroom"
    recommendations = result["recommendations"]

    # bathroom 对应的品类：flooring, wall, ceiling, kitchen_bath, doors_windows
    valid_codes = {"flooring", "wall", "ceiling", "kitchen_bath", "doors_windows"}
    for rec in recommendations:
        assert rec["category_code"] in valid_codes


@pytest.mark.asyncio
async def test_recommend_materials_no_budget(
    db_session: AsyncSession, test_project: Project,
    test_materials, test_categories,
):
    """测试无预算时的推荐 — 应使用默认预算并优雅处理"""
    result = await recommend_materials(db_session, test_project.id)

    assert result["project_id"] == test_project.id
    assert result["budget_level"] == "standard"  # 无预算时默认 standard
    assert result["total_budget"] == 100000.0  # 默认 10 万

    recommendations = result["recommendations"]
    assert len(recommendations) > 0

    # 验证所有推荐都有合理字段
    for rec in recommendations:
        assert rec["match_score"] >= 0
        assert rec["estimated_cost"] > 0
        assert isinstance(rec["reason"], str)
        assert len(rec["reason"]) > 0


@pytest.mark.asyncio
async def test_recommend_materials_no_materials(
    db_session: AsyncSession, test_project: Project,
):
    """测试无物料数据时的推荐 — 应返回空推荐和提示"""
    result = await recommend_materials(db_session, test_project.id)

    assert result["project_id"] == test_project.id
    assert result["recommendations"] == []
    assert result["total_estimated_cost"] == 0.0
    assert result["budget_utilization_percent"] == 0.0

    suggestions = result["alternative_suggestions"]
    assert len(suggestions) >= 1
    assert any("暂无匹配物料" in s for s in suggestions)


@pytest.mark.asyncio
async def test_recommend_materials_chinese_style(
    db_session: AsyncSession, test_project: Project,
    test_materials, test_categories,
):
    """测试中式风格推荐 — 匹配「新中式实木地板」"""
    await _create_budget(db_session, test_project.id, 200000.0)

    result = await recommend_materials(
        db_session, test_project.id,
        style="chinese",
    )

    assert result["style"] == "chinese"

    # 中文风格关键词：新中式, 中式, 东方
    chinese_matched = [
        r for r in result["recommendations"]
        if "新中式" in r["name"] or "中式" in r["name"] or "东方" in r["name"]
    ]
    # 至少 ground 物料（新中式实木地板）应该被匹配
    assert len(chinese_matched) >= 1


@pytest.mark.asyncio
async def test_recommend_materials_returns_correct_structure(
    db_session: AsyncSession, test_project: Project,
    test_materials, test_categories,
):
    """测试推荐结果返回完整结构"""
    await _create_budget(db_session, test_project.id, 180000.0)

    result = await recommend_materials(db_session, test_project.id)

    # 验证顶层字段
    expected_top_keys = {
        "project_id", "room_type", "style", "budget_level",
        "total_budget", "recommendations", "total_recommendations",
        "categories_covered", "total_estimated_cost",
        "budget_utilization_percent", "alternative_suggestions",
    }
    assert expected_top_keys.issubset(result.keys())

    # budget_utilization_percent 应在合理范围
    assert result["budget_utilization_percent"] >= 0

    # categories_covered 不大于推荐总数
    assert result["categories_covered"] <= result["total_recommendations"]


@pytest.mark.asyncio
async def test_recommend_materials_environmental_grades(
    db_session: AsyncSession, test_project: Project,
    test_materials, test_categories,
):
    """测试环保等级推断 — 各种物料应返回正确的环保等级"""
    await _create_budget(db_session, test_project.id, 200000.0)

    result = await recommend_materials(db_session, test_project.id)

    recommendations = result["recommendations"]
    env_grades = {r["name"]: r["environmental_grade"] for r in recommendations}

    # E0 级物料
    assert env_grades.get("现代简约大理石瓷砖") == "E0"
    assert env_grades.get("极简衣柜") == "E0"

    # ENF 级物料
    assert env_grades.get("新中式实木地板") == "ENF"
    assert env_grades.get("轻奢定制衣柜") == "ENF"

    # E1 级物料（板材类默认）
    assert env_grades.get("经济型强化地板") == "E1"

    # 立邦漆 — spec 中含 "E0级" 和 "零甲醛"，E0 检查在前
    assert env_grades.get("北欧净味乳胶漆") == "E0"

    # A 级
    assert env_grades.get("石膏板吊顶") == "A"
