"""v1.2.8 讨论式方案交互测试

覆盖：
- design_proposal_service: LLM 生成 / 修订 / fallback 降级
- agent_tool_registry: FunctionCall 工具执行 + flag 门控
- api/agents: REST 端点 /design/proposals + /design/proposals/{id}/revise
- api/config: feature-flags 暴露
"""
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import design_proposal_service as dps
from app.services.design_proposal_service import (
    ProposalSpec,
    generate_proposals,
    revise_proposal,
)
from app.services.agent_tool_registry import ToolRegistry


# ── design_proposal_service 单元测试 ──


@pytest.fixture(autouse=True)
async def _reset_store():
    """每个测试前清空方案缓存存储"""
    from app.services.cache_service import cache
    await cache.delete_pattern("design_proposal:*")
    yield
    await cache.delete_pattern("design_proposal:*")


@pytest.mark.asyncio
async def test_generate_proposals_fallback_when_flag_off(monkeypatch):
    """flag 关闭时降级到单方案 fallback"""
    monkeypatch.setattr(dps.settings, "design_proposal_llm_enabled", False)
    result = await generate_proposals("帮我设计厨房", "sess_test")
    assert len(result.proposals) == 1
    assert result.proposals[0].source == "fallback"
    assert result.proposals[0].proposal_id == "A"
    assert result.session_id == "sess_test"


@pytest.mark.asyncio
async def test_generate_proposals_llm_success(monkeypatch):
    """flag 开启 + LLM 返回有效 JSON → 解析为多方案"""
    monkeypatch.setattr(dps.settings, "design_proposal_llm_enabled", True)
    llm_response = json.dumps({
        "proposals": [
            {"proposal_id": "A", "title": "紧凑型", "layout_type": "L型",
             "area_sqm": 5.2, "budget_cny": 18000, "highlights": ["动线紧凑"]},
            {"proposal_id": "B", "title": "标准型", "layout_type": "U型",
             "area_sqm": 6.8, "budget_cny": 24000, "highlights": ["台面大"]},
        ]
    })
    with patch.object(dps, "_call_llm", new_callable=AsyncMock, return_value=llm_response):
        result = await generate_proposals("设计厨房", "sess_llm")
    assert len(result.proposals) == 2
    assert result.proposals[0].proposal_id == "A"
    assert result.proposals[1].proposal_id == "B"
    assert result.proposals[0].source == "llm"
    assert result.proposals[1].budget_cny == 24000


@pytest.mark.asyncio
async def test_generate_proposals_llm_unparseable_falls_back(monkeypatch):
    """LLM 返回无法解析的内容 → 降级 fallback"""
    monkeypatch.setattr(dps.settings, "design_proposal_llm_enabled", True)
    with patch.object(dps, "_call_llm", new_callable=AsyncMock, return_value="这不是JSON"):
        result = await generate_proposals("设计客厅", "sess_bad")
    assert len(result.proposals) == 1
    assert result.proposals[0].source == "fallback"


@pytest.mark.asyncio
async def test_generate_proposals_llm_all_providers_fail(monkeypatch):
    """LLM 全链路不可用 → 降级 fallback"""
    monkeypatch.setattr(dps.settings, "design_proposal_llm_enabled", True)
    with patch.object(dps, "_call_llm", new_callable=AsyncMock, return_value=None):
        result = await generate_proposals("设计卫生间", "sess_fail")
    assert len(result.proposals) == 1
    assert result.proposals[0].source == "fallback"


@pytest.mark.asyncio
async def test_revise_proposal_no_history_returns_none(monkeypatch):
    """无历史方案时修订返回 None"""
    monkeypatch.setattr(dps.settings, "design_proposal_llm_enabled", True)
    result = await revise_proposal("B", "加中岛", "sess_empty")
    assert result is None


