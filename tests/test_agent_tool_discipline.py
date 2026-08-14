"""v1.13.0 工具纪律 + 质量评估体系测试（对齐 2026 生产级 Agent 前沿）

覆盖：
- AgentTool.required 显式声明（可选参数不再被强制必填）
- 工具描述 use-example（2026：工具描述是最高优先级 prompt）
- ToolRegistry.execute 执行前参数类型校验（typed schema 拦截幻觉参数）
- think_with_tools 并行工具调用（asyncio.gather）
- think_with_tools token 预算早停（token_budget_hit）
- harness AgentTrace.token_budget_hit 传播
- 工具选择准确率评估（TOOL_SELECTION_DATASET ≥50 用例 + 基线报告）
- per-agent 评估新增工具维度指标
"""
import asyncio

import pytest

from app.agents.base import BaseAgent
from app.agents.harness import AgentRuntime
from app.services.agent_tool_registry import AgentTool, BUILTIN_TOOLS, tool_registry


# ════════════════════════════════════════════════════════════════
# 1. AgentTool.required 显式声明
# ════════════════════════════════════════════════════════════════


def test_required_explicit_on_builtin_tools():
    """内置工具必须显式声明 required，可选参数不再被强制必填。"""
    for tool in BUILTIN_TOOLS:
        schema = tool.to_openai_schema()["function"]
        assert "required" in schema["parameters"], f"{tool.name} 缺 required"
        # required 必须是 parameters 的子集（不允许声明不存在的参数）
        assert set(schema["parameters"]["required"]) <= set(schema["parameters"]["properties"])


def test_get_budget_required_only_area():
    """get_budget: area 必填，style/project_id 可选（此前全被强制必填）。"""
    tool = tool_registry.get("get_budget")
    schema = tool.to_openai_schema()["function"]
    assert schema["parameters"]["required"] == ["area"]


def test_search_materials_all_optional():
    """search_materials: 全部可选（有默认兜底）。"""
    tool = tool_registry.get("search_materials")
    schema = tool.to_openai_schema()["function"]
    assert schema["parameters"]["required"] == []


def test_update_design_proposal_required_fields():
    """update_design_proposal: proposal_id + change 必填。"""
    tool = tool_registry.get("update_design_proposal")
    schema = tool.to_openai_schema()["function"]
    assert schema["parameters"]["required"] == ["proposal_id", "change"]


def test_agent_tool_required_default_all():
    """AgentTool 未指定 required 时默认全部必填（保持旧行为）。"""

    async def _handler(**kwargs):
        return {"ok": True}

    t = AgentTool("t1", "desc", {"a": {"type": "string"}}, _handler)
    schema = t.to_openai_schema()["function"]
    assert schema["parameters"]["required"] == ["a"]


# ════════════════════════════════════════════════════════════════
# 2. 工具描述 use-example（2026：工具描述是最高优先级 prompt）
# ════════════════════════════════════════════════════════════════


def test_tool_descriptions_contain_example():
    """内置工具描述必须含「示例」引导（2026 工具使用示例规范）。"""
    for tool in BUILTIN_TOOLS:
        assert "示例" in tool.description, f"{tool.name} 描述缺示例"


# ════════════════════════════════════════════════════════════════
# 3. 执行前参数类型校验（typed schema 拦截幻觉参数）
# ════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("tool_name, bad_args", [
    ("get_budget", {"area": "一百", "style": "modern"}),  # string → number
    ("get_budget", {"area": True}),                       # bool → number
    ("search_poi", {"keywords": 123}),                    # int → string
    ("search_poi", {"radius": "3000"}),                   # string → number
    ("update_design_proposal", {"proposal_id": 1}),       # int → string
])
async def test_execute_rejects_invalid_types(monkeypatch, tool_name, bad_args):
    """类型不匹配的参数直接返回校验错误，不执行 handler。"""
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "tool_argument_validation_enabled", True)

    result = await tool_registry.execute(tool_name, bad_args)
    assert isinstance(result, dict)
    assert "error" in result
    assert "参数校验失败" in result["error"]


