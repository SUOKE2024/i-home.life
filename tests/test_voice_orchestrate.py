"""语音智能体编排 API 集成测试

覆盖端点:
- POST /api/voice/orchestrate         (语音启动/编排/控制 Agent 任务)
- GET  /api/voice/orchestrate/tasks   (语音任务列表)

覆盖服务:
- app/services/voice_orchestrator.py  (split_multi_intent / parse_task_command / VoiceTaskRegistry)
"""
import asyncio
import time

import pytest
from httpx import AsyncClient

from app.api import voice_orchestrate
from app.services.voice_orchestrator import parse_task_command, split_multi_intent


@pytest.fixture
def orch_enabled(monkeypatch):
    """开启语音编排 feature flag（monkeypatch 自动还原）"""
    monkeypatch.setattr(
        voice_orchestrate.settings, "voice_agent_orchestration_enabled", True
    )


async def _auth_headers(client: AsyncClient, phone: str) -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "语音编排测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _wait_tasks(
    client: AsyncClient, headers: dict, expect_finished: int, timeout: float = 5.0
) -> list[dict]:
    """轮询任务列表直到指定数量任务进入终态"""
    deadline = time.time() + timeout
    tasks: list[dict] = []
    while time.time() < deadline:
        resp = await client.get("/api/voice/orchestrate/tasks", headers=headers)
        assert resp.status_code == 200
        tasks = resp.json()["tasks"]
        finished = sum(
            1 for t in tasks if t["status"] in ("done", "failed", "cancelled")
        )
        if finished >= expect_finished:
            return tasks
        await asyncio.sleep(0.05)
    return tasks


# ── 纯函数单元测试 ──


def test_split_multi_intent():
    assert split_multi_intent("帮我设计客厅") == ["帮我设计客厅"]
    parts = split_multi_intent("帮我设计一个客厅，同时做一份100平的预算")
    assert parts == ["帮我设计一个客厅", "做一份100平的预算"]
    parts = split_multi_intent("查一下施工进度；另外帮我搜一下瓷砖")
    assert parts == ["查一下施工进度", "帮我搜一下瓷砖"]


def test_parse_task_command():
    assert parse_task_command("任务列表") == {"action": "list", "task_ref": None}
    assert parse_task_command("查看任务进度") == {"action": "status", "task_ref": None}
    assert parse_task_command("任务2做得怎么样了") == {"action": "status", "task_ref": "2"}
    assert parse_task_command("取消任务") == {"action": "cancel", "task_ref": None}
    assert parse_task_command("取消第1个任务") == {"action": "cancel", "task_ref": "1"}
    # 业务意图不应被劫持
    assert parse_task_command("查一下施工进度") is None
    assert parse_task_command("帮我设计客厅") is None


# ── 端点测试 ──


