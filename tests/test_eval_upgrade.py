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
    # success_rate / fallback_rate / avg_latency / token_budget_hit_rate（v1.13.1）
    assert len(designer) == 4
    assert all(d["status"] == "ok" for d in designer)


async def test_drift_token_budget_hit_rate_critical(db_session):
    """token 预算早停率高 → critical（v1.13.1：早停率 > 20% 需优化工具结果上下文）。"""
    from datetime import datetime, timezone
    # 10 条轨迹，6 条预算早停（60% > 上限 20%）
    for i in range(10):
        db_session.add(AgentTraceRecord(
            id=f"budget_stop_{i}",
            agent_name="budget",
            status="success",
            fallback_used=False,
            token_budget_hit=(i < 6),
            latency_ms=1000.0,
            created_at=datetime.now(timezone.utc),
        ))
    await db_session.commit()
    drift = await detect_agent_drift(db_session, window_days=7)
    budget = [d for d in drift if d["agent_name"] == "budget"]
    budget_hit = next(d for d in budget if d["metric"] == "token_budget_hit_rate")
    # 60% vs 目标 20%，差距 >10% → critical
    assert budget_hit["status"] == "critical"
    assert budget_hit["current"] == 60.0


async def test_drift_token_budget_hit_rate_ok(db_session):
    """token 预算早停率低 → ok（v1.13.1）。"""
    from datetime import datetime, timezone
    for i in range(10):
        db_session.add(AgentTraceRecord(
            id=f"designer_ok_{i}",
            agent_name="designer",
            status="success",
            fallback_used=False,
            token_budget_hit=(i < 1),  # 10% ≤ 20%
            latency_ms=1000.0,
            created_at=datetime.now(timezone.utc),
        ))
    await db_session.commit()
    drift = await detect_agent_drift(db_session, window_days=7)
    designer = [d for d in drift if d["agent_name"] == "designer"]
    budget_hit = next(d for d in designer if d["metric"] == "token_budget_hit_rate")
    assert budget_hit["status"] == "ok"


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


# ── v1.13.4 反馈满意度漂移（agent_feedbacks 纳入质量门禁）──


async def _seed_feedback(db, agent: str, likes: int, dislikes: int) -> str:
    """预置 feedback 记录（直接插入 User + AgentFeedback），返回 user_id"""
    import uuid
    from datetime import datetime, timezone

    from app.models.agent_feedback import AgentFeedback
    from app.models.user import User

    user = User(phone=f"13{str(uuid.uuid4().int)[:9]}", name="评估测试用户")
    db.add(user)
    await db.flush()
    for i in range(likes):
        db.add(AgentFeedback(
            user_id=user.id, agent_name=agent, message_hash=f"h_l_{i}",
            feedback_type="like", user_message="msg", agent_reply="reply",
            created_at=datetime.now(timezone.utc),
        ))
    for i in range(dislikes):
        db.add(AgentFeedback(
            user_id=user.id, agent_name=agent, message_hash=f"h_d_{i}",
            feedback_type="dislike", user_message="msg", agent_reply="reply",
            created_at=datetime.now(timezone.utc),
        ))
    await db.commit()
    return user.id


async def test_feedback_drift_like_rate_ok(db_session):
    """like 率 ≥ 目标（8/10=80% ≥ 70%）→ ok"""
    from app.eval.ihome_eval import detect_feedback_drift

    await _seed_feedback(db_session, "designer", likes=8, dislikes=2)
    drift = await detect_feedback_drift(db_session, window_days=7)
    designer = [d for d in drift if d["agent_name"] == "designer"]
    assert len(designer) == 1
    assert designer[0]["metric"] == "feedback_like_rate"
    assert designer[0]["status"] == "ok"
    assert designer[0]["current"] == 80.0


