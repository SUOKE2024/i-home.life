"""v1.15.5 前沿借鉴落地测试 — 失败学习 / 协议信任层 / 语境工程 / 自适应路由

覆盖（对应 docs/frontier-borrowing-2026-08-17.md 执行记录）：
- P0-1 失败案例蒸馏：确定性失败分类 / 失败 Case 沉淀 / harness 降级提取 /
  反模式 Skill 蒸馏 / 反模式提示注入
- P0-2 协议信任层：A2A 证据链（trace_id + evidence）/ 可验证支付意图
  （HMAC 签发与校验 / 篡改 / 过期 / 字段比对 / 端点 403+503）
- P1-3 语境工程：上下文压缩（阈值 / 摘要注入 / 失败回退截断 / flag 关闭）
- P1-4 自适应路由：复杂度判定规则 / 供应商链动态排序 / 向后兼容
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.agents.base import BaseAgent
from app.agents.harness import AgentRunStatus, get_harness
from app.config import get_settings
from app.models.agent_case import AgentCase
from app.models.agent_skill import AgentSkill, STATUS_ACTIVE, STATUS_DRAFT
from app.models.project import Project
from app.models.procurement import Supplier, ProcurementOrder
from app.models.user import User
from app.services.agent_case_service import (
    _classify_failure_type,
    extract_failure_case_from_trace,
)
from app.services.agent_skill_evolution_service import (
    _ANTI_PATTERN_PREFIX,
    distill_anti_pattern_skill,
    get_anti_pattern_hints,
    run_skill_evolution_cycle,
)
from app.services.context_compaction_service import compact_history
from app.services.agent_payment_intent import (
    create_payment_intent,
    verify_payment_intent,
)

settings = get_settings()


# ════════════════════════════════════════════════════════════════
# P0-1 失败案例蒸馏闭环
# ════════════════════════════════════════════════════════════════

class TestFailureClassification:
    """确定性失败分类（零 LLM 成本，病理键抗过拟合）"""

    def test_timeout_from_fallback_reason(self):
        trace = {"status": "fallback", "fallback_reason": "all_retries_exhausted"}
        assert _classify_failure_type(trace) == "timeout"

    def test_timeout_from_error_type(self):
        trace = {"status": "failed", "error_type": "asyncio.TimeoutError"}
        assert _classify_failure_type(trace) == "timeout"

    def test_empty_reply_explicit_signal(self):
        trace = {"status": "failed", "fallback_reason": "empty reply from LLM"}
        assert _classify_failure_type(trace) == "empty_reply"

    def test_fallback_status(self):
        trace = {"status": "fallback", "fallback_reason": "rule_fallback"}
        assert _classify_failure_type(trace) == "fallback"

    def test_llm_error(self):
        trace = {"status": "failed", "error_message": "connection reset"}
        assert _classify_failure_type(trace) == "llm_error"

    def test_tool_loop(self):
        trace = {"status": "failed", "error_message": "token_budget_hit 预算触顶"}
        assert _classify_failure_type(trace) == "tool_loop"

    def test_unknown(self):
        assert _classify_failure_type({"status": "failed"}) == "unknown"


class TestFailureCaseExtraction:
    def _trace(self, **overrides):
        base = {
            "trace_id": "fail_trace_001",
            "agent_name": "designer",
            "user_message": "帮我设计一个北欧风格的客厅方案",
            "status": "fallback",
            "fallback_reason": "all_retries_exhausted",
        }
        base.update(overrides)
        return base

    async def test_creates_failed_case(self, db_session):
        case = await extract_failure_case_from_trace(
            self._trace(), db_session, owner_id="user_1", created_by="user_1",
        )
        assert case is not None
        assert case.outcome == "failed"
        assert case.quality_score == 0.0
        assert case.failure_type == "timeout"
        assert case.agent_name == "designer"

    async def test_skips_success_trace(self, db_session):
        case = await extract_failure_case_from_trace(
            self._trace(status="success"), db_session, owner_id="user_1",
        )
        assert case is None

    async def test_dedupes_by_trace_id(self, db_session):
        await extract_failure_case_from_trace(
            self._trace(), db_session, owner_id="user_1", created_by="user_1",
        )
        second = await extract_failure_case_from_trace(
            self._trace(), db_session, owner_id="user_1", created_by="user_1",
        )
        assert second is None

    async def test_flag_off_returns_none(self, db_session, monkeypatch):
        monkeypatch.setattr(get_settings(), "agent_failure_learning_enabled", False)
        case = await extract_failure_case_from_trace(
            self._trace(), db_session, owner_id="user_1",
        )
        assert case is None


class TestHarnessFailureExtraction:
    async def test_harness_fallback_extracts_failure_case(self, db_session):
        """harness 降级轨迹 → 失败 Case 沉淀（此前失败完全不沉淀）"""
        harness = get_harness()
        trace = harness.start_trace(
            "designer", "帮我设计一个北欧风格儿童房方案", user_id="user_9", project_id="proj_9",
        )
        trace.finish(AgentRunStatus.FALLBACK)
        trace.fallback_reason = "all_retries_exhausted"
        await harness._maybe_extract_case(
            trace, {"db": db_session, "user_id": "user_9", "project_id": "proj_9"},
        )
        result = await db_session.execute(
            select(AgentCase).where(AgentCase.trace_id == trace.trace_id)
        )
        case = result.scalars().first()
        assert case is not None
        assert case.outcome == "failed"
        assert case.failure_type == "timeout"
        assert case.scope == "project"
        assert case.owner_id == "proj_9"


async def _seed_failed_cases(db_session, agent_name="designer", failure_type="timeout", n=3):
    import uuid as _uuid
    for i in range(n):
        db_session.add(AgentCase(
            id=str(_uuid.uuid4()),
            scope="personal", owner_id="user_1", agent_name=agent_name,
            task_intent=f"帮我设计方案（第{i}次）",
            approach=json.dumps([{"step": 1, "attempted": "x", "result": failure_type}]),
            outcome="failed", quality_score=0.0, failure_type=failure_type,
            created_by="user_1",
        ))
    await db_session.flush()


class TestAntiPatternDistillation:
    async def test_below_threshold_returns_none(self, db_session):
        await _seed_failed_cases(db_session, n=2)
        skill = await distill_anti_pattern_skill(
            db_session, agent_name="designer", failure_type="timeout",
            owner_id="user_1", scope="personal", created_by="cycle",
        )
        assert skill is None

    async def test_distills_anti_pattern_skill(self, db_session, monkeypatch):
        monkeypatch.setattr(get_settings(), "agent_failure_learning_enabled", True)
        await _seed_failed_cases(db_session, n=3)

        async def fake_chat(self, messages, **kwargs):
            return json.dumps({
                "name": "推理超时", "description": "深推理模型超时，先降级快速模型",
                "system_prompt": "避免深推理模型超时：先降级快速模型",
            })

        with patch("app.agents.base.BaseAgent._chat", fake_chat):
            with patch("app.agents.base.BaseAgent.close", new_callable=AsyncMock):
                skill = await distill_anti_pattern_skill(
                    db_session, agent_name="designer", failure_type="timeout",
                    owner_id="user_1", scope="personal", created_by="cycle",
                )
        assert skill is not None
        assert skill.name.startswith(_ANTI_PATTERN_PREFIX)
        assert skill.status == STATUS_DRAFT
        # Case 已标记蒸馏，避免重复蒸馏
        result = await db_session.execute(
            select(AgentCase).where(
                AgentCase.failure_type == "timeout",
                AgentCase.distilled_to_skill_id.is_(None),
            )
        )
        assert result.scalars().first() is None

    async def test_flag_off_returns_none(self, db_session, monkeypatch):
        monkeypatch.setattr(get_settings(), "agent_failure_learning_enabled", False)
        await _seed_failed_cases(db_session, n=3)
        skill = await distill_anti_pattern_skill(
            db_session, agent_name="designer", failure_type="timeout",
            owner_id="user_1", scope="personal",
        )
        assert skill is None


class TestAntiPatternInjection:
    async def test_hints_returned(self, db_session):
        db_session.add(AgentSkill(
            name=f"{_ANTI_PATTERN_PREFIX}推理超时", description="避免深推理模型超时",
            agent_name="designer", owner_scope="personal", owner_id="user_1",
            system_prompt="教训", status=STATUS_ACTIVE, created_by="user_1",
        ))
        await db_session.flush()
        hints = await get_anti_pattern_hints(
            db_session, agent_name="designer", owner_id="user_1", scope="personal",
        )
        assert "避免深推理模型超时" in hints

    async def test_flag_off_returns_empty(self, db_session, monkeypatch):
        monkeypatch.setattr(get_settings(), "agent_failure_learning_enabled", False)
        hints = await get_anti_pattern_hints(
            db_session, agent_name="designer", owner_id="user_1", scope="personal",
        )
        assert hints == []


class TestEvolutionCycleFailurePhase:
    async def test_cycle_distills_failure_cluster(self, db_session, monkeypatch):
        monkeypatch.setattr(get_settings(), "agent_failure_learning_enabled", True)
        await _seed_failed_cases(db_session, n=3)

        async def fake_chat(self, messages, **kwargs):
            return json.dumps({
                "name": "推理超时", "description": "深推理模型超时，先降级快速模型",
                "system_prompt": "避免深推理模型超时：先降级快速模型",
            })

        with patch("app.agents.base.BaseAgent._chat", fake_chat):
            with patch("app.agents.base.BaseAgent.close", new_callable=AsyncMock):
                report = await run_skill_evolution_cycle(db_session)
        assert report["failure_clusters_found"] >= 1
        assert len(report["anti_pattern_distilled"]) >= 1
        entry = report["anti_pattern_distilled"][0]
        assert entry["failure_type"] == "timeout"


# ════════════════════════════════════════════════════════════════
# P0-2 协议信任层：可验证支付意图（AP2 对齐）
# ════════════════════════════════════════════════════════════════

class TestPaymentIntentService:
    def test_create_and_verify_ok(self):
        intent = create_payment_intent("order_1", 1500.0, "user_1")
        result = verify_payment_intent(
            intent["token"], order_id="order_1", amount=1500.0, actor_user_id="user_1",
        )
        assert result["valid"] is True

    def test_tampered_token_rejected(self):
        intent = create_payment_intent("order_1", 1500.0, "user_1")
        tampered = intent["token"][:-2] + "aa"
        result = verify_payment_intent(
            tampered, order_id="order_1", amount=1500.0, actor_user_id="user_1",
        )
        assert result["valid"] is False
        assert result["reason"] == "signature"

    def test_amount_mismatch_rejected(self):
        intent = create_payment_intent("order_1", 1500.0, "user_1")
        result = verify_payment_intent(
            intent["token"], order_id="order_1", amount=1501.0, actor_user_id="user_1",
        )
        assert result["valid"] is False
        assert result["reason"] == "amount_mismatch"

    def test_actor_mismatch_rejected(self):
        intent = create_payment_intent("order_1", 1500.0, "user_1")
        result = verify_payment_intent(
            intent["token"], order_id="order_1", amount=1500.0, actor_user_id="user_2",
        )
        assert result["valid"] is False
        assert result["reason"] == "actor_mismatch"

    def test_expired_rejected(self):
        intent = create_payment_intent("order_1", 1500.0, "user_1", ttl_seconds=-1)
        result = verify_payment_intent(
            intent["token"], order_id="order_1", amount=1500.0, actor_user_id="user_1",
        )
        assert result["valid"] is False
        assert result["reason"] == "expired"

    def test_malformed_rejected(self):
        result = verify_payment_intent(
            "garbage", order_id="o", amount=1.0, actor_user_id="u",
        )
        assert result["valid"] is False
        assert result["reason"] == "malformed"


async def _make_order_for_user(db_session, user_id: str):
    """建 project + supplier + order 归 user_id（payment-intent 端点测试用）"""
    import uuid as _uuid
    project = Project(
        id=str(_uuid.uuid4()), owner_id=user_id, name="测试项目",
        status="active",
    )
    supplier = Supplier(
        id=str(_uuid.uuid4()), name="测试供应商", phone="13800000000",
        category="主材",
    )
    order = ProcurementOrder(
        id=str(_uuid.uuid4()), project_id=project.id, supplier_id=supplier.id,
        total_amount=1500.0, status="confirmed",
    )
    db_session.add_all([project, supplier, order])
    await db_session.flush()
    return order


class TestPaymentIntentEndpoints:
    async def test_create_intent_owner_ok(self, client, auth_headers, db_session):
        user = (await db_session.execute(
            select(User).order_by(User.created_at.desc()).limit(1)
        )).scalars().first()
        order = await _make_order_for_user(db_session, user.id)
        resp = await client.post(
            f"/api/procurement/orders/{order.id}/payment-intent", headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["order_id"] == order.id
        assert body["amount"] == 1500.0
        assert body["token"]
        # 返回的 token 可被服务端验证（端到端闭环）
        result = verify_payment_intent(
            body["token"], order_id=order.id, amount=1500.0, actor_user_id=user.id,
        )
        assert result["valid"] is True

    async def test_create_intent_non_owner_403(self, client, auth_headers, db_session):
        order = await _make_order_for_user(db_session, "other_user_999")
        resp = await client.post(
            f"/api/procurement/orders/{order.id}/payment-intent", headers=auth_headers,
        )
        assert resp.status_code == 403

    async def test_create_intent_flag_off_503(self, client, auth_headers, db_session, monkeypatch):
        monkeypatch.setattr(get_settings(), "agent_payment_intent_enabled", False)
        user = (await db_session.execute(
            select(User).order_by(User.created_at.desc()).limit(1)
        )).scalars().first()
        order = await _make_order_for_user(db_session, user.id)
        resp = await client.post(
            f"/api/procurement/orders/{order.id}/payment-intent", headers=auth_headers,
        )
        assert resp.status_code == 503

    async def test_verify_endpoint(self, client, auth_headers):
        intent = create_payment_intent("order_x", 99.0, "user_x")
        resp = await client.post(
            "/api/procurement/payment-intents/verify", headers=auth_headers,
            json={
                "token": intent["token"], "order_id": "order_x",
                "amount": 99.0, "actor_user_id": "user_x",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    async def test_verify_endpoint_rejects_tampered(self, client, auth_headers):
        intent = create_payment_intent("order_x", 99.0, "user_x")
        resp = await client.post(
            "/api/procurement/payment-intents/verify", headers=auth_headers,
            json={
                "token": intent["token"] + "x", "order_id": "order_x",
                "amount": 99.0, "actor_user_id": "user_x",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is False


class TestA2AEvidenceChain:
    async def test_unregistered_agent_evidence(self, client, auth_headers):
        """未注册 Agent → FAILED + evidence 诚实标注降级原因"""
        resp = await client.post(
            "/api/a2a/tasks/send", headers=auth_headers,
            json={"agent_name": "NotExistAgent", "message": "hi"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["state"] == "failed"
        assert body["evidence"] == {"degraded": True, "reason": "agent_not_registered"}

    async def test_task_query_returns_evidence_fields(self, client, auth_headers):
        resp = await client.post(
            "/api/a2a/tasks/send", headers=auth_headers,
            json={"agent_name": "NotExistAgent", "message": "hi"},
        )
        task_id = resp.json()["task_id"]
        resp2 = await client.get(f"/api/a2a/tasks/{task_id}", headers=auth_headers)
        assert resp2.status_code == 200
        body = resp2.json()
        assert "trace_id" in body
        assert body["evidence"]["degraded"] is True

    async def test_business_ops_non_admin_evidence(self, client, auth_headers):
        """商业运营 Agent 非管理员下发 → 权限证据"""
        resp = await client.post(
            "/api/a2a/tasks/send", headers=auth_headers,
            json={"agent_name": "growth", "message": "查增长"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["state"] == "failed"
        assert body["evidence"] == {"degraded": True, "reason": "permission_denied"}


# ════════════════════════════════════════════════════════════════
# P1-3 语境工程：上下文压缩
# ════════════════════════════════════════════════════════════════

class TestContextCompaction:
    def _history(self, n=30):
        return [{"role": "user" if i % 2 == 0 else "assistant", "content": f"消息{i}"} for i in range(n)]

    async def test_under_threshold_unchanged(self):
        history = self._history(10)
        result = await compact_history(history, max_turns=10)
        assert result == history

    async def test_over_threshold_summarizes_head(self):
        history = self._history(30)

        async def fake_summarize(head):
            return f"前 {len(head)} 条摘要"

        result = await compact_history(history, max_turns=10, summarize_fn=fake_summarize)
        assert len(result) == 11  # 1 摘要 + 10 尾部
        assert result[0]["role"] == "system"
        assert "前 20 条摘要" in result[0]["content"]
        assert result[-1] == history[-1]  # 尾部不丢

    async def test_summary_failure_falls_back_truncation(self):
        history = self._history(30)

        async def failing_summarize(head):
            raise RuntimeError("LLM 不可用")

        result = await compact_history(history, max_turns=10, summarize_fn=failing_summarize)
        assert result == history[-10:]

    async def test_flag_off_passthrough(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "chat_context_compaction_enabled", False)
        history = self._history(30)
        assert await compact_history(history, max_turns=10) == history

    async def test_empty_history(self):
        assert await compact_history(None) == []

    async def test_chat_with_long_history_still_200(self, client, auth_headers):
        """集成：无 API key 环境下长 history 压缩失败回退截断，接口仍 200"""
        # schema 上限 20 条；阈值 10 → 头部 10 条进入摘要路径（无 key 时摘要失败回退截断）
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"消息{i}"}
            for i in range(20)
        ]
        resp = await client.post(
            "/api/agents/chat", headers=auth_headers,
            json={"message": "你好", "agent_type": "orchestrator", "history": history},
        )
        assert resp.status_code == 200, resp.text


# ════════════════════════════════════════════════════════════════
# P1-4 复杂度自适应路由（ARISE 借鉴）
# ════════════════════════════════════════════════════════════════

class TestTaskComplexity:
    def test_low_short_greeting(self):
        assert BaseAgent._estimate_task_complexity("你好") == "low"

    def test_high_three_domains(self):
        msg = "帮我做设计、预算和施工排期，风格北欧，预算15万，防水怎么做"
        assert BaseAgent._estimate_task_complexity(msg) == "high"

    def test_high_long_text(self):
        assert BaseAgent._estimate_task_complexity("家" * 301) == "high"

    def test_high_process_keyword(self):
        assert BaseAgent._estimate_task_complexity("帮我安排整个流程") == "high"

    def test_standard_single_domain(self):
        assert BaseAgent._estimate_task_complexity("厨房水电怎么走线") == "standard"

    def test_empty_standard(self):
        assert BaseAgent._estimate_task_complexity("") == "standard"


class TestAdaptiveChain:
    def _agent(self, cost_tier="standard"):
        agent = BaseAgent()
        agent.cost_tier = cost_tier
        agent.provider = "deepseek"
        return agent

    def test_low_complexity_cheap_first(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "adaptive_reasoning_routing_enabled", True)
        monkeypatch.setattr(get_settings(), "economy_providers", "qwen,glm")
        chain = self._agent()._resolve_chain("low")
        assert chain[0] == "qwen"
        assert "deepseek" in chain  # 主供应商保留兜底

    def test_high_complexity_primary_first(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "adaptive_reasoning_routing_enabled", True)
        monkeypatch.setattr(get_settings(), "economy_providers", "qwen,glm")
        chain = self._agent()._resolve_chain("high")
        assert chain[0] == "deepseek"

    def test_flag_off_primary_first(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "adaptive_reasoning_routing_enabled", False)
        monkeypatch.setattr(get_settings(), "economy_providers", "qwen,glm")
        chain = self._agent()._resolve_chain("low")
        assert chain[0] == "deepseek"

    def test_economy_tier_unchanged(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "adaptive_reasoning_routing_enabled", True)
        monkeypatch.setattr(get_settings(), "cost_tiered_routing_enabled", True)
        monkeypatch.setattr(get_settings(), "economy_providers", "qwen,glm")
        chain = self._agent("economy")._resolve_chain("high")
        assert chain[0] == "qwen"

    def test_backward_compat_no_arg(self, monkeypatch):
        """旧调用方 _resolve_chain() 无参仍为 primary-first（不破坏既有行为）"""
        monkeypatch.setattr(get_settings(), "adaptive_reasoning_routing_enabled", True)
        chain = self._agent()._resolve_chain()
        assert chain[0] == "deepseek"
