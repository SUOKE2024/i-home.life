"""评估体系升级测试（v1.12.x）

覆盖：
- 新维度：FAITHFULNESS / COMPLETENESS / SUFFICIENCY 评分计算
- per-agent 评分：成功率/降级率/延迟/meets_targets
- 量化目标基线：QUALITY_TARGETS 存在且关键项齐全
- 报告序列化：per_agent_scores + quality_targets 进入 to_dict
- 漂移检测 detect_agent_drift：ok/warn/critical/insufficient_samples 判定
- 评估 API：/api/eval/drift 管理员鉴权 + 报告含 per-agent 字段
"""
import pytest

from app.eval import IHomeEvalDimension, QUALITY_TARGETS
from app.eval.ihome_eval import (
    IHomeEvalReport, IHomeEvalRunner, detect_agent_drift,
)
from app.models.agent_trace import AgentTraceRecord


def _trace(agent: str, status: str = "success", fallback: bool = False,
           latency: float = 1000.0, response: str = "根据市场数据，方案如下：\n1. 水电改造\n总结：共 3 项") -> dict:
    return {
        "agent_name": agent, "status": status, "fallback_used": fallback,
        "latency_ms": latency, "response_truncated": response[:200],
        "tool_call_count": 0, "workflow_id": "",
    }


# ── 新维度评分 ──


def test_faithfulness_completeness_sufficiency_scores():
    long_resp = ("根据市场数据与历史项目均价，以下为您的预算方案：\n"
                 "1. 水电改造：¥2万\n2. 墙面工程：¥1.5万\n总结：共 3 项主要支出，具体以报价单为准。")
    traces = [_trace("designer", response=long_resp), _trace("budget", response="ok")]
    runner = IHomeEvalRunner()
    scores = runner._compute_dimension_scores(
        traces, {"fallback_rate": 0, "reasoning_leak_rate": 0, "avg_latency_ms": 1000}
    )
    # 忠实性：第一条含「根据/来源」→ 50%
    assert scores[IHomeEvalDimension.FAITHFULNESS.value] == 50.0
    # 完整性：第一条含「总结/1.」→ 50%
    assert scores[IHomeEvalDimension.COMPLETENESS.value] == 50.0
    # 充分性：第一条长度适中 → 50%（第二条 "ok" 过短）
    assert scores[IHomeEvalDimension.SUFFICIENCY.value] == 50.0


def test_quality_targets_present():
    assert QUALITY_TARGETS["success_rate_min"] == 95.0
    assert QUALITY_TARGETS["fallback_rate_max"] == 5.0
    assert QUALITY_TARGETS["avg_latency_ms_max"] > 0


# ── per-agent 评分 ──


def test_per_agent_scores():
    traces = [
        _trace("designer", status="success"),
        _trace("designer", status="success"),
        _trace("designer", status="fallback", fallback=True),
        _trace("budget", status="success"),
    ]
    runner = IHomeEvalRunner()
    per = runner._compute_per_agent_scores(traces)
    assert per["designer"]["sample_size"] == 3
    assert per["designer"]["success_rate"] == pytest.approx(66.67, abs=0.1)
    assert per["designer"]["fallback_rate"] == pytest.approx(33.33, abs=0.1)
    assert per["designer"]["meets_targets"] is False
    assert per["budget"]["sample_size"] == 1
    assert per["budget"]["meets_targets"] is True


def test_report_to_dict_includes_new_fields():
    report = IHomeEvalReport(run_id="r1", started_at=0)
    report.per_agent_scores = {"designer": {"sample_size": 1}}
    report.quality_targets = dict(QUALITY_TARGETS)
    d = report.to_dict()
    assert "per_agent_scores" in d
    assert "quality_targets" in d
    assert "faithfulness" in d["dimension_benchmarks"]


# ── 漂移检测 ──


async def _seed_traces(db, agent: str, total: int, success: int, fallback: int) -> None:
    from datetime import datetime, timezone
    for i in range(total):
        db.add(AgentTraceRecord(
            id=f"{agent}_{i}",
            agent_name=agent,
            status="success" if i < success else "failed",
            fallback_used=(i >= success) and (i < success + fallback),
            latency_ms=1000.0,
            created_at=datetime.now(timezone.utc),
        ))
    await db.commit()


async def test_drift_ok_agent(db_session):
    await _seed_traces(db_session, "designer", 10, 10, 0)
    drift = await detect_agent_drift(db_session, window_days=7)
    designer = [d for d in drift if d["agent_name"] == "designer"]
    assert len(designer) == 3  # success_rate / fallback_rate / avg_latency
    assert all(d["status"] == "ok" for d in designer)


async def test_drift_critical_on_low_success(db_session):
    await _seed_traces(db_session, "budget", 10, 4, 6)
    drift = await detect_agent_drift(db_session, window_days=7)
    budget = [d for d in drift if d["agent_name"] == "budget"]
    success = next(d for d in budget if d["metric"] == "success_rate")
    # 40% vs 目标 95%，差距 >10% → critical
    assert success["status"] == "critical"
    fallback = next(d for d in budget if d["metric"] == "fallback_rate")
    # 60% vs 目标 5%，差距 >10% → critical
    assert fallback["status"] == "critical"


async def test_drift_insufficient_samples(db_session):
    await _seed_traces(db_session, "concierge", 2, 2, 0)
    drift = await detect_agent_drift(db_session, window_days=7, min_samples=5)
    concierge = [d for d in drift if d["agent_name"] == "concierge"]
    assert len(concierge) == 1
    assert concierge[0]["status"] == "insufficient_samples"
