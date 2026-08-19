"""v1.13.6 质量评估体系测试（响应速度实测 + LLM judge + 快照层 + UX 维度）

覆盖：
- _percentile 分位数
- _compute_runtime_metrics 延迟分位数 + 首 token p95
- llm_judge 解析 + 注入 judge 评估
- compute_ux_metrics（任务完成率/弃单率/会话轮次/星级）
- persist_eval_snapshot / list_eval_snapshots / compute_snapshot_trend
- fetch_agent_traces_as_dicts 映射
- 新端点：/api/eval/llm-judge（门控）/trend/drift/history/snapshots
"""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from app.eval.ihome_eval import (
    IHomeEvalReport,
    IHomeEvalRunner,
    _percentile,
    compute_snapshot_trend,
    compute_ux_metrics,
    fetch_agent_traces_as_dicts,
    list_eval_snapshots,
    persist_eval_snapshot,
)


async def _register_admin(client: AsyncClient) -> dict:
    """直接通过 DB 创建管理员并签发 token（register 已禁止自注册 admin）"""
    import uuid as _uuid
    from app.database import async_session
    from app.models.user import User
    from app.auth.paseto_handler import create_token

    user_id = str(_uuid.uuid4())
    async with async_session() as db:
        db.add(User(id=user_id, phone=f"139{_uuid.uuid4().hex[:8]}", name="管理员测试", role="admin", hashed_password="x"))
        await db.commit()
    return {"Authorization": f"Bearer {create_token(user_id, 'admin')}"}


# ── 分位数 ──


def test_percentile():
    assert _percentile([], 0.95) == 0.0
    assert _percentile([1, 2, 3, 4], 0.5) == 2.5
    assert _percentile([1, 2, 3, 4, 5], 0.5) == 3.0
    assert _percentile([100], 0.95) == 100.0
    assert _percentile([10, 20, 30], 0.5) == 20.0


def test_runtime_metrics_latency_percentiles():
    traces = [
        {
            "status": "success", "fallback_used": False, "latency_ms": 100,
            "first_token_latency_ms": 40, "agent_name": "a",
            "response_truncated": "x", "tool_call_count": 0, "token_budget_hit": False,
        },
        {
            "status": "success", "fallback_used": False, "latency_ms": 200,
            "first_token_latency_ms": 60, "agent_name": "a",
            "response_truncated": "x", "tool_call_count": 0, "token_budget_hit": False,
        },
        {
            "status": "success", "fallback_used": False, "latency_ms": 300,
            "first_token_latency_ms": 80, "agent_name": "a",
            "response_truncated": "x", "tool_call_count": 0, "token_budget_hit": False,
        },
    ]
    m = IHomeEvalRunner()._compute_runtime_metrics(traces)
    assert m["latency_p50_ms"] == 200.0
    assert m["latency_p95_ms"] == 290.0  # [100,200,300] p95 线性插值
    assert m["first_token_p95_ms"] > 0
    assert m["success_rate"] == 100.0


def test_runtime_metrics_first_token_empty_fallback():
    """无首 token 数据 → first_token_p95 = 0（诚实标注，不伪造）"""
    traces = [
        {
            "status": "success", "fallback_used": False, "latency_ms": 100,
            "first_token_latency_ms": 0, "agent_name": "a",
            "response_truncated": "x", "tool_call_count": 0, "token_budget_hit": False,
        },
    ]
    m = IHomeEvalRunner()._compute_runtime_metrics(traces)
    assert m["first_token_p95_ms"] == 0.0


def test_runtime_metrics_delivery_p95_ms():
    """交付链路（designer/budget 等）延迟聚合为 delivery_p95_ms；非交付 Agent 不计入"""
    traces = [
        {
            "status": "success", "fallback_used": False, "latency_ms": 100,
            "first_token_latency_ms": 0, "agent_name": "designer",
            "response_truncated": "x", "tool_call_count": 0, "token_budget_hit": False,
        },
        {
            "status": "success", "fallback_used": False, "latency_ms": 300,
            "first_token_latency_ms": 0, "agent_name": "budget",
            "response_truncated": "x", "tool_call_count": 0, "token_budget_hit": False,
        },
        {
            "status": "success", "fallback_used": False, "latency_ms": 9999,
            "first_token_latency_ms": 0, "agent_name": "concierge",
            "response_truncated": "x", "tool_call_count": 0, "token_budget_hit": False,
        },
    ]
    m = IHomeEvalRunner()._compute_runtime_metrics(traces)
    # 仅 designer + budget 计入交付链路：[100, 300] p95 = 290；concierge 被排除
    assert m["delivery_p95_ms"] == 290.0