@pytest.mark.asyncio
async def test_revise_proposal_not_found(monkeypatch):
    """方案 ID 不存在时返回 None"""
    monkeypatch.setattr(dps.settings, "design_proposal_llm_enabled", True)
    # 先存一个方案
    await dps._store_proposals("sess_x", [
        ProposalSpec(proposal_id="A", title="紧凑型", layout_type="L型",
                     area_sqm=5.0, budget_cny=15000, highlights=["x"])
    ])
    result = await revise_proposal("Z", "改一下", "sess_x")
    assert result is None


@pytest.mark.asyncio
async def test_revise_proposal_success(monkeypatch):
    """LLM 修订成功 → 返回修订后方案，内存更新"""
    monkeypatch.setattr(dps.settings, "design_proposal_llm_enabled", True)
    await dps._store_proposals("sess_rev", [
        ProposalSpec(proposal_id="A", title="紧凑型", layout_type="L型",
                     area_sqm=5.0, budget_cny=15000, highlights=["x"]),
        ProposalSpec(proposal_id="B", title="标准型", layout_type="U型",
                     area_sqm=6.5, budget_cny=22000, highlights=["y"]),
    ])
    revised_json = json.dumps({
        "proposal_id": "B", "title": "标准型+", "layout_type": "U型+中岛",
        "area_sqm": 7.0, "budget_cny": 26000, "highlights": ["y", "中岛"],
        "change_log": ["加中岛"]
    })
    with patch.object(dps, "_call_llm", new_callable=AsyncMock, return_value=revised_json):
        revised = await revise_proposal("B", "加中岛", "sess_rev")
    assert revised is not None
    assert revised.layout_type == "U型+中岛"
    assert revised.budget_cny == 26000
    assert "加中岛" in revised.change_log
    # 验证缓存已更新
    stored = await dps._get_proposals("sess_rev")
    assert next(p for p in stored if p.proposal_id == "B").budget_cny == 26000


@pytest.mark.asyncio
async def test_revise_proposal_flag_off_appends_changelog(monkeypatch):
    """flag 关闭时修订仅追加 change_log，不改字段"""
    monkeypatch.setattr(dps.settings, "design_proposal_llm_enabled", False)
    await dps._store_proposals("sess_flag", [
        ProposalSpec(proposal_id="A", title="标准型", layout_type="L型",
                     area_sqm=6.0, budget_cny=20000, highlights=["x"])
    ])
    revised = await revise_proposal("A", "加中岛", "sess_flag")
    assert revised is not None
    assert revised.budget_cny == 20000  # 未变
    assert any("加中岛" in log for log in revised.change_log)


# ── FunctionCall 工具执行测试 ──


@pytest.mark.asyncio
async def test_tool_generate_design_proposals_executes(monkeypatch):
    """工具 generate_design_proposals 可被 ToolRegistry 执行"""
    monkeypatch.setattr(dps.settings, "design_proposal_llm_enabled", False)
    registry = ToolRegistry()
    result = await registry.execute(
        "generate_design_proposals",
        {"requirement": "设计厨房"},
        _user_id="user123",
    )
    assert result["generated"] is True
    assert len(result["proposals"]) >= 1
    assert result["session_id"] == "proposal_user123"


@pytest.mark.asyncio
async def test_tool_update_design_proposal_no_history(monkeypatch):
    """工具 update_design_proposal 无历史方案时返回 updated=False"""
    monkeypatch.setattr(dps.settings, "design_proposal_llm_enabled", False)
    registry = ToolRegistry()
    result = await registry.execute(
        "update_design_proposal",
        {"proposal_id": "B", "change": "加中岛"},
        _user_id="user_nohistory",
    )
    assert result["updated"] is False


@pytest.mark.asyncio
async def test_tool_update_design_proposal_success(monkeypatch):
    """工具 update_design_proposal 修订成功"""
    monkeypatch.setattr(dps.settings, "design_proposal_llm_enabled", False)
    # 先用 generate 工具创建方案
    registry = ToolRegistry()
    await registry.execute(
        "generate_design_proposals",
        {"requirement": "设计厨房"},
        _user_id="user_rev",
    )
    result = await registry.execute(
        "update_design_proposal",
        {"proposal_id": "A", "change": "加中岛"},
        _user_id="user_rev",
    )
    assert result["updated"] is True
    assert result["proposal"]["proposal_id"] == "A"


