"""积分系统服务 — 积分增减、等级管理、排名、商城兑换"""

import logging
import secrets
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.points import (
    PointsAccount, PointsTransaction, PointsRule,
    PointsMallItem, PointsRedemption, PointsRanking,
)

logger = logging.getLogger(__name__)

# ── 等级配置 ──
LEVEL_CONFIG = {
    "bronze":   {"min": 0,     "max": 499,   "label": "铜牌"},
    "silver":   {"min": 500,   "max": 1999,  "label": "银牌"},
    "gold":     {"min": 2000,  "max": 4999,  "label": "金牌"},
    "platinum": {"min": 5000,  "max": 9999,  "label": "铂金"},
    "diamond":  {"min": 10000, "max": None,  "label": "钻石"},
}


def compute_level(balance: int) -> str:
    for level, cfg in LEVEL_CONFIG.items():
        if balance >= cfg["min"] and (cfg["max"] is None or balance <= cfg["max"]):
            return level
    return "bronze"


# ── 账户管理 ──

async def ensure_account(db: AsyncSession, user_id: str) -> PointsAccount:
    """确保用户有积分账户，没有则自动创建"""
    stmt = select(PointsAccount).where(PointsAccount.user_id == user_id)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()
    if not account:
        account = PointsAccount(user_id=user_id, account_type="user")
        db.add(account)
        await db.flush()
        # refresh 获取 server_default 生成的 created_at / updated_at
        await db.refresh(account)
    # 检查是否需要重置年度统计
    current_year = datetime.now(timezone.utc).year
    if account.year_updated != current_year:
        account.year_earned = 0
        account.year_spent = 0
        account.year_updated = current_year
        await db.flush()
    return account


# ── 积分变更 ──

async def earn_points(
    db: AsyncSession,
    user_id: str,
    source: str,
    amount: int | None = None,
    reference_id: str | None = None,
    description: str | None = None,
) -> PointsTransaction | None:
    """给用户增加积分（正数=获得, 负数=扣减）"""
    account = await ensure_account(db, user_id)

    # 如果未指定金额，从规则表读取
    if amount is None:
        stmt = select(PointsRule).where(
            PointsRule.action == source,
            PointsRule.is_active.is_(True),
        )
        result = await db.execute(stmt)
        rule = result.scalar_one_or_none()
        if not rule:
            logger.warning(f"未找到积分规则: source={source}")
            return None
        amount = rule.points
        description = description or rule.description

        # 检查每日/每周限额
        if rule.limit_daily or rule.limit_weekly:
            now = datetime.now(timezone.utc)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            count_stmt = select(func.count()).select_from(PointsTransaction).where(
                PointsTransaction.account_id == account.id,
                PointsTransaction.source == source,
                PointsTransaction.created_at >= today_start,
            )
            count_result = await db.execute(count_stmt)
            daily_count = count_result.scalar() or 0
            if rule.limit_daily and daily_count >= rule.limit_daily:
                logger.info(f"已达每日上限: source={source}, user={user_id}")
                return None

    if not description:
        description = f"积分{'奖励' if amount >= 0 else '扣减'}: {source}"

    new_balance = account.balance + amount
    if new_balance < 0:
        new_balance = 0
        amount = -account.balance  # 最多扣到 0

    transaction = PointsTransaction(
        account_id=account.id,
        user_id=user_id,
        amount=amount,
        transaction_type="earn" if amount >= 0 else "penalty",
        source=source,
        reference_id=reference_id,
        description=description,
        balance_after=new_balance,
    )
    db.add(transaction)

    # 更新账户
    account.balance = new_balance
    if amount > 0:
        account.total_earned += amount
        account.year_earned += amount
    else:
        account.total_spent += abs(amount)
        account.year_spent += abs(amount)
    account.level = compute_level(new_balance)

    await db.flush()
    return transaction


# ── 商城兑换 ──

