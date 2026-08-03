"""AgentTrace scope 字段测试（v1.4.0 借鉴 YC QM 四级作用域）

验证 AgentTrace 的 scope 字段：
- 默认空字符串（向后兼容）
- start_trace 传 scope 后 trace.scope 正确
- to_dict() 输出含 scope 键
"""

from app.agents.harness import AgentRuntime, AgentTrace


def test_agent_trace_scope_default_empty():
    """AgentTrace() 默认 scope == ''（向后兼容）"""
    trace = AgentTrace(agent_name="designer")
    assert trace.scope == ""


def test_start_trace_with_scope():
    """start_trace(..., scope='project') → trace.scope == 'project'"""
    harness = AgentRuntime()
    trace = harness.start_trace(
        agent_name="designer",
        user_message="120平北欧风",
        provider="deepseek",
        user_id="u1",
        project_id="p1",
        scope="project",
    )
    assert trace.scope == "project"
    assert trace.user_id == "u1"
    assert trace.project_id == "p1"


def test_trace_to_dict_includes_scope():
    """to_dict() 输出含 'scope' 键"""
    trace = AgentTrace(agent_name="designer", scope="team")
    data = trace.to_dict()
    assert "scope" in data
    assert data["scope"] == "team"
