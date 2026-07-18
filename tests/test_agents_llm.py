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
from app.api.agents import _extract_reply_from_llm_json, _looks_like_reasoning_leak


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
async def test_chat_explicit_agent_type_skips_classify(client: AsyncClient, force_mock_mode):
    """显式指定 agent_type 时应直接路由到该 Agent，跳过 OrchestratorAgent.classify_intent

    验证 AGENT_TYPE_TO_INTENT 映射：发送 general 消息但指定 agent_type=budget，
    响应的 agent_type 应为 budget（而非 general/orchestrator）。
    """
    token = await _register(client, "13900005030")
    resp = await client.post(
        "/api/agents/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "你好", "agent_type": "budget"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_type"] == "budget", (
        f"显式 agent_type=budget 应直接路由到 budget Agent，"
        f"实际: {data['agent_type']}"
    )


@pytest.mark.asyncio
async def test_chat_explicit_agent_type_designer(client: AsyncClient, force_mock_mode):
    """显式 agent_type=designer 应路由到 designer Agent（mock 模式下走 generate_layouts）"""
    token = await _register(client, "13900005031")
    resp = await client.post(
        "/api/agents/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "你好", "agent_type": "designer"},
    )
    assert resp.status_code == 200
    assert resp.json()["agent_type"] == "designer"


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


# === /agents/chat/stream SSE 契约测试 ===


