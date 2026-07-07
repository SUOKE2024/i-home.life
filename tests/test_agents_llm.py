"""AI Agent LLM/Mock 路径与 Orchestrator 路由测试

覆盖:
- OrchestratorAgent.fallback_classify 各意图
- DesignerAgent.generate_layouts 三种面积预设
- DesignerAgent.detect_modification_intent 添加/删除/移动
- /agents/chat 各意图分支(mock 模式,不依赖 LLM API)
- mock 模式不会因缺 API Key 而崩溃
"""

import pytest
from httpx import AsyncClient

from app.agents.orchestrator import OrchestratorAgent
from app.agents.designer import DesignerAgent


async def _register(client: AsyncClient, phone: str = "13900005001") -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "Agent测试用户", "password": "test123456"},
    )
    return resp.json()["access_token"]


# === OrchestratorAgent.fallback_classify 单元测试 ===


def test_fallback_classify_design():
    r = OrchestratorAgent.fallback_classify("帮我设计一个三室两厅的户型")
    assert r["intent"] == "design"


def test_fallback_classify_budget():
    r = OrchestratorAgent.fallback_classify("126平米装修预算多少钱")
    assert r["intent"] == "budget"


def test_fallback_classify_procurement():
    r = OrchestratorAgent.fallback_classify("我要采购瓷砖和地板")
    assert r["intent"] == "procurement"


def test_fallback_classify_construction():
    r = OrchestratorAgent.fallback_classify("施工进度怎么样了,什么时候验收")
    assert r["intent"] == "construction"


def test_fallback_classify_general():
    r = OrchestratorAgent.fallback_classify("你好,今天天气怎么样")
    assert r["intent"] == "general"


# === DesignerAgent.generate_layouts 单元测试 ===


@pytest.mark.asyncio
async def test_designer_layouts_126():
    agent = DesignerAgent()
    try:
        r = await agent.generate_layouts("126㎡ 三室两厅")
        assert "plans" in r
        assert len(r["plans"]) == 3
        assert "recommendation" in r
        assert "materials" in r
        assert len(r["materials"]) >= 2
        # 每套方案应有房间列表
        for plan in r["plans"]:
            assert "rooms" in plan
            assert len(plan["rooms"]) >= 5
            assert "total_area" in plan
    finally:
        await agent.close()


@pytest.mark.asyncio
async def test_designer_layouts_90():
    agent = DesignerAgent()
    try:
        r = await agent.generate_layouts("90㎡ 小户型")
        assert len(r["plans"]) == 3
        for plan in r["plans"]:
            assert len(plan["rooms"]) >= 5
    finally:
        await agent.close()


@pytest.mark.asyncio
async def test_designer_layouts_160():
    agent = DesignerAgent()
    try:
        r = await agent.generate_layouts("160㎡ 大平层")
        assert len(r["plans"]) == 3
        # 160 ㎡ 应有更多房间
        for plan in r["plans"]:
            assert len(plan["rooms"]) >= 7
    finally:
        await agent.close()


# === DesignerAgent.detect_modification_intent ===


def test_modification_add_room():
    actions = DesignerAgent.detect_modification_intent("加一个 3×4 的书房")
    assert len(actions) == 1
    a = actions[0]
    assert a["action"] == "add_room"
    assert a["name"] == "书房"
    assert a["roomType"] == "study"
    assert a["w"] == 3.0
    assert a["h"] == 4.0


def test_modification_add_room_default_size():
    actions = DesignerAgent.detect_modification_intent("添加一个卧室")
    assert len(actions) == 1
    a = actions[0]
    assert a["action"] == "add_room"
    assert a["name"] == "卧室"
    # 无尺寸时使用默认值
    assert a["w"] > 0 and a["h"] > 0


def test_modification_delete_room():
    actions = DesignerAgent.detect_modification_intent("删除客厅")
    assert len(actions) == 1
    assert actions[0]["action"] == "delete_room"
    assert actions[0]["oldName"] == "客厅"


def test_modification_move_room():
    actions = DesignerAgent.detect_modification_intent("把客厅向右移动 1.5 米")
    assert len(actions) == 1
    a = actions[0]
    assert a["action"] == "move_room"
    assert a["name"] == "客厅"
    assert a["dx"] == 1.5


