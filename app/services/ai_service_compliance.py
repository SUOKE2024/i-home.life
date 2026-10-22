"""AI 服务合规闸门 —— 拟人化互动 + 金融边界（AI 产品治理 · 契约 1，2026-10-15）

依据《人工智能拟人化互动服务管理暂行办法》（国家网信办等五部门令第 21 号，2026-07-15 施行：
提供拟人化互动服务的经营者应明确告知用户其正在与 AI 而非真人交互）与证券投资顾问相关资质要求。

与 ``health_claim_compliance`` 的分工（两模块正交，可在同一输出路径串联，见 ``app/agents/care.py``）：
- ``health_claim_compliance``：健康**功效宣称**（治疗/降压/降糖/康复率…）→ 阻断或附加免责声明
- 本模块：① 拟人化 **自称真人 / 情感陪伴承诺** → 阻断；② 金融**收益承诺 / 荐股** → 阻断

受 ``settings.ai_service_compliance_enabled`` 控制（默认 True）；关闭即放行并诚实标注
``gate_enabled=False``，不伪装已校验。口径文件 ``assets/legal/ai-service-compliance-notice.md``。
"""
from __future__ import annotations

import logging

from app.config import get_settings

logger = logging.getLogger(__name__)

# ── prohibited：拟人化红线（自称真人 / 情感陪伴承诺，命中即阻断）──
PROHIBITED_PERSONIFICATION_PHRASES: frozenset[str] = frozenset({
    "我是真人", "我是人类", "我不是AI", "我不是 AI", "我不是人工智能",
    "我是你的男朋友", "我是你的女朋友", "我是你的恋人", "我是你的老公", "我是你的老婆",
    "我永远不会离开你", "我绝不会离开你", "我只属于你", "我是真实的人",
})

# ── caution：拟人化软化表达（放行 + 附加 AI 身份声明）──
CAUTION_PERSONIFICATION_PHRASES: frozenset[str] = frozenset({
    "我一直陪着你", "我会一直陪着你", "随时陪你聊天", "我懂你的感受",
    "只有我懂你", "我会想你的",
})

# ── prohibited：金融红线（收益承诺 / 荐股，命中即阻断）──
PROHIBITED_FINANCE_PHRASES: frozenset[str] = frozenset({
    "保证收益", "保本高收益", "稳赚不赔", "包赚不赔", "必赚",
    "投资回报率保证", "保证年化", "内幕消息", "荐股", "帮你炒股",
})

# ── 否定语境标记：命中词前 N 字符内出现即视为免责表述，不计为违规 ──
NEGATION_MARKERS: tuple[str, ...] = (
    "不具", "不具有", "不替代", "不构成", "不得", "不能", "不是", "不含",
    "非", "无", "禁止", "没有", "避免", "拒绝", "并非",
)
_NEGATION_LOOKBEHIND = 8

STANDARD_AI_DISCLOSURE = (
    "以上内容由 AI 智能体生成，非真人回复，不构成医疗诊断或投资建议；"
    "如需专业意见请咨询相应资质的机构或人员。"
)

# 红线命中后的统一安全回复（Agent 出口与 CareAgent 共用单一文案源）。
SAFE_SERVICE_BLOCK_REPLY = (
    "检测到该回复含拟人化或金融红线表述，已按合规口径拦截。"
    "本服务为 AI 智能体（非真人），仅提供空间环境与生活方式建议，"
    "不构成医疗诊断或投资建议；如需专业意见请咨询相应资质的机构或人员。"
)


def is_gate_enabled() -> bool:
    """合规闸门是否开启（flag 关闭时调用方须诚实标注未校验）。"""
    return bool(getattr(get_settings(), "ai_service_compliance_enabled", True))


def _in_negation_context(text: str, start: int) -> bool:
    """判断 text[start] 处的命中词是否处于否定/免责语境。"""
    window_start = max(0, start - _NEGATION_LOOKBEHIND)
    window = text[window_start:start]
    return any(marker in window for marker in NEGATION_MARKERS)