@pytest.mark.asyncio
async def test_orchestrate_flag_disabled(client: AsyncClient):
    """feature flag 关闭时返回 503（默认生产安全）"""
    headers = await _auth_headers(client, "13950050001")
    resp = await client.post(
        "/api/voice/orchestrate", json={"text": "帮我设计客厅"}, headers=headers,
    )
    assert resp.status_code == 503
    assert "未启用" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_orchestrate_unauthorized(client: AsyncClient, orch_enabled):
    resp = await client.post(
        "/api/voice/orchestrate", json={"text": "帮我设计客厅"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_launch_single_task(client: AsyncClient, orch_enabled):
    """一句话启动后台 Agent 任务并完成"""
    headers = await _auth_headers(client, "13950050002")
    resp = await client.post(
        "/api/voice/orchestrate",
        json={"text": "帮我设计一个客厅布局"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "launch"
    assert len(data["launched"]) == 1
    assert data["launched"][0]["intent"] == "design"
    assert "任务" in data["reply"]

    tasks = await _wait_tasks(client, headers, expect_finished=1)
    assert tasks[0]["status"] == "done"
    assert tasks[0]["reply"]


@pytest.mark.asyncio
async def test_launch_multi_intent_parallel(client: AsyncClient, orch_enabled):
    """一句话并行编排多个 Agent（连接词切分）"""
    headers = await _auth_headers(client, "13950050003")
    resp = await client.post(
        "/api/voice/orchestrate",
        json={"text": "帮我设计一个客厅，同时做一份100平的预算"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "launch"
    assert len(data["launched"]) == 2
    intents = {t["intent"] for t in data["launched"]}
    assert intents == {"design", "budget"}
    assert "并行" in data["reply"]

    tasks = await _wait_tasks(client, headers, expect_finished=2)
    assert all(t["status"] == "done" for t in tasks)


@pytest.mark.asyncio
async def test_voice_task_status_and_list(client: AsyncClient, orch_enabled):
    """语音查询任务进度 + 任务列表（生命周期控制）"""
    headers = await _auth_headers(client, "13950050004")
    await client.post(
        "/api/voice/orchestrate",
        json={"text": "帮我做一份120平的预算"},
        headers=headers,
    )
    await _wait_tasks(client, headers, expect_finished=1)

    resp = await client.post(
        "/api/voice/orchestrate", json={"text": "任务进度怎么样"}, headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "status"
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["status"] == "done"

    resp = await client.post(
        "/api/voice/orchestrate", json={"text": "任务列表"}, headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "list"
    assert len(data["tasks"]) == 1


@pytest.mark.asyncio
async def test_voice_cancel_running_task(client: AsyncClient, orch_enabled, monkeypatch):
    """语音取消运行中的任务"""

    async def _slow_agent(text, intent, user_name, context="", emotion=None):
        await asyncio.sleep(30)
        return "不应到达"

    monkeypatch.setattr(voice_orchestrate, "_route_voice_to_agent", _slow_agent)

    headers = await _auth_headers(client, "13950050005")
    resp = await client.post(
        "/api/voice/orchestrate",
        json={"text": "帮我设计一个客厅布局"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["launched"][0]["intent"] == "design"

    resp = await client.post(
        "/api/voice/orchestrate", json={"text": "取消任务"}, headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "cancel"
    assert "已取消" in data["reply"]

    tasks = await _wait_tasks(client, headers, expect_finished=1)
    assert tasks[0]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_construction_progress_not_hijacked(client: AsyncClient, orch_enabled):
    """「施工进度」属于业务意图，应启动 construction 任务而非任务控制"""
    headers = await _auth_headers(client, "13950050006")
    resp = await client.post(
        "/api/voice/orchestrate",
        json={"text": "查一下施工进度"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "launch"
    assert data["launched"][0]["intent"] == "construction"


@pytest.mark.asyncio
async def test_orchestrate_project_ownership(client: AsyncClient, orch_enabled):
    """项目归属校验：他⼈项目 403 / 不存在项目 404"""
    headers_a = await _auth_headers(client, "13950050007")
    headers_b = await _auth_headers(client, "13950050008")

    resp = await client.post(
        "/api/projects",
        json={"name": "A 的项目", "total_area": 100.0},
        headers=headers_a,
    )
    project_id = resp.json()["id"]

    resp = await client.post(
        "/api/voice/orchestrate",
        json={"text": "帮我设计客厅", "project_id": project_id},
        headers=headers_b,
    )
    assert resp.status_code == 403

    resp = await client.post(
        "/api/voice/orchestrate",
        json={"text": "帮我设计客厅", "project_id": "nonexistent"},
        headers=headers_a,
    )
    assert resp.status_code == 404


# ── realtime WebSocket 编排钩子（_try_voice_orchestration）──


class _FakeWebSocket:
    """捕获 send_json 负载的假 WebSocket"""

    def __init__(self):
        self.messages: list[dict] = []

    async def send_json(self, payload: dict):
        self.messages.append(payload)


def _make_session(user_id: str):
    from app.services.voice_realtime_service import voice_session_manager

    return voice_session_manager.create_session(user_id=user_id)


@pytest.mark.asyncio
async def test_ws_hook_flag_disabled(monkeypatch):
    """flag 关闭时钩子不拦截，返回 False 走常规路径"""
    from app.api import voice_realtime

    monkeypatch.setattr(
        voice_realtime.settings, "voice_agent_orchestration_enabled", False
    )
    ws = _FakeWebSocket()
    handled = await voice_realtime._try_voice_orchestration(
        ws, _make_session("ws-unit-1"), "任务列表"
    )
    assert handled is False
    assert ws.messages == []


@pytest.mark.asyncio
async def test_ws_hook_task_control(monkeypatch):
    """WS 语音「任务列表」→ 任务控制回复"""
    from app.api import voice_realtime

    monkeypatch.setattr(
        voice_realtime.settings, "voice_agent_orchestration_enabled", True
    )
    ws = _FakeWebSocket()
    handled = await voice_realtime._try_voice_orchestration(
        ws, _make_session("ws-unit-2"), "任务列表"
    )
    assert handled is True
    assert len(ws.messages) == 1
    msg = ws.messages[0]
    assert msg["type"] == "reply"
    assert msg["intent"] == "task_control"
    assert msg["action"] == "list"


@pytest.mark.asyncio
async def test_ws_hook_multi_intent_launch(monkeypatch):
    """WS 语音多意图 → 并行启动后台任务并回执"""
    from app.api import voice_realtime
    from app.services.voice_orchestrator import voice_task_registry

    monkeypatch.setattr(
        voice_realtime.settings, "voice_agent_orchestration_enabled", True
    )
    ws = _FakeWebSocket()
    handled = await voice_realtime._try_voice_orchestration(
        ws, _make_session("ws-unit-3"), "帮我设计一个客厅，同时做一份100平的预算"
    )
    assert handled is True
    msg = ws.messages[0]
    assert msg["intent"] == "orchestrate"
    assert len(msg["launched"]) == 2
    assert {t["intent"] for t in msg["launched"]} == {"design", "budget"}

    # 后台任务最终完成
    deadline = time.time() + 5
    while time.time() < deadline:
        tasks = await voice_task_registry.list("ws-unit-3")
        if tasks and all(t.status == "done" for t in tasks):
            break
        await asyncio.sleep(0.05)
    assert all(t.status == "done" for t in tasks)


@pytest.mark.asyncio
async def test_ws_hook_single_intent_passthrough(monkeypatch):
    """单意图不拦截（走常规同步路径），避免重复处理"""
    from app.api import voice_realtime

    monkeypatch.setattr(
        voice_realtime.settings, "voice_agent_orchestration_enabled", True
    )
    ws = _FakeWebSocket()
    handled = await voice_realtime._try_voice_orchestration(
        ws, _make_session("ws-unit-4"), "帮我设计一个客厅布局"
    )
    assert handled is False
    assert ws.messages == []