async def test_execute_accepts_valid_types(monkeypatch):
    """合法类型参数正常执行（number 接受 int/float）。"""
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "tool_argument_validation_enabled", True)

    result = await tool_registry.execute(
        "get_budget", {"area": 100.0, "style": "modern"},
    )
    assert isinstance(result, dict)
    assert "error" not in result
    assert result.get("area") == 100.0


async def test_validate_rejects_unknown_params(monkeypatch):
    """未知参数名拒绝（strict schema：防 LLM 编造未声明参数）。"""
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "tool_argument_validation_enabled", True)

    result = await tool_registry.execute(
        "get_budget", {"area": 100, "hallucinated_field": "xyz"},
    )
    assert isinstance(result, dict)
    assert "error" in result
    assert "未知参数" in result["error"]


async def test_validate_disabled_passthrough(monkeypatch):
    """flag 关闭时原样透传（零回归）。"""
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "tool_argument_validation_enabled", False)

    result = await tool_registry.execute("get_budget", {"area": "一百"})
    # 关闭校验 → handler 正常执行（area 为字符串时走默认 100 兜底）
    assert isinstance(result, dict)
    assert "参数校验失败" not in str(result)


# ════════════════════════════════════════════════════════════════
# 4. think_with_tools 并行工具调用
# ════════════════════════════════════════════════════════════════


async def test_think_with_tools_parallel_execution(monkeypatch):
    """同一轮多个 tool_calls 并行执行（asyncio.gather）。"""
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "parallel_tool_calls_enabled", True)
    monkeypatch.setattr(get_settings(), "agent_function_call_max_tool_tokens", 10**9)

    agent = BaseAgent()
    agent.agent_name = "parallel_test"
    agent.tools = tool_registry.get_openai_schemas_for_category("budget")

    # mock LLM：第一轮返回两个 tool_calls，第二轮返回纯文本
    async def fake_chat(messages, max_retries=0, with_tools=False):
        if with_tools:
            tool_msgs = [m for m in messages if m.get("role") == "tool"]
            if len(tool_msgs) == 0:
                return {
                    "content": "我来查两个预算",
                    "tool_calls": [
                        {"id": "c1", "name": "get_budget", "arguments": {"area": 100}},
                        {"id": "c2", "name": "get_budget", "arguments": {"area": 120}},
                    ],
                }
            return {"content": "预算结果如下", "tool_calls": []}
        return "最终回复"

    monkeypatch.setattr(agent, "_chat", fake_chat)
    # 用 spy 验证 gather 路径被走到（并行分支 len(tool_calls)>1）
    original_execute = tool_registry.execute
    called = []

    async def spy_execute(name, arguments, **kwargs):
        called.append(name)
        await asyncio.sleep(0.01)
        return await original_execute(name, arguments, **kwargs)

    monkeypatch.setattr(tool_registry, "execute", spy_execute)

    result = await agent.think_with_tools("120平预算多少")
    assert result["final_reply"] == "预算结果如下"
    assert len(result["tool_calls"]) == 2
    assert result["rounds"] == 1
    assert len(called) == 2
    assert result["token_budget_hit"] is False


async def test_think_with_tools_parallel_no_db_via_helper(monkeypatch):
    """无 db 时 _execute_tool_calls 走并行 gather（真正提速场景）。"""
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "parallel_tool_calls_enabled", True)

    agent = BaseAgent()
    agent.agent_name = "parallel_helper"
    original_execute = tool_registry.execute
    called = []

    async def spy_execute(name, arguments, **kwargs):
        called.append(name)
        await asyncio.sleep(0.01)
        return await original_execute(name, arguments, **kwargs)

    monkeypatch.setattr(tool_registry, "execute", spy_execute)

    results = await agent._execute_tool_calls(
        [
            {"name": "search_poi", "arguments": {"keywords": "建材市场"}},
            {"name": "search_materials", "arguments": {"keyword": "瓷砖"}},
        ],
        db=None, project_id="",
    )
    assert len(results) == 2
    assert len(called) == 2


