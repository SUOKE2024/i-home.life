"""反合理化反驳引擎（借鉴索克生活 Raven Agent + Guideline-as-Code）

索克生活的 Raven Agent 通过 suoke_model_spec 的 HC 硬约束检测 LLM 输出中的「合理化借口」
并注入反驳提示。本模块将该方法论移植到家居领域：在 Agent 输出后扫描 HC 违规关键词，
若命中则返回 rebuttal_prompt 供调用方重生成或提示用户。

工作流：
1. load_model_spec() 加载 config/ihome_model_spec.json
2. check_output(agent_name, output_text) 扫描该 agent 适用约束的违规关键词
3. 命中时返回 {violated: True, constraint_id, rebuttal_prompt}
4. 调用方（DesignerAgent/BudgetAgent 等）可注入 rebuttal_prompt 重新调用 _chat()

HC-009 特殊处理：检查是否包含反面论证关键词（替代方案/反之/另一种等），
缺失时触发 rebuttal（单边建议 → 要求补充备选方案）。
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# HC-009 反面论证检测关键词
_COUNTER_ARGUMENT_KEYWORDS = (
    "替代方案", "备选", "反之", "另一种", "另外一种", "然而", "需要注意",
    "风险提示", "权衡", "或者", "也可考虑", "plan b", "备选方案",
)


@lru_cache(maxsize=1)
def load_model_spec() -> dict[str, Any]:
    """加载 Model Spec（缓存）。

    受 settings.model_spec_enabled feature flag 控制：关闭时返回空 spec。
    """
    if not settings.model_spec_enabled:
        return {"hard_constraints": [], "soft_constraints": []}
    try:
        spec_path = Path(__file__).resolve().parents[2] / settings.model_spec_path
        if not spec_path.exists():
            logger.warning("model_spec 文件不存在: %s", spec_path)
            return {"hard_constraints": [], "soft_constraints": []}
        return json.loads(spec_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("load_model_spec 失败: %s", e)
        return {"hard_constraints": [], "soft_constraints": []}


def get_constraints_for_agent(agent_name: str) -> list[dict[str, Any]]:
    """获取适用于该 agent 的硬约束列表。"""
    spec = load_model_spec()
    result = []
    for c in spec.get("hard_constraints", []):
        applies_to = c.get("applies_to", [])
        if not applies_to or agent_name in applies_to:
            result.append(c)
    return result


def check_output(agent_name: str, output_text: str) -> dict[str, Any]:
    """检查 Agent 输出是否违反 HC 硬约束。

    Args:
        agent_name: Agent 名称（designer/budget/procurement/...）
        output_text: Agent 的输出文本

    Returns:
        {
            "violated": bool,
            "violations": [
                {"constraint_id": "HC-001", "title": "...", "rebuttal_prompt": "..."},
                ...
            ],
            "counter_argument_present": bool,  # HC-009 专用
        }
    """
    if not settings.model_spec_enabled or not output_text:
        return {"violated": False, "violations": [], "counter_argument_present": True}

    constraints = get_constraints_for_agent(agent_name)
    violations = []
    counter_argument_present = False

    text_lower = output_text.lower()

    for c in constraints:
        # HC-009 特殊处理：反面论证义务
        if c.get("is_counter_argument_constraint"):
            counter_argument_present = any(
                kw in text_lower for kw in _COUNTER_ARGUMENT_KEYWORDS
            )
            if not counter_argument_present:
                violations.append({
                    "constraint_id": c["id"],
                    "title": c["title"],
                    "rebuttal_prompt": c["rebuttal_prompt"],
                })
            continue

        # 普通约束：关键词扫描
        keywords = c.get("violation_keywords", [])
        if any(kw in output_text for kw in keywords):
            violations.append({
                "constraint_id": c["id"],
                "title": c["title"],
                "rebuttal_prompt": c["rebuttal_prompt"],
                "matched_keywords": [kw for kw in keywords if kw in output_text],
            })

    return {
        "violated": len(violations) > 0,
        "violations": violations,
        "counter_argument_present": counter_argument_present,
    }


def build_rebuttal_context(violations: list[dict[str, Any]]) -> str:
    """将违规列表转换为可注入 LLM 的反驳上下文。

    调用方在 _chat() 失败/违规时，将此上下文作为 system 消息追加，
    要求 LLM 基于反驳提示重新生成合规输出。
    """
    if not violations:
        return ""
    parts = ["你的上一条回复违反了以下硬约束，请基于反驳提示重新生成合规输出：\n"]
    for v in violations:
        parts.append(f"\n【{v['constraint_id']} {v.get('title', '')}】\n{v['rebuttal_prompt']}\n")
    return "".join(parts)


def reload_spec() -> None:
    """清除缓存，强制重新加载 spec（配置变更后调用）。"""
    load_model_spec.cache_clear()


# ── v1.1.31 FP-9（S6）：HC 语义校验 LLM 兜底 ──

_SEMANTIC_CHECK_SYSTEM_PROMPT = """你是装修方案合规审核员。判断给定的 Agent 输出是否违反指定的硬约束（HC）。

