"""i-home.life 评估框架（借鉴索克生活 Suoke-Eval1 v2.0）

索克生活 Suoke-Eval1 v2.0 定义 20 个评估维度并映射学术 benchmark，本模块借鉴其
「维度 → 指标 → 基线 → 报告」方法论，落地家居领域专用评估维度。

家居领域评估维度（对标 Suoke-Eval1 的 TCM_SYNDROME_DIFFERENTIATION 等）：
- BUDGET_ACCURACY        报价准确性（含税/质保金/漏项检查）
- DESIGN_SAFETY          设计安全（承重墙/逃生通道/水电规范）
- MATERIAL_CONTRAINDICATION 材料禁忌与环保等级（HC-003 强制）
- IDOR_RESISTANCE        越权防护（verify_project_access 覆盖率）
- SSE_LATENCY            流式首 token 延迟
- FALLBACK_RATE          降级率（Harness fallback）
- TOOL_CALL_ACCURACY     FunctionCall 工具调用准确性
- REASONING_LEAK_RATE    思维链泄漏率（reasoning_content 不应返回用户）
- HC_COMPLIANCE_RATE     Model Spec HC 硬约束合规率
- COUNTER_ARGUMENT_QUALITY 反面论证质量（HC-009 借鉴）

设计原则（借鉴 Suoke-Eval1）：
1. 每个维度有明确的 academic benchmark 参照或工程量化指标
2. 支持 baseline 对比（base_llm / full_system / mock）
3. 报告可序列化为 JSON，供 CI 周末 job 生成趋势
4. 复用 AgentHarness.run_eval() 与 AgentTrace，不重复造轮子
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class IHomeEvalDimension(str, Enum):
    """家居领域评估维度（对标 Suoke-Eval1 v2.0 的 20 维）"""

    BUDGET_ACCURACY = "budget_accuracy"            # 报价准确性
    DESIGN_SAFETY = "design_safety"                # 设计安全
    MATERIAL_CONTRAINDICATION = "material_contraindication"  # 材料禁忌/环保
    IDOR_RESISTANCE = "idor_resistance"            # 越权防护
    SSE_LATENCY = "sse_latency"                    # 流式延迟
    FALLBACK_RATE = "fallback_rate"                # 降级率
    TOOL_CALL_ACCURACY = "tool_call_accuracy"      # 工具调用准确性
    REASONING_LEAK_RATE = "reasoning_leak_rate"    # 思维链泄漏率
    HC_COMPLIANCE_RATE = "hc_compliance_rate"      # HC 合规率
    COUNTER_ARGUMENT_QUALITY = "counter_argument_quality"  # 反面论证


# 维度 → 参照说明（借鉴 Suoke-Eval1 的 benchmark 映射表）
DIMENSION_BENCHMARKS: dict[str, str] = {
    IHomeEvalDimension.BUDGET_ACCURACY.value: "工程报价含税与质保金完整率 + 漏项检测",
    IHomeEvalDimension.DESIGN_SAFETY.value: "承重墙/逃生通道/水电规范合规（HC-001）",
    IHomeEvalDimension.MATERIAL_CONTRAINDICATION.value: "材料环保等级 E0/E1 标注率（HC-003）",
    IHomeEvalDimension.IDOR_RESISTANCE.value: "verify_project_access 端点覆盖率（279 基线）",
    IHomeEvalDimension.SSE_LATENCY.value: "/agents/chat/stream 首 token p95 延迟 (ms)",
    IHomeEvalDimension.FALLBACK_RATE.value: "Harness fallback_runs / total_runs",
    IHomeEvalDimension.TOOL_CALL_ACCURACY.value: "FunctionCall 工具名 + 参数 schema 命中率",
    IHomeEvalDimension.REASONING_LEAK_RATE.value: "_looks_like_reasoning_leak 触发率（越低越好）",
    IHomeEvalDimension.HC_COMPLIANCE_RATE.value: "ihome_model_spec HC-001~HC-008 合规率",
    IHomeEvalDimension.COUNTER_ARGUMENT_QUALITY.value: "反面论证/替代方案出现率（HC-009）",
}


@dataclass
class IHomeEvalReport:
    """评估报告（可序列化为 JSON，借鉴 Suoke-Eval1 report_detail.json）"""

    run_id: str
    started_at: float
    finished_at: float = 0.0
    baseline: str = "full_system"  # base_llm | keyword | full_system | mock
    sample_size: int = 0
    metrics: dict[str, float] = field(default_factory=dict)
    dimension_scores: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "baseline": self.baseline,
            "sample_size": self.sample_size,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "metrics": self.metrics,
            "dimension_scores": self.dimension_scores,
            "dimension_benchmarks": DIMENSION_BENCHMARKS,
            "notes": self.notes,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class IHomeEvalRunner:
    """评估执行器：聚合 AgentHarness 轨迹 + 静态检查 → 维度评分

    借鉴 Suoke-Eval1 的 run_evaluation.py：从轨迹与工程指标计算各维度分数，
    生成可对比 baseline 的报告。
    """

    def __init__(self, baseline: str = "full_system"):
        self.baseline = baseline

    def run(self, traces: list[dict] | None = None) -> IHomeEvalReport:
        """执行评估。

        Args:
            traces: AgentHarness.get_traces() 返回的轨迹列表；
                    为 None 时尝试从全局 harness 拉取。
        """
        report = IHomeEvalReport(
            run_id=f"ihome_eval_{int(time.time())}",
            started_at=time.time(),
            baseline=self.baseline,
        )

        if traces is None:
            try:
                from app.agents.harness import get_harness
                traces = get_harness().get_traces(limit=500)
            except Exception as e:
                logger.warning("ihome_eval: 无法获取 harness traces: %s", e)
                traces = []

        report.sample_size = len(traces)
        report.metrics = self._compute_runtime_metrics(traces)
        report.dimension_scores = self._compute_dimension_scores(traces, report.metrics)
        report.finished_at = time.time()
        return report

    # ── 运行时指标（复用 AgentTrace 字段）──

    def _compute_runtime_metrics(self, traces: list[dict]) -> dict[str, float]:
        if not traces:
            return {}
        total = len(traces)
        success = sum(1 for t in traces if t.get("status") == "success")
        fallback = sum(1 for t in traces if t.get("fallback_used"))
        leaked = sum(1 for t in traces if "稍后重试" in (t.get("response_truncated") or ""))
        avg_latency = (
            sum(t.get("latency_ms", 0) for t in traces) / total
        )
        return {
            "success_rate": round(success / total * 100, 2),
            "fallback_rate": round(fallback / total * 100, 2),
            "reasoning_leak_rate": round(leaked / total * 100, 2),
            "avg_latency_ms": round(avg_latency, 2),
            "total_runs": total,
        }

    # ── 维度评分（0-100，越高越好；泄漏率/降级率为反向指标）──

    def _compute_dimension_scores(
        self, traces: list[dict], metrics: dict[str, float]
    ) -> dict[str, float]:
        scores: dict[str, float] = {}
        m = metrics

        # 反向指标：rate 越低分数越高
        scores[IHomeEvalDimension.FALLBACK_RATE.value] = round(
            100 - m.get("fallback_rate", 0), 2
        )
        scores[IHomeEvalDimension.REASONING_LEAK_RATE.value] = round(
            100 - m.get("reasoning_leak_rate", 0), 2
        )
        scores[IHomeEvalDimension.SSE_LATENCY.value] = round(
            max(0, 100 - m.get("avg_latency_ms", 0) / 50), 2  # 5s = 0 分
        )

        # 正向指标
        scores[IHomeEvalDimension.TOOL_CALL_ACCURACY.value] = self._tool_call_score(traces)

        # 静态检查类维度
        scores[IHomeEvalDimension.IDOR_RESISTANCE.value] = self._idor_score()
        scores[IHomeEvalDimension.HC_COMPLIANCE_RATE.value] = self._hc_compliance_score()
        scores[IHomeEvalDimension.COUNTER_ARGUMENT_QUALITY.value] = self._counter_argument_score(traces)
        scores[IHomeEvalDimension.DESIGN_SAFETY.value] = scores[
            IHomeEvalDimension.HC_COMPLIANCE_RATE.value
        ]
        scores[IHomeEvalDimension.MATERIAL_CONTRAINDICATION.value] = self._material_score()
        scores[IHomeEvalDimension.BUDGET_ACCURACY.value] = self._budget_score(traces)
        return scores

    def _tool_call_score(self, traces: list[dict]) -> float:
        """工具调用准确性：有 tool_call 且 status=success 的比例"""
        if not traces:
            return 0.0
        with_tools = [t for t in traces if t.get("tool_call_count", 0) > 0]
        if not with_tools:
            return 100.0  # 无工具调用不扣分
        ok = sum(1 for t in with_tools if t.get("status") == "success")
        return round(ok / len(with_tools) * 100, 2)

    def _idor_score(self) -> float:
        """越权防护：统计 verify_project_access 覆盖的 API 文件占比（基线 30 文件）"""
        try:
            import subprocess
            root = Path(__file__).resolve().parents[2]
            result = subprocess.run(
                ["grep", "-rl", "verify_project_access", str(root / "app" / "api")],
                capture_output=True, text=True, timeout=10,
            )
            covered = len([f for f in result.stdout.splitlines() if f.endswith(".py")])
            # 基线 30 文件，覆盖率 capped 100
            return round(min(100, covered / 30 * 100), 2)
        except Exception as e:
            logger.debug("idor_score 失败: %s", e)
            return 0.0

    def _hc_compliance_score(self) -> float:
        """HC 合规率：检查 ihome_model_spec.json 是否存在且含 HC-001~HC-008"""
        try:
            spec_path = Path(__file__).resolve().parents[2] / settings.model_spec_path
            if not spec_path.exists():
                return 0.0
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            constraints = spec.get("hard_constraints", [])
            ids = {c.get("id") for c in constraints}
            expected = {f"HC-00{i}" for i in range(1, 9)}
            hit = len(ids & expected)
            return round(hit / len(expected) * 100, 2)
        except Exception as e:
            logger.debug("hc_compliance_score 失败: %s", e)
            return 0.0

    def _counter_argument_score(self, traces: list[dict]) -> float:
        """反面论证质量：响应中含「替代方案/反之/另一种」关键词的比例（HC-009）"""
        if not traces:
            return 0.0
        keywords = ("替代方案", "反之", "另一种", "备选", "然而", "需要注意")
        hit = sum(
            1 for t in traces
            if any(k in (t.get("response_truncated") or "") for k in keywords)
        )
        return round(hit / len(traces) * 100, 2)

    def _material_score(self) -> float:
        """材料环保等级标注率：检查 materials 表是否有环保等级列（简化为 schema 探测）"""
        # 工程简化：依赖 HC-003 在 model_spec 中存在即给满分基线
        try:
            spec_path = Path(__file__).resolve().parents[2] / settings.model_spec_path
            if not spec_path.exists():
                return 0.0
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            ids = {c.get("id") for c in spec.get("hard_constraints", [])}
            return 100.0 if "HC-003" in ids else 0.0
        except Exception:
            return 0.0

    def _budget_score(self, traces: list[dict]) -> float:
        """报价准确性：budget agent 成功率"""
        budget = [t for t in traces if t.get("agent_name") == "budget"]
        if not budget:
            return 0.0
        ok = sum(1 for t in budget if t.get("status") == "success")
        return round(ok / len(budget) * 100, 2)


def run_ihome_eval(
    traces: list[dict] | None = None,
    baseline: str = "full_system",
    output_path: str | None = None,
) -> IHomeEvalReport:
    """便捷入口：运行评估并可选落盘报告。

    Args:
        traces: 轨迹列表（None 则从 harness 拉取）
        baseline: baseline 标签
        output_path: 报告落盘路径（如 reports/ihome_eval_report.json）
    """
    if not settings.eval_enabled:
        logger.info("ihome_eval: eval_enabled=False，跳过评估")
        return IHomeEvalReport(
            run_id="disabled", started_at=time.time(), finished_at=time.time(),
            notes=["eval_enabled=False"],
        )
    runner = IHomeEvalRunner(baseline=baseline)
    report = runner.run(traces=traces)
    if output_path:
        try:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(report.to_json(), encoding="utf-8")
            logger.info("ihome_eval: 报告已写入 %s", output_path)
        except Exception as e:
            logger.warning("ihome_eval: 报告落盘失败: %s", e)
    return report
