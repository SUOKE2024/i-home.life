"""增长分析 Agent — 平台功能使用率周报 + Agent 调用统计 + 零使用预警

借鉴 Polsia 增长智能体（跟踪 KPI、优化转化）+ 义乌「AI 嵌入生意每一环」运营思维。

数据源诚实标注：
- 统计基于 agent_feedbacks 表（用户主动反馈 like/dislike/rating）；
- 调用次数统计需解析 chat_messages.auto_reply_meta，本期周报先给反馈分布；
- 无反馈的 Agent 不代表零使用，仅代表零反馈。
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


class GrowthAgent(BaseAgent):
    agent_name = "growth"
    # 周报分析为离线低频任务，用 economy 档降低成本（受 cost_tiered_routing_enabled 控制）
    cost_tier = "economy"
    system_prompt = """你是索克家居（i-home.life）平台增长分析 Agent。

你的职责：
1. 统计各 Agent 的用户反馈分布（like/dislike/评分）
2. 识别高满意度与低满意度 Agent，输出优化建议
3. 生成平台功能使用率周报
4. 识别低反馈 Agent 并给出优化建议（基于 agent_feedbacks，数据源限制见下方标注）

数据源诚实标注：统计基于 agent_feedbacks 表；调用次数需解析 chat_messages.auto_reply_meta，
本期周报先给反馈分布，未覆盖无反馈但有调用的场景。"""

    async def generate_weekly_report(self, db: AsyncSession, days: int = 7) -> dict:
        """生成功能使用率周报（规则路径，基于 AgentFeedback 表统计）

        诚实标注：
        - data_source="agent_feedbacks"（非全量调用日志）
        - 调用次数统计需解析 auto_reply_meta，本期仅给反馈分布
        - 无反馈的 Agent 不代表零使用，仅代表零反馈
        """
        if not settings.growth_agent_enabled:
            return {
                "enabled": False,
                "note": "growth_agent_enabled=False，周报未生成",
            }

        since = datetime.now(timezone.utc) - timedelta(days=days)

        try:
            from sqlalchemy import select, func
            from app.models.agent_feedback import AgentFeedback

            stmt = (
                select(
                    AgentFeedback.agent_name,
                    AgentFeedback.feedback_type,
                    func.count().label("count"),
                    func.avg(AgentFeedback.rating).label("avg_rating"),
                )
                .where(AgentFeedback.created_at >= since)
                .group_by(AgentFeedback.agent_name, AgentFeedback.feedback_type)
            )
            result = await db.execute(stmt)
            rows = result.all()
        except Exception as e:
            logger.warning("growth.generate_weekly_report: 查询失败: %s", e)
            return {
                "enabled": True,
                "error": str(e),
                "note": "查询失败，周报未生成",
                "data_source": "agent_feedbacks",
            }

        # 组装反馈分布
        feedback_dist: dict[str, dict] = {}
        for row in rows:
            agent = row.agent_name
            if agent not in feedback_dist:
                feedback_dist[agent] = {
                    "like": 0, "dislike": 0, "avg_rating": None, "total": 0,
                }
            ftype = row.feedback_type if row.feedback_type in ("like", "dislike") else "dislike"
            feedback_dist[agent][ftype] = int(row.count)
            feedback_dist[agent]["total"] += int(row.count)
            if row.avg_rating is not None:
                feedback_dist[agent]["avg_rating"] = round(float(row.avg_rating), 2)

        # 识别高低满意度（按 like - dislike 排序）
        ranked = sorted(
            feedback_dist.items(),
            key=lambda x: (x[1]["like"] - x[1]["dislike"]),
            reverse=True,
        )
        top_agents = [{"agent": a, **d} for a, d in ranked[:3] if d["like"] > 0]
        bottom_agents = [{"agent": a, **d} for a, d in ranked[-3:] if d["dislike"] > 0]

        return {
            "enabled": True,
            "period_days": days,
            "generated_at": datetime.now(_BJ_TZ).isoformat(),
            "data_source": "agent_feedbacks",
            "feedback_distribution": feedback_dist,
            "top_agents": top_agents,
            "bottom_agents": bottom_agents,
            "total_feedback_count": sum(d["total"] for d in feedback_dist.values()),
            "note": (
                "数据源为 agent_feedbacks 表（用户主动反馈）。"
                "调用次数统计需解析 chat_messages.auto_reply_meta，本期未覆盖。"
                "无反馈的 Agent 不代表零使用，仅代表零反馈。"
            ),
        }
