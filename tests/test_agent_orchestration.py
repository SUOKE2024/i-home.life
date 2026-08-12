"""多智能体协作编排服务测试（v1.12.x，对齐 2026 hub-spoke/pipeline 编排）

覆盖：
- validate_dag：合法 DAG / 重复 ID / 悬空依赖 / 环检测
- topological_order：依赖拓扑序 + 环返回 None
- _rule_decompose：关键词规则单任务分解
- decompose_request：LLM 失败诚实降级规则分解
- run_workflow：拓扑执行子 Agent（复用 harness）→ 结构化结果
- aggregate_results：汇总/失败/跳过统计 + 结构化输出
- OrchestratorAgent.plan_and_delegate：flag 关闭降级
- API：POST /agents/orchestrate 鉴权/编排结果/项目归属

测试隔离：monkeypatch.setattr(get_settings(), "flag", value)，teardown 自动还原
"""
import uuid

import pytest
from httpx import AsyncClient

from app.agents.orchestrator import OrchestratorAgent
from app.config import get_settings
from app.models.agent_trace import AgentTraceRecord
from app.services.agent_orchestration_service import (
    AgentTask, AgentTaskResult, _rule_decompose, aggregate_results,
    decompose_request, run_workflow, topological_order, validate_dag,
)


async def _register(client: AsyncClient, phone: str = "") -> str:
    resp = await client.post(
        "/api/auth/register",
        json={
            "phone": phone or f"137{str(uuid.uuid4().int)[:8]}",
            "name": "编排测试", "password": "test123456",
        },
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


def _task(tid: str, agent: str = "budget", deps: list[str] | None = None) -> AgentTask:
    return AgentTask(task_id=tid, agent_name=agent, description=f"任务{tid}", dependencies=deps or [])


# ── DAG 校验 / 拓扑 ──


def test_validate_dag_ok():
    tasks = [_task("a"), _task("b", deps=["a"]), _task("c", deps=["a", "b"])]
    ok, err = validate_dag(tasks)
    assert ok is True and err == ""


def test_validate_dag_duplicate_id():
    tasks = [_task("a"), _task("a")]
    ok, err = validate_dag(tasks)
    assert ok is False and "重复" in err


def test_validate_dag_dangling_dep():
    tasks = [_task("a"), _task("b", deps=["nonexistent"])]
    ok, err = validate_dag(tasks)
    assert ok is False and "不存在" in err


def test_validate_dag_cycle():
    tasks = [_task("a", deps=["b"]), _task("b", deps=["a"])]
    ok, err = validate_dag(tasks)
    assert ok is False and "环" in err


def test_topological_order_respects_deps():
    tasks = [_task("a"), _task("b", deps=["a"]), _task("c", deps=["a"])]
    order = topological_order(tasks)
    assert order is not None
    ids = [t.task_id for t in order]
    assert ids.index("a") < ids.index("b")
    assert ids.index("a") < ids.index("c")


def test_topological_order_cycle_returns_none():
    tasks = [_task("a", deps=["b"]), _task("b", deps=["a"])]
    assert topological_order(tasks) is None


# ── 规则分解 ──


def test_rule_decompose_budget_message():
    tasks = _rule_decompose("120平米房子装修预算大概多少钱")
    assert len(tasks) == 1
    assert tasks[0].agent_name == "budget"


def test_rule_decompose_general_message():
    tasks = _rule_decompose("今天天气怎么样")
    assert len(tasks) == 1
    assert tasks[0].agent_name == "concierge"


# ── v1.13.x 逐项审计：编排注册表补齐新 Agent ──


def test_orchestration_registry_includes_new_agents():
    """编排注册表含 5 个新补齐的专用 Agent（此前收敛到 concierge）。"""
    from app.services.agent_orchestration_service import _agent_registry

    registry = _agent_registry()
    for name in ("files", "products", "identity", "notifications", "ifc_export"):
        assert name in registry, f"{name} 未加入编排注册表"


def test_rule_decompose_new_agents_not_concierge():
    """新 Agent 意图不再收敛到 concierge（编排覆盖全量）。"""
    cases = [
        ("帮我把合同文件上传一下", "files"),
        ("实名认证状态帮我查一下", "identity"),
        ("我要导出一份IFC模型", "ifc_export"),
        ("通知设置在哪", "notifications"),
    ]
    for msg, expect in cases:
        tasks = _rule_decompose(msg)
        assert len(tasks) == 1
        assert tasks[0].agent_name == expect, f"{msg} 应派发 {expect}，实际 {tasks[0].agent_name}"


async def test_run_workflow_dispatches_new_agents(db_session):
    """run_workflow 可派发到新补齐的专用 Agent（files）。"""
    tasks = [_task("t1", agent="files")]
    results = await run_workflow(
        tasks, db=db_session, user_id="u_orch_files", workflow_id="wf_files",
    )
    assert len(results) == 1
    assert results[0].status == "success"


# ── LLM 分解失败诚实降级 ──


async def test_decompose_request_falls_back_to_rule(monkeypatch):
    """LLM 返回 mock 非 JSON → 诚实降级为规则单任务（不伪装）"""
    monkeypatch.setattr(get_settings(), "agent_orchestration_pipeline_enabled", True)
    tasks = await decompose_request("帮我算一下90平米装修预算")
    assert len(tasks) == 1
    assert tasks[0].agent_name == "budget"


async def test_decompose_request_flag_off_rule_only(monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_orchestration_pipeline_enabled", False)
    tasks = await decompose_request("帮我设计一个客厅")
    assert len(tasks) == 1
    assert tasks[0].agent_name == "designer"


# ── 工作流执行 ──


async def test_run_workflow_executes_in_topological_order(db_session):
    tasks = [
        _task("t1", agent="budget"),
        _task("t2", agent="concierge", deps=["t1"]),
    ]
    results = await run_workflow(
        tasks, db=db_session, user_id="u_orch_1", workflow_id="wf_orch_1",
    )
    assert len(results) == 2
    # 无 API key → harness mock 回复仍计入 success（mock 模式契约对齐）
    assert all(r.status == "success" for r in results)
    assert results[0].task_id == "t1"
    assert results[1].task_id == "t2"

    # 轨迹落库：workflow_id 贯穿所有子任务
    from sqlalchemy import select
    rows = (await db_session.execute(select(AgentTraceRecord))).scalars().all()
    assert len(rows) == 2
    assert all(r.workflow_id == "wf_orch_1" for r in rows)


async def test_run_workflow_skips_when_dependency_failed(db_session, monkeypatch):
    """前置任务失败 → 依赖任务跳过（不级联执行）"""
    tasks = [
        _task("t1", agent="concierge"),
        _task("t2", agent="budget", deps=["t1"]),
    ]
    # 强制 t1 失败
    monkeypatch.setattr(
        "app.services.agent_orchestration_service._agent_registry",
        lambda: {"concierge": _BoomAgentCls, "budget": _BoomAgentCls},
    )
    results = await run_workflow(tasks, db=db_session, user_id="u_orch_2")
    assert results[0].status == "failed"
    assert results[1].status == "skipped"


class _BoomAgentCls:
    """占位 Agent 类：无 think/think_with_tools → harness.run 触发降级（测试专用）。"""

    agent_name = "boom"
    tools = []

    def __init__(self):
        pass

    async def close(self):
        pass


# ── 聚合 ──


def test_aggregate_results_summary():
    results = [
        AgentTaskResult(task_id="t1", agent_id="budget", status="success", result="预算结果"),
        AgentTaskResult(task_id="t2", agent_id="concierge", status="failed", result="", reasoning="超时"),
        AgentTaskResult(task_id="t3", agent_id="designer", status="skipped", result=""),
    ]
    agg = aggregate_results(results)
    assert agg["success_count"] == 1
    assert agg["failed_count"] == 1
    assert agg["skipped_count"] == 1
    assert "已完成 1/3" in agg["summary"]
    assert "预算结果" in agg["reply"]
    assert agg["engine"] == "orchestration_pipeline"


# ── plan_and_delegate ──


async def test_plan_and_delegate_flag_off(monkeypatch):
    """flag 关闭 → 诚实降级（engine=rule_single，不执行编排）"""
    monkeypatch.setattr(get_settings(), "agent_orchestration_pipeline_enabled", False)
    agent = OrchestratorAgent()
    try:
        result = await agent.plan_and_delegate("帮我做个预算", user_id="u_orch_3")
    finally:
        await agent.close()
    assert result["engine"] == "rule_single"
    assert "编排未启用" in result["summary"]


async def test_plan_and_delegate_rule_path(monkeypatch, db_session):
    """flag 开 + LLM 不可用 → 规则单任务执行 + workflow_id 落库"""
    monkeypatch.setattr(get_settings(), "agent_orchestration_pipeline_enabled", True)
    agent = OrchestratorAgent()
    try:
        result = await agent.plan_and_delegate(
            "90平米预算多少", db=db_session, user_id="u_orch_4",
        )
    finally:
        await agent.close()
    assert result["engine"] == "orchestration_pipeline"
    assert result["workflow_id"]
    assert result["success_count"] == 1
    from sqlalchemy import select
    rows = (await db_session.execute(select(AgentTraceRecord))).scalars().all()
    assert len(rows) == 1
    assert rows[0].workflow_id == result["workflow_id"]


async def test_plan_and_delegate_dag_failure_falls_back_to_rule(monkeypatch, db_session):
    """LLM 分解出坏 DAG（环）→ 规则分解兜底保留意图（而非硬编码客服）。

    v1.13.x 逐项审计：DAG 非法原硬编码 concierge 丢失意图路由，
    改为规则分解后「90平米预算」仍派发 budget。
    """
    from app.services import agent_orchestration_service as orc

    monkeypatch.setattr(get_settings(), "agent_orchestration_pipeline_enabled", True)

    async def _bad_llm_decompose(message, db=None, user_id="", project_id="", user_context=""):
        # 构造环：A 依赖 B，B 依赖 A
        return [
            orc.AgentTask(task_id="a", agent_name="budget", description="预算", dependencies=["b"]),
            orc.AgentTask(task_id="b", agent_name="concierge", description="客服", dependencies=["a"]),
        ]

    monkeypatch.setattr(orc, "_llm_decompose", _bad_llm_decompose)
    agent = OrchestratorAgent()
    try:
        result = await agent.plan_and_delegate(
            "90平米装修预算多少", db=db_session, user_id="u_orch_5",
        )
    finally:
        await agent.close()
    assert result["success_count"] == 1
    assert result["results"][0]["agent_id"] == "budget"


# ── API：POST /agents/orchestrate ──


@pytest.mark.asyncio
async def test_orchestrate_requires_auth(client: AsyncClient):
    """未认证请求编排端点返回 401"""
    resp = await client.post("/api/agents/orchestrate", json={"message": "90平预算"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_orchestrate_happy_path(client: AsyncClient):
    """认证用户编排 → 200，返回 reply + 结构化 card_payload"""
    token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/api/agents/orchestrate",
        json={"message": "帮我算一下120平米装修预算"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_type"] == "orchestrator"
    assert data["reply"]
    assert data["card_payload"]["workflow_id"]
    assert data["card_payload"]["engine"] == "orchestration_pipeline"
    assert isinstance(data["card_payload"]["results"], list)
    assert data["card_payload"]["results"][0]["status"] == "success"


@pytest.mark.asyncio
async def test_orchestrate_flag_off_rule_single(client: AsyncClient, monkeypatch):
    """flag 关闭 → engine=rule_single，诚实标注编排未启用"""
    monkeypatch.setattr(get_settings(), "agent_orchestration_pipeline_enabled", False)
    token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/api/agents/orchestrate",
        json={"message": "帮我算一下90平预算"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["card_payload"]["engine"] == "rule_single"
    assert "编排未启用" in data["card_payload"]["summary"]
    assert data["reply"]  # 规则单任务仍给出回复


@pytest.mark.asyncio
async def test_orchestrate_project_not_found(client: AsyncClient):
    """project_id 不存在 → 404"""
    token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/api/agents/orchestrate",
        json={"message": "做预算", "project_id": "nonexistent-project"},
        headers=headers,
    )
    assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════
# v1.10.x 全景全量全链路记忆（2026-08-12）
# 覆盖：编排入口写侧记忆提取闭环 + design/proposals 端点记忆闭环
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_orchestrate_extracts_memory(client: AsyncClient):
    """编排端点写侧闭环：用户消息偏好/城市 → 长期记忆可查"""
    token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/api/agents/orchestrate",
        json={"message": "我在北京，喜欢原木风，帮我算120平装修预算"},
        headers=headers,
    )
    assert resp.status_code == 200

    mem = await client.get("/api/agents/memory", headers=headers)
    assert mem.status_code == 200
    items = mem.json()["items"]
    values = [m.get("value") for m in items]
    assert any("北京" in v for v in values), f"应提取城市记忆，实际: {values}"


@pytest.mark.asyncio
async def test_design_proposals_endpoint_extracts_memory(client: AsyncClient, monkeypatch):
    """design/proposals 写侧闭环：需求偏好 → 长期记忆可查（不再断裂）"""
    monkeypatch.setattr(get_settings(), "design_proposal_llm_enabled", False)
    token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/api/agents/design/proposals",
        json={"requirement": "我喜欢极简风，帮我设计一个厨房"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["source"] == "fallback"

    mem = await client.get("/api/agents/memory", headers=headers)
    assert mem.status_code == 200
    items = mem.json()["items"]
    values = [m.get("value") for m in items]
    assert any("极简风" in v for v in values), f"应提取偏好记忆，实际: {values}"


@pytest.mark.asyncio
async def test_design_proposals_revise_endpoint_extracts_memory(client: AsyncClient, monkeypatch):
    """design/proposals/{id}/revise 写侧闭环：修订指令偏好 → 长期记忆可查"""
    monkeypatch.setattr(get_settings(), "design_proposal_llm_enabled", False)
    token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}

    # 先生成方案（fallback 单方案），再修订
    gen = await client.post(
        "/api/agents/design/proposals",
        json={"requirement": "设计厨房"},
        headers=headers,
    )
    assert gen.status_code == 200
    proposal_id = gen.json()["proposals"][0]["proposal_id"]

    rev = await client.post(
        f"/api/agents/design/proposals/{proposal_id}/revise",
        json={"change": "我喜欢白色的台面"},
        headers=headers,
    )
    assert rev.status_code == 200

    mem = await client.get("/api/agents/memory", headers=headers)
    assert mem.status_code == 200
    values = [m.get("value") for m in mem.json()["items"]]
    assert any("白色" in v for v in values), f"应提取修订偏好记忆，实际: {values}"