def scan_service_claims(text: str) -> list[dict]:
    """扫描拟人化与金融红线声明。

    Returns:
        [{"term": str, "severity": "prohibited"|"caution", "category": "personification"|"finance",
          "position": int}]；否定语境（免责声明自身）中的词不计为命中。
    """
    if not text:
        return []

    scan_text = text.replace(STANDARD_AI_DISCLOSURE, "")

    rules = (
        [(w, "prohibited", "personification") for w in PROHIBITED_PERSONIFICATION_PHRASES]
        + [(w, "caution", "personification") for w in CAUTION_PERSONIFICATION_PHRASES]
        + [(w, "prohibited", "finance") for w in PROHIBITED_FINANCE_PHRASES]
    )

    claims: list[dict] = []
    seen: set[tuple[str, str, int]] = set()
    for word, severity, category in rules:
        start = scan_text.find(word)
        while start != -1:
            key = (word, category, start)
            if key not in seen and not _in_negation_context(scan_text, start):
                seen.add(key)
                claims.append({"term": word, "severity": severity,
                               "category": category, "position": start})
            start = scan_text.find(word, start + 1)

    claims.sort(key=lambda c: c["position"])
    return claims


def ensure_service_compliance(text: str, *, append_disclaimer: bool = True) -> dict:
    """AI 服务合规闸门（拟人化互动 + 金融边界）。

    Args:
        text: 待检文案（AI 输出）
        append_disclaimer: caution 命中时是否附加标准 AI 身份声明

    Returns:
        {
          "gate_enabled": bool,     # False 时未做校验（诚实标注）
          "compliant": bool,        # 无 prohibited 命中
          "blocked": bool,          # prohibited 命中 → 阻断
          "claims": [...],          # 命中明细
          "text": str,              # 处理后的安全文案
          "blocked_reason": str,    # 仅 blocked 时有意义
        }
    """
    if not is_gate_enabled():
        return {
            "gate_enabled": False,
            "compliant": True,
            "blocked": False,
            "claims": [],
            "text": text,
            "blocked_reason": "ai_service_compliance_enabled=False，未执行合规校验",
        }

    claims = scan_service_claims(text)
    prohibited = [c for c in claims if c["severity"] == "prohibited"]
    caution = [c for c in claims if c["severity"] == "caution"]

    if prohibited:
        hit_terms = ", ".join(c["term"] for c in prohibited[:5])
        logger.info("ai_service_blocked: 命中红线词=%s 数量=%d", hit_terms, len(prohibited))
        return {
            "gate_enabled": True,
            "compliant": False,
            "blocked": True,
            "claims": claims,
            "text": "",
            "blocked_reason": f"含拟人化/金融红线表述（{hit_terms}），已阻断输出",
        }

    if caution and append_disclaimer and STANDARD_AI_DISCLOSURE not in text:
        return {
            "gate_enabled": True,
            "compliant": True,
            "blocked": False,
            "claims": claims,
            "text": f"{text}\n\n{STANDARD_AI_DISCLOSURE}",
            "blocked_reason": "",
        }

    return {
        "gate_enabled": True,
        "compliant": True,
        "blocked": False,
        "claims": claims,
        "text": text,
        "blocked_reason": "",
    }


# ── 能力合规分级台账（契约 1；供 agent_tool_registry 注册时派生）──
# 索克居家居当前工具均属「物理空间/装修」域，无卫生健康或金融边界；卫生边界在 agent 输出层
# 由 health_claim_compliance 承担，拟人化/金融边界由本模块 ensure_service_compliance 承担。
_SAFE: dict = {"personification": False, "health": False, "finance": False, "notice": ""}

_CATEGORY_CLASSIFICATION: dict[str, dict] = {
    "budget": _SAFE,
    "design": _SAFE,
    "procurement": _SAFE,
    "construction": _SAFE,
    "qa": _SAFE,
    "location": _SAFE,
    "orchestration": _SAFE,
    "design_proposal": _SAFE,
    "admin": _SAFE,
    "general": _SAFE,
}


def classify_tool(name: str, category: str) -> dict:
    """返回单个工具的合规分级；未登记 category → ``classified=False``（调用方 fail-closed）。"""
    base = _CATEGORY_CLASSIFICATION.get((category or "").strip().lower())
    if base is None:
        return {"classified": False, "source": "unclassified",
                "personification": None, "health": None, "finance": None, "notice": None}
    return {"classified": True, "source": "category", **base}


def unclassified_categories(categories) -> list[str]:
    """返回未登记分级的 category 列表（为空即台账完整）。"""
    return sorted({c for c in categories if not classify_tool("", c)["classified"]})


def known_categories() -> list[str]:
    """已登记的 category 清单。"""
    return sorted(_CATEGORY_CLASSIFICATION)