async def redeem_item(
    db: AsyncSession,
    user_id: str,
    item_id: str,
) -> dict:
    """积分兑换商品"""
    # 获取商品
    stmt = select(PointsMallItem).where(
        PointsMallItem.id == item_id,
        PointsMallItem.is_active.is_(True),
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        return {"success": False, "error": "商品不存在或已下架"}

    # 检查库存
    if item.stock == 0:
        return {"success": False, "error": "商品已售罄"}
    if item.stock > 0:
        item.stock -= 1

    # 检查积分
    account = await ensure_account(db, user_id)
    if account.balance < item.points_required:
        return {"success": False, "error": f"积分不足，需要 {item.points_required} 积分，当前余额 {account.balance}"}

    # 扣减积分
    account.balance -= item.points_required
    account.total_spent += item.points_required
    account.year_spent += item.points_required
    account.level = compute_level(account.balance)

    # 积分流水
    txn = PointsTransaction(
        account_id=account.id,
        user_id=user_id,
        amount=-item.points_required,
        transaction_type="redeem",
        source="redeem_" + (item.category or "item"),
        reference_id=item_id,
        description=f"兑换: {item.name}",
        balance_after=account.balance,
    )
    db.add(txn)

    # 生成折扣码（如果是折扣类）
    discount_code = None
    if item.category in ("discount", "coupon", "vip"):
        discount_code = f"SK{item.category[:3].upper()}-{secrets.token_hex(4).upper()}"

    # 兑换记录
    redemption = PointsRedemption(
        user_id=user_id,
        account_id=account.id,
        item_id=item.id,
        item_name=item.name,
        points_spent=item.points_required,
        discount_code=discount_code,
        discount_type=item.discount_type,
        discount_value=item.discount_value,
        discount_max=item.discount_max,
        expires_at=datetime.now(timezone.utc) + timedelta(days=item.validity_days) if item.validity_days else None,
        status="active",
    )
    db.add(redemption)

    await db.flush()
    return {
        "success": True,
        "item_name": item.name,
        "points_spent": item.points_required,
        "balance_after": account.balance,
        "discount_code": discount_code,
        "redemption_id": redemption.id,
    }


# ── 排名 ──

async def recompute_ranking(
    db: AsyncSession,
    year: int | None = None,
    category: str = "overall",
) -> int:
    """重新计算积分排名"""
    if year is None:
        year = datetime.now(timezone.utc).year

    # 按 year_earned 降序排列，按角色分组
    stmt = (
        select(PointsAccount)
        .where(PointsAccount.account_type == "user", PointsAccount.year_earned > 0)
        .order_by(desc(PointsAccount.year_earned))
    )
    result = await db.execute(stmt)
    accounts = result.scalars().all()

    # 清空旧排名
    delete_stmt = select(PointsRanking).where(
        PointsRanking.year == year,
        PointsRanking.category == category,
    )
    del_result = await db.execute(delete_stmt)
    for old in del_result.scalars().all():
        await db.delete(old)

    # 按角色分组排名
    role_ranks: dict[str, int] = {}
    rankings = []
    for account in accounts:
        user_stmt = select(User).where(User.id == account.user_id)
        user_result = await db.execute(user_stmt)
        user = user_result.scalar_one_or_none()
        role = user.role if user else "homeowner"

        role_ranks.setdefault(role, 0)
        role_ranks[role] += 1

        rankings.append(PointsRanking(
            user_id=account.user_id,
            role=role,
            year=year,
            category=category,
            year_earned=account.year_earned,
            rank=role_ranks[role],
        ))

    db.add_all(rankings)
    await db.flush()
    return len(rankings)


async def get_ranking(
    db: AsyncSession,
    role: str | None = None,
    year: int | None = None,
    category: str = "overall",
    limit: int = 50,
) -> list[dict]:
    """获取排行榜"""
    if year is None:
        year = datetime.now(timezone.utc).year

    conditions = [PointsRanking.year == year, PointsRanking.category == category]
    if role:
        conditions.append(PointsRanking.role == role)

    stmt = (
        select(PointsRanking, User.name, PointsAccount.level)
        .join(User, PointsRanking.user_id == User.id)
        .join(PointsAccount, PointsAccount.user_id == PointsRanking.user_id)
        .where(*conditions)
        .order_by(PointsRanking.rank)
        .limit(limit)
    )
    result = await db.execute(stmt)
    items = result.all()

    return [
        {
            "user_id": r.user_id,
            "user_name": name,
            "role": r.role,
            "year_earned": r.year_earned,
            "rank": r.rank,
            "level": level,
        }
        for r, name, level in items
    ]
