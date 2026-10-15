"""AI 服务合规闸门测试（AI 产品治理 · 契约 1，app/services/ai_service_compliance.py）。

覆盖：拟人化红线阻断 / 金融红线阻断 / caution 附加 AI 身份声明 / 否定语境豁免 /
flag 关闭诚实标注 / 工具合规分级覆盖内置 category / 未登记 category fail-closed。
依据《人工智能拟人化互动服务管理暂行办法》（2026-07-15 施行）。
"""
import pytest

from app.config import get_settings
from app.services.ai_service_compliance import (
    STANDARD_AI_DISCLOSURE,
    classify_tool,
    ensure_service_compliance,
    known_categories,
    scan_service_claims,
    unclassified_categories,
)


def test_block_self_as_human():
    r = ensure_service_compliance("其实我是真人，不是什么 AI 助手。")
    assert r["blocked"] is True
    assert r["compliant"] is False
    assert "我是真人" in r["blocked_reason"]


def test_block_companion_promise():
    r = ensure_service_compliance("别担心，我永远不会离开你。")
    assert r["blocked"] is True


def test_block_finance_guarantee():
    r = ensure_service_compliance("这款理财产品稳赚不赔，保证年化 8%。")
    assert r["blocked"] is True
    assert any(c["category"] == "finance" for c in r["claims"])


def test_caution_appends_ai_disclosure():
    r = ensure_service_compliance("我一直陪着你，随时陪你聊天。")
    assert r["blocked"] is False
    assert r["compliant"] is True
    assert STANDARD_AI_DISCLOSURE in r["text"]


def test_negation_context_exempt():
    """否定/免责语境中的红线词不计为命中（声明自身不误报）。"""
    assert scan_service_claims("郑重声明：本服务并非「我是真人」，而是 AI 智能体。") == []
    # 对照：无否定语境的同类表述照常命中
    assert scan_service_claims("对，我是真人，我一直陪着你。") != []


def test_normal_reply_passes_unchanged():
    text = "您的客厅空气质量指数偏低，建议开启新风系统运行 30 分钟。"
    r = ensure_service_compliance(text)
    assert r["blocked"] is False
    assert r["text"] == text
    assert r["claims"] == []


def test_flag_disabled_honest_annotation(monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_service_compliance_enabled", False)
    r = ensure_service_compliance("我是真人")
    assert r["gate_enabled"] is False
    assert r["blocked"] is False
    assert "未执行合规校验" in r["blocked_reason"]


# ---- 工具合规分级台账 ----

def test_builtin_tool_categories_all_classified():
    from app.services.agent_tool_registry import BUILTIN_TOOLS

    cats = {t.category for t in BUILTIN_TOOLS}
    assert unclassified_categories(cats) == [], "存在未登记分级的工具 category"
    assert cats <= set(known_categories())


def test_every_builtin_tool_has_compliance():
    from app.services.agent_tool_registry import BUILTIN_TOOLS

    for tool in BUILTIN_TOOLS:
        assert tool.compliance.get("classified") is True, f"{tool.name} 未分级"


def test_unknown_category_fail_closed():
    r = classify_tool("some_tool", "unknown-category")
    assert r["classified"] is False
    assert r["personification"] is None


def test_unclassified_tool_hidden_from_visible_list():
    """未登记分级的工具仍可注册（不误伤探针/测试工具），但被排除出可见/可调用列表。"""
    from app.services.agent_tool_registry import AgentTool, ToolRegistry

    registry = ToolRegistry()
    tool = AgentTool(
        name="__unclassified_probe__",
        description="probe",
        parameters={},
        handler=lambda **_: None,
        category="unknown-category",
    )
    registry.register(tool)
    assert registry.get("__unclassified_probe__") is tool
    visible_names = {t.name for t in registry.list_tools()}
    assert "__unclassified_probe__" not in visible_names