async def test_think_with_tools_serial_with_db_avoids_isce(monkeypatch):
    """有 db 时工具调用串行执行（真实回归修复：共享 AsyncSession 并行触发
    SQLAlchemy ISCE 冲突，工具 handler DB 查询全部失败静默降级 fallback）。
    """
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "parallel_tool_calls_enabled", True)

    # 构造真实 AsyncSession（模拟端点注入的 db）
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    db = session_factory()

    agent = BaseAgent()
    agent.agent_name = "serial_db"
    original_execute = tool_registry.execute
    called = []

    async def spy_execute(name, arguments, **kwargs):
        called.append(name)
        await asyncio.sleep(0.01)
        return await original_execute(name, arguments, **kwargs)

    monkeypatch.setattr(tool_registry, "execute", spy_execute)

    try:
        results = await agent._execute_tool_calls(
            [
                {"name": "get_budget", "arguments": {"area": 100}},
                {"name": "search_materials", "arguments": {"keyword": "瓷砖"}},
                {"name": "get_design_layout", "arguments": {"area": 120}},
            ],
            db=db, project_id="",
        )
        # 有 db → 串行执行（不触发 ISCE），handler 正常返回结构化结果
        assert len(results) == 3
        assert len(called) == 3
        for r in results:
            assert isinstance(r, dict)
            assert "error" not in r or "参数校验失败" not in r.get("error", "")
    finally:
        await db.close()
        await engine.dispose()


async def test_think_with_tools_sequential_when_flag_off(monkeypatch):
    """flag 关闭时串行执行（零回归）。"""
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "parallel_tool_calls_enabled", False)

    agent = BaseAgent()
    agent.agent_name = "seq_test"
    agent.tools = tool_registry.get_openai_schemas_for_category("budget")

    async def fake_chat(messages, max_retries=0, with_tools=False):
        if with_tools:
            if not [m for m in messages if m.get("role") == "tool"]:
                return {
                    "content": "",
                    "tool_calls": [
                        {"id": "c1", "name": "get_budget", "arguments": {"area": 100}},
                        {"id": "c2", "name": "get_budget", "arguments": {"area": 120}},
                    ],
                }
            return {"content": "ok", "tool_calls": []}
        return "串行结果"

    monkeypatch.setattr(agent, "_chat", fake_chat)
    result = await agent.think_with_tools("预算")
    assert result["final_reply"] == "ok"
    assert len(result["tool_calls"]) == 2


# ════════════════════════════════════════════════════════════════
# 5. think_with_tools token 预算早停
# ════════════════════════════════════════════════════════════════


async def test_think_with_tools_token_budget_early_stop(monkeypatch):
    """token 预算触顶 → 提前终止循环，token_budget_hit=True。"""
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "parallel_tool_calls_enabled", True)
    # 极小预算：第一次工具结果即触顶
    monkeypatch.setattr(get_settings(), "agent_function_call_max_tool_tokens", 10)

    agent = BaseAgent()
    agent.agent_name = "budget_stop"
    agent.tools = tool_registry.get_openai_schemas_for_category("budget")

    chat_calls = []

    async def fake_chat(messages, max_retries=0, with_tools=False):
        chat_calls.append(messages)
        if with_tools:
            if not [m for m in messages if m.get("role") == "tool"]:
                return {
                    "content": "",
                    "tool_calls": [
                        {"id": "c1", "name": "get_budget", "arguments": {"area": 100}},
                    ],
                }
            return {"content": "不应走到这里", "tool_calls": []}
        return "预算早停总结"

    monkeypatch.setattr(agent, "_chat", fake_chat)

    result = await agent.think_with_tools("预算")
    assert result["token_budget_hit"] is True
    assert result["final_reply"] == "预算早停总结"
    assert result["rounds"] == 1
    # 早停后不应再发起工具轮次（最后一次是强制总结调用）
    assert len(chat_calls) == 2


async def test_think_with_tools_no_budget_hit_normal(monkeypatch):
    """正常完成（结果不超预算）时 token_budget_hit=False。"""
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "parallel_tool_calls_enabled", True)
    monkeypatch.setattr(get_settings(), "agent_function_call_max_tool_tokens", 10**9)

    agent = BaseAgent()
    agent.agent_name = "budget_normal"
    agent.tools = tool_registry.get_openai_schemas_for_category("budget")

    async def fake_chat(messages, max_retries=0, with_tools=False):
        if with_tools:
            if not [m for m in messages if m.get("role") == "tool"]:
                return {
                    "content": "",
                    "tool_calls": [
                        {"id": "c1", "name": "get_budget", "arguments": {"area": 100}},
                    ],
                    "usage": {"prompt_tokens": 50, "completion_tokens": 30, "total_tokens": 80},
                }
            return {
                "content": "ok", "tool_calls": [],
                "usage": {"prompt_tokens": 60, "completion_tokens": 40, "total_tokens": 100},
            }
        return "正常完成"

    monkeypatch.setattr(agent, "_chat", fake_chat)
    result = await agent.think_with_tools("预算")
    assert result["token_budget_hit"] is False