# ── LLM-as-judge ──


def test_parse_judge_reply():
    from app.eval.llm_judge import _parse_judge_reply

    scores = _parse_judge_reply('{"faithfulness": 5, "completeness": 4, "sufficiency": 3}')
    assert scores == {"faithfulness": 1.0, "completeness": 0.8, "sufficiency": 0.6}
    assert _parse_judge_reply("invalid") == {
        "faithfulness": 0.0, "completeness": 0.0, "sufficiency": 0.0,
    }
    # markdown 包裹的 JSON 也能解析
    assert _parse_judge_reply('```\n{"faithfulness": 2, "completeness": 2, "sufficiency": 2}\n```')[
        "faithfulness"
    ] == 0.4


@pytest.mark.asyncio
async def test_evaluate_llm_judge_injected():
    from app.eval.llm_judge import evaluate_llm_judge

    async def fake_judge(prompt: str, reply: str) -> dict:
        return {"faithfulness": 1.0, "completeness": 0.5, "sufficiency": 0.0}

    samples = [{"prompt": f"q{i}", "reply": f"r{i}"} for i in range(5)]
    report = await evaluate_llm_judge(
        samples=samples, sample_size=3, random_seed=42, judge=fake_judge,
    )
    assert report["report_type"] == "llm_judge_semantic_quality"
    assert report["sample_size"] == 3
    assert report["dimensions"]["faithfulness"]["llm_judge"] == 1.0
    assert report["dimensions"]["completeness"]["llm_judge"] == 0.5
    assert report["dimensions"]["sufficiency"]["llm_judge"] == 0.0
    # 关键词基线并列存在
    assert "keyword_baseline" in report["dimensions"]["faithfulness"]


@pytest.mark.asyncio
async def test_evaluate_llm_judge_empty_samples():
    from app.eval.llm_judge import evaluate_llm_judge

    report = await evaluate_llm_judge(samples=[], sample_size=5)
    assert report["sample_size"] == 0
    assert report["dimensions"]["faithfulness"]["llm_judge"] == 0.0


@pytest.mark.asyncio
async def test_judge_reply_pass_k_consistent():
    """pass^k：k 次一致 → agreement=1.0，均值等于单次分。"""
    from app.eval.llm_judge import judge_reply_pass_k

    async def fake(prompt: str, reply: str) -> dict:
        return {"faithfulness": 1.0, "completeness": 0.8, "sufficiency": 0.6}

    result = await judge_reply_pass_k("q", "r", k=3, judge=fake)
    assert result["k"] == 3
    assert result["agreement"] == 1.0
    assert result["scores"]["faithfulness"] == 1.0
    assert result["scores"]["completeness"] == 0.8
    assert result["scores"]["sufficiency"] == 0.6


@pytest.mark.asyncio
async def test_judge_reply_pass_k_agreement_computed():
    """pass^k：k 次分不一致 → agreement 按维度极差 ≤0.2 计算。"""
    from app.eval.llm_judge import judge_reply_pass_k

    call = {"n": 0}

    async def fake(prompt: str, reply: str) -> dict:
        # faithfulness 恒 1.0（一致），completeness 逐次递减（不一致）
        scores = {
            "faithfulness": 1.0,
            "completeness": [0.8, 0.6, 0.4][call["n"] % 3],
            "sufficiency": 0.6,
        }
        call["n"] += 1
        return scores

    result = await judge_reply_pass_k("q", "r", k=3, judge=fake)
    # completeness 极差 0.4 > 0.2 → 不一致；其余两维一致 → agreement = 2/3
    assert result["agreement"] == pytest.approx(2 / 3, abs=0.01)
    assert result["scores"]["completeness"] == pytest.approx(0.6, abs=0.01)


