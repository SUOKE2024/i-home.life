"""真实后端 SSE 烟雾测试 — /api/agents/chat/stream

闭环验证 Web 控制台 streamChat → 后端 SSE 链路（批次 1-7 仅 mock 前端，
本文件首次对真实后端 SSE 生成代码做端到端验证）。

覆盖：
- 未认证 401
- 真实认证 + 真实 DB 会话持久化 + 真实 SSE 事件序列（meta → token* → done）
- token 事件拼装为完整回复、session_id 跨 meta/done 一致
- 项目归属校验：他人项目 → 403

测试约定（对齐 tests/conftest.py）：
- DEEPSEEK_API_KEY="" 强制 mock 模式，避免真实 LLM 60-90s 超时
- 选用 "你好,今天天气怎么样" 命中 fallback_classify → intent="general"
  → 走 else 分支 canned reply（无 LLM、无 stream_agent），确定性假流式
- httpx AsyncClient + ASGITransport 直驱 FastAPI app（真实端点代码执行）
"""
import json
import uuid

import pytest
from httpx import AsyncClient


def _parse_sse(body: str) -> list[dict]:
    """解析 SSE 响应体为事件列表。

    格式：data: {json}\n\n（对齐 api-client.ts parseSseEvent）
    """
    events: list[dict] = []
    for block in body.split("\n\n"):
        block = block.strip()
        if not block.startswith("data:"):
            continue
        payload = block[len("data:"):].strip()
        if not payload:
            continue
        try:
            events.append(json.loads(payload))
        except json.JSONDecodeError:
            continue
    return events