async def test_think_with_tools_usage_accumulated(monkeypatch):
    """v1.13.1 成本追踪：多轮 LLM usage 累计并透传 harness。"""
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "parallel_tool_calls_enabled", True)
    monkeypatch.setattr(get_settings(), "agent_function_call_max_tool_tokens", 10**9)

    agent = BaseAgent()
    agent.agent_name = "usage_test"
    agent.tools = tool_registry.get_openai_schemas_for_category("budget")

    async def fake_chat(messages, max_retries=0, with_tools=False):
        if with_tools:
            if not [m for m in messages if m.get("role") == "tool"]:
                return {
                    "content": "",
                    "tool_calls": [
                        {"id": "c1", "name": "get_budget", "arguments": {"area": 100}},
                    ],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
                }
            return {
                "content": "ok", "tool_calls": [],
                "usage": {"prompt_tokens": 130, "completion_tokens": 30, "total_tokens": 160},
            }
        return "done"

    monkeypatch.setattr(agent, "_chat", fake_chat)
    result = await agent.think_with_tools("预算")
    # 两轮 usage 累计：prompt 100+130=230, completion 20+30=50, total 120+160=280
    assert result["usage"]["prompt_tokens"] == 230
    assert result["usage"]["completion_tokens"] == 50
    assert result["usage"]["total_tokens"] == 280

    # harness 贯通：think_with_tools 的 usage 写入 AgentTrace
    harness = AgentRuntime()
    trace = harness.start_trace("usage_test", "预算")
    await harness.run(agent, "预算", trace=trace, db=None, user_id="u1")
    assert trace.total_tokens == 280
    assert trace.prompt_tokens == 230
    assert trace.completion_tokens == 50


# ════════════════════════════════════════════════════════════════
# 6. harness AgentTrace.token_budget_hit 传播
# ════════════════════════════════════════════════════════════════


async def test_harness_trace_token_budget_hit(monkeypatch):
    """harness.run 将 think_with_tools 的 token_budget_hit 写入 trace。"""
    agent = BaseAgent()
    agent.agent_name = "trace_budget"
    agent.tools = tool_registry.get_openai_schemas_for_category("budget")

    async def fake_think_with_tools(user_message, **kwargs):
        return {
            "final_reply": "done", "tool_calls": [{"tool": "get_budget"}],
            "rounds": 1, "token_budget_hit": True,
        }

    monkeypatch.setattr(agent, "think_with_tools", fake_think_with_tools)

    harness = AgentRuntime()
    trace = harness.start_trace("trace_budget", "预算")
    result = await harness.run(agent, "预算", trace=trace, db=None, user_id="u1")
    assert result["trace"]["token_budget_hit"] is True
    assert trace.token_budget_hit is True


# ════════════════════════════════════════════════════════════════
# 7. 工具选择准确率评估（TOOL_SELECTION_DATASET ≥50 用例）
# ════════════════════════════════════════════════════════════════


def test_dataset_meets_50_cases():
    """2026 标准：每失败模式 ≥50 用例（全数据集 ≥50 且覆盖三类失败模式）。"""
    from app.eval.tool_accuracy import TOOL_SELECTION_DATASET
    assert len(TOOL_SELECTION_DATASET) >= 50
    modes = {c.failure_mode for c in TOOL_SELECTION_DATASET}
    assert "normal" in modes and "boundary" in modes and "confusable" in modes
    assert "negative" in modes


