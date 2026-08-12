"""智能体交互全面体检修复回归测试（2026-08-12）

覆盖诊断报告问题：
- P0-1 语音会话跨连接共享：connect() 复用前先关闭旧连接（防覆盖泄漏）
- P0-2 Qwen 断连后降级：_send_raw_json 失败置 _ws=None（状态一致不再静默丢弃）
- P0-3 mock 音频解码协议对齐：base64（兼容 hex/非法输入降级）
- P1-1 TTL 清理孤儿消息：purge 后 agent_messages 无残留
- P2-2 语音后台任务 db 透传：_launch_segment_tasks 传 db/user_id 到 _route_voice_to_agent
- P2-3 VoiceTaskRegistry 每用户任务上限 + seq 单调递增
"""

import base64
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.agent_session import AgentMessage


# ── P0-1: connect() 复用防泄漏 ──


@pytest.mark.asyncio
async def test_connect_closes_previous_ws(monkeypatch):
    """同一 session 再次 connect() 前先关闭旧连接（旧 Qwen WS 不再被覆盖泄漏）"""
    from app.config import get_settings
    from app.services.voice_realtime_service import VoiceRealtimeSession

    class FakeWs:
        def __init__(self):
            self.closed = False

        async def close(self):
            self.closed = True

        async def send(self, data):
            pass

    # 无 API key → connect 走 mock 分支；防泄漏代码在 key 检查之前执行
    monkeypatch.setattr(get_settings(), "qwen_audio_api_key", "")
    session = VoiceRealtimeSession(user_id="p01_user")
    old_ws = FakeWs()
    session._ws = old_ws

    await session.connect()

    assert old_ws.closed is True
    assert session._ws is None


# ── P0-2: _send_raw_json 失败置 _ws=None ──


@pytest.mark.asyncio
async def test_send_raw_json_failure_marks_disconnected():
    """发送失败说明连接已失效，置 _ws=None 使后续调用走 no-op 分支（防静默丢弃）"""
    from app.services.voice_realtime_service import VoiceRealtimeSession

    class BrokenWs:
        async def send(self, data):
            raise ConnectionError("broken")

    session = VoiceRealtimeSession(user_id="p02_user")
    session._ws = BrokenWs()

    await session._send_raw_json({"type": "response.create"})

    assert session._ws is None


# ── P0-3: mock 音频解码（协议 base64）──


def test_decode_audio_data_base64():
    """协议主路径：base64 正确解码"""
    from app.api.voice_realtime import _decode_audio_data

    raw = bytes([0x00, 0x01, 0x02, 0x7F, 0x80, 0xFF])
    b64 = base64.b64encode(raw).decode()
    assert _decode_audio_data(b64) == raw


def test_decode_audio_data_empty():
    from app.api.voice_realtime import _decode_audio_data

    assert _decode_audio_data("") == b""


def test_decode_audio_data_invalid_fallback():
    """非 base64/hex 输入降级为原始字节（历史兼容，不抛异常）"""
    from app.api.voice_realtime import _decode_audio_data

    # "aaaaa" 长度 mod 4 == 1 → b64decode 必抛错；非 hex → encode 降级
    assert _decode_audio_data("aaaaa") == b"aaaaa"


# ── P1-1: TTL 清理无孤儿消息 ──


@pytest.mark.asyncio
async def test_purge_expired_no_orphan_messages(db_session):
    """purge 过期会话后 agent_messages 无孤儿残留（先删消息再删会话）"""
    from app.services import agent_session_service as srv

    session = await srv.create_session(db_session, user_id="u1", title="过期孤儿")
    await srv.persist_message(db_session, session, "user", "你好")
    await srv.persist_message(db_session, session, "assistant", "你好！有什么可以帮您？")
    session.is_deleted = True
    session.deleted_at = datetime.now(timezone.utc) - timedelta(days=31)
    await db_session.commit()

    await srv.purge_all_expired_sessions(db_session)

    result = await db_session.execute(
        select(AgentMessage).where(AgentMessage.session_id == session.id)
    )
    assert result.scalars().all() == []


# ── P2-2: 语音后台任务 db 透传 ──


@pytest.mark.asyncio
async def test_launch_segment_tasks_passes_db(monkeypatch):
    """_launch_segment_tasks 透传 db/user_id 到 _route_voice_to_agent（自进化闭环）"""
    from types import SimpleNamespace

    from app.api import voice_orchestrate

    captured: dict = {}

    async def fake_route(text, intent, user_name, context="", emotion=None,
                         db=None, user_id="", project_id=""):
        captured["text"] = text
        captured["intent"] = intent
        captured["db"] = db
        captured["user_id"] = user_id
        return "已处理"

    async def fake_launch(user_id, intent, command, coro):
        # 同步执行后台 coroutine，保证 captured 在断言前填充
        await coro
        return SimpleNamespace(task_id="t1", seq=1, intent=intent, command=command)

    monkeypatch.setattr(voice_orchestrate, "_route_voice_to_agent", fake_route)
    monkeypatch.setattr(
        voice_orchestrate, "voice_task_registry",
        SimpleNamespace(launch=fake_launch),
    )

    launched, inline = await voice_orchestrate._launch_segment_tasks(
        "user_p2", "测试用户", ["帮我设计客厅"],
        db="FAKE_DB_OBJ",
    )

    assert captured["db"] == "FAKE_DB_OBJ"
    assert captured["user_id"] == "user_p2"
    assert captured["intent"] == "design"
    assert len(launched) == 1
    assert inline == []


# ── P2-3: VoiceTaskRegistry 上限 + seq 单调递增 ──


@pytest.mark.asyncio
async def test_task_registry_caps_retained():
    """每用户任务数有上限，裁剪最旧任务且 seq 保持单调递增"""
    from app.services.voice_orchestrator import VoiceTaskRegistry

    reg = VoiceTaskRegistry()

    async def _dummy():
        return "ok"

    total = reg.MAX_RETAINED_TASKS + 5
    for i in range(total):
        await reg.launch("user_cap", "design", f"任务{i}", _dummy())

    tasks = await reg.list("user_cap")
    assert len(tasks) == reg.MAX_RETAINED_TASKS
    # 裁剪后保留的是最近的任务，seq 单调递增（原 len()+1 会因裁剪产生重复）
    seqs = [t.seq for t in tasks]
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == len(seqs)
    assert tasks[-1].seq == total
    assert tasks[0].seq == 6
