"""积分系统模型 — 积分账户、流水、规则、排名、商城、兑换"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, func, Text, Integer, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PointsAccount(Base):
    """积分账户 — 用户和 AI Agent 均有积分账户"""
    __tablename__ = "points_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, unique=True)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    # user / agent

    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_spent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="bronze")
    # bronze / silver / gold / platinum / diamond

    # 年度统计（用于排名）
    year_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    year_spent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    year_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=lambda: datetime.now(timezone.utc).year)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PointsTransaction(Base):
    """积分流水"""
    __tablename__ = "points_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("points_accounts.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # 正数=获得, 负数=扣减
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # earn / spend / penalty / reward / adjust / redeem / bonus
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    # task_complete / quality_review / product_publish / task_claim /
    # first_verify / project_complete / agent_assist / positive_review /
    # complaint / delay / cancel / fake_product / malicious_review /
    # redeem_discount / redeem_coupon / daily_login
    reference_id: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 关联业务 ID
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PointsRule(Base):
    """积分规则"""
    __tablename__ = "points_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    # homeowner / designer / contractor / supplier / agent / all
    points: Mapped[int] = mapped_column(Integer, nullable=False)  # 惩罚为负数
    limit_daily: Mapped[int | None] = mapped_column(Integer, nullable=True)   # 每日上限
    limit_weekly: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 每周上限
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PointsMallItem(Base):
    """积分商城商品"""
    __tablename__ = "points_mall_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False, default="discount")
    # discount(平台服务费折扣) / coupon(优惠券) / vip(会员权益) / physical(实物礼品)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    points_required: Mapped[int] = mapped_column(Integer, nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)  # -1 表示无限

    # 折扣类：discount_value 为折扣比例（如 0.10 表示 10% off）
    discount_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # percentage(比例折扣) / fixed(固定金额减免)
    discount_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount_max: Mapped[float | None] = mapped_column(Float, nullable=True)  # 最大折扣金额

    # 有效期（天）
    validity_days: Mapped[int] = mapped_column(Integer, nullable=False, default=365)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PointsRedemption(Base):
    """积分兑换记录"""
    __tablename__ = "points_redemptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("points_accounts.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("points_mall_items.id"), nullable=False, index=True)
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    points_spent: Mapped[int] = mapped_column(Integer, nullable=False)

    # 折扣兑换详情
    discount_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    discount_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    discount_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    # active / used / expired / refunded

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PointsRanking(Base):
    """积分排行榜缓存 — 按角色/分类定期更新"""
    __tablename__ = "points_rankings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    # homeowner / designer / contractor / supplier
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False, default="overall")
    # overall(总排名) / design / construction / supply / quality / contribution

    year_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)  # 排名

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
