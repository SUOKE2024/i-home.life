"""i-home.life 评估框架（借鉴索克生活 Suoke-Eval1 v2.0）

提供家居领域专用的 Agent 输出质量评估维度与离线评测循环。
"""

from app.eval.ihome_eval import (
    DIMENSION_BENCHMARKS,
    IHomeEvalDimension,
    IHomeEvalReport,
    IHomeEvalRunner,
    run_ihome_eval,
)

__all__ = [
    "DIMENSION_BENCHMARKS",
    "IHomeEvalDimension",
    "IHomeEvalReport",
    "IHomeEvalRunner",
    "run_ihome_eval",
]
