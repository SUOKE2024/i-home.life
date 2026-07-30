"""设计方案生成与修订服务（讨论式方案交互）

v1.2.8 借鉴 Qwen-Audio-3.0-Realtime "能聊天更能办事" 范式：
- LLM 根据自然语言描述生成 2-3 套设计方案
- 支持基于语音调整指令（"方案B加中岛"）增量修订
- LLM 不可用时降级到 DesignerAgent.generate_layouts 确定性算法（单方案）

复用 app/agents/base.py 的 PROVIDER_REGISTRY fallback chain（deepseek→glm→qwen）。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.agents.base import PROVIDER_REGISTRY
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# LLM fallback chain 顺序（对齐 voice.py 的 _VOICE_LLM_FALLBACK_CHAIN）
_PROPOSAL_LLM_CHAIN = ["deepseek", "glm", "qwen"]

# 方案生成 system prompt
_PROPOSAL_GEN_SYSTEM = """你是装修设计专家。根据用户需求生成 2-3 套差异化设计方案。

输出严格 JSON 格式（不要 markdown code block，不要额外文字）：
{
  "proposals": [
    {
      "proposal_id": "A",
      "title": "紧凑型",
      "layout_type": "L型",
      "area_sqm": 5.2,
      "budget_cny": 18000,
      "highlights": ["动线紧凑", "储物充足"],
      "rationale": "适合小户型，最大化利用空间"
    },
    {
      "proposal_id": "B",
      "title": "标准型",
      "layout_type": "U型",
      "area_sqm": 6.8,
      "budget_cny": 24000,
      "highlights": ["操作台面大", "动线流畅"],
      "rationale": "平衡空间与功能"
    }
  ]
}

要求：
- 2-3 套方案，proposal_id 用 A/B/C
- 每套方案 title/layout_type/area_sqm/budget_cny/highlights 必填
- 方案间差异化（布局/面积/预算/亮点均不同）
- 预算合理（参考：厨房 1.5-4 万，客厅 2-6 万，卫生间 0.8-2 万）"""

# 方案修订 system prompt
_PROPOSAL_REVISE_SYSTEM = """你是装修设计专家。用户要对已有方案做调整。

当前方案列表（JSON）：
{existing_proposals}

用户调整指令：{change_instruction}

输出严格 JSON 格式（仅返回被修改方案的完整新版本，不要 markdown code block）：
{{
  "proposal_id": "B",
  "title": "标准型",
  "layout_type": "U型+中岛",
  "area_sqm": 7.2,
  "budget_cny": 28000,
  "highlights": ["操作台面大", "动线流畅", "增加中岛"],
  "rationale": "在标准型基础上增加中岛，扩展备餐与社交功能",
  "change_log": ["加中岛（用户语音）"]
}}

