"""营销获客 Agent — 多渠道推广素材生成

借鉴义乌「AI 包揽内容产出」模式：小红书图文/抖音短视频脚本/朋友圈文案。
LLM 生成 + 诚实降级（无 key 时 _chat 返回 mock，解析失败原样返回草稿，不伪装）。
"""

import json
import logging

from app.agents.base import BaseAgent
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_CHANNEL_MAP = {
    "xiaohongshu": "小红书图文（标题+正文+话题标签，种草风格）",
    "douyin": "抖音短视频脚本（前3秒钩子+正文+引导互动，口语化）",
    "moments": "朋友圈文案（简洁+九宫格配文建议）",
}


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


class MarketingAgent(BaseAgent):
    agent_name = "marketing"
    cost_tier = "economy"
    system_prompt = """你是索克家居（i-home.life）平台营销获客 Agent。

你的职责：
1. 生成多渠道推广素材（小红书图文/抖音短视频脚本/朋友圈文案）
2. 基于装修案例生成传播内容
3. A/B 测试标题建议
4. 诚实标注：素材为 AI 生成草稿，需人工审核后发布

请用中文输出，风格贴近家居装修场景。"""

    async def generate_content(self, case_summary: str, channel: str = "xiaohongshu") -> dict:
        """生成单条营销素材（LLM 优先，失败/非 JSON 原样返回草稿，诚实标注）

        Args:
            case_summary: 装修案例摘要（户型/风格/亮点/预算）
            channel: xiaohongshu / douyin / moments
        """
        if not settings.marketing_agent_enabled:
            return {"enabled": False, "note": "marketing_agent_enabled=False"}

        channel_desc = _CHANNEL_MAP.get(channel, _CHANNEL_MAP["xiaohongshu"])
        prompt = (
            f"基于以下装修案例生成{channel_desc}：\n\n{case_summary}\n\n"
            "必须只输出如下 JSON（不要输出任何其他文字）：\n"
            '{"title": "标题", "body": "正文", "tags": ["标签1","标签2"], '
            '"hook": "前3秒钩子（视频专用，图文可空）"}'
        )
        try:
            reply = await self._chat([
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ])
        except Exception as e:
            logger.warning("marketing.generate_content: LLM 调用失败: %s", e)
            return {
                "enabled": True,
                "channel": channel,
                "content_source": "error",
                "note": f"LLM 调用失败: {e}",
            }

        parsed = _parse_json_reply(reply)
        if parsed is None:
            return {
                "enabled": True,
                "channel": channel,
                "content_source": "raw",
                "raw_reply": (reply[:500] if isinstance(reply, str) else ""),
                "note": "LLM 返回非 JSON，已原样返回草稿，需人工整理",
            }

        parsed["channel"] = channel
        parsed["content_source"] = "llm"
        parsed["note"] = "AI 生成草稿，需人工审核后发布"
        return parsed
