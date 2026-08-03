"""意图成本路由测试（v1.4.x，借鉴 EY token strategy + 端侧分层）

覆盖:
- _resolve_chain: standard 默认链 / economy 低成本优先 + 原主兜底 / 开关关闭回退
- _record_tier_usage: llm_tier_usage_total 指标记录不抛异常
- 经济档 agent 类标记：concierge/files/identity/notifications/admin
- 工具执行写 AGENT_ACTION 审计（QM 的"可还原"）
"""

import pytest
from httpx import AsyncClient

from app.config import get_settings
from app.agents.base import BaseAgent, DEFAULT_FALLBACK_CHAIN
from app.agents.concierge import ConciergeAgent
from app.agents.files_agent import FilesAgent
from app.agents.identity_agent import IdentityAgent
from app.agents.notifications_agent import NotificationsAgent
from app.agents.admin import AdminAgent


class _DummyAgent(BaseAgent):
    agent_name = "dummy"
    provider = "deepseek"


def _set_routing(monkeypatch, enabled: bool):
    settings = get_settings()
    monkeypatch.setattr(settings, "llm_fallback_enabled", True)
    monkeypatch.setattr(settings, "cost_tiered_routing_enabled", enabled)
    monkeypatch.setattr(settings, "economy_providers", "qwen,glm")
    return settings


def test_standard_chain_keeps_default_behavior(monkeypatch):
    """standard 档：主供应商 + fallback chain，与 v1.1.28 一致"""
    _set_routing(monkeypatch, enabled=False)
    agent = _DummyAgent()  # cost_tier = "standard"
    chain = agent._resolve_chain()
    assert chain[0] == "deepseek"
    assert set(chain) == {"deepseek"} | set(DEFAULT_FALLBACK_CHAIN)
    assert chain.count("deepseek") == 1


def test_economy_chain_prefers_low_cost_providers(monkeypatch):
    """economy 档 + 开关开启：qwen/glm 优先，原主供应商 deepseek 保留兜底"""
    _set_routing(monkeypatch, enabled=True)
    agent = _DummyAgent()
    agent.cost_tier = "economy"
    chain = agent._resolve_chain()
    assert chain[0] == "qwen"
    assert chain[1] == "glm"
    # 低成本供应商必须排在原主供应商之前（deepseek 退居兜底位）
    assert chain.index("deepseek") > chain.index("glm")
    assert "deepseek" in chain
    # 无重复
    assert len(chain) == len(set(chain))


def test_economy_chain_off_flag_keeps_standard(monkeypatch):
    """economy 档但路由开关关闭：回退 standard 行为（主供应商优先）"""
    _set_routing(monkeypatch, enabled=False)
    agent = _DummyAgent()
    agent.cost_tier = "economy"
    chain = agent._resolve_chain()
    assert chain[0] == "deepseek"


def test_economy_agent_classes_marked():
    """低价值 agent 类应标记 cost_tier=economy，BaseAgent 默认 standard"""
    assert BaseAgent.cost_tier == "standard"
    assert ConciergeAgent.cost_tier == "economy"
    assert FilesAgent.cost_tier == "economy"
    assert IdentityAgent.cost_tier == "economy"
    assert NotificationsAgent.cost_tier == "economy"
    assert AdminAgent.cost_tier == "economy"


def test_record_tier_usage_metric_no_raise():
    """成本档位指标记录应可调用且不抛异常"""
    BaseAgent._record_tier_usage("economy", "dummy", "qwen", "success")
    BaseAgent._record_tier_usage("standard", "dummy", "deepseek", "success")
    BaseAgent._record_tier_usage("economy", "dummy", "qwen", "mock")
    from app.metrics import llm_tier_usage_total  # noqa: F401 仅验证导入


@pytest.mark.asyncio
async def test_tool_execute_writes_agent_action_audit(db_session):
    """工具执行应写入 AGENT_ACTION 审计（best-effort，失败不阻断）"""
    from sqlalchemy import select
    from app.models.audit_log import AuditLog
    from app.services.agent_tool_registry import tool_registry

    result = await tool_registry.execute(
        "search_materials", {"category": "瓷砖"},
        _db=db_session, _project_id="p1", _user_id="u1",
    )
    assert "results" in result
    rows = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "AGENT_ACTION")
        )
    ).scalars().all()
    assert any(a.resource_type == "tool:search_materials" for a in rows)


@pytest.mark.asyncio
async def test_chat_concierge_economy_mock(client: AsyncClient):
    """economy 档 concierge chat 在 mock 模式（无 key）下应正常响应"""
    resp = await client.post(
        "/api/auth/register",
        json={"phone": "13900006009", "name": "成本路由", "password": "test123456"},
    )
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    resp = await client.post(
        "/api/agents/chat",
        json={"message": "你们有售后服务吗", "agent_type": "concierge"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "reply" in resp.json()


@pytest.mark.asyncio
async def test_economy_local_unconfigured_falls_back(monkeypatch):
    """local 端点未配置 key 时应被跳过并 fallback（不 mock、不抛异常）"""
    settings = get_settings()
    monkeypatch.setattr(settings, "llm_fallback_enabled", True)
    monkeypatch.setattr(settings, "cost_tiered_routing_enabled", True)
    monkeypatch.setattr(settings, "economy_providers", "local,qwen")
    monkeypatch.setattr(settings, "local_llm_api_key", "")

    agent = _DummyAgent()
    agent.cost_tier = "economy"
    # 无任何 API key（mock 环境）：local 不可用 → fallback 到 qwen/glm/deepseek，
    # 最终返回 mock 响应而非异常
    reply = await agent._chat([{"role": "user", "content": "你好"}])
    assert isinstance(reply, str)
    assert "[mock]" in reply
