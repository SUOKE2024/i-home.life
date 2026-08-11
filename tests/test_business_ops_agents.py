"""v1.6.0 平台商业运营 Agent 测试 — Growth/Marketing/CompetitorResearch/FinanceRecon + Orchestrator 日报

验证维度（对应 CLAUDE.md「Goal-Driven Execution — 加功能先写验收用例」）：
1. 商业运营子 Agent v1.13.2 起默认开启（growth/marketing/competitor/finance 默认 True）；
   显式关闭（monkeypatch False）时各 Agent 方法返回 enabled=False（不触发 LLM/DB，诚实降级）
2. Orchestrator 默认开启（business_ops_orchestrator_enabled=True），db=None 时 best-effort 聚合不崩；
   显式关闭时返回 enabled=False
3. feature flag 开启后（monkeypatch）：返回含 data_source 的结构，DB 不可用时降级
4. /api/admin/daily-briefing 端点未授权 401
"""

import pytest
from httpx import AsyncClient

from app.agents.competitor_research import CompetitorResearchAgent
from app.agents.finance_recon import FinanceReconAgent
from app.agents.growth import GrowthAgent
from app.agents.marketing import MarketingAgent
from app.agents.orchestrator import OrchestratorAgent


# ── feature flag 显式关闭（不触发 LLM/DB，诚实返回 enabled=False）──


@pytest.mark.asyncio
async def test_growth_agent_disabled_when_flag_off(monkeypatch):
    from app.agents import growth as growth_mod
    monkeypatch.setattr(growth_mod.settings, "growth_agent_enabled", False)

    agent = GrowthAgent()
    try:
        result = await agent.generate_weekly_report(db=None, days=7)
        assert result["enabled"] is False
        assert "growth_agent_enabled" in result["note"]
    finally:
        await agent.close()


@pytest.mark.asyncio
async def test_marketing_agent_disabled_when_flag_off(monkeypatch):
    from app.agents import marketing as marketing_mod
    monkeypatch.setattr(marketing_mod.settings, "marketing_agent_enabled", False)

    agent = MarketingAgent()
    try:
        result = await agent.generate_content(case_summary="90㎡ 现代简约", channel="xiaohongshu")
        assert result["enabled"] is False
    finally:
        await agent.close()


@pytest.mark.asyncio
async def test_competitor_research_agent_disabled_when_flag_off(monkeypatch):
    from app.agents import competitor_research as comp_mod
    monkeypatch.setattr(comp_mod.settings, "competitor_research_agent_enabled", False)

    agent = CompetitorResearchAgent()
    try:
        result = await agent.generate_research_brief(competitor_name="酷家乐")
        assert result["enabled"] is False
    finally:
        await agent.close()


@pytest.mark.asyncio
async def test_finance_recon_agent_disabled_when_flag_off(monkeypatch):
    from app.agents import finance_recon as fin_mod
    monkeypatch.setattr(fin_mod.settings, "finance_recon_agent_enabled", False)

    agent = FinanceReconAgent()
    try:
        result = await agent.generate_recon_report(db=None, days=30)
        assert result["enabled"] is False
    finally:
        await agent.close()


@pytest.mark.asyncio
async def test_orchestrator_daily_briefing_disabled_when_flag_off(monkeypatch):
    """business_ops_orchestrator_enabled=False 时返回 enabled=False（显式关闭降级）"""
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "business_ops_orchestrator_enabled", False)

    orch = OrchestratorAgent()
    try:
        result = await orch.generate_daily_briefing(db=None)
        assert result["enabled"] is False
        assert "business_ops_orchestrator_enabled" in result["note"]
    finally:
        await orch.close()


@pytest.mark.asyncio
async def test_orchestrator_daily_briefing_enabled_by_default():
    """v1.13.2 起 orchestrator 默认 True；db=None 时各 section best-effort 降级不阻断简报"""
    orch = OrchestratorAgent()
    try:
        result = await orch.generate_daily_briefing(db=None)
        assert result["enabled"] is True
        assert "sections" in result
        # 子 Agent 默认开启 → db=None 时 enabled=True + data_source 诚实降级标注
        assert "growth_weekly" in result["sections"]
        assert "finance_recon" in result["sections"]
        assert result["sections"]["growth_weekly"].get("enabled") is True
        assert result["sections"]["finance_recon"].get("enabled") is True
        assert "data_source" in result["sections"]["growth_weekly"]
        assert "data_source" in result["sections"]["finance_recon"]
    finally:
        await orch.close()


# ── feature flag 开启后结构校验（monkeypatch settings 对象属性）──


@pytest.mark.asyncio
async def test_growth_agent_enabled_returns_structure(monkeypatch):
    """growth_agent_enabled=True 时返回含 data_source 的结构（db=None 触发查询异常降级）"""
    from app.agents import growth as growth_mod
    monkeypatch.setattr(growth_mod.settings, "growth_agent_enabled", True)

    agent = GrowthAgent()
    try:
        result = await agent.generate_weekly_report(db=None, days=7)
        assert result["enabled"] is True
        assert result["data_source"] == "agent_feedbacks"
        # db=None 应触发查询异常降级（best-effort，不阻断）
        assert "error" in result or "feedback_distribution" in result
    finally:
        await agent.close()


@pytest.mark.asyncio
async def test_finance_recon_agent_enabled_structure(monkeypatch):
    """finance_recon_agent_enabled=True 时返回含 data_source 的结构"""
    from app.agents import finance_recon as fin_mod
    monkeypatch.setattr(fin_mod.settings, "finance_recon_agent_enabled", True)

    agent = FinanceReconAgent()
    try:
        result = await agent.generate_recon_report(db=None, days=30)
        assert result["enabled"] is True
        assert result["data_source"] == "internal_tables"
        # 无 Stripe/广告平台对接诚实标注
        assert "note" in result
    finally:
        await agent.close()


@pytest.mark.asyncio
async def test_orchestrator_briefing_aggregates_sections(monkeypatch):
    """business_ops_orchestrator_enabled=True 时聚合 growth + finance 两个 section"""
    # orchestrator 内局部 get_settings()，monkeypatch 全局 settings 对象
    from app.config import get_settings
    _settings = get_settings()
    monkeypatch.setattr(_settings, "business_ops_orchestrator_enabled", True)

    orch = OrchestratorAgent()
    try:
        result = await orch.generate_daily_briefing(db=None)
        assert result["enabled"] is True
        assert result["briefing_type"] == "daily"
        assert "growth_weekly" in result["sections"]
        assert "finance_recon" in result["sections"]
    finally:
        await orch.close()


# ── /api/admin/daily-briefing 端点鉴权（CLAUDE.md：API 必须校验身份认证）──


@pytest.mark.asyncio
async def test_daily_briefing_endpoint_requires_auth(client: AsyncClient):
    """未授权访问 /api/admin/daily-briefing 应返回 401"""
    resp = await client.get("/api/admin/daily-briefing")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_daily_briefing_endpoint_normal_user_forbidden(client: AsyncClient):
    """普通用户（非管理员）访问应返回 403（require_platform_manage）"""
    resp = await client.post(
        "/api/auth/register",
        json={"phone": "13900000888", "name": "普通用户", "password": "test123456"},
    )
    token = resp.json()["access_token"]
    resp = await client.get(
        "/api/admin/daily-briefing",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
