"""成本与延迟优化测试（v1.12.x）

覆盖：
- LLM 响应缓存：相同 messages 二次调用命中缓存（不重复调用 LLM）
- with_tools=True 不缓存（工具调用有副作用）
- flag 关闭 → 直通 LLM 不缓存
- Orchestrator cost_tier=economy（意图分类走低成本档）
- cost_tiered_routing_enabled 默认开启 + economy 供应商链优先

测试隔离：monkeypatch.setattr(get_settings(), "flag", value)，teardown 自动还原
"""
from app.agents.base import BaseAgent
from app.agents.orchestrator import OrchestratorAgent
from app.config import get_settings


class _EchoAgent(BaseAgent):
    """无 tools 的测试 Agent，仅记录 _chat_single_provider 调用次数"""

    agent_name = "echo"

    def __init__(self):
        super().__init__()
        self.calls = 0

    async def _chat_single_provider(self, provider, messages, max_retries=0, with_tools=False):
        self.calls += 1
        return f"reply-{self.calls}"


_MESSAGES = [
    {"role": "system", "content": "你是测试 Agent"},
    {"role": "user", "content": "相同的确定性问题"},
]


async def test_llm_response_cache_hit(monkeypatch):
    """相同 messages 第二次调用命中缓存，不重复调用 LLM"""
    monkeypatch.setattr(get_settings(), "llm_response_cache_enabled", True)
    monkeypatch.setattr(get_settings(), "llm_response_cache_ttl", 600)
    agent = _EchoAgent()
    try:
        first = await agent._chat(_MESSAGES)
        second = await agent._chat(_MESSAGES)
    finally:
        await agent.close()
    assert first == "reply-1"
    assert second == "reply-1"  # 缓存命中 → 仍是第一次的回复
    assert agent.calls == 1  # 只调用了一次 LLM


async def test_llm_response_cache_disabled(monkeypatch):
    """flag 关闭 → 直通 LLM，每次重新调用"""
    monkeypatch.setattr(get_settings(), "llm_response_cache_enabled", False)
    agent = _EchoAgent()
    try:
        await agent._chat(_MESSAGES)
        await agent._chat(_MESSAGES)
    finally:
        await agent.close()
    assert agent.calls == 2


async def test_llm_tools_call_not_cached(monkeypatch):
    """with_tools=True → 不缓存（工具调用有副作用）"""
    monkeypatch.setattr(get_settings(), "llm_response_cache_enabled", True)
    monkeypatch.setattr(get_settings(), "llm_response_cache_ttl", 600)
    agent = _EchoAgent()
    agent.tools = [{"type": "function", "function": {"name": "f", "parameters": {}}}]
    try:
        await agent._chat(_MESSAGES, with_tools=True)
        await agent._chat(_MESSAGES, with_tools=True)
    finally:
        await agent.close()
    assert agent.calls == 2  # 工具模式两次都真实调用


async def test_llm_cache_key_differs_by_content(monkeypatch):
    """不同消息 → 不同缓存 key（互不污染）"""
    monkeypatch.setattr(get_settings(), "llm_response_cache_enabled", True)
    monkeypatch.setattr(get_settings(), "llm_response_cache_ttl", 600)
    agent = _EchoAgent()
    try:
        other = [{"role": "user", "content": "另一个不同的问题"}]
        k1 = agent._build_llm_cache_key(_MESSAGES)
        k2 = agent._build_llm_cache_key(other)
    finally:
        await agent.close()
    assert k1 and k2 and k1 != k2


def test_orchestrator_economy_tier():
    """Orchestrator 意图分类走 economy 档（低成本优先）"""
    assert OrchestratorAgent.cost_tier == "economy"


def test_cost_tiered_routing_enabled_by_default():
    assert get_settings().cost_tiered_routing_enabled is True


def test_economy_chain_prioritizes_cheap_providers(monkeypatch):
    """economy 档：qwen/glm 优先，主供应商兜底"""
    monkeypatch.setattr(get_settings(), "cost_tiered_routing_enabled", True)
    monkeypatch.setattr(get_settings(), "llm_fallback_enabled", True)
    agent = _EchoAgent()
    agent.cost_tier = "economy"
    chain = agent._resolve_chain()
    # 无 httpx 客户端需要清理，无需 await close()
    # qwen/glm（economy 列表）应排在前，deepseek（主供应商）兜底
    assert chain[0] == "qwen"
    assert chain[1] == "glm"
    assert "deepseek" in chain
