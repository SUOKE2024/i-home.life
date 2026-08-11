"""Agent 注册完整性测试（v1.13.x 逐项审计修复）

覆盖审计发现的链路断裂修复：
1. harness 注册 22 个 Agent（此前仅 10 个，A2A/IM 群聊对 12 个专用 Agent
   返回「未注册」/规则占位）
2. a2a._resolve_agent_cls 兼容类名（KitchenAgent）与小写注册名（kitchen）
   ——此前 Agent Card 暴露类名，客户端按 Card 传类名一律查不到
3. a2a 任务下发到新注册 Agent 不再报「未注册」
4. chat_service._resolve_agent_class 对 12 个新 Agent 可解析（IM 群聊走真实 Agent）
"""
import pytest
from httpx import AsyncClient

from app.agents.harness import get_harness

# 22 个应注册的 Agent（与 a2a.py REGISTERED_AGENT_NAMES 对齐）
EXPECTED_AGENTS = {
    "orchestrator", "designer", "budget", "procurement", "construction",
    "settlement", "qa_inspector", "concierge", "content_publisher", "admin",
    "kitchen", "bathroom", "mep", "appliance", "furniture", "door_window",
    "files", "products", "identity", "notifications", "takeoff", "ifc_export",
}


def test_harness_registers_all_22_agents():
    """harness 注册表包含全部 22 个 Agent（此前仅 10 个）。"""
    registry = get_harness()._agent_registry
    missing = EXPECTED_AGENTS - set(registry.keys())
    assert not missing, f"未注册 Agent: {missing}"


def test_a2a_resolve_agent_class_name():
    """a2a 解析兼容类名（Agent Card 暴露的命名）。"""
    from app.api.a2a import _resolve_agent_cls

    harness = get_harness()
    assert _resolve_agent_cls(harness, "KitchenAgent") is not None
    assert _resolve_agent_cls(harness, "OrchestratorAgent") is not None
    assert _resolve_agent_cls(harness, "QAInspectorAgent") is not None
    assert _resolve_agent_cls(harness, "IfcExportAgent") is not None


def test_a2a_resolve_lowercase_name():
    """a2a 解析兼容小写注册名。"""
    from app.api.a2a import _resolve_agent_cls

    harness = get_harness()
    assert _resolve_agent_cls(harness, "kitchen") is not None
    assert _resolve_agent_cls(harness, "orchestrator") is not None
    assert _resolve_agent_cls(harness, "qa_inspector") is not None


def test_a2a_resolve_unknown_returns_none():
    """未知 Agent 名返回 None（诚实报未注册）。"""
    from app.api.a2a import _resolve_agent_cls

    harness = get_harness()
    assert _resolve_agent_cls(harness, "NoSuchAgent") is None
    assert _resolve_agent_cls(harness, "") is None


@pytest.mark.asyncio
async def test_a2a_send_task_new_agent_registered(auth_headers: dict, client: AsyncClient):
    """A2A 任务下发到新注册 Agent（类名 KitchenAgent）不再报「未注册」。

    修复前：harness 未注册 kitchen + 类名/小写名不匹配 → 直接返回「Agent 'KitchenAgent' 未注册」。
    修复后：可解析并进入执行（LLM 无 key 走 mock 降级，仍为成功/降级响应而非未注册）。
    """
    resp = await client.post(
        "/api/a2a/tasks/send",
        json={"agent_name": "KitchenAgent", "message": "帮我看看厨房布局"},
        headers=auth_headers,
    )
    assert resp.status_code in (200, 201, 503)
    body = resp.json()
    # 关键断言：不再是「未注册」失败
    assert "未注册" not in str(body.get("error", ""))


def test_chat_service_resolves_new_agents():
    """IM 群聊 Agent 解析：12 个新注册 Agent 不再走规则占位。"""
    from app.services.chat_service import _resolve_agent_class

    assert _resolve_agent_class("kitchen") is not None
    assert _resolve_agent_class("ifc_export") is not None
    assert _resolve_agent_class("identity") is not None
    # 未知 Agent 仍返回 None（诚实降级占位）
    assert _resolve_agent_class("no_such_agent") is None
