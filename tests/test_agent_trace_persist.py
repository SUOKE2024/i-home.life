"""Agent 执行轨迹持久化测试（v1.12.x 可观测性打磨）

覆盖：
- Harness run 成功路径 → agent_traces 落库（含 workflow_id / prompt 采样 / token）
- Harness 降级路径（异常）→ 落库 fallback 记录
- flag 关闭（agent_trace_persist_enabled=False）→ 零落库
- 采样率 0（agent_trace_sample_rate=0）→ 零落库
- start_trace workflow_id 透传 → to_dict 携带 workflow_id

测试隔离：monkeypatch.setattr(get_settings(), "flag", value)，teardown 自动还原
（禁止 get_settings.cache_clear()——v1.1.29 教训：致跨文件测试隔离失败）
"""
from sqlalchemy import select

from app.agents.harness import AgentRuntime
from app.agents.designer import DesignerAgent
from app.config import get_settings
from app.models.agent_trace import AgentTraceRecord


async def _count_traces(db) -> int:
    result = await db.execute(select(AgentTraceRecord))
    return len(result.scalars().all())


async def test_harness_run_persists_trace(db_session):
    """成功路径：harness run 后 agent_traces 落一条记录"""
    harness = AgentRuntime()
    agent = DesignerAgent()
    try:
        result = await harness.run(
            agent, "帮我设计一个 120 平米的北欧风格客厅方案",
            db=db_session, user_id="u_test_1", workflow_id="wf_test_1",
        )
    finally:
        await agent.close()
    assert result["reply"]
    assert await _count_traces(db_session) == 1

    record = (await db_session.execute(select(AgentTraceRecord))).scalars().one()
    assert record.agent_name == "designer"
    assert record.workflow_id == "wf_test_1"
    assert record.user_id == "u_test_1"
    assert record.status == "success"
    # prompt 上下文采样：system prompt 截断落库
    assert record.prompt_preview and len(record.prompt_preview) <= 500
    assert record.response_preview and len(record.response_preview) <= 1000
    assert record.created_at is not None


async def test_harness_run_persists_fallback_trace(db_session, monkeypatch):
    """降级路径：Agent 抛异常 → 落库 fallback 记录"""
    harness = AgentRuntime()

    class _BoomAgent(DesignerAgent):
        async def think_with_tools(self, *args, **kwargs):  # noqa: D102
            raise RuntimeError("boom")

    agent = _BoomAgent()
    try:
        result = await harness.run(
            agent, "触发失败路径",
            db=db_session, user_id="u_test_2",
        )
    finally:
        await agent.close()
    assert result["fallback"] is True
    record = (await db_session.execute(select(AgentTraceRecord))).scalars().one()
    assert record.status == "fallback"
    assert record.fallback_used is True
    assert record.error_type == "RuntimeError"


async def test_harness_trace_persist_disabled_no_record(db_session, monkeypatch):
    """flag 关闭：零落库"""
    monkeypatch.setattr(get_settings(), "agent_trace_persist_enabled", False)
    harness = AgentRuntime()
    agent = DesignerAgent()
    try:
        await harness.run(
            agent, "帮我设计一个卧室方案",
            db=db_session, user_id="u_test_3",
        )
    finally:
        await agent.close()
    assert await _count_traces(db_session) == 0


async def test_harness_trace_sample_rate_zero_no_record(db_session, monkeypatch):
    """采样率 0：零落库"""
    monkeypatch.setattr(get_settings(), "agent_trace_sample_rate", 0.0)
    harness = AgentRuntime()
    agent = DesignerAgent()
    try:
        await harness.run(
            agent, "帮我设计一个厨房方案",
            db=db_session, user_id="u_test_4",
        )
    finally:
        await agent.close()
    assert await _count_traces(db_session) == 0


def test_start_trace_carries_workflow_id():
    """start_trace 透传 workflow_id，to_dict 可见"""
    harness = AgentRuntime()
    trace = harness.start_trace(
        "budget", "90平预算", provider="deepseek",
        user_id="u1", project_id="p1", scope="project", workflow_id="wf_abc",
    )
    d = trace.to_dict()
    assert d["workflow_id"] == "wf_abc"
    assert d["scope"] == "project"


def test_serialize_tool_calls_truncates_long_result():
    """tool_calls 序列化截断 arguments/result（防 PII 扩散 + 体积爆炸）。"""
    import json
    from app.agents.harness import _serialize_tool_calls_for_trace

    payload = _serialize_tool_calls_for_trace([
        {"tool": "get_budget", "arguments": {"area": 100}, "result": "x" * 1000},
    ])
    assert payload is not None
    parsed = json.loads(payload)
    assert parsed[0]["tool"] == "get_budget"
    assert len(parsed[0]["result"]) == 300  # result 截到 300 字符
    assert _serialize_tool_calls_for_trace([]) is None  # 无调用 → NULL


async def test_harness_persists_tool_calls_json(db_session):
    """轨迹落库时 tool_calls 序列化为 JSON 字符串（可回放）。"""
    import json
    from app.agents.harness import AgentRunStatus

    harness = AgentRuntime()
    agent = DesignerAgent()
    try:
        trace = harness.start_trace(
            "budget", "90平预算", provider="deepseek",
            user_id="u_tool", project_id="p_tool",
        )
        trace.tool_calls = [
            {"tool": "get_budget", "arguments": {"area": 90}, "result": {"total": 144000}},
        ]
        trace.tool_call_count = 1
        trace.response = "预算约 14.4 万"
        trace.finish(AgentRunStatus.SUCCESS)
        await harness._persist_trace(
            trace, {"db": db_session, "user_id": "u_tool"}, agent,
        )
    finally:
        await agent.close()

    record = (await db_session.execute(select(AgentTraceRecord))).scalars().one()
    assert record.tool_calls is not None
    parsed = json.loads(record.tool_calls)
    assert parsed[0]["tool"] == "get_budget"
    assert "144000" in parsed[0]["result"]