def test_modification_no_action():
    actions = DesignerAgent.detect_modification_intent("今天天气真好")
    assert len(actions) == 0


# === /agents/chat 路由集成测试(mock 模式) ===


@pytest.fixture(autouse=False)
def force_mock_mode(monkeypatch):
    """强制启用 mock 模式,避免依赖 .env 中真实 API Key"""
    monkeypatch.setattr("app.api.agents.MOCK_MODE", True)


@pytest.mark.asyncio
async def test_chat_design_intent_mock(client: AsyncClient, force_mock_mode):
    """设计意图在 mock 模式下应走 generate_layouts 而非 LLM"""
    token = await _register(client, "13900005010")
    resp = await client.post(
        "/api/agents/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "帮我设计 126㎡ 三室两厅 户型", "agent_type": "orchestrator"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_type"] == "designer"
    assert "126" in data["reply"] or "方案" in data["reply"]
    assert len(data["suggestions"]) >= 1


@pytest.mark.asyncio
async def test_chat_budget_intent_mock(client: AsyncClient, force_mock_mode):
    token = await _register(client, "13900005011")
    resp = await client.post(
        "/api/agents/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "126平米装修预算多少", "agent_type": "orchestrator"},
    )
    assert resp.status_code == 200
    assert resp.json()["agent_type"] == "budget"


@pytest.mark.asyncio
async def test_chat_procurement_intent_mock(client: AsyncClient, force_mock_mode):
    token = await _register(client, "13900005012")
    resp = await client.post(
        "/api/agents/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "采购瓷砖和地板材料", "agent_type": "orchestrator"},
    )
    assert resp.status_code == 200
    assert resp.json()["agent_type"] == "procurement"


@pytest.mark.asyncio
async def test_chat_construction_intent_mock(client: AsyncClient, force_mock_mode):
    token = await _register(client, "13900005013")
    resp = await client.post(
        "/api/agents/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "施工进度和验收时间", "agent_type": "orchestrator"},
    )
    assert resp.status_code == 200
    assert resp.json()["agent_type"] == "construction"


@pytest.mark.asyncio
async def test_chat_general_intent_mock(client: AsyncClient, force_mock_mode):
    token = await _register(client, "13900005014")
    resp = await client.post(
        "/api/agents/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "你好,你能做什么", "agent_type": "orchestrator"},
    )
    assert resp.status_code == 200
    assert resp.json()["agent_type"] == "orchestrator"


@pytest.mark.asyncio
async def test_chat_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/api/agents/chat",
        json={"message": "测试"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_chat_empty_message_rejected(client: AsyncClient):
    token = await _register(client, "13900005015")
    resp = await client.post(
        "/api/agents/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": ""},
    )
    assert resp.status_code == 422


# === /agents/design 端点 ===


@pytest.mark.asyncio
async def test_design_with_room_info(client: AsyncClient):
    token = await _register(client, "13900005016")
    resp = await client.post(
        "/api/agents/design",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "三室两厅", "room_info": "客厅35,主卧20,次卧15,书房10,厨房10,卫生间6"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["space_planning"]) > 10
    assert len(data["material_plan"]) > 10


@pytest.mark.asyncio
async def test_design_160_area(client: AsyncClient):
    token = await _register(client, "13900005017")
    resp = await client.post(
        "/api/agents/design",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "160㎡ 大平层"},
    )
    assert resp.status_code == 200
    assert "160" in resp.json()["space_planning"] or "160" in resp.json()["full_reply"]


# === mock 模式健壮性 ===


@pytest.mark.asyncio
async def test_mock_mode_no_llm_call_for_chat(client: AsyncClient, force_mock_mode):
    """mock 模式下 /agents/chat 设计意图不应触发 LLM,应在 1s 内返回"""
    import time
    token = await _register(client, "13900005018")
    t0 = time.time()
    resp = await client.post(
        "/api/agents/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "设计 126㎡ 户型"},
    )
    elapsed = time.time() - t0
    assert resp.status_code == 200
    # mock 模式不应超过 2s(避免 LLM 超时)
    assert elapsed < 2.0, f"mock 模式响应过慢: {elapsed:.2f}s"