@pytest.mark.asyncio
async def test_judge_reply_pass_k_k1_degenerates():
    """k=1 退化为单次 judge，agreement=1.0。"""
    from app.eval.llm_judge import judge_reply_pass_k

    async def fake(prompt: str, reply: str) -> dict:
        return {"faithfulness": 0.5, "completeness": 0.5, "sufficiency": 0.5}

    result = await judge_reply_pass_k("q", "r", k=1, judge=fake)
    assert result["k"] == 1
    assert result["agreement"] == 1.0
    assert len(result["runs"]) == 1


# ════════════════════════════════════════════════════════════════
# v1.15.8 P2-4：终端任务成功率评测（ITBench-AA 式用户目标达成率）
# ════════════════════════════════════════════════════════════════

def test_parse_task_success_reply():
    from app.eval.llm_judge import _parse_task_success_reply

    assert _parse_task_success_reply('{"task_success": 1}') == 1
    assert _parse_task_success_reply('```\n{"task_success": 0}\n```') == 0
    # markdown 包裹 + 多余文本
    assert _parse_task_success_reply('评估结果：\n{"task_success": 1}') == 1
    # 解析失败 → None（诚实标注 unknown）
    assert _parse_task_success_reply("invalid output") is None
    assert _parse_task_success_reply('{"task_success": 5}') is None


@pytest.mark.asyncio
async def test_judge_task_success_injected_agent():
    """注入 mock agent：LLM 输出解析为达成/未达成/unknown。"""
    from unittest.mock import AsyncMock
    from app.eval.llm_judge import judge_task_success

    agent = AsyncMock()
    agent.chat.return_value = '{"task_success": 1}'
    assert (await judge_task_success("q", "r", agent=agent))["success"] is True

    agent.chat.return_value = '{"task_success": 0}'
    assert (await judge_task_success("q", "r", agent=agent))["success"] is False

    agent.chat.return_value = "无法解析"
    assert (await judge_task_success("q", "r", agent=agent))["success"] is None


@pytest.mark.asyncio
async def test_evaluate_task_success_rate_injected():
    """注入 fake judge：聚合达成率 + unknown 不计入分母。"""
    from app.eval.llm_judge import evaluate_task_success_rate

    async def fake_judge(prompt: str, reply: str) -> dict:
        # 按回复内容返回：达成/未达成/解析失败
        if reply == "ok":
            return {"success": True}
        if reply == "fail":
            return {"success": False}
        return {"success": None}

    samples = [
        {"prompt": "q0", "reply": "ok"},
        {"prompt": "q1", "reply": "ok"},
        {"prompt": "q2", "reply": "fail"},
        {"prompt": "q3", "reply": "unknown"},
    ]
    report = await evaluate_task_success_rate(
        samples=samples, sample_size=10, judge=fake_judge,
    )
    assert report["report_type"] == "llm_judge_task_success_rate"
    assert report["sample_size"] == 4
    assert report["success_count"] == 2
    assert report["failure_count"] == 1
    assert report["unknown_count"] == 1
    # 分母 = 2 成功 + 1 失败 = 3（unknown 排除）
    assert report["success_rate"] == pytest.approx(2 / 3, abs=0.001)


@pytest.mark.asyncio
async def test_evaluate_task_success_rate_sampling():
    """random_seed 可复现抽样 + 空样本诚实返回 0。"""
    from app.eval.llm_judge import evaluate_task_success_rate

    async def fake_judge(prompt: str, reply: str) -> dict:
        return {"success": True}

    samples = [{"prompt": f"q{i}", "reply": "ok"} for i in range(10)]
    r1 = await evaluate_task_success_rate(
        samples=samples, sample_size=4, random_seed=7, judge=fake_judge,
    )
    r2 = await evaluate_task_success_rate(
        samples=samples, sample_size=4, random_seed=7, judge=fake_judge,
    )
    assert r1["sample_size"] == 4
    assert r1["success_count"] == r2["success_count"] == 4
    assert r1["success_rate"] == 1.0

    empty = await evaluate_task_success_rate(samples=[], judge=fake_judge)
    assert empty["sample_size"] == 0
    assert empty["success_rate"] == 0.0