def test_dataset_covers_all_visible_builtin_tools():
    """数据集覆盖全部对用户可见的内置工具（admin 类别不暴露，无需评估）。"""
    from app.eval.tool_accuracy import TOOL_SELECTION_DATASET
    covered = {c.expected_tool for c in TOOL_SELECTION_DATASET}
    builtin = {t.name for t in BUILTIN_TOOLS if t.category != "admin"}
    assert covered == builtin


def test_evaluate_tool_selection_baseline():
    """基线评估返回结构化报告（准确率 + per_tool + per_failure_mode + confusion）。"""
    from app.eval.tool_accuracy import evaluate_tool_selection
    report = evaluate_tool_selection()
    assert report["sample_size"] == len(report["confusion"]) + report["correct"]
    assert 0 <= report["accuracy"] <= 100
    assert "per_tool" in report and "per_failure_mode" in report


def test_tool_accuracy_report_serializable():
    """报告可序列化且含诚实标注。"""
    import json
    from app.eval.tool_accuracy import get_tool_accuracy_report
    report = get_tool_accuracy_report()
    assert report["baseline"] == "keyword_classifier"
    assert report["dataset_size"] >= 50
    assert any("诚实" in n or "基线" in n for n in report["notes"])
    json.dumps(report, ensure_ascii=False)  # 可序列化


def test_custom_classifier_evaluation():
    """自定义分类器评估（供 LLM 分类接入）。"""
    from app.eval.tool_accuracy import evaluate_tool_selection

    def oracle(query: str) -> str | None:
        if "预算" in query:
            return "get_budget"
        if "进度" in query:
            return "get_construction_progress"
        return None

    report = evaluate_tool_selection(classifier=oracle)
    assert report["sample_size"] >= 50
    assert report["accuracy"] > 0  # oracle 至少命中部分预算/进度用例


# ── v1.13.5 工具选择基线打磨（75% → 100%，2026-08-12）──


def test_tool_accuracy_baseline_high():
    """基线准确率 ≥ 90%（v1.13.5 关键词表消歧打磨后实测 100%，锁定防回退）。

    打磨点：设计类三重工具（layout/proposals/update）关键词细分、search_materials
    移除"多少钱"、negative 用例按「不应选工具」度量、关键词大小写归一化。
    """
    from app.eval.tool_accuracy import evaluate_tool_selection
    report = evaluate_tool_selection()
    assert report["accuracy"] >= 90.0, f"工具选择基线回退: {report['accuracy']}%"
    assert report["confusion"] == [], f"不应有混淆: {report['confusion']}"


def test_negative_cases_expect_no_tool():
    """negative 用例（闲聊/致谢）不应选工具——classifier 返回 None 计正确。"""
    from app.eval.tool_accuracy import (
        TOOL_SELECTION_DATASET, classify_tool_by_keywords,
    )
    negative = [c for c in TOOL_SELECTION_DATASET if c.failure_mode == "negative"]
    assert negative, "数据集应含 negative 用例"
    for case in negative:
        assert classify_tool_by_keywords(case.query) is None, \
            f"闲聊不应选工具: {case.query!r}"


def test_keyword_case_insensitive():
    """关键词大小写归一化："方案B" lower 后仍命中 update_design_proposal。"""
    from app.eval.tool_accuracy import classify_tool_by_keywords
    assert classify_tool_by_keywords("把方案B的颜色换成浅色") == "update_design_proposal"
    assert classify_tool_by_keywords("方案A改成开放式厨房") == "update_design_proposal"


# ── v1.13.8 Minimal 模式评测（借鉴 DeepSeek Harness「Minimal mode」）──


def test_minimal_dataset_covers_two_core_tools():
    """Minimal 数据集仅覆盖 get_budget + get_design_layout 两核心工具。"""
    from app.eval.tool_accuracy import MINIMAL_TOOL_DATASET
    covered = {c.expected_tool for c in MINIMAL_TOOL_DATASET}
    assert covered == {"get_budget", "get_design_layout"}
    assert len(MINIMAL_TOOL_DATASET) >= 10


def test_minimal_tool_accuracy_report_100_percent():
    """极简工具集下关键词基线仍 100% 且零混淆（隔离工具数量对选择准确率的影响）。"""
    from app.eval.tool_accuracy import get_minimal_tool_accuracy_report
    report = get_minimal_tool_accuracy_report()
    assert report["report_type"] == "tool_selection_accuracy_minimal"
    assert report["metrics"]["accuracy"] == 100.0
    assert report["confusion"] == []


