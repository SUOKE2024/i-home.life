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
