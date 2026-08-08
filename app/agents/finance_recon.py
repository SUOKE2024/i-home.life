"""平台财务对账 Agent — 平台抽成收入/广告支出追踪

区别于 settlement.py（工程结算，面向用户交付）；本 Agent 面向平台自身财务。

借鉴 Polsia 财务智能体（Stripe 对账 + 追踪收入成本）。

数据源诚实标注：基于平台内部 payment/escrow 表统计；
无 Stripe/广告平台实时对接时标注为平台内部账，非外部账单核对。
表/字段不匹配时 best-effort 降级，不伪装数据。
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# 业务时区（平台业务时区为北京时间，对齐 agent_context_service._DEFAULT_TZ）
_BJ_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")


class FinanceReconAgent(BaseAgent):
    agent_name = "finance_recon"
    cost_tier = "economy"
    system_prompt = """你是索克家居（i-home.life）平台财务对账 Agent。

你的职责：
1. 统计平台抽成收入（按时间段/项目）
2. 追踪广告支出（如有）
3. 生成财务对账简报
4. 诚实标注：区别于 settlement 工程结算，本 Agent 面向平台自身财务

请用中文回复。"""

    async def generate_recon_report(self, db: AsyncSession, days: int = 30) -> dict:
        """生成平台财务对账简报

        诚实标注：数据源为平台内部 payment/escrow 表；无 Stripe/广告平台实时对接，
        非外部账单核对。表/字段不匹配时 best-effort 跳过并标注。
        """
        if not settings.finance_recon_agent_enabled:
            return {"enabled": False, "note": "finance_recon_agent_enabled=False"}

        since = datetime.now(timezone.utc) - timedelta(days=days)
        report: dict = {
            "enabled": True,
            "period_days": days,
            "generated_at": datetime.now(_BJ_TZ).isoformat(),
            "data_source": "internal_tables",
            "note": (
                "基于平台内部 payment/escrow 表统计；无 Stripe/广告平台实时对接，"
                "非外部账单核对"
            ),
        }

        # payment 统计（best-effort：表/字段不匹配时降级标注，不阻断）
        try:
            from sqlalchemy import select, func
            from app.models.payment import Payment  # type: ignore

            stmt = (
                select(func.count(), func.coalesce(func.sum(Payment.amount), 0))
                .where(Payment.created_at >= since)
            )
            row = (await db.execute(stmt)).one_or_none()
            if row:
                report["payment_count"] = int(row[0] or 0)
                report["payment_total"] = float(row[1] or 0)
        except Exception as e:
            logger.debug("finance_recon: payment 统计失败: %s", e)
            report["payment_note"] = f"payment 表查询失败: {e}"

        # escrow 统计（best-effort）
        try:
            from sqlalchemy import select, func
            from app.models.escrow import EscrowOrder  # type: ignore

            stmt = (
                select(func.count(), func.coalesce(func.sum(EscrowOrder.amount), 0))
                .where(EscrowOrder.created_at >= since)
            )
            row = (await db.execute(stmt)).one_or_none()
            if row:
                report["escrow_count"] = int(row[0] or 0)
                report["escrow_total"] = float(row[1] or 0)
        except Exception as e:
            logger.debug("finance_recon: escrow 统计失败: %s", e)
            report["escrow_note"] = f"escrow 表查询失败: {e}"

        return report
