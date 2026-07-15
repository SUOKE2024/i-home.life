"""points_service 测试 — 积分等级 / 账户 / 增减 / 兑换 / 排名"""

import pytest

from app.models.user import User
from app.models.points import (
    PointsAccount,
    PointsRule,
    PointsMallItem,
)
from app.services.points_service import (
    compute_level,
    ensure_account,
    earn_points,
    redeem_item,
    recompute_ranking,
    get_ranking,
)


async def _create_user(db_session, phone="13900005001", name="积分测试", role="homeowner"):
    user = User(phone=phone, name=name, role=role, hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# ════════════════════════════════════════════════════════════════
# compute_level
# ════════════════════════════════════════════════════════════════


def test_compute_level_bronze():
    assert compute_level(0) == "bronze"
    assert compute_level(499) == "bronze"


def test_compute_level_silver_to_diamond():
    assert compute_level(500) == "silver"
    assert compute_level(2000) == "gold"
    assert compute_level(5000) == "platinum"
    assert compute_level(10000) == "diamond"
    assert compute_level(99999) == "diamond"


# ════════════════════════════════════════════════════════════════
# ensure_account
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_ensure_account_creates_new(db_session):
    user = await _create_user(db_session)
    account = await ensure_account(db_session, user.id)

    assert isinstance(account, PointsAccount)
    assert account.balance == 0
    assert account.level == "bronze"


@pytest.mark.asyncio
async def test_ensure_account_idempotent(db_session):
    user = await _create_user(db_session)
    account1 = await ensure_account(db_session, user.id)
    account2 = await ensure_account(db_session, user.id)

    assert account1.id == account2.id


# ════════════════════════════════════════════════════════════════
# earn_points
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_earn_points_positive(db_session):
    user = await _create_user(db_session)
    txn = await earn_points(db_session, user.id, source="test_action", amount=100)

    assert txn is not None
    assert txn.amount == 100
    assert txn.balance_after == 100

    account = await ensure_account(db_session, user.id)
    assert account.balance == 100
    assert account.total_earned == 100
    assert account.level == "bronze"


@pytest.mark.asyncio
async def test_earn_points_negative_to_zero(db_session):
    user = await _create_user(db_session)
    await earn_points(db_session, user.id, source="test_action", amount=100)
    # 扣减超过余额
    txn = await earn_points(db_session, user.id, source="penalty", amount=-200)

    assert txn is not None
    account = await ensure_account(db_session, user.id)
    assert account.balance == 0  # clamp 到 0,不会变负


@pytest.mark.asyncio
async def test_earn_points_to_silver_level(db_session):
    user = await _create_user(db_session)
    await earn_points(db_session, user.id, source="test_action", amount=500)

    account = await ensure_account(db_session, user.id)
    assert account.balance >= 500
    assert account.level == "silver"


@pytest.mark.asyncio
async def test_earn_points_rule_not_found(db_session):
    user = await _create_user(db_session)
    txn = await earn_points(db_session, user.id, source="nonexistent_action", amount=None)
    assert txn is None


@pytest.mark.asyncio
async def test_earn_points_with_rule(db_session):
    user = await _create_user(db_session)
    rule = PointsRule(
        action="login",
        points=10,
        role="homeowner",
        description="每日登录",
        is_active=True,
    )
    db_session.add(rule)
    await db_session.commit()

    txn = await earn_points(db_session, user.id, source="login", amount=None)
    assert txn is not None
    assert txn.amount == 10


@pytest.mark.asyncio
async def test_earn_points_daily_limit_exceeded(db_session):
    user = await _create_user(db_session)
    rule = PointsRule(
        action="daily_action",
        points=10,
        role="homeowner",
        description="测试每日限额",
        is_active=True,
        limit_daily=2,
    )
    db_session.add(rule)
    await db_session.commit()

    txn1 = await earn_points(db_session, user.id, source="daily_action", amount=None)
    txn2 = await earn_points(db_session, user.id, source="daily_action", amount=None)
    txn3 = await earn_points(db_session, user.id, source="daily_action", amount=None)

    assert txn1 is not None
    assert txn2 is not None
    assert txn3 is None  # 第 3 次被限额拦截


# ════════════════════════════════════════════════════════════════
# redeem_item
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_redeem_item_success(db_session):
    user = await _create_user(db_session)
    item = PointsMallItem(
        name="折扣券",
        category="discount",
        points_required=50,
        stock=10,
        is_active=True,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)

    await earn_points(db_session, user.id, source="test_action", amount=100)
    result = await redeem_item(db_session, user.id, item.id)

    assert result["success"] is True
    assert result["balance_after"] == 50
    assert result["discount_code"] is not None
    assert len(result["discount_code"]) > 0


@pytest.mark.asyncio
async def test_redeem_item_insufficient_points(db_session):
    user = await _create_user(db_session)
    item = PointsMallItem(
        name="折扣券",
        category="discount",
        points_required=50,
        stock=-1,  # 无限库存,排除库存干扰
        is_active=True,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)

    result = await redeem_item(db_session, user.id, item.id)
    assert result["success"] is False
    assert "积分不足" in result["error"]


@pytest.mark.asyncio
async def test_redeem_item_out_of_stock(db_session):
    user = await _create_user(db_session)
    item = PointsMallItem(
        name="折扣券",
        category="discount",
        points_required=50,
        stock=0,
        is_active=True,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)

    result = await redeem_item(db_session, user.id, item.id)
    assert result["success"] is False
    assert "售罄" in result["error"]


@pytest.mark.asyncio
async def test_redeem_item_not_found(db_session):
    user = await _create_user(db_session)
    result = await redeem_item(db_session, user.id, "nonexistent-item-id")
    assert result["success"] is False
    assert "不存在" in result["error"]


@pytest.mark.asyncio
async def test_redeem_item_decrements_stock(db_session):
    user = await _create_user(db_session)
    item = PointsMallItem(
        name="折扣券",
        category="discount",
        points_required=50,
        stock=5,
        is_active=True,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)

    await earn_points(db_session, user.id, source="test_action", amount=100)
    result = await redeem_item(db_session, user.id, item.id)
    assert result["success"] is True

    await db_session.refresh(item)
    assert item.stock == 4


# ════════════════════════════════════════════════════════════════
# recompute_ranking / get_ranking
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_recompute_ranking_basic(db_session):
    user1 = await _create_user(db_session, phone="13900005010", name="用户A")
    user2 = await _create_user(db_session, phone="13900005011", name="用户B")
    user3 = await _create_user(db_session, phone="13900005012", name="用户C")

    await earn_points(db_session, user1.id, source="test", amount=100)
    await earn_points(db_session, user2.id, source="test", amount=200)
    await earn_points(db_session, user3.id, source="test", amount=50)

    count = await recompute_ranking(db_session)
    assert count == 3

    ranking = await get_ranking(db_session)
    assert len(ranking) == 3
    # 按 year_earned 降序
    assert ranking[0]["year_earned"] == 200
    assert ranking[1]["year_earned"] == 100
    assert ranking[2]["year_earned"] == 50


@pytest.mark.asyncio
async def test_get_ranking_filter_by_role(db_session):
    user1 = await _create_user(db_session, phone="13900005010", name="业主A", role="homeowner")
    user2 = await _create_user(db_session, phone="13900005011", name="设计师B", role="designer")
    user3 = await _create_user(db_session, phone="13900005012", name="业主C", role="homeowner")

    await earn_points(db_session, user1.id, source="test", amount=100)
    await earn_points(db_session, user2.id, source="test", amount=200)
    await earn_points(db_session, user3.id, source="test", amount=50)

    await recompute_ranking(db_session)

    ranking = await get_ranking(db_session, role="homeowner")
    assert len(ranking) == 2
    assert all(r["role"] == "homeowner" for r in ranking)


@pytest.mark.asyncio
async def test_get_ranking_empty(db_session):
    ranking = await get_ranking(db_session)
    assert ranking == []