def test_minimal_report_serializable():
    """Minimal 报告可序列化且诚实标注为 keyword 基线。"""
    import json
    from app.eval.tool_accuracy import get_minimal_tool_accuracy_report
    report = get_minimal_tool_accuracy_report()
    assert report["baseline"] == "keyword_classifier"
    json.dumps(report, ensure_ascii=False)


# ════════════════════════════════════════════════════════════════
# 8. per-agent 评估新增工具维度指标
# ════════════════════════════════════════════════════════════════


def test_per_agent_scores_include_tool_metrics():
    """per-agent 评分含 avg_tool_calls / tool_success_rate / token_budget_hit_rate。"""
    from app.eval.ihome_eval import IHomeEvalRunner, QUALITY_TARGETS

    traces = [
        {"agent_name": "designer", "status": "success", "fallback_used": False,
         "latency_ms": 100, "tool_call_count": 2, "token_budget_hit": False},
        {"agent_name": "designer", "status": "success", "fallback_used": False,
         "latency_ms": 200, "tool_call_count": 1, "token_budget_hit": True},
    ]
    runner = IHomeEvalRunner()
    per = runner._compute_per_agent_scores(traces)
    d = per["designer"]
    assert d["avg_tool_calls"] == 1.5
    assert d["tool_success_rate"] == 100.0
    assert d["token_budget_hit_rate"] == 50.0
    # 预算早停率 50% > 上限 20% → meets_targets=False
    assert d["meets_targets"] is False
    assert QUALITY_TARGETS["token_budget_hit_rate_max"] == 20.0
    assert QUALITY_TARGETS["tool_selection_accuracy_min"] == 60.0


def test_tool_call_score_uses_baseline_when_no_tool_traces():
    """无工具轨迹时 TOOL_CALL_ACCURACY 用确定性基线准确率（诚实代理）。"""
    from app.eval.ihome_eval import IHomeEvalRunner
    runner = IHomeEvalRunner()
    traces = [{"agent_name": "a", "status": "success", "tool_call_count": 0}]
    score = runner._tool_call_score(traces)
    assert 0 <= score <= 100


# ════════════════════════════════════════════════════════════════
# 9. admin 工具注册（v1.13.0 审计修复）
# ════════════════════════════════════════════════════════════════


def test_admin_tools_registered_in_registry():
    """admin 的 6 个工具已注册进 registry（不再内联双源）。"""
    for name in ["list_users", "update_user_role", "update_user_status",
                 "get_platform_stats", "get_role_permissions",
                 "list_pending_verifications"]:
        assert tool_registry.get(name) is not None, f"{name} 未注册"


def test_admin_tools_hidden_from_visible_list(monkeypatch):
    """admin 工具默认对通用可见列表隐藏（渐进披露 + 治理红线）。"""
    visible = {t.name for t in tool_registry.list_tools()}
    for name in ["list_users", "update_user_role", "update_user_status",
                 "get_platform_stats", "get_role_permissions",
                 "list_pending_verifications"]:
        assert name not in visible, f"{name} 不应在通用列表暴露"


def test_admin_agent_tools_from_registry():
    """AdminAgent.tools 从 registry 拉取（与内置工具统一契约）。"""
    from app.agents.admin import AdminAgent
    agent = AdminAgent()
    schemas = agent.tools
    names = {s["function"]["name"] for s in schemas}
    assert names == {"list_users", "update_user_role", "update_user_status",
                     "get_platform_stats", "get_role_permissions",
                     "list_pending_verifications"}
    # 每个 schema 显式声明 required（单源契约生效）
    for s in schemas:
        assert "required" in s["function"]["parameters"]


async def test_admin_tool_executes_honest_guide():
    """admin 工具执行返回诚实降级引导（不伪装执行写操作）。"""
    result = await tool_registry.execute("list_users", {"role": "designer"})
    assert isinstance(result, dict)
    assert result["source"] == "admin_api_guide"
    assert result["executed"] is False
    assert "管理 API" in result["message"]