def test_tool_registry_hides_design_proposal_when_flag_disabled(monkeypatch):
    """flag 关闭时 _visible_tools 隐藏 design_proposal 类别"""
    from app.services.agent_tool_registry import settings as reg_settings
    monkeypatch.setattr(reg_settings, "design_proposal_llm_enabled", False)
    monkeypatch.setattr(reg_settings, "voice_agent_orchestration_enabled", False)
    registry = ToolRegistry()
    names = [t.name for t in registry._visible_tools()]
    assert "generate_design_proposals" not in names
    assert "update_design_proposal" not in names


def test_tool_registry_shows_design_proposal_when_flag_enabled(monkeypatch):
    """flag 开启时 _visible_tools 显示 design_proposal 类别"""
    from app.services.agent_tool_registry import settings as reg_settings
    monkeypatch.setattr(reg_settings, "design_proposal_llm_enabled", True)
    monkeypatch.setattr(reg_settings, "voice_agent_orchestration_enabled", False)
    registry = ToolRegistry()
    names = [t.name for t in registry._visible_tools()]
    assert "generate_design_proposals" in names
    assert "update_design_proposal" in names


# ── REST API 端点测试 ──


def test_feature_flags_expose_design_proposal_flags():
    """/config/feature-flags 暴露新 flag"""
    client = TestClient(app)
    resp = client.get("/api/config/feature-flags")
    assert resp.status_code == 200
    data = resp.json()
    assert "voice_floating_widget_enabled" in data
    assert "design_proposal_llm_enabled" in data


def test_design_proposals_endpoint_fallback(monkeypatch):
    """POST /api/agents/design/proposals 在 flag 关闭时返回 fallback 单方案"""
    from app.services import design_proposal_service as svc
    monkeypatch.setattr(svc.settings, "design_proposal_llm_enabled", False)
    client = TestClient(app)
    # 需要认证，用 mock
    from app.auth import get_current_user
    from app.models.user import User

    mock_user = User(id="test-user-1", phone="13800000000", name="test", role="homeowner")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        resp = client.post(
            "/api/agents/design/proposals",
            json={"requirement": "设计厨房"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["proposals"]) >= 1
        assert data["source"] == "fallback"
    finally:
        app.dependency_overrides.clear()


def test_design_proposals_cache_user_isolation(monkeypatch):
    """缓存隔离：不同用户传相同 session_id 不能跨用户读写方案（IDOR 修复）"""
    from app.services import design_proposal_service as svc
    monkeypatch.setattr(svc.settings, "design_proposal_llm_enabled", False)
    client = TestClient(app)
    from app.auth import get_current_user
    from app.models.user import User

    user_a = User(id="user-a", phone="13800000001", name="A", role="homeowner")
    user_b = User(id="user-b", phone="13800000002", name="B", role="homeowner")

    # 用户 A 生成方案（客户端传 session_id=shared），后端应强制用户命名空间
    app.dependency_overrides[get_current_user] = lambda: user_a
    try:
        resp = client.post(
            "/api/agents/design/proposals",
            json={"requirement": "设计厨房", "session_id": "shared"},
        )
        assert resp.status_code == 200
        assert resp.json()["session_id"] == "proposal_user-a:shared"
    finally:
        app.dependency_overrides.clear()

    # 用户 B 用相同 session_id 修订 → 404（无法读用户 A 的缓存方案）
    app.dependency_overrides[get_current_user] = lambda: user_b
    try:
        resp = client.post(
            "/api/agents/design/proposals/A/revise",
            json={"change": "加中岛", "session_id": "shared"},
        )
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