要求：
- 只返回被修改的那一套方案（通过 proposal_id 匹配）
- change_log 记录本次修改摘要
- 其余字段保持与原方案风格一致"""


class ProposalSpec(BaseModel):
    """单套设计方案"""

    proposal_id: str = Field(..., description="方案标识 A/B/C")
    title: str = Field(..., description="方案标题：紧凑型/标准型/豪华型")
    layout_type: str = Field(..., description="布局类型：L型/U型/岛型等")
    area_sqm: float = Field(..., description="面积（平方米）")
    budget_cny: int = Field(..., description="预算（元）")
    highlights: list[str] = Field(default_factory=list, description="亮点列表")
    rationale: str = Field(default="", description="设计理由")
    change_log: list[str] = Field(default_factory=list, description="修订历史")
    source: str = Field("llm", description="来源：llm | fallback")


class ProposalSet(BaseModel):
    """方案集合（生成结果）"""

    proposals: list[ProposalSpec]
    session_id: str = Field("", description="关联的语音会话 ID")


# ── 内存级方案存储（按 session_id 索引）──
# 讨论式交互需要跨轮保留方案上下文供修订。
# 生产可换 Redis；当前单实例内存足够（语音会话 TTL 1 小时）。
_proposal_store: dict[str, list[ProposalSpec]] = {}


def _store_proposals(session_id: str, proposals: list[ProposalSpec]) -> None:
    """缓存方案供后续修订"""
    if session_id:
        _proposal_store[session_id] = proposals


def _get_proposals(session_id: str) -> list[ProposalSpec]:
    """读取缓存的方案"""
    return _proposal_store.get(session_id, [])


def _parse_llm_json(content: str) -> dict | None:
    """从 LLM 响应中解析 JSON（兼容 markdown code block 与裸 JSON）"""
    if not content:
        return None
    candidates = [content]
    code_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if code_match:
        candidates.insert(0, code_match.group(1))
    json_match = re.search(r"\{.*\}", content, re.DOTALL)
    if json_match and json_match.group() not in candidates:
        candidates.insert(0, json_match.group())
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


async def _call_llm(system_prompt: str, user_prompt: str) -> str | None:
    """调用 LLM（fallback chain），返回文本响应或 None"""
    for provider in _PROPOSAL_LLM_CHAIN:
        cfg = PROVIDER_REGISTRY[provider]
        api_key = cfg["api_key"]()
        if not api_key:
            continue
        try:
            async with httpx.AsyncClient(
                base_url=cfg["api_base"](),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                timeout=httpx.Timeout(30.0),
            ) as client:
                response = await client.post(
                    cfg["chat_path"],
                    json={
                        "model": cfg["model"](),
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.7,
                        "max_tokens": 1024,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"].get("content", "").strip()
        except Exception as e:
            logger.warning("design_proposal: LLM %s 调用失败: %s", provider, e)
    return None


async def generate_proposals(
    user_requirement: str, session_id: str = ""
) -> ProposalSet:
    """生成 2-3 套设计方案

    Args:
        user_requirement: 用户自然语言需求（"帮我设计厨房"）
        session_id: 关联语音会话 ID，供后续修订

    Returns:
        ProposalSet 含 2-3 套方案；LLM 不可用时降级到 DesignerAgent 单方案
    """
    if not settings.design_proposal_llm_enabled:
        proposals = [_fallback_proposal(user_requirement)]
        _store_proposals(session_id, proposals)
        return ProposalSet(proposals=proposals, session_id=session_id)

    content = await _call_llm(_PROPOSAL_GEN_SYSTEM, user_requirement)
    if not content:
        logger.warning("design_proposal: LLM 全链路不可用，降级到 fallback 单方案")
        proposals = [_fallback_proposal(user_requirement)]
    else:
        parsed = _parse_llm_json(content)
        if not parsed or "proposals" not in parsed:
            logger.warning("design_proposal: LLM 响应无法解析: %s", content[:200])
            proposals = [_fallback_proposal(user_requirement)]
        else:
            proposals = []
            for item in parsed["proposals"]:
                try:
                    proposals.append(ProposalSpec(**item, source="llm"))
                except Exception as e:
                    logger.warning("design_proposal: 方案解析失败: %s", e)

    if not proposals:
        proposals = [_fallback_proposal(user_requirement)]

    _store_proposals(session_id, proposals)
    return ProposalSet(proposals=proposals, session_id=session_id)


async def revise_proposal(
    proposal_id: str, change_instruction: str, session_id: str = ""
) -> ProposalSpec | None:
    """修订指定方案

    Args:
        proposal_id: 要修订的方案 ID（A/B/C）
        change_instruction: 用户调整指令（"加中岛"）
        session_id: 语音会话 ID，用于读取历史方案

    Returns:
        修订后的 ProposalSpec；找不到原方案或 LLM 不可用返回 None
    """
    existing = _get_proposals(session_id)
    if not existing:
        logger.warning("design_proposal: session=%s 无历史方案", session_id)
        return None

    target = next((p for p in existing if p.proposal_id == proposal_id), None)
    if target is None:
        logger.warning("design_proposal: 方案 %s 不存在", proposal_id)
        return None

    if not settings.design_proposal_llm_enabled:
        # flag 关闭：简单追加 change_log，不改字段
        target.change_log.append(f"{change_instruction}（本地降级，未调 LLM）")
        return target

    existing_json = json.dumps(
        [p.model_dump() for p in existing], ensure_ascii=False
    )
    system = _PROPOSAL_REVISE_SYSTEM.format(
        existing_proposals=existing_json,
        change_instruction=change_instruction,
    )
    content = await _call_llm(system, change_instruction)
    if not content:
        logger.warning("design_proposal: 修订 LLM 不可用，返回原方案")
        return target

    parsed = _parse_llm_json(content)
    if not parsed:
        return target

    try:
        revised = ProposalSpec(**parsed, source="llm")
        # 更新内存中的方案
        for i, p in enumerate(existing):
            if p.proposal_id == proposal_id:
                existing[i] = revised
                break
        _store_proposals(session_id, existing)
        return revised
    except Exception as e:
        logger.warning("design_proposal: 修订结果解析失败: %s", e)
        return target


def _fallback_proposal(requirement: str) -> ProposalSpec:
    """LLM 不可用时的降级单方案（确定性）"""
    return ProposalSpec(
        proposal_id="A",
        title="标准型",
        layout_type="L型",
        area_sqm=6.0,
        budget_cny=20000,
        highlights=["动线合理", "储物充足"],
        rationale=f"基于「{requirement[:30]}」的标准方案（LLM 降级，确定性生成）",
        source="fallback",
    )