async def test_feedback_drift_like_rate_warn(db_session):
    """like 率略低于目标（8/12=66.67% < 70%，差距 <10%）→ warn"""
    from app.eval.ihome_eval import detect_feedback_drift

    await _seed_feedback(db_session, "budget", likes=8, dislikes=4)
    drift = await detect_feedback_drift(db_session, window_days=7)
    budget = [d for d in drift if d["agent_name"] == "budget"]
    assert budget[0]["status"] == "warn"
    assert budget[0]["current"] == 66.67


async def test_feedback_drift_like_rate_critical(db_session):
    """like 率严重低于目标（5/10=50%，差距 ≥10%）→ critical"""
    from app.eval.ihome_eval import detect_feedback_drift

    await _seed_feedback(db_session, "concierge", likes=5, dislikes=5)
    drift = await detect_feedback_drift(db_session, window_days=7)
    concierge = [d for d in drift if d["agent_name"] == "concierge"]
    assert concierge[0]["status"] == "critical"
    assert concierge[0]["current"] == 50.0


async def test_feedback_drift_insufficient_samples(db_session):
    """反馈样本量不足（2 < 5）→ insufficient_samples（诚实标注不判定）"""
    from app.eval.ihome_eval import detect_feedback_drift

    await _seed_feedback(db_session, "kitchen", likes=2, dislikes=0)
    drift = await detect_feedback_drift(db_session, window_days=7, min_samples=5)
    kitchen = [d for d in drift if d["agent_name"] == "kitchen"]
    assert len(kitchen) == 1
    assert kitchen[0]["status"] == "insufficient_samples"
    assert kitchen[0]["metric"] == "feedback_sample_size"
    assert kitchen[0]["current"] == 2


async def test_feedback_drift_no_feedback_returns_empty(db_session):
    """无反馈数据 → 空列表（诚实降级，不伪造）"""
    from app.eval.ihome_eval import detect_feedback_drift

    drift = await detect_feedback_drift(db_session, window_days=7)
    assert drift == []


# ── v1.13.7 P0：评测框架正确性修复 ──


def test_reasoning_leak_rate_uses_leak_detector():
    """思维链泄漏率应检测 reasoning 特征，而非「稍后重试」降级文案。"""
    runner = IHomeEvalRunner()
    traces = [
        # 推理超时降级文案（不应算作思维链泄漏）
        _trace("designer", response="抱歉，AI 推理超时，请稍后重试或简化您的问题。"),
        # 第一人称思维链特征（应算作泄漏）
        _trace("budget", response="我需要理解用户的需求，首先分析户型图。"),
    ]
    metrics = runner._compute_runtime_metrics(traces)
    assert metrics["reasoning_leak_rate"] == 50.0


def test_reasoning_leak_rate_zero_for_normal_replies():
    """正常回复不应触发思维链泄漏。"""
    runner = IHomeEvalRunner()
    traces = [
        _trace("designer", response="根据市场数据，方案如下：\n1. 水电改造\n总结：共 3 项"),
        _trace("budget", response="报价含税：¥20 万，含质保金。"),
    ]
    metrics = runner._compute_runtime_metrics(traces)
    assert metrics["reasoning_leak_rate"] == 0.0


def test_idor_score_uses_actual_route_denominator():
    """IDOR 覆盖率应为 0-100 的自维护占比，不再依赖硬编码 30 基线。"""
    runner = IHomeEvalRunner()
    score = runner._idor_score()
    assert 0.0 < score <= 100.0


def test_hc_compliance_score_measures_wiring():
    """HC 合规率 = 硬约束 applies_to 命中真实 Agent 的占比（经别名映射）。"""
    runner = IHomeEvalRunner()
    score = runner._hc_compliance_score()
    # 9 条 HC 均至少命中一个真实 Agent（door_window 经别名 door_window_waterproof）
    assert score == 100.0


def test_material_score_graded_by_target_agents():
    """材料环保维度 = HC-003 目标 Agent 可达率（procurement/designer/budget 全真实）。"""
    runner = IHomeEvalRunner()
    assert runner._material_score() == 100.0