@pytest.mark.asyncio
async def test_chat_stream_unauthorized(client: AsyncClient):
    """未认证用户无法发起 SSE 聊天"""
    resp = await client.post(
        "/api/agents/chat/stream",
        json={"message": "你好"},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_chat_stream_sse_smoke(auth_headers: dict, client: AsyncClient):
    """真实后端 SSE 烟雾：meta → token → done 事件序列 + session 一致性

    这是对 Web 控制台 streamChat 链路（console-src/src/services/api-client.ts:streamChat
    → app/api/agents.py:chat_stream → generate_sse）首次接入真实后端的端到端验证。
    """
    resp = await client.post(
        "/api/agents/chat/stream",
        json={
            "message": "你好,今天天气怎么样",
            "agent_type": "orchestrator",  # 默认走 classify_intent → general
            "project_id": None,
            "history": [],
            "stream": True,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, f"SSE 请求失败: {resp.status_code} {resp.text[:200]}"
    assert "text/event-stream" in resp.headers.get("content-type", "")

    events = _parse_sse(resp.text)
    assert len(events) >= 4, f"事件数不足: {events}"

    # 真实事件序（对齐 app/api/agents.py:generate_sse）：
    #   thinking_step(意图分类) → thinking_step(Agent 调度) → meta → token* → done
    event_types = [e.get("event") for e in events]

    # 1) 思考步骤事件在前（v1.1.29 thinking_step，前端 SseEventType 已支持）
    assert event_types[0] == "thinking_step", f"首事件应为 thinking_step，实际: {event_types[0]}"
    assert event_types.count("thinking_step") >= 1

    # 2) meta 事件（在 thinking_step 之后），含 session_id 与 agent_type
    meta_idx = event_types.index("meta")
    assert meta_idx > 0, "meta 应在 thinking_step 之后"
    meta = events[meta_idx]
    assert meta.get("session_id"), "meta 缺少 session_id"
    assert meta.get("agent_type"), "meta 缺少 agent_type"

    # 3) token 事件（在 meta 之后），拼装为完整回复
    token_events = [e for e in events if e.get("event") == "token"]
    assert len(token_events) > 0, "无 token 事件"
    full_reply = "".join(e.get("content", "") for e in token_events)
    assert full_reply, "token 拼装为空"
    # general 意图 canned reply 前缀（对齐 app/api/agents.py:1114）
    assert "我理解您的问题是关于" in full_reply, f"回复内容异常: {full_reply[:80]}"

    # 4) done 末事件，session_id 与 meta 一致（验证会话持久化回写）
    done = events[-1]
    assert done.get("event") == "done", f"末事件应为 done，实际: {done.get('event')}"
    assert done.get("session_id") == meta["session_id"], "done 与 meta 的 session_id 不一致"


@pytest.mark.asyncio
async def test_chat_stream_session_continuity(auth_headers: dict, client: AsyncClient):
    """同一 session_id 续聊：第二轮 done.session_id 与首轮一致

    验证 app/api/agents.py:902 get_or_create_session 的复用语义
    （传入已有 session_id 应继续同一会话而非新建）。
    """
    # 第一轮
    resp1 = await client.post(
        "/api/agents/chat/stream",
        json={"message": "你好,今天天气怎么样", "agent_type": "orchestrator"},
        headers=auth_headers,
    )
    assert resp1.status_code == 200
    events1 = _parse_sse(resp1.text)
    session_id = events1[-1].get("session_id")
    assert session_id, "首轮未返回 session_id"

    # 第二轮带同一 session_id
    resp2 = await client.post(
        "/api/agents/chat/stream",
        json={
            "message": "讲个笑话吧",
            "agent_type": "orchestrator",
            "session_id": session_id,
        },
        headers=auth_headers,
    )
    assert resp2.status_code == 200
    events2 = _parse_sse(resp2.text)
    done2 = events2[-1]
    assert done2.get("event") == "done"
    assert done2.get("session_id") == session_id, "续聊应复用同一 session_id"


@pytest.mark.asyncio
async def test_chat_stream_project_ownership_denied(auth_headers: dict, client: AsyncClient):
    """项目归属校验：他人项目 → 403（对齐 app/api/agents.py:898 越权防护）"""
    # 用户 A 创建项目
    create = await client.post(
        "/api/projects",
        json={"name": "SSE归属测试项目", "total_area": 90.0},
        headers=auth_headers,
    )
    assert create.status_code == 201
    project_id_a = create.json()["id"]

    # 用户 B 注册
    reg = await client.post(
        "/api/auth/register",
        json={
            "phone": f"139{str(uuid.uuid4().int)[:8]}",
            "name": "他人",
            "password": "test123456",
        },
    )
    assert reg.status_code == 201
    headers_b = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    # 用户 B 用 A 的 project_id 发起 SSE → 403（项目归属校验在流开启前）
    resp = await client.post(
        "/api/agents/chat/stream",
        json={"message": "你好", "project_id": project_id_a},
        headers=headers_b,
    )
    assert resp.status_code == 403, f"越权访问应被拒: {resp.status_code}"


@pytest.mark.asyncio
async def test_chat_stream_agent_error_emits_error_event(
    auth_headers: dict, client: AsyncClient, monkeypatch: pytest.MonkeyPatch,
):
    """v1.3.1 修复：流式 Agent 中途异常 → 诚实送达 error 事件而非静默断开。

    回归背景：此前真流式分支（app/api/agents.py think_stream）无 except，
    异常会穿透生成器导致 SSE 无 done/error 直接断开；前端 for-await 自然结束
    时 isLoading 永不复位（输入栏禁用 + typing 常驻）。本测试锁住
    "异常仍要送达 error 事件 + 流以 done 收尾" 的契约。
    """
    from app.api import agents as agents_api

    async def boom(self, message, user_ctx):  # noqa: ANN001
        yield "橱柜建议"
        raise RuntimeError("模拟 LLM 超时")

    monkeypatch.setattr(agents_api.KitchenAgent, "think_stream", boom)

    # "厨房橱柜布局黄金三角" 仅命中 kitchen 关键词（fallback_classify 规则，
    # 避免 design 关键词并列导致路由到 DesignerAgent 假流式分支）
    resp = await client.post(
        "/api/agents/chat/stream",
        json={"message": "厨房橱柜布局黄金三角", "agent_type": "orchestrator"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, f"SSE 请求失败: {resp.status_code} {resp.text[:200]}"

    events = _parse_sse(resp.text)
    types = [e.get("event") for e in events]
    assert "error" in types, f"应送达 error 事件: {types}"

    error_event = next(e for e in events if e.get("event") == "error")
    assert "生成回复失败" in error_event.get("content", ""), error_event
    assert error_event.get("agent_type") == "kitchen", error_event

    # 流仍以 done 收尾且 session_id 一致（会话持久化不受异常影响）
    done = events[-1]
    assert done.get("event") == "done", f"末事件应为 done: {types}"
    meta = next(e for e in events if e.get("event") == "meta")
    assert done.get("session_id") == meta["session_id"], "done 与 meta 的 session_id 不一致"
