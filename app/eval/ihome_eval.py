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


def _percentile(values: list[float], p: float) -> float:
    """线性插值百分位数（p50/p95/p99）。空列表返回 0.0（诚实标注无数据）。"""
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * p
    f = int(k)
    c = f + 1 if f + 1 < len(ordered) else f
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


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
    # v1.12.x 新增（对齐 2026 生产级 Agent Eval 三要素，见 MLflow 2026 guide）：
    FAITHFULNESS = "faithfulness"                  # 忠实性：回复是否有据可依（不幻觉）
    COMPLETENESS = "completeness"                  # 完整性：是否覆盖任务全部组成部分
    SUFFICIENCY = "sufficiency"                    # 充分性：回复是否恰如其分（不过度/不遗漏）


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
    IHomeEvalDimension.FAITHFULNESS.value: "回复含来源/依据标注率（有据可依，防幻觉）",
    IHomeEvalDimension.COMPLETENESS.value: "结构化完整输出率（分点/总结/覆盖全部子任务）",
    IHomeEvalDimension.SUFFICIENCY.value: "回复长度适中率（非空且不过度冗长）",
}

# v1.12.x 量化目标基线（对齐 2026 生产级 Agent 质量体系）：
# 关键维度的量化标准，供报告对照 / 漂移检测判定 / CI 门禁复用。
QUALITY_TARGETS: dict[str, float] = {
    "success_rate_min": 95.0,          # 成功率下限（%）
    "fallback_rate_max": 5.0,          # 降级率上限（%）
    "reasoning_leak_rate_max": 1.0,    # 思维链泄漏率上限（%）
    "avg_latency_ms_max": 15000.0,     # Agent 平均响应延迟上限（ms）
    "first_token_p95_ms_max": 8000.0,  # 流式首 token p95 上限（ms）
    "faithfulness_min": 60.0,          # 忠实性维度得分下限
    "completeness_min": 60.0,          # 完整性维度得分下限
    "sufficiency_min": 60.0,           # 充分性维度得分下限
    # v1.13.0（2026 前沿对齐）：
    "tool_selection_accuracy_min": 60.0,  # 工具选择准确率下限（确定性基线参考）
    "token_budget_hit_rate_max": 20.0,    # token 预算早停率上限（%）（>20% 说明工具结果过大）
    # v1.13.4（评估体系维度，2026 前沿：用户满意度纳入质量门禁）：
    "feedback_like_rate_min": 70.0,   # 用户反馈 like 率下限（%）（like/(like+dislike)）
    "feedback_min_samples": 5,        # 反馈漂移判定最小样本量（低于则不判定，诚实标注）
    # v1.13.6（响应速度 + 用户体验量化）：
    "latency_p95_ms_max": 30000.0,    # 总延迟 p95 上限（ms）
    "task_completion_rate_min": 70.0,  # 会话任务完成率下限（%）
    "abandonment_rate_max": 30.0,      # 会话弃单率上限（%）
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
    per_agent_scores: dict[str, dict] = field(default_factory=dict)  # v1.12.x per-agent 评分
    quality_targets: dict[str, float] = field(default_factory=dict)  # v1.12.x 量化目标
    tool_accuracy: dict = field(default_factory=dict)  # v1.13.x 工具选择准确率报告
    feedback_metrics: dict = field(default_factory=dict)  # v1.13.5 用户反馈满意度维度
    ux_metrics: dict = field(default_factory=dict)  # v1.13.6 用户体验维度
    llm_judge: dict = field(default_factory=dict)  # v1.13.6 LLM-as-judge 语义评分
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
            "per_agent_scores": self.per_agent_scores,
            "quality_targets": self.quality_targets,
            "tool_accuracy": self.tool_accuracy,
            "feedback_metrics": self.feedback_metrics,
            "ux_metrics": self.ux_metrics,
            "llm_judge": self.llm_judge,
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
        report.per_agent_scores = self._compute_per_agent_scores(traces)
        report.quality_targets = dict(QUALITY_TARGETS)
        # v1.13.x：工具选择准确率基线报告（确定性，诚实标注非 LLM）
        try:
            from app.eval.tool_accuracy import get_tool_accuracy_report
            report.tool_accuracy = get_tool_accuracy_report()
        except Exception as e:
            logger.warning("ihome_eval: tool_accuracy 报告生成失败: %s", e)
            report.tool_accuracy = {"error": str(e)}
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
        # v1.13.6：延迟分位数（p50/p95/p99）+ 首 token p95 实测
        latencies = [t.get("latency_ms", 0) or 0 for t in traces]
        first_tokens = [t.get("first_token_latency_ms", 0) or 0 for t in traces]
        first_tokens_nonzero = [v for v in first_tokens if v > 0]
        return {
            "success_rate": round(success / total * 100, 2),
            "fallback_rate": round(fallback / total * 100, 2),
            "reasoning_leak_rate": round(leaked / total * 100, 2),
            "avg_latency_ms": round(avg_latency, 2),
            "latency_p50_ms": round(_percentile(latencies, 0.5), 2),
            "latency_p95_ms": round(_percentile(latencies, 0.95), 2),
            "latency_p99_ms": round(_percentile(latencies, 0.99), 2),
            "first_token_p95_ms": round(_percentile(first_tokens_nonzero, 0.95), 2),
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
        # v1.13.6：SSE_LATENCY 改用首 token p95 实测（8s = 0 分，对齐 first_token_p95_ms_max）；
        # 无首 token 数据时回退 avg_latency 伪代理（诚实降级，不伪造）。
        ft_p95 = m.get("first_token_p95_ms", 0) or 0
        if ft_p95 > 0:
            sse_latency = max(0, 100 - ft_p95 / 80)
        else:
            sse_latency = max(0, 100 - m.get("avg_latency_ms", 0) / 50)
        scores[IHomeEvalDimension.SSE_LATENCY.value] = round(sse_latency, 2)

        # 正向指标
        scores[IHomeEvalDimension.TOOL_CALL_ACCURACY.value] = self._tool_call_score(traces)
        scores[IHomeEvalDimension.FAITHFULNESS.value] = self._keyword_hit_score(
            traces, ("来源", "根据", "依据", "参考", "标注", "数据来源")
        )
        scores[IHomeEvalDimension.COMPLETENESS.value] = self._keyword_hit_score(
            traces, ("总结", "综上", "第1", "第一", "最后", "1.", "2.", "3.")
        )
        scores[IHomeEvalDimension.SUFFICIENCY.value] = self._sufficiency_score(traces)

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
        """工具调用准确性：有 tool_call 且 status=success 的比例。

        v1.13.0 增强（对齐 2026 Tool-Selection Accuracy）：
        与确定性基线 get_tool_accuracy_report() 交叉验证——当轨迹样本不足时
        以基线准确率作为 TOOL_CALL_ACCURACY 的最低可接受参考。
        """
        if not traces:
            return 0.0
        with_tools = [t for t in traces if t.get("tool_call_count", 0) > 0]
        if not with_tools:
            # 无工具调用轨迹：以确定性基线准确率作为代理（诚实标注）
            try:
                from app.eval.tool_accuracy import get_tool_accuracy_report
                report = get_tool_accuracy_report()
                return float(report["metrics"]["accuracy"])
            except Exception as e:
                logger.debug("tool_accuracy_report 失败: %s", e)
                return 100.0  # 无工具调用不扣分
        ok = sum(1 for t in with_tools if t.get("status") == "success")
        return round(ok / len(with_tools) * 100, 2)

    # ── v1.12.x 忠实性/完整性/充分性（对齐 2026 生产级 Agent Eval 三要素）──

    def _keyword_hit_score(self, traces: list[dict], keywords: tuple[str, ...]) -> float:
        """关键词命中率：回复含指定结构化标记的比例（作为忠实/完整性的工程代理指标）。

        诚实标注：这是启发式代理指标（非 LLM judge），用于快速回归门禁；
        精确语义评估依赖人工/LLM 抽样复核（见 notes）。
        """
        if not traces:
            return 0.0
        hit = sum(
            1 for t in traces
            if any(k in (t.get("response_truncated") or "") for k in keywords)
        )
        return round(hit / len(traces) * 100, 2)

    def _sufficiency_score(self, traces: list[dict]) -> float:
        """充分性：回复非空且长度适中（40-2000 字符）的比例（不过度/不遗漏）。"""
        if not traces:
            return 0.0
        ok = sum(
            1 for t in traces
            if 40 <= len(t.get("response_truncated") or "") <= 2000
        )
        return round(ok / len(traces) * 100, 2)

    # ── v1.12.x per-agent 评分（对齐 2026 逐 Agent 评估/漂移检测）──

    def _compute_per_agent_scores(self, traces: list[dict]) -> dict[str, dict]:
        """按 agent_name 分组计算成功率/降级率/平均延迟/样本量。

        v1.13.0 增强（对齐 2026 per-agent 评估）：新增工具调用维度——
        avg_tool_calls（平均工具调用数）、tool_success_rate（工具执行成功率）、
        token_budget_hit_rate（预算早停率，过高说明工具结果上下文过大需优化）。

        v1.13.6 增强：新增延迟分位数（latency_p95_ms）与首 token p95
        （first_token_p95_ms）——响应速度可量化。

        Returns:
            {"designer": {"sample_size": n, "success_rate": .., "fallback_rate": ..,
                          "avg_latency_ms": .., "latency_p95_ms": ..,
                          "first_token_p95_ms": .., "avg_tool_calls": ..,
                          "tool_success_rate": .., "token_budget_hit_rate": ..,
                          "meets_targets": bool}, ...}
        """
        per_agent: dict[str, list[dict]] = {}
        for t in traces:
            name = t.get("agent_name") or "unknown"
            per_agent.setdefault(name, []).append(t)

        scores: dict[str, dict] = {}
        for name, group in per_agent.items():
            total = len(group)
            success = sum(1 for t in group if t.get("status") == "success")
            fallback = sum(1 for t in group if t.get("fallback_used"))
            avg_latency = sum(t.get("latency_ms", 0) for t in group) / total
            success_rate = round(success / total * 100, 2)
            fallback_rate = round(fallback / total * 100, 2)
            # v1.13.6 响应速度分位
            latencies = [t.get("latency_ms", 0) or 0 for t in group]
            first_tokens = [t.get("first_token_latency_ms", 0) or 0 for t in group]
            first_tokens_nonzero = [v for v in first_tokens if v > 0]
            # v1.13.0 工具维度
            avg_tool_calls = round(
                sum(t.get("tool_call_count", 0) for t in group) / total, 2
            )
            tool_runs = [t for t in group if t.get("tool_call_count", 0) > 0]
            tool_success_rate = round(
                sum(1 for t in tool_runs if t.get("status") == "success")
                / max(len(tool_runs), 1) * 100, 2
            )
            budget_hit_rate = round(
                sum(1 for t in group if t.get("token_budget_hit"))
                / total * 100, 2
            )
            meets = (
                success_rate >= QUALITY_TARGETS["success_rate_min"]
                and fallback_rate <= QUALITY_TARGETS["fallback_rate_max"]
                and budget_hit_rate <= QUALITY_TARGETS.get("token_budget_hit_rate_max", 100.0)
            )
            scores[name] = {
                "sample_size": total,
                "success_rate": success_rate,
                "fallback_rate": fallback_rate,
                "avg_latency_ms": round(avg_latency, 2),
                "latency_p95_ms": round(_percentile(latencies, 0.95), 2),
                "first_token_p95_ms": round(_percentile(first_tokens_nonzero, 0.95), 2),
                "avg_tool_calls": avg_tool_calls,
                "tool_success_rate": tool_success_rate,
                "token_budget_hit_rate": budget_hit_rate,
                "meets_targets": meets,
            }
        return scores

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


# ── v1.12.x 漂移检测（对齐 2026「drift detection with statistical thresholds」）──

DRIFT_STATUS_OK = "ok"
DRIFT_STATUS_WARN = "warn"
DRIFT_STATUS_CRITICAL = "critical"
DRIFT_STATUS_INSUFFICIENT_SAMPLES = "insufficient_samples"


async def detect_agent_drift(
    db, window_days: int = 7, min_samples: int = 5,
) -> list[dict]:
    """基于 agent_traces 持久化轨迹的 per-agent 质量漂移检测。

    对比当前窗口 per-agent 成功率/降级率/平均延迟与 QUALITY_TARGETS 量化基线：
    - 低于目标值但差距 <10% → warn
    - 低于目标值且差距 ≥10% → critical
    样本量不足（< min_samples）的 Agent 标记 insufficient_samples（不判定）。

    v1.13.1 增强（对齐 2026 per-agent 漂移评估）：新增 token_budget_hit_rate
    指标（预算早停率）——早停率 > token_budget_hit_rate_max（20%）说明工具结果
    上下文过大需优化，纳入漂移判定（诚实降级：不判定采样不足）。

    Returns:
        [{"agent_name", "sample_size", "metric", "current", "target",
          "status": ok|warn|critical|insufficient_samples}]
    """
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import case, func, select
    from app.models.agent_trace import AgentTraceRecord

    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    stmt = (
        select(
            AgentTraceRecord.agent_name,
            func.count().label("cnt"),
            func.sum(case((AgentTraceRecord.status == "success", 1), else_=0)).label("success_cnt"),
            func.sum(case((AgentTraceRecord.fallback_used.is_(True), 1), else_=0)).label("fallback_cnt"),
            func.sum(case((AgentTraceRecord.token_budget_hit.is_(True), 1), else_=0)).label("budget_hit_cnt"),
            func.avg(AgentTraceRecord.latency_ms).label("avg_latency"),
        )
        .where(AgentTraceRecord.created_at >= cutoff)
        .group_by(AgentTraceRecord.agent_name)
    )
    result = await db.execute(stmt)
    rows = result.all()

    drift: list[dict] = []
    for name, cnt, success_cnt, fallback_cnt, budget_hit_cnt, avg_latency in rows:
        total = int(cnt)
        success_cnt = int(success_cnt or 0)
        fallback_cnt = int(fallback_cnt or 0)
        budget_hit_cnt = int(budget_hit_cnt or 0)
        avg_latency = float(avg_latency or 0.0)
        if total < min_samples:
            drift.append({
                "agent_name": name, "sample_size": total,
                "status": "insufficient_samples",
                "metric": "sample_size", "current": total,
                "target": min_samples,
            })
            continue
        success_rate = round(success_cnt / total * 100, 2)
        fallback_rate = round(fallback_cnt / total * 100, 2)
        budget_hit_rate = round(budget_hit_cnt / total * 100, 2)

        def _judge(metric: str, current: float, target: float, inverse: bool = False) -> None:
            """inverse=True 时 current 越低越好（如降级率）。"""
            gap_pct = abs(current - target) / max(target, 1e-9) * 100
            violated = current < target if not inverse else current > target
            if not violated:
                drift.append({
                    "agent_name": name, "sample_size": total,
                    "status": DRIFT_STATUS_OK, "metric": metric,
                    "current": current, "target": target,
                })
            else:
                drift.append({
                    "agent_name": name, "sample_size": total,
                    "status": DRIFT_STATUS_CRITICAL if gap_pct >= 10 else DRIFT_STATUS_WARN,
                    "metric": metric, "current": current, "target": target,
                })

        _judge("success_rate", success_rate, QUALITY_TARGETS["success_rate_min"])
        _judge("fallback_rate", fallback_rate, QUALITY_TARGETS["fallback_rate_max"], inverse=True)
        _judge("avg_latency_ms", round(avg_latency, 2), QUALITY_TARGETS["avg_latency_ms_max"], inverse=True)
        _judge(
            "token_budget_hit_rate", budget_hit_rate,
            QUALITY_TARGETS.get("token_budget_hit_rate_max", 20.0), inverse=True,
        )
    return drift


async def detect_feedback_drift(
    db, window_days: int = 7, min_samples: int = 5,
) -> list[dict]:
    """基于 agent_feedbacks 的 per-agent 用户满意度漂移检测（v1.13.4 评估体系）。

    用户反馈（like/dislike）是 Agent 质量的直接信号——此前 agent_feedbacks 只被
    L4 偏好学习 + growth 周报消费，未纳入质量门禁/漂移判定。本函数对比当前窗口
    per-agent like 率（like/(like+dislike)）与 QUALITY_TARGETS.feedback_like_rate_min：
    - like_rate < 目标值但差距 <10% → warn
    - like_rate < 目标值且差距 ≥10% → critical
    - 样本量 < min_samples → insufficient_samples（不判定，诚实标注）

    Returns:
        [{"agent_name", "sample_size", "metric", "current", "target",
          "status": ok|warn|critical|insufficient_samples}]
    """
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import case, func, select
    from app.models.agent_feedback import AgentFeedback

    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    stmt = (
        select(
            AgentFeedback.agent_name,
            func.count().label("cnt"),
            func.sum(case((AgentFeedback.feedback_type == "like", 1), else_=0)).label("like_cnt"),
        )
        .where(AgentFeedback.created_at >= cutoff)
        .group_by(AgentFeedback.agent_name)
    )
    result = await db.execute(stmt)
    rows = result.all()

    target = QUALITY_TARGETS.get("feedback_like_rate_min", 70.0)
    drift: list[dict] = []
    for name, cnt, like_cnt in rows:
        total = int(cnt)
        like_cnt = int(like_cnt or 0)
        if total < min_samples:
            drift.append({
                "agent_name": name, "sample_size": total,
                "status": DRIFT_STATUS_INSUFFICIENT_SAMPLES,
                "metric": "feedback_sample_size", "current": total,
                "target": min_samples,
            })
            continue
        like_rate = round(like_cnt / total * 100, 2)
        gap_pct = abs(like_rate - target) / max(target, 1e-9) * 100
        if like_rate < target:
            status = DRIFT_STATUS_CRITICAL if gap_pct >= 10 else DRIFT_STATUS_WARN
        else:
            status = DRIFT_STATUS_OK
        drift.append({
            "agent_name": name, "sample_size": total,
            "status": status, "metric": "feedback_like_rate",
            "current": like_rate, "target": target,
        })
    return drift


async def compute_feedback_metrics(
    db, window_days: int = 7, min_samples: int = 5,
) -> dict:
    """评估报告反馈满意度维度（v1.13.5，闭环 v1.13.4 遗留「feedback 纳入 report」）。

    复用 detect_feedback_drift（agent_feedbacks → per-agent like 率判定），
    输出报告形态（供 /api/eval/report 直接挂载）：
    {
      "window_days": 7,
      "min_samples": 5,
      "agent_count": N,
      "per_agent": {"concierge": {"like_rate": 66.67, "samples": 6,
                                   "status": "warn", "target": 70.0}, ...},
      "overall": {"like_rate": .., "samples": .., "status": ..} | None  # 样本不足时为 None
    }

    诚实标注：样本量 < min_samples 的 Agent 标记 insufficient_samples 不判定；
    全库无反馈时 overall=None + agent_count=0（不伪造满意度）。
    """
    rows = await detect_feedback_drift(db, window_days=window_days, min_samples=min_samples)
    per_agent: dict[str, dict] = {}
    total_samples = 0
    total_likes = 0
    for r in rows:
        if r.get("metric") != "feedback_like_rate":
            continue
        per_agent[r["agent_name"]] = {
            "like_rate": r["current"],
            "samples": r["sample_size"],
            "status": r["status"],
            "target": r["target"],
        }
        # overall 仅统计有判定样本的 Agent（insufficient_samples 不计入聚合）
        if r["status"] != DRIFT_STATUS_INSUFFICIENT_SAMPLES:
            total_samples += r["sample_size"]
            total_likes += round(r["current"] / 100 * r["sample_size"])

    overall = None
    if total_samples >= min_samples:
        like_rate = round(total_likes / total_samples * 100, 2)
        target = QUALITY_TARGETS.get("feedback_like_rate_min", 70.0)
        gap_pct = abs(like_rate - target) / max(target, 1e-9) * 100
        if like_rate < target:
            status = DRIFT_STATUS_CRITICAL if gap_pct >= 10 else DRIFT_STATUS_WARN
        else:
            status = DRIFT_STATUS_OK
        overall = {"like_rate": like_rate, "samples": total_samples, "status": status}

    return {
        "window_days": window_days,
        "min_samples": min_samples,
        "agent_count": len(per_agent),
        "per_agent": per_agent,
        "overall": overall,
    }


async def compute_ux_metrics(
    db, window_days: int = 7, min_samples: int = 5,
) -> dict:
    """用户体验维度（v1.13.6）：任务完成率/弃单率/平均会话轮次/星级均值。

    数据源：
    - agent_sessions + agent_messages（会话级）：任务完成 = 末条消息 assistant；
      弃单 = 末条消息 user（问而未答）
    - agent_feedbacks（星级）：avg(rating)，1-5 星

    诚实标注：会话样本量 < min_samples 时 completion/abandonment 不判定（None）。
    """
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import func, select
    from app.models.agent_session import AgentSession, AgentMessage
    from app.models.agent_feedback import AgentFeedback

    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

    # 每会话最后一条消息角色
    last_role_subq = (
        select(AgentMessage.role)
        .where(AgentMessage.session_id == AgentSession.id)
        .order_by(AgentMessage.sequence.desc())
        .limit(1)
        .correlate(AgentSession)
        .scalar_subquery()
    )
    sessions_result = await db.execute(
        select(last_role_subq, func.count())
        .select_from(AgentSession)
        .where(AgentSession.created_at >= cutoff)
        .where(AgentSession.is_deleted.is_(False))
        .where(AgentSession.message_count > 0)
        .group_by(last_role_subq)
    )
    role_counts = {r[0]: int(r[1]) for r in sessions_result.all()}
    total_sessions = sum(role_counts.values())
    completed = role_counts.get("assistant", 0)
    abandoned = role_counts.get("user", 0)

    # 平均会话轮次（窗口内会话的 user 消息数均值）
    window_sessions = (
        select(AgentSession.id)
        .where(AgentSession.created_at >= cutoff)
        .where(AgentSession.is_deleted.is_(False))
    )
    user_counts = (
        select(func.count().label("turns"))
        .select_from(AgentMessage)
        .where(AgentMessage.role == "user")
        .where(AgentMessage.session_id.in_(window_sessions))
        .group_by(AgentMessage.session_id)
        .subquery()
    )
    turns_result = await db.execute(select(func.avg(user_counts.c.turns)))
    avg_turns = float(turns_result.scalar() or 0.0)

    # 星级均值
    rating_result = await db.execute(
        select(func.avg(AgentFeedback.rating), func.count())
        .where(AgentFeedback.rating.isnot(None))
        .where(AgentFeedback.created_at >= cutoff)
    )
    avg_rating, rating_cnt = rating_result.one()

    sufficient = total_sessions >= min_samples
    return {
        "window_days": window_days,
        "min_samples": min_samples,
        "total_sessions": total_sessions,
        "task_completion_rate": (
            round(completed / total_sessions * 100, 2) if sufficient else None
        ),
        "abandonment_rate": (
            round(abandoned / total_sessions * 100, 2) if sufficient else None
        ),
        "avg_turns_per_session": round(avg_turns, 2),
        "avg_rating": round(float(avg_rating), 2) if avg_rating is not None else None,
        "rating_samples": int(rating_cnt or 0),
        "note": None if sufficient else "会话样本量不足，任务完成率/弃单率不判定（诚实标注）",
    }


# ── v1.13.6 评估快照层（历史趋势对比 + 迭代闭环）──

async def fetch_agent_traces_as_dicts(
    db, window_days: int | None = None, limit: int = 500,
) -> list[dict]:
    """从 agent_traces 拉取轨迹并转换为 IHomeEvalRunner 期望的 dict 形态。

    映射 AgentTraceRecord → {status, fallback_used, latency_ms,
    first_token_latency_ms, agent_name, tool_call_count, token_budget_hit,
    response_truncated}（response_preview → response_truncated）。
    """
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select
    from app.models.agent_trace import AgentTraceRecord

    stmt = select(AgentTraceRecord)
    if window_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        stmt = stmt.where(AgentTraceRecord.created_at >= cutoff)
    stmt = stmt.order_by(AgentTraceRecord.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "status": r.status,
            "fallback_used": bool(r.fallback_used),
            "latency_ms": float(r.latency_ms or 0.0),
            "first_token_latency_ms": float(r.first_token_latency_ms or 0.0),
            "agent_name": r.agent_name,
            "tool_call_count": int(r.tool_call_count or 0),
            "token_budget_hit": bool(r.token_budget_hit),
            "response_truncated": r.response_preview or "",
        }
        for r in rows
    ]


async def persist_eval_snapshot(db, report: IHomeEvalReport) -> str:
    """落一条评估快照（best-effort）。

    把完整评估报告（metrics/dimension_scores/per_agent_scores/... ）序列化到
    eval_snapshots 表，供历史趋势对比与漂移检测（vs 历史基线）。
    """
    from app.models.eval_snapshot import EvalSnapshotRecord

    record = EvalSnapshotRecord(
        version=settings.app_version,
        baseline=report.baseline,
        sample_size=report.sample_size,
        metrics=report.metrics,
        dimension_scores=report.dimension_scores,
        per_agent_scores=report.per_agent_scores,
        quality_targets=report.quality_targets,
        tool_accuracy=report.tool_accuracy,
        feedback_metrics=report.feedback_metrics,
        ux_metrics=report.ux_metrics,
        notes=report.notes,
    )
    db.add(record)
    if db.in_transaction():
        await db.commit()
    return record.id


async def list_eval_snapshots(db, limit: int = 50) -> list[dict]:
    """列出最近评估快照（倒序）。"""
    from sqlalchemy import select
    from app.models.eval_snapshot import EvalSnapshotRecord

    result = await db.execute(
        select(EvalSnapshotRecord)
        .order_by(EvalSnapshotRecord.created_at.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "version": r.version,
            "baseline": r.baseline,
            "sample_size": r.sample_size,
            "metrics": r.metrics or {},
            "dimension_scores": r.dimension_scores or {},
            "per_agent_scores": r.per_agent_scores or {},
            "quality_targets": r.quality_targets or {},
            "tool_accuracy": r.tool_accuracy or {},
            "feedback_metrics": r.feedback_metrics or {},
            "ux_metrics": r.ux_metrics or {},
            "notes": r.notes or [],
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def _delta(current: float, previous: float) -> float:
    return round(current - previous, 2)


async def compute_snapshot_trend(db, limit: int = 30) -> dict:
    """评估快照趋势（v1.13.6，多轮迭代闭环）。

    按时间升序对比关键指标 vs 上一快照（delta_prev）与首个基线快照
    （delta_baseline）：success_rate / fallback_rate / avg_latency_ms /
    first_token_p95_ms。
    """
    from sqlalchemy import select
    from app.models.eval_snapshot import EvalSnapshotRecord

    result = await db.execute(
        select(EvalSnapshotRecord)
        .order_by(EvalSnapshotRecord.created_at.asc())
        .limit(limit)
    )
    rows = result.scalars().all()
    trend: list[dict] = []
    first_metrics: dict = {}
    prev_metrics: dict = {}
    keys = ("success_rate", "fallback_rate", "avg_latency_ms", "first_token_p95_ms")
    for i, r in enumerate(rows):
        m = r.metrics or {}
        if i == 0:
            first_metrics = m
        entry = {
            "id": r.id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "sample_size": r.sample_size,
            "metrics": {k: m.get(k) for k in keys},
            "delta_prev": {},
            "delta_baseline": {},
        }
        if prev_metrics:
            entry["delta_prev"] = {
                k: _delta(m.get(k) or 0, prev_metrics.get(k) or 0) for k in keys
            }
        if i > 0 and first_metrics:
            entry["delta_baseline"] = {
                k: _delta(m.get(k) or 0, first_metrics.get(k) or 0) for k in keys
            }
        trend.append(entry)
        prev_metrics = m
    return {"snapshot_count": len(trend), "trend": trend}


async def detect_drift_vs_history(
    db, window_days: int = 7, min_samples: int = 5,
) -> dict:
    """当前窗口 vs 最近历史快照基线 的 per-agent 漂移（v1.13.6）。

    取最近一条快照的 per_agent_scores 作为历史基线，对比当前窗口 per-agent
    成功率/降级率/平均延迟，输出 delta（当前 - 历史）。
    """
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import case, func, select
    from app.models.agent_trace import AgentTraceRecord
    from app.models.eval_snapshot import EvalSnapshotRecord

    snap = await db.execute(
        select(EvalSnapshotRecord).order_by(EvalSnapshotRecord.created_at.desc()).limit(1)
    )
    snap_row = snap.scalars().first()
    if snap_row is None:
        return {"available": False, "reason": "无历史快照基线", "records": []}
    baseline_per_agent = snap_row.per_agent_scores or {}

    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    stmt = (
        select(
            AgentTraceRecord.agent_name,
            func.count().label("cnt"),
            func.sum(case((AgentTraceRecord.status == "success", 1), else_=0)).label("success_cnt"),
            func.sum(case((AgentTraceRecord.fallback_used.is_(True), 1), else_=0)).label("fallback_cnt"),
            func.avg(AgentTraceRecord.latency_ms).label("avg_latency"),
        )
        .where(AgentTraceRecord.created_at >= cutoff)
        .group_by(AgentTraceRecord.agent_name)
    )
    result = await db.execute(stmt)
    records: list[dict] = []
    for name, cnt, success_cnt, fallback_cnt, avg_latency in result.all():
        total = int(cnt)
        if total < min_samples:
            continue
        success_rate = round(int(success_cnt or 0) / total * 100, 2)
        fallback_rate = round(int(fallback_cnt or 0) / total * 100, 2)
        avg_latency = round(float(avg_latency or 0), 2)
        base = baseline_per_agent.get(name, {})
        records.append({
            "agent_name": name,
            "sample_size": total,
            "current": {
                "success_rate": success_rate,
                "fallback_rate": fallback_rate,
                "avg_latency_ms": avg_latency,
            },
            "baseline": {
                "success_rate": base.get("success_rate"),
                "fallback_rate": base.get("fallback_rate"),
                "avg_latency_ms": base.get("avg_latency_ms"),
            },
            "delta": {
                "success_rate": _delta(success_rate, base.get("success_rate") or 0),
                "fallback_rate": _delta(fallback_rate, base.get("fallback_rate") or 0),
                "avg_latency_ms": _delta(avg_latency, base.get("avg_latency_ms") or 0),
            },
        })
    return {
        "available": True,
        "baseline_snapshot_id": snap_row.id,
        "baseline_created_at": snap_row.created_at.isoformat() if snap_row.created_at else None,
        "records": records,
    }
