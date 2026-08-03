"""积分系统 API — 积分账户、流水、排名、商城、兑换"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.points import (
    PointsTransaction, PointsRule,
    PointsMallItem, PointsRedemption,
)
from app.auth import get_current_user
from app.rbac import allow_admin
from app.schemas.points import (
    PointsAccountResponse, PointsTransactionResponse,
    PointsRuleResponse, PointsMallItemResponse,
    RedemptionRequest, RedemptionResponse,
    PointsEarnRequest, RankingResponse,
)
from app.services import points_service

router = APIRouter(prefix="/points", tags=["积分系统"])


# ── 账户 ──

@router.get("/account", response_model=PointsAccountResponse)
async def get_my_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户积分账户"""
    account = await points_service.ensure_account(db, current_user.id)
    return PointsAccountResponse.model_validate(account)


@router.get("/account/{user_id}", response_model=PointsAccountResponse)
async def get_user_account(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查看指定用户的积分账户"""
    account = await points_service.ensure_account(db, user_id)
    return PointsAccountResponse.model_validate(account)


# ── 流水 ──

@router.get("/transactions", response_model=list[PointsTransactionResponse])
async def get_transactions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """获取当前用户积分流水"""
    account = await points_service.ensure_account(db, current_user.id)
    stmt = (
        select(PointsTransaction)
        .where(PointsTransaction.account_id == account.id)
        .order_by(desc(PointsTransaction.created_at))
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    transactions = result.scalars().all()
    return [PointsTransactionResponse.model_validate(t) for t in transactions]


# ── 规则 ──

@router.get("/rules", response_model=list[PointsRuleResponse])
async def get_rules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取积分规则列表"""
    stmt = select(PointsRule).where(PointsRule.is_active.is_(True))
    result = await db.execute(stmt)
    rules = result.scalars().all()
    return [PointsRuleResponse.model_validate(r) for r in rules]


# ── 积分增减（内部/管理员调用） ──

@router.post("/earn", response_model=PointsTransactionResponse)
async def earn_points(
    data: PointsEarnRequest,
    current_user: User = Depends(allow_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理员手动调整积分"""
    txn = await points_service.earn_points(
        db,
        user_id=data.user_id,
        source=data.source,
        amount=data.amount,
        reference_id=data.reference_id,
        description=data.description,
    )
    if not txn:
        raise HTTPException(status_code=400, detail="积分变更失败，检查规则配置")
    return PointsTransactionResponse.model_validate(txn)


# ── 商城 ──

@router.get("/mall", response_model=list[PointsMallItemResponse])
async def get_mall_items(
    category: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取积分商城商品列表"""
    conditions = [PointsMallItem.is_active.is_(True)]
    if category:
        conditions.append(PointsMallItem.category == category)

    stmt = (
        select(PointsMallItem)
        .where(*conditions)
        .order_by(PointsMallItem.sort_order, PointsMallItem.points_required)
    )
    result = await db.execute(stmt)
    items = result.scalars().all()
    return [PointsMallItemResponse.model_validate(i) for i in items]


@router.post("/redeem", response_model=RedemptionResponse)
async def redeem_item(
    data: RedemptionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """积分兑换商品"""
    result = await points_service.redeem_item(db, current_user.id, data.item_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "兑换失败"))

    # 获取兑换记录
    stmt = select(PointsRedemption).where(
        PointsRedemption.id == result["redemption_id"]
    )
    db_result = await db.execute(stmt)
    redemption = db_result.scalar_one_or_none()

    if not redemption:
        return RedemptionResponse(
            id=result["redemption_id"],
            user_id=current_user.id,
            item_id=data.item_id,
            item_name=result["item_name"],
            points_spent=result["points_spent"],
        )
    return RedemptionResponse.model_validate(redemption)


@router.get("/redemptions", response_model=list[RedemptionResponse])
async def get_my_redemptions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """获取当前用户兑换记录"""
    stmt = (
        select(PointsRedemption)
        .where(PointsRedemption.user_id == current_user.id)
        .order_by(desc(PointsRedemption.created_at))
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    redemptions = result.scalars().all()
    return [RedemptionResponse.model_validate(r) for r in redemptions]


# ── 排名 ──

@router.get("/ranking", response_model=list[RankingResponse])
async def get_ranking(
    role: str | None = Query(None, description="按角色筛选: homeowner / designer / contractor / supplier"),
    year: int | None = Query(None),
    category: str = Query("overall", description="排名分类: overall / design / construction / supply / quality"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, le=100),
):
    """获取年度积分排行榜"""
    rankings = await points_service.get_ranking(db, role=role, year=year, category=category, limit=limit)
    return [RankingResponse(**r) for r in rankings]


@router.post("/ranking/recompute")
async def recompute_ranking(
    year: int | None = None,
    current_user: User = Depends(allow_admin),
    db: AsyncSession = Depends(get_db),
):
    """重新计算排行榜（管理员）"""
    count = await points_service.recompute_ranking(db, year=year)
    return {"message": "排行榜已更新", "count": count}