规则：
- 仅判断"明确违反"的情况，对模糊/边界情况倾向于"未违反"（避免误伤）
- 严格基于约束的语义判断，不要过度引申
- 输出必须是合法 JSON，格式：{"violated": true/false, "constraint_id": "HC-XXX 或 null", "reason": "简短理由"}
- 若无违反，返回 {"violated": false, "constraint_id": null, "reason": "未发现违规"}
"""


async def check_output_with_semantic(
    agent_name: str, output_text: str, agent=None,
) -> dict[str, Any]:
    """HC 校验：关键词预筛 + LLM 语义兜底

    v1.1.31 FP-9（S6）：原 ``check_output`` 仅关键词扫描，对"换说法绕过"无能为力。
    现升级为两阶段：

    1. 关键词预筛（同步，快速）：命中即返回，无需 LLM
    2. LLM 语义兜底：关键词无命中但 ``hc_semantic_check_enabled=True`` 时，
       将 HC 约束 + 输出交给 LLM 判断是否语义违规

    受 ``settings.hc_semantic_check_enabled`` 控制（默认 True）：
    - True：关键词无命中后追加 LLM 语义判定
    - False：仅关键词扫描（原行为，回滚用）

    Args:
        agent_name: Agent 名称
        output_text: Agent 输出文本
        agent: 可选的 BaseAgent 实例，用于复用其 _chat 调用 LLM；
               为 None 或无 API key 时跳过 LLM 兜底（降级为关键词-only）

    Returns:
        同 check_output 的返回结构，可能多一个 "semantic_check" 字段
    """
    # 第一阶段：关键词预筛（始终执行）
    result = check_output(agent_name, output_text)
    if result["violated"]:
        # 关键词已命中，无需 LLM（节省成本）
        return result

    # 第二阶段：LLM 语义兜底
    if not settings.hc_semantic_check_enabled:
        return result
    if not agent or not output_text:
        return result

    constraints = get_constraints_for_agent(agent_name)
    if not constraints:
        return result

    # 检查是否有 LLM API key（避免无 key 时的 mock 噪音）
    try:
        from app.agents.base import PROVIDER_REGISTRY
        provider = getattr(agent, "provider", "deepseek")
        cfg = PROVIDER_REGISTRY.get(provider, {})
        if not cfg or not cfg.get("api_key")():
            # 无 API key：跳过 LLM 兜底（测试环境/MOCK_MODE）
            return result
    except Exception:
        return result

    # 构造约束描述（精简，避免 prompt 过长）
    constraint_descs = []
    for c in constraints:
        if c.get("is_counter_argument_constraint"):
            continue  # HC-009 由关键词处理，不走 LLM
        constraint_descs.append(
            f"- {c['id']} {c.get('title', '')}: {c.get('description', c.get('rebuttal_prompt', ''))[:200]}"
        )
    if not constraint_descs:
        return result

    constraints_block = "\n".join(constraint_descs)
    user_msg = (
        f"硬约束列表：\n{constraints_block}\n\n"
        f"Agent 输出：\n{output_text[:2000]}\n\n"
        f"请判断该输出是否违反任一硬约束，输出 JSON。"
    )

    try:
        reply = await agent._chat([
            {"role": "system", "content": _SEMANTIC_CHECK_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ])
        if not isinstance(reply, str):
            return result
        # 解析 LLM 返回的 JSON（容忍前后多余文本）
        import re as _re
        json_match = _re.search(r'\{[^{}]*"violated"[^{}]*\}', reply, _re.DOTALL)
        if not json_match:
            return result
        verdict = json.loads(json_match.group(0))
        if verdict.get("violated") and verdict.get("constraint_id"):
            # LLM 判定违规：追加到 violations
            cid = verdict["constraint_id"]
            # 找到对应约束的 rebuttal_prompt
            matched_c = next((c for c in constraints if c["id"] == cid), None)
            result["violated"] = True
            result["violations"].append({
                "constraint_id": cid,
                "title": matched_c.get("title", "") if matched_c else "",
                "rebuttal_prompt": matched_c["rebuttal_prompt"] if matched_c else "请修正输出以符合该约束。",
                "matched_keywords": [],
                "semantic_reason": verdict.get("reason", ""),
                "detected_by": "llm_semantic",
            })
            result["semantic_check"] = {"ran": True, "verdict": verdict}
        else:
            result["semantic_check"] = {"ran": True, "verdict": verdict}
    except Exception as e:
        logger.debug("check_output_with_semantic: LLM 语义校验失败（降级关键词-only）: %s", e)
        result["semantic_check"] = {"ran": False, "error": str(e)}

    return result
