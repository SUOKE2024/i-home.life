"""OTel GenAI 语义约定埋点对齐测试

覆盖:
- _generate_w3c_trace_context: W3C Trace Context（traceparent/tracestate/baggage）格式
- AgentTrace.to_dict: otel_genai_semconv_enabled 开关控制 _meta 注入（flag 关闭零回归）
- AgentRuntime.start_trace: flag 开启时自动生成 w3c_trace
"""
import re

import pytest

from app.agents.harness import (
    AgentRuntime,
    AgentTrace,
    _generate_w3c_trace_context,
)
from app.config import get_settings

TRACEPARENT_RE = re.compile(r"^00-[0-9a-f]{32}-[0-9a-f]{16}-01$")


def test_generate_w3c_trace_context_format():
    """traceparent 匹配 W3C 格式，tracestate 含 gen_ai，baggage 可空"""
    ctx = _generate_w3c_trace_context()
    assert TRACEPARENT_RE.match(ctx["traceparent"])
    assert "gen_ai" in ctx["tracestate"]
    assert ctx["baggage"] == ""


def test_to_dict_no_meta_when_flag_off(monkeypatch):
    """flag 关闭时 to_dict() 不含 _meta 键（零回归，即使 w3c_trace 非空）"""
    monkeypatch.setattr(get_settings(), "otel_genai_semconv_enabled", False)
    trace = AgentTrace(
        agent_name="designer",
        provider="deepseek",
        model="deepseek-chat",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        w3c_trace=_generate_w3c_trace_context(),
    )
    data = trace.to_dict()
    assert "_meta" not in data
    assert data["agent_name"] == "designer"
    assert data["provider"] == "deepseek"
    assert data["total_tokens"] == 15


def test_to_dict_meta_when_flag_on(monkeypatch):
    """flag 开启时 to_dict() 含 _meta，gen_ai 语义约定字段正确映射"""
    monkeypatch.setattr(get_settings(), "otel_genai_semconv_enabled", True)
    trace = AgentTrace(
        agent_name="designer",
        provider="deepseek",
        model="deepseek-chat",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        w3c_trace=_generate_w3c_trace_context(),
    )
    data = trace.to_dict()
    meta = data["_meta"]
    assert TRACEPARENT_RE.match(meta["traceparent"])
    assert meta["tracestate"] == "gen_ai=v1"
    assert meta["gen_ai"]["system"] == "deepseek"
    assert meta["gen_ai"]["model"] == "deepseek-chat"
    assert meta["gen_ai"]["agent.name"] == "designer"
    assert meta["gen_ai"]["usage"]["input_tokens"] == 10
    assert meta["gen_ai"]["usage"]["output_tokens"] == 5
    assert meta["gen_ai"]["usage"]["total_tokens"] == 15


def test_start_trace_generates_w3c_when_flag_on(monkeypatch):
    """集成：flag 开启时 start_trace 返回的 trace 自动携带 w3c_trace"""
    monkeypatch.setattr(get_settings(), "otel_genai_semconv_enabled", True)
    runtime = AgentRuntime()
    trace = runtime.start_trace("designer", "120平三室两厅北欧风", provider="deepseek")
    assert trace.w3c_trace
    assert TRACEPARENT_RE.match(trace.w3c_trace["traceparent"])
    # to_dict 亦应携带 _meta
    assert "_meta" in trace.to_dict()


def test_start_trace_no_w3c_when_flag_off(monkeypatch):
    """集成：flag 关闭时 start_trace 返回的 trace.w3c_trace 保持为空"""
    monkeypatch.setattr(get_settings(), "otel_genai_semconv_enabled", False)
    runtime = AgentRuntime()
    trace = runtime.start_trace("designer", "120平三室两厅北欧风", provider="deepseek")
    assert trace.w3c_trace == {}
    assert "_meta" not in trace.to_dict()


@pytest.mark.parametrize("enabled", [True, False])
def test_to_dict_existing_keys_stable(monkeypatch, enabled):
    """既有键不因 flag 开关而增删改（零回归：只可能新增 _meta 键）"""
    monkeypatch.setattr(get_settings(), "otel_genai_semconv_enabled", enabled)
    trace = AgentTrace(agent_name="designer", provider="deepseek")
    data = trace.to_dict()
    for key in (
        "trace_id", "agent_name", "agent_version", "provider", "model",
        "started_at", "finished_at", "status", "user_message_truncated",
        "response_truncated", "prompt_tokens", "completion_tokens",
        "total_tokens", "tool_call_count", "tool_call_rounds",
        "fallback_used", "fallback_reason", "retry_count", "latency_ms",
        "first_token_latency_ms", "error_message", "error_type",
        "user_id", "project_id", "scope", "context_source",
    ):
        assert key in data