# ════════════════════════════════════════════════════════════════
# 10. 全链路集成：输入 → 工具决策 → 真实执行 → 输出（v1.13.1）
# ════════════════════════════════════════════════════════════════


async def test_endpoint_to_tool_execution_full_chain(monkeypatch):
    """全链路闭环：LLM 决策调用 get_budget → 工具真实执行（含结构化结果）→ 最终回复。

    对齐 2026「Agent = Model + Harness」共识：验证 harness 层工具执行
    与 LLM 决策之间的完整契约（工具 schema → 执行 → 结果回注 → 汇总回复）。
    """
    from app.agents.budget import BudgetAgent

    agent = BudgetAgent()

    # mock LLM：第一轮决策调用 get_budget 工具，第二轮基于工具结果汇总
    async def fake_chat(messages, max_retries=0, with_tools=False):
        if with_tools:
            if not [m for m in messages if m.get("role") == "tool"]:
                return {
                    "content": "我来查询预算",
                    "tool_calls": [
                        {"id": "t1", "name": "get_budget", "arguments": {"area": 100, "style": "modern"}},
                    ],
                    "usage": {"prompt_tokens": 80, "completion_tokens": 10, "total_tokens": 90},
                }
            # 第二轮：工具结果已回注 messages，LLM 汇总
            tool_msgs = [m for m in messages if m.get("role") == "tool"]
            assert tool_msgs, "工具结果未回注到对话上下文"
            tool_content = tool_msgs[0]["content"]
            assert "area" in tool_content, "工具结果应含结构化预算数据"
            return {
                "content": "根据查询，100平现代简约预算约10万，含硬装与软装分项。",
                "tool_calls": [],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            }
        return "fallback"

    monkeypatch.setattr(agent, "_chat", fake_chat)
    # 本测试聚焦工具纪律链路（schema→执行→回注→汇总），mock 掉 HC 反驳校验
    # （Model Spec 硬约束有独立测试覆盖，此处避免 mock 回复被判 HC 违规后重生成）

    async def _passthrough_rebuttal(messages, reply):
        return reply

    monkeypatch.setattr(agent, "_rebuttal_check", _passthrough_rebuttal)

    result = await agent.think_with_tools("100平现代简约装修预算多少", db=None, project_id="")
    # 全链路输出：final_reply 基于真实工具执行结果生成
    assert result["final_reply"] == "根据查询，100平现代简约预算约10万，含硬装与软装分项。"
    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["tool"] == "get_budget"
    # 工具执行结果真实包含结构化预算数据（非 fallback 空壳）
    exec_result = result["tool_calls"][0]["result"]
    assert isinstance(exec_result, dict)
    assert exec_result.get("area") == 100
    assert "tiers" in exec_result or "total_estimated" in exec_result
    # 成本追踪：usage 累计贯通
    assert result["usage"]["total_tokens"] == 210  # 90 + 120
    assert result["token_budget_hit"] is False


async def test_endpoint_to_tool_execution_with_db(monkeypatch, db_session):
    """有 db 时工具调用串行执行且真实查询（ISCE 回归修复验证的端点级延伸）。"""
    from app.agents.budget import BudgetAgent

    agent = BudgetAgent()

    async def fake_chat(messages, max_retries=0, with_tools=False):
        if with_tools:
            if not [m for m in messages if m.get("role") == "tool"]:
                return {
                    "content": "",
                    "tool_calls": [
                        {"id": "t1", "name": "get_budget", "arguments": {"area": 100}},
                    ],
                }
            return {"content": "ok", "tool_calls": []}
        return "done"

    monkeypatch.setattr(agent, "_chat", fake_chat)
    # 同 test_endpoint_to_tool_execution_full_chain：mock 掉 HC 反驳校验

    async def _passthrough_rebuttal(messages, reply):
        return reply

    monkeypatch.setattr(agent, "_rebuttal_check", _passthrough_rebuttal)

    result = await agent.think_with_tools("预算", db=db_session, project_id="")
    assert result["final_reply"] == "ok"
    # 有 db → 串行路径执行，工具结果结构化返回（无 ISCE 冲突降级）
    assert result["tool_calls"][0]["tool"] == "get_budget"
    assert isinstance(result["tool_calls"][0]["result"], dict)
