"""竞品调研 Agent — 周期性竞品动态监控 + 差异化策略建议

借鉴 Polsia 竞品调研智能体。

诚实标注：无实时爬虫能力，分析基于 LLM 训练数据中的公开信息，
非实时数据，需人工补充最新动态。不伪装实时竞品监控能力。
"""

import json
import logging

from app.agents.base import BaseAgent
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _parse_json_reply(reply) -> dict | None:
    """宽容解析 LLM 回复中的 JSON（支持 ```json 代码块包裹），非法返回 None。"""
    if not isinstance(reply, str):
        return None
    text = reply.strip()
    if text.startswith("```"):
        start = text.find("\n")
        end = text.rfind("```")
        if start != -1 and end > start:
            text = text[start:end].strip()
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


class CompetitorResearchAgent(BaseAgent):
    agent_name = "competitor_research"
    cost_tier = "economy"
    system_prompt = """你是索克家居（i-home.life）平台竞品调研 Agent。

你的职责：
1. 输出竞品调研框架（产品/定价/获客/差异化维度）
2. 基于公开知识生成竞品对比分析
3. 给出索克家居的差异化策略建议

诚实标注：无实时爬虫能力，分析基于 LLM 训练数据中的公开信息，
非实时数据，需人工补充最新动态。"""

    async def generate_research_brief(
        self, competitor_name: str, focus: str = "产品与定价"
    ) -> dict:
        """生成竞品调研简报

        Args:
            competitor_name: 竞品名称（如「酷家乐/三维家/爱空间」）
            focus: 调研焦点（产品与定价/获客与营销/技术架构/差异化）
        """
        if not settings.competitor_research_agent_enabled:
            return {"enabled": False, "note": "competitor_research_agent_enabled=False"}

        prompt = (
            f"针对竞品「{competitor_name}」，聚焦「{focus}」生成调研简报。\n\n"
            "必须只输出如下 JSON（不要输出任何其他文字）：\n"
            '{"competitor": "名称", "focus": "焦点", "product": "产品概述", '
            '"pricing": "定价模式", "strengths": ["优势1","优势2"], '
            '"weaknesses": ["劣势1","劣势2"], '
            '"suoke_differentiation": ["索克可发力点1","索克可发力点2"]}'
        )
        try:
            reply = await self._chat([
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ])
        except Exception as e:
            logger.warning("competitor_research: LLM 调用失败: %s", e)
            return {
                "enabled": True,
                "competitor": competitor_name,
                "data_source": "error",
                "note": f"LLM 调用失败: {e}",
            }

        parsed = _parse_json_reply(reply)
        if parsed is None:
            return {
                "enabled": True,
                "competitor": competitor_name,
                "data_source": "raw",
                "raw_reply": (reply[:500] if isinstance(reply, str) else ""),
                "note": "LLM 返回非 JSON，原样返回草稿",
            }

        parsed["competitor"] = competitor_name
        parsed["focus"] = focus
        parsed["data_source"] = "llm_public_knowledge"
        parsed["note"] = (
            "基于 LLM 训练数据中的公开信息，非实时数据，需人工补充最新动态"
        )
        return parsed