@pytest.mark.asyncio
async def test_evaluate_judge_alignment():
    """金标对齐：judge 与金标完全一致 → overall_mae=0，agreement_rate=1.0。"""
    from app.eval.llm_judge import evaluate_judge_alignment

    async def perfect_judge(prompt: str, reply: str) -> dict:
        return {"faithfulness": 1.0, "completeness": 1.0, "sufficiency": 1.0}

    gold = [
        {"prompt": "p1", "reply": "r1",
         "gold": {"faithfulness": 1.0, "completeness": 1.0, "sufficiency": 1.0}},
        {"prompt": "p2", "reply": "r2",
         "gold": {"faithfulness": 1.0, "completeness": 1.0, "sufficiency": 1.0}},
    ]
    report = await evaluate_judge_alignment(judge=perfect_judge, gold_dataset=gold)
    assert report["available"] is True
    assert report["sample_size"] == 2
    assert report["overall_mae"] == 0.0
    assert report["agreement_rate"] == 1.0


@pytest.mark.asyncio
async def test_evaluate_judge_alignment_no_gold():
    """无金标数据 → available=False 诚实标注。"""
    from app.eval.llm_judge import evaluate_judge_alignment

    report = await evaluate_judge_alignment(gold_dataset=[])
    assert report["available"] is False
    assert report["sample_size"] == 0