@pytest.mark.asyncio
async def test_chat_stream_sse_contract(client: AsyncClient, force_mock_mode):
    """验证 SSE 流式响应的事件字段契约为 `event`（Flutter sse_service.dart 依赖）

    Flutter 客户端 sse_service.dart 通过 `data['event']` 字段判断事件类型，
    后端必须使用 `event` 字段（而非 `type`）以保持契约一致。
    本测试用主代理身份锁定该契约，防止回归。
    """
    import json as _json

    token = await _register(client, "13900005019")
    resp = await client.post(
        "/api/agents/chat/stream",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "126平米装修预算多少", "agent_type": "orchestrator"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    body = resp.text
    assert body, "SSE 响应体不应为空"

    # 解析所有 data: 行
    events = []
    for line in body.split("\n"):
        if line.startswith("data: "):
            payload = line[6:].strip()
            if not payload:
                continue
            try:
                events.append(_json.loads(payload))
            except _json.JSONDecodeError:
                pass

    assert len(events) >= 2, f"应至少收到 meta + done 事件，实际收到 {len(events)} 个"

    # 第一个事件应为 meta，且必须用 `event` 字段（不是 `type`）
    meta_events = [e for e in events if e.get("event") == "meta"]
    assert len(meta_events) >= 1, (
        f"未找到 meta 事件 — 后端可能误用 `type` 字段而非 `event`，"
        f"将破坏 Flutter/Web SSE 客户端契约。所有事件: {events[:3]}"
    )
    assert "agent_type" in meta_events[0], "meta 事件必须包含 agent_type"
    assert meta_events[0]["agent_type"] in (
        "designer", "budget", "procurement", "construction",
        "settlement", "qa_inspector", "concierge", "orchestrator",
        "content_publisher", "admin",
    ), f"未预期的 agent_type 值: {meta_events[0]['agent_type']}"

    # 必须有 token 事件（携带 content 字段）
    token_events = [e for e in events if e.get("event") == "token"]
    assert len(token_events) >= 1, "未找到 token 事件"
    assert all("content" in e for e in token_events), "token 事件必须包含 content 字段"

    # 必须有 done 结束事件
    done_events = [e for e in events if e.get("event") == "done"]
    assert len(done_events) >= 1, "未找到 done 结束事件"


@pytest.mark.asyncio
async def test_chat_stream_requires_auth(client: AsyncClient):
    """/agents/chat/stream 必须认证"""
    resp = await client.post(
        "/api/agents/chat/stream",
        json={"message": "测试"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_chat_stream_project_not_owned(client: AsyncClient, force_mock_mode):
    """带他人 project_id 调用 /agents/chat/stream 应返回 403"""
    token_a = await _register(client, "13900005020")
    proj_resp = await client.post(
        "/api/projects",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"name": "Stream项目A", "address": "地址A"},
    )
    project_id_a = proj_resp.json()["id"]

    token_b = await _register(client, "13900005021")
    resp = await client.post(
        "/api/agents/chat/stream",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"message": "你好", "project_id": project_id_a},
    )
    assert resp.status_code == 403


# === _extract_reply_from_llm_json 单元测试 ===


def test_extract_reply_from_json_with_codeblock():
    """LLM 输出 ```json ... ``` 包裹的 JSON，应提取 reply 字段"""
    raw = '```json\n{"plans": [{"name": "方案A"}], "reply": "已为您生成1套方案"}\n```'
    assert _extract_reply_from_llm_json(raw) == "已为您生成1套方案"


def test_extract_reply_from_plain_json():
    """LLM 输出纯 JSON（无代码块包裹），应提取 reply 字段"""
    raw = '{"plans": [{"name": "A"}], "recommendation": "推荐A", "reply": "完成"}'
    assert _extract_reply_from_llm_json(raw) == "完成"


def test_extract_reply_json_without_reply_field():
    """JSON 有效但无 reply 字段，应返回含 plans 数量的摘要"""
    raw = '```json\n{"plans": [{"name": "A"}, {"name": "B"}], "recommendation": "推荐B"}\n```'
    result = _extract_reply_from_llm_json(raw)
    assert "2" in result
    assert "推荐B" in result


def test_extract_reply_from_natural_language():
    """LLM 输出自然语言（非 JSON），应原样返回"""
    raw = "已为您生成3套方案，请查看对比。"
    assert _extract_reply_from_llm_json(raw) == raw


def test_extract_reply_empty_input():
    """空字符串输入应原样返回"""
    assert _extract_reply_from_llm_json("") == ""
    assert _extract_reply_from_llm_json(None) is None


def test_extract_reply_truncated_json():
    """LLM 输出被截断的 JSON（解析失败），应原样返回避免崩溃"""
    raw = '```json\n{"plans": [{"name": "方案A", "rooms": ['
    assert _extract_reply_from_llm_json(raw) == raw


# === _looks_like_reasoning_leak 单元测试 (v1.0.17 修复) ===


def test_reasoning_leak_detected_first_person_start():
    """思维链开头（"我们需要理解..."）应被识别为泄漏"""
    text = "我们需要理解用户需求：126平米三室两厅方案。应该生成3套不同方案。"
    assert _looks_like_reasoning_leak(text) is True


def test_reasoning_leak_detected_me_start():
    """"让我" 开头应被识别为泄漏"""
    text = "让我分析一下用户的需求，首先应该输出JSON格式，包含plans数组"
    assert _looks_like_reasoning_leak(text) is True


def test_reasoning_leak_detected_keyword_density():
    """前 200 字含 2+ 个元描述关键词应识别为泄漏"""
    text = "根据输出格式要求，应该输出JSON格式，包含plans和reply字段。接下来我开始生成方案..."
    assert _looks_like_reasoning_leak(text) is True


def test_reasoning_leak_not_detected_normal_reply():
    """正常友好回复不应被误判为泄漏"""
    text = "已为您生成3套126㎡北欧风格设计方案，请查看对比，点击可查看详细布局与材料清单。"
    assert _looks_like_reasoning_leak(text) is False


def test_reasoning_leak_not_detected_short_text():
    """短文本（<10 字符）不应被误判"""
    assert _looks_like_reasoning_leak("好的") is False
    assert _looks_like_reasoning_leak("") is False
    assert _looks_like_reasoning_leak(None) is False


def test_reasoning_leak_not_detected_normal_budget_reply():
    """预算 Agent 的正常回复不应被误判"""
    text = "126 平米装修预算按舒适型约 18-25 万元，包含硬装、定制柜体、软装和管理费。"
    assert _looks_like_reasoning_leak(text) is False


def test_reasoning_leak_not_detected_markdown_reply():
    """Markdown 格式的正常回复不应被误判"""
    text = "## 预算明细\n\n| 项目 | 金额 |\n|------|------|\n| 硬装 | 9-11万 |\n\n建议每阶段验收合格后再付款。"
    assert _looks_like_reasoning_leak(text) is False


# === DesignerAgent fallback 集成测试 (v1.0.17 修复) ===


@pytest.mark.asyncio
async def test_chat_designer_fallback_on_timeout(client: AsyncClient, monkeypatch):
    """LLM 返回"稍后重试"友好错误时，design 分支应 fallback 到 generate_layouts

    验证 base.py 的"AI 推理超时"友好错误消息也会触发 fallback，
    用户始终收到"已为您生成N套方案"而非"稍后重试"。
    """
    # 确保 MOCK_MODE=False（让代码走 think() 路径）
    monkeypatch.setattr("app.api.agents.MOCK_MODE", False)

    # Mock DesignerAgent.think 返回 base.py 的友好错误消息
    async def _mock_think(self, message, context=""):
        return "抱歉，AI 推理超时，请稍后重试或简化您的问题。(finish_reason=length)"

    monkeypatch.setattr(DesignerAgent, "think", _mock_think)

    token = await _register(client, "13900005040")
    resp = await client.post(
        "/api/agents/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "设计126平米户型", "agent_type": "designer"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_type"] == "designer"
    # 不应包含"稍后重试"（应 fallback 到 generate_layouts）
    assert "稍后重试" not in data["reply"], (
        f"LLM 超时时应 fallback 到 generate_layouts，实际返回: {data['reply'][:100]}"
    )
    # 应返回预设布局方案的 reply
    assert "已为您生成" in data["reply"] or "方案" in data["reply"]


@pytest.mark.asyncio
async def test_chat_designer_fallback_on_reasoning_leak(client: AsyncClient, monkeypatch):
    """LLM 返回 reasoning_content（思维链）时，应 fallback 到 generate_layouts"""
    monkeypatch.setattr("app.api.agents.MOCK_MODE", False)

    async def _mock_think(self, message, context=""):
        return "我们需要理解用户需求：126平米三室两厅方案。应该生成3套不同方案。需要输出JSON格式。"

    monkeypatch.setattr(DesignerAgent, "think", _mock_think)

    token = await _register(client, "13900005041")
    resp = await client.post(
        "/api/agents/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "设计126平米户型", "agent_type": "designer"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # 不应包含思维链文本
    assert "我们需要理解" not in data["reply"], (
        f"reasoning 泄漏时应 fallback，实际返回: {data['reply'][:100]}"
    )
    assert "已为您生成" in data["reply"] or "方案" in data["reply"]


# === BaseAgent._chat content 为空时的 fallback 行为测试 ===
# v1.0.16 引入的 fallback 把 reasoning_content 当作回复返回，导致用户看到 LLM
# 内部思维链。v1.1.1 修复：content 为空时返回友好错误消息，不返回 reasoning_content。


@pytest.mark.asyncio
async def test_chat_empty_content_returns_friendly_error(monkeypatch):
    """LLM 返回 content="" 但 reasoning_content 非空时，应返回友好错误消息

    回归测试：v1.0.16 fallback 逻辑会把 reasoning_content 当作回复返回，
    导致用户看到 "我们需要理解用户需求..." 等内部思维链。
    修复后应返回友好错误消息而非 reasoning_content。
    """
    from app.agents.base import BaseAgent

    class TestAgent(BaseAgent):
        agent_name = "test"
        system_prompt = "test"
        provider = "deepseek"

    agent = TestAgent()
    # 禁用 content 为空重试，直接测试友好错误消息
    agent._EMPTY_CONTENT_RETRIES = 0

    class _MockResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "choices": [{
                    "message": {
                        "content": "",
                        "reasoning_content": "我们需要理解用户需求：126平米三室两厅方案。应该生成3套不同方案。"
                    },
                    "finish_reason": "length"
                }]
            }

    class _MockClient:
        async def post(self, path, json=None):
            return _MockResponse()

    async def _mock_get_client(provider=None):
        return _MockClient()

    monkeypatch.setattr(agent, "_get_client", _mock_get_client)

    try:
        result = await agent._chat([{"role": "user", "content": "test"}])
        # 不应返回 reasoning_content 的内容
        assert "我们需要理解用户需求" not in result, (
            "content 为空时不应返回 reasoning_content（LLM 内部思维链）"
        )
        # 应返回友好错误消息
        assert "稍后重试" in result or "超时" in result, (
            f"应返回友好错误消息，实际返回: {result}"
        )
        # 应包含 finish_reason 信息便于排查
        assert "length" in result, "错误消息应包含 finish_reason 便于排查"
    finally:
        await agent.close()


@pytest.mark.asyncio
async def test_chat_empty_content_retry_then_success(monkeypatch):
    """v1.1.1: content 为空时自动重试，重试后成功返回 content

    场景：首次 content="" + finish_reason="length"（reasoning 占满 token），
    重试时降温到 0.3，第二次返回正常 content。
    """
    from app.agents.base import BaseAgent

    class TestAgent(BaseAgent):
        agent_name = "test"
        system_prompt = "test"
        provider = "deepseek"

    agent = TestAgent()

    call_count = {"n": 0}

    class _MockResponse:
        def __init__(self, content, finish):
            self._content = content
            self._finish = finish

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "choices": [{
                    "message": {
                        "content": self._content,
                        "reasoning_content": "思维链" if not self._content else ""
                    },
                    "finish_reason": self._finish
                }]
            }

    class _MockClient:
        async def post(self, path, json=None):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # 首次：content 为空，finish=length
                return _MockResponse("", "length")
            # 重试：正常 content
            return _MockResponse("已为您生成3套方案", "stop")

    async def _mock_get_client(provider=None):
        return _MockClient()

    monkeypatch.setattr(agent, "_get_client", _mock_get_client)

    try:
        result = await agent._chat([{"role": "user", "content": "test"}])
        assert result == "已为您生成3套方案", f"重试后应返回正常 content，实际: {result}"
        assert call_count["n"] == 2, f"应调用 2 次 LLM（首次 + 重试），实际: {call_count['n']}"
    finally:
        await agent.close()


@pytest.mark.asyncio
async def test_chat_normal_content_not_affected(monkeypatch):
    """LLM 正常返回 content 时，不应被 fallback 逻辑影响"""
    from app.agents.base import BaseAgent

    class TestAgent(BaseAgent):
        agent_name = "test"
        system_prompt = "test"
        provider = "deepseek"

    agent = TestAgent()

    class _MockResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "choices": [{
                    "message": {
                        "content": "已为您生成3套方案",
                        "reasoning_content": "内部思维链"
                    },
                    "finish_reason": "stop"
                }]
            }

    class _MockClient:
        async def post(self, path, json=None):
            return _MockResponse()

    async def _mock_get_client(provider=None):
        return _MockClient()

    monkeypatch.setattr(agent, "_get_client", _mock_get_client)

    try:
        result = await agent._chat([{"role": "user", "content": "test"}])
        assert result == "已为您生成3套方案", f"正常 content 应原样返回，实际: {result}"
    finally:
        await agent.close()
