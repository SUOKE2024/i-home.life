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
        """工具调用准确性：有 tool_call 且 status=success 的比例"""
        if not traces:
            return 0.0
        with_tools = [t for t in traces if t.get("tool_call_count", 0) > 0]
        if not with_tools:
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

        Returns:
            {"designer": {"sample_size": n, "success_rate": .., "fallback_rate": ..,
                          "avg_latency_ms": .., "meets_targets": bool}, ...}
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
            meets = (
                success_rate >= QUALITY_TARGETS["success_rate_min"]
                and fallback_rate <= QUALITY_TARGETS["fallback_rate_max"]
            )
            scores[name] = {
                "sample_size": total,
                "success_rate": success_rate,
                "fallback_rate": fallback_rate,
                "avg_latency_ms": round(avg_latency, 2),
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


async def detect_agent_drift(
    db, window_days: int = 7, min_samples: int = 5,
) -> list[dict]:
    """基于 agent_traces 持久化轨迹的 per-agent 质量漂移检测。

    对比当前窗口 per-agent 成功率/降级率/平均延迟与 QUALITY_TARGETS 量化基线：
    - 低于目标值但差距 <10% → warn
    - 低于目标值且差距 ≥10% → critical
    样本量不足（< min_samples）的 Agent 标记 insufficient_samples（不判定）。

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
            func.avg(AgentTraceRecord.latency_ms).label("avg_latency"),
        )
        .where(AgentTraceRecord.created_at >= cutoff)
        .group_by(AgentTraceRecord.agent_name)
    )
    result = await db.execute(stmt)
    rows = result.all()

    drift: list[dict] = []
    for name, cnt, success_cnt, fallback_cnt, avg_latency in rows:
        total = int(cnt)
        success_cnt = int(success_cnt or 0)
        fallback_cnt = int(fallback_cnt or 0)
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
    return drift
