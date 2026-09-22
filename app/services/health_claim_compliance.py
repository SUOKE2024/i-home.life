"""健康声明合规检查器 — Phase 0（继承索克生活口径，2026-09-13）

背景：项目定位从「AI 智能装修平台」收口为「空间健康资产运营商」后，
康养 / 疗愈 / 旅居 / 适老相关文案成为对外主要输出。此类文案一旦含疗效宣称，
将触发《广告法》《食品安全法》药食同源监管红线，并在索克生活生态回流时
被 `eco_guard` 拦截（prohibited 词命中即阻断，不调 LLM）。

本模块与索克生活 `shared/wellness_claim_compliance` 语义对齐：
- prohibited（疾病治疗/预防/干预红线词）→ 命中即阻断
- caution（保健调理语义）→ 放行但附加标准免责声明
- 否定语境豁免（免责声明自身出现的功效词不误报）

口径文件：`assets/legal/health-claim-disclaimer.md`
受 settings.health_claim_compliance_enabled 控制（默认 True）；
关闭即放行并诚实标注 gate_enabled=False，不伪装已校验。
"""
from __future__ import annotations

import logging

from app.config import get_settings

logger = logging.getLogger(__name__)

# ── prohibited：疾病治疗 / 预防 / 干预红线词（命中即阻断）──
PROHIBITED_CLAIM_WORDS: frozenset[str] = frozenset({
    "治疗", "治愈", "根治", "消炎", "抗癌", "防癌",
    "降压", "降血压", "降糖", "降血糖", "降血脂", "降三高",
    "控糖", "控血糖", "控血脂", "控血压",
    "通便", "减肥", "瘦身", "排毒", "延年益寿", "包治",
    "疗效", "药效", "处方", "医治",
    "康复率", "有效率", "治愈率",
})

# ── caution：保健调理语义（放行 + 附加免责声明）──
CAUTION_CLAIM_WORDS: frozenset[str] = frozenset({
    "调理", "祛湿", "补气", "养血", "安神", "助眠",
    "改善睡眠", "增强免疫", "提高免疫力",
    "缓解疲劳", "舒缓压力", "养生", "滋补", "温补", "活血", "化瘀",
})

# ── 否定语境标记：命中词前 N 字符内出现即视为免责表述，不计为宣称 ──
NEGATION_MARKERS: tuple[str, ...] = (
    "不具", "不具有", "不替代", "不构成", "不得", "不能", "不是", "不含",
    "非", "无", "禁止", "没有", "避免", "拒绝",
)
# 回看窗口（字符数）：覆盖「不具治疗、调理功效」类并列结构
_NEGATION_LOOKBEHIND = 8

STANDARD_HEALTH_DISCLAIMER = (
    "以上内容为空间环境与生活方式建议，不构成医疗诊断或治疗建议，"
    "不替代执业医师面诊。如有健康问题请及时就医。"
)


def is_gate_enabled() -> bool:
    """合规闸门是否开启（flag 关闭时调用方须诚实标注未校验）。"""
    return bool(getattr(get_settings(), "health_claim_compliance_enabled", True))


def _in_negation_context(text: str, start: int) -> bool:
    """判断 text[start] 处的命中词是否处于否定/免责语境。"""
    window_start = max(0, start - _NEGATION_LOOKBEHIND)
    window = text[window_start:start]
    return any(marker in window for marker in NEGATION_MARKERS)


def scan_health_claims(text: str) -> list[dict]:
    """扫描健康功效宣称。

    Returns:
        [{"term": str, "severity": "prohibited"|"caution", "position": int}]
        否定语境（免责声明自身）中的功效词不计为命中。
    """
    if not text:
        return []

    # 标准免责声明自身不参与扫描（避免自我误报）
    scan_text = text.replace(STANDARD_HEALTH_DISCLAIMER, "")

    claims: list[dict] = []
    seen: set[tuple[str, int]] = set()

    for word, severity in (
        [(w, "prohibited") for w in PROHIBITED_CLAIM_WORDS]
        + [(w, "caution") for w in CAUTION_CLAIM_WORDS]
    ):
        start = scan_text.find(word)
        while start != -1:
            key = (word, start)
            if key not in seen and not _in_negation_context(scan_text, start):
                seen.add(key)
                claims.append({"term": word, "severity": severity, "position": start})
            start = scan_text.find(word, start + 1)

    claims.sort(key=lambda c: c["position"])
    return claims


def ensure_health_claim_compliance(
    text: str,
    *,
    append_disclaimer: bool = True,
) -> dict:
    """健康声明合规闸门。

    Args:
        text: 待检文案
        append_disclaimer: caution 命中时是否附加标准免责声明

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
            "blocked_reason": "health_claim_compliance_enabled=False，未执行合规校验",
        }

    claims = scan_health_claims(text)
    prohibited = [c for c in claims if c["severity"] == "prohibited"]
    caution = [c for c in claims if c["severity"] == "caution"]

    if prohibited:
        hit_terms = ", ".join(c["term"] for c in prohibited[:5])
        logger.info(
            "health_claim_blocked: 命中 prohibited 疗效词=%s 数量=%d",
            hit_terms, len(prohibited),
        )
        return {
            "gate_enabled": True,
            "compliant": False,
            "blocked": True,
            "claims": claims,
            "text": "",
            "blocked_reason": f"含疗效宣称红线词（{hit_terms}），已阻断输出",
        }

    if caution and append_disclaimer and STANDARD_HEALTH_DISCLAIMER not in text:
        return {
            "gate_enabled": True,
            "compliant": True,
            "blocked": False,
            "claims": claims,
            "text": f"{text}\n\n{STANDARD_HEALTH_DISCLAIMER}",
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