def test_budget_score_none_without_traces():
    """无 budget 轨迹时返回 None，不伪造 0 分。"""
    runner = IHomeEvalRunner()
    assert runner._budget_score([]) is None
    assert runner._budget_score([_trace("designer")]) is None


def test_dimension_scores_omit_budget_without_data():
    """无 budget 数据时维度评分应省略 budget_accuracy，静态维度仍存在。"""
    runner = IHomeEvalRunner()
    scores = runner._compute_dimension_scores(
        [], {"fallback_rate": 0, "reasoning_leak_rate": 0, "avg_latency_ms": 0}
    )
    assert "budget_accuracy" not in scores
    assert "hc_compliance_rate" in scores
    assert "idor_resistance" in scores


# ── 2026-08-20 评估闭环：IDOR 覆盖率精确化 + 无数据维度诚实省略 ──


def test_idor_coverage_details_classification():
    """IDOR 覆盖率按 covered/admin_gated/public/needs_review 分类，管理员与公开模块不再误计为缺口。"""
    import glob
    import os
    runner = IHomeEvalRunner()
    details = runner._idor_coverage_details()
    api_dir = os.path.join(os.path.dirname(__file__), "..", "app", "api")
    expect_total = len(glob.glob(os.path.join(api_dir, "*.py"))) - 1  # 排除 __init__.py
    assert details["total"] == expect_total
    assert 0.0 < details["score"] <= 100.0
    # 管理员门禁与公开模块正确分类（此前被误计为未覆盖缺口）
    assert "admin.py" in details["admin_gated"]
    assert "harness_api.py" in details["admin_gated"]
    assert "analytics.py" in details["public"]
    # 用户态模块未检出项目归属校验 → 审计候选（非漏洞结论）
    assert "chat.py" in details["needs_review"]
    assert "note" in details


def test_idor_score_refined_above_string_heuristic():
    """精确分类后覆盖率应高于旧的字符串存在性粗筛（管理员/公开模块不再被计为缺口）。"""
    runner = IHomeEvalRunner()
    # 旧启发式 = 含 verify_project_access 的模块占比
    import glob
    import os
    api_dir = os.path.join(os.path.dirname(__file__), "..", "app", "api")
    total = len(glob.glob(os.path.join(api_dir, "*.py"))) - 1  # 排除 __init__.py
    covered = sum(
        1 for p in glob.glob(os.path.join(api_dir, "*.py"))
        if p.endswith("__init__.py") is False
        and "verify_project_access" in open(p, encoding="utf-8", errors="ignore").read()
    )
    old_score = covered / total * 100
    assert runner._idor_score() > old_score


def test_empty_traces_omit_data_driven_dimensions():
    """无轨迹样本时省略数据驱动维度（诚实标注），仅保留静态维度——不再输出「降级率 100/忠实性 0」失真混合。"""
    runner = IHomeEvalRunner()
    report = runner.run(traces=[])
    scores = report.dimension_scores
    data_dims = {
        "fallback_rate", "reasoning_leak_rate", "sse_latency",
        "tool_call_accuracy", "faithfulness", "completeness",
        "sufficiency", "counter_argument_quality",
    }
    assert not (data_dims & set(scores)), f"无数据时不应输出数据驱动维度: {sorted(data_dims & set(scores))}"
    assert "idor_resistance" in scores
    assert "hc_compliance_rate" in scores
    assert "material_contraindication" in scores
    assert report.notes, "无数据时应含诚实标注 note"


def test_report_to_dict_includes_idor_coverage():
    """报告序列化应包含 idor_coverage 明细（可行动审计清单）。"""
    runner = IHomeEvalRunner()
    report = runner.run(traces=[])
    d = report.to_dict()
    assert "idor_coverage" in d
    assert d["idor_coverage"]["total"] > 0
    assert "needs_review" in d["idor_coverage"]