@pytest.mark.asyncio
async def test_evaluate_llm_judge_pass_k():
    """evaluate_llm_judge pass_k>1 走 judge_reply_pass_k，报告含 pass_k/agreement。"""
    from app.eval.llm_judge import evaluate_llm_judge

    async def fake(prompt: str, reply: str) -> dict:
        return {"faithfulness": 1.0, "completeness": 0.6, "sufficiency": 0.6}

    report = await evaluate_llm_judge(
        samples=[{"prompt": "q", "reply": "r"}],
        sample_size=1,
        judge=fake,
        pass_k=3,
    )
    assert report["pass_k"] == 3
    assert report["agreement"] == 1.0  # fake 恒同分 → 各维一致
    assert report["sample_size"] == 1
    assert report["dimensions"]["faithfulness"]["llm_judge"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_evaluate_llm_judge_default_single_shot():
    """evaluate_llm_judge 不传 pass_k → 默认单次（旧行为），pass_k=1。"""
    from app.eval.llm_judge import evaluate_llm_judge

    async def fake(prompt: str, reply: str) -> dict:
        return {"faithfulness": 0.5, "completeness": 0.5, "sufficiency": 0.5}

    report = await evaluate_llm_judge(
        samples=[{"prompt": "q", "reply": "r"}],
        sample_size=1,
        judge=fake,
    )
    assert report["pass_k"] == 1
    assert report["agreement"] == 1.0


# ── UX 指标 ──


@pytest.mark.asyncio
async def test_compute_ux_metrics(db_session):
    from app.models.agent_session import AgentSession, AgentMessage
    from app.models.user import User

    user = User(phone=f"17{str(uuid.uuid4().int)[:9]}", name="ux用户")
    db_session.add(user)
    await db_session.flush()
    now = datetime.now(timezone.utc)

    # 会话1：末条 assistant（完成）
    s1 = AgentSession(user_id=user.id, message_count=2, created_at=now)
    db_session.add(s1)
    await db_session.flush()
    db_session.add(AgentMessage(session_id=s1.id, role="user", content="hi", sequence=1, created_at=now))
    db_session.add(AgentMessage(session_id=s1.id, role="assistant", content="hello", sequence=2, created_at=now))

    # 会话2：末条 user（弃单）
    s2 = AgentSession(user_id=user.id, message_count=1, created_at=now)
    db_session.add(s2)
    await db_session.flush()
    db_session.add(AgentMessage(session_id=s2.id, role="user", content="?", sequence=1, created_at=now))
    await db_session.commit()

    metrics = await compute_ux_metrics(db_session, min_samples=1)
    assert metrics["total_sessions"] == 2
    assert metrics["task_completion_rate"] == 50.0
    assert metrics["abandonment_rate"] == 50.0
    assert metrics["avg_turns_per_session"] == 1.0


@pytest.mark.asyncio
async def test_compute_ux_metrics_insufficient_samples(db_session):
    metrics = await compute_ux_metrics(db_session, min_samples=5)
    assert metrics["total_sessions"] == 0
    assert metrics["task_completion_rate"] is None
    assert metrics["abandonment_rate"] is None
    assert "样本量不足" in metrics["note"]


# ── 快照层 ──


def _make_report(**metrics) -> IHomeEvalReport:
    report = IHomeEvalReport(run_id="t", started_at=0.0)
    report.sample_size = 10
    report.metrics = {"success_rate": 95.0, "avg_latency_ms": 100.0, **metrics}
    return report


@pytest.mark.asyncio
async def test_persist_list_trend_snapshot(db_session):
    sid = await persist_eval_snapshot(db_session, _make_report(first_token_p95_ms=800.0))
    assert sid

    snapshots = await list_eval_snapshots(db_session)
    assert len(snapshots) == 1
    assert snapshots[0]["metrics"]["success_rate"] == 95.0
    assert snapshots[0]["metrics"]["first_token_p95_ms"] == 800.0

    trend = await compute_snapshot_trend(db_session)
    assert trend["snapshot_count"] == 1
    assert trend["trend"][0]["metrics"]["success_rate"] == 95.0
    assert trend["trend"][0]["delta_prev"] == {}
    assert trend["trend"][0]["delta_baseline"] == {}


@pytest.mark.asyncio
async def test_snapshot_trend_delta(db_session):
    await persist_eval_snapshot(db_session, _make_report(success_rate=90.0))
    await persist_eval_snapshot(db_session, _make_report(success_rate=95.0))

    trend = await compute_snapshot_trend(db_session)
    assert trend["snapshot_count"] == 2
    assert trend["trend"][1]["delta_prev"]["success_rate"] == 5.0
    assert trend["trend"][1]["delta_baseline"]["success_rate"] == 5.0


@pytest.mark.asyncio
async def test_fetch_agent_traces_as_dicts(db_session):
    from app.models.agent_trace import AgentTraceRecord

    db_session.add(AgentTraceRecord(
        agent_name="designer", status="success", latency_ms=123.0,
        first_token_latency_ms=45.0, response_preview="reply",
    ))
    await db_session.commit()

    traces = await fetch_agent_traces_as_dicts(db_session)
    assert len(traces) == 1
    assert traces[0]["agent_name"] == "designer"
    assert traces[0]["latency_ms"] == 123.0
    assert traces[0]["first_token_latency_ms"] == 45.0
    assert traces[0]["response_truncated"] == "reply"


# ── 端点 ──


@pytest.mark.asyncio
async def test_llm_judge_endpoint_gated(client: AsyncClient, monkeypatch):
    """llm_judge_enabled=False（默认）→ 503 诚实降级"""
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "llm_judge_enabled", False)

    headers = await _register_admin(client)
    resp = await client.post("/api/eval/llm-judge", json={"sample_size": 5}, headers=headers)
    assert resp.status_code == 503
    assert "未启用" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_trend_endpoint_admin(client: AsyncClient):
    headers = await _register_admin(client)
    resp = await client.get("/api/eval/trend", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "snapshot_count" in data
    assert "trend" in data


@pytest.mark.asyncio
async def test_drift_history_endpoint_admin(client: AsyncClient):
    headers = await _register_admin(client)
    resp = await client.get("/api/eval/drift/history", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "available" in data
    # 无历史快照基线时诚实标注
    assert data["available"] is False
    assert "records" in data


@pytest.mark.asyncio
async def test_snapshots_endpoint_admin(client: AsyncClient):
    headers = await _register_admin(client)
    resp = await client.get("/api/eval/snapshots", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data
    assert "snapshots" in data


@pytest.mark.asyncio
async def test_eval_run_persists_snapshot(client: AsyncClient):
    """POST /api/eval/run → 报告含 ux_metrics 且落快照（notes 含 snapshot_id）"""
    headers = await _register_admin(client)
    resp = await client.post("/api/eval/run", json={"baseline": "full_system"}, headers=headers)
    assert resp.status_code == 200, f"eval/run: {resp.status_code} {resp.text[:200]}"
    data = resp.json()
    assert "ux_metrics" in data, "报告应包含 ux_metrics（v1.13.6）"
    assert any(n.startswith("snapshot_id=") for n in data["notes"]), data["notes"]
