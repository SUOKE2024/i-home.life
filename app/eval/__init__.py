"""i-home.life 评估框架（借鉴索克生活 Suoke-Eval1 v2.0）

提供家居领域专用的 Agent 输出质量评估维度与离线评测循环。
"""

from app.eval.ihome_eval import (
    DIMENSION_BENCHMARKS,
    IHomeEvalDimension,
    IHomeEvalReport,
    IHomeEvalRunner,
    QUALITY_TARGETS,
    compute_feedback_metrics,
    detect_agent_drift,
    run_ihome_eval,
)
from app.eval.tool_accuracy import (
    TOOL_SELECTION_DATASET,
    classify_tool_by_keywords,
    classify_tool_by_llm,
    evaluate_llm_tool_selection,
    evaluate_tool_selection,
    get_tool_accuracy_report,
)

__all__ = [
    "DIMENSION_BENCHMARKS",
    "IHomeEvalDimension",
    "IHomeEvalReport",
    "IHomeEvalRunner",
    "QUALITY_TARGETS",
    "compute_feedback_metrics",
    "detect_agent_drift",
    "run_ihome_eval",
    "TOOL_SELECTION_DATASET",
    "classify_tool_by_keywords",
    "classify_tool_by_llm",
    "evaluate_llm_tool_selection",
    "evaluate_tool_selection",
    "get_tool_accuracy_report",
]
