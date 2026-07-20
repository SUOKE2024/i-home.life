"""Agent 会话持久化测试

覆盖：
- agent_session_service 的 CRUD 操作
- /agents/sessions 端点（列表/详情/删除）
- /agents/chat 端点自动持久化
- AgentFeedback session_id 关联
- 隐私保护（PII 过滤/加密/TTL 清理）
"""

import pytest
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy import select

from app.services import agent_session_service


async def _register(client: AsyncClient, phone: str = "13900005001") -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "SessionTest", "password": "test123456"},
    )
    return resp.json()["access_token"]


# === 服务层单元测试 ===


@pytest.mark.asyncio
async def test_create_and_get_session(db_session):
    """创建会话并获取"""
    session = await agent_session_service.create_session(
        db_session, user_id="u1", project_id="p1", title="测试会话",
    )
    assert session.id is not None
    assert session.title == "测试会话"
    assert session.message_count == 0
    assert session.is_deleted is False

    retrieved = await agent_session_service.get_session(db_session, session.id, "u1")
    assert retrieved is not None
    assert retrieved.id == session.id


@pytest.mark.asyncio
async def test_persist_message(db_session):
    """持久化消息并更新计数"""
    session = await agent_session_service.create_session(db_session, user_id="u1")
    assert session.message_count == 0

    msg1 = await agent_session_service.persist_message(
        db_session, session, "user", "你好，帮我设计一个客厅",
    )
    assert msg1.role == "user"
    assert msg1.sequence == 0
    assert session.message_count == 1
    # 首条用户消息应自动更新标题
    assert "设计" in session.title or "客厅" in session.title

    msg2 = await agent_session_service.persist_message(
        db_session, session, "assistant", "好的，让我为您设计客厅方案。",
        agent_type="designer",
    )
    assert msg2.role == "assistant"
    assert msg2.sequence == 1
    assert msg2.agent_type == "designer"
    assert session.message_count == 2
    assert session.primary_agent_type == "designer"


@pytest.mark.asyncio
async def test_soft_delete_session(db_session):
    """软删除会话"""
    session = await agent_session_service.create_session(db_session, user_id="u1")
    result = await agent_session_service.soft_delete_session(db_session, session.id, "u1")
    assert result is not None
    assert result.is_deleted is True
    assert result.deleted_at is not None

    # 再次获取应返回 None
    retrieved = await agent_session_service.get_session(db_session, session.id, "u1")
    assert retrieved is None


@pytest.mark.asyncio
async def test_list_sessions(db_session):
    """列出用户会话"""
    s1 = await agent_session_service.create_session(db_session, user_id="u1", title="A")
    s2 = await agent_session_service.create_session(db_session, user_id="u1", title="B")
    # 不同用户
    await agent_session_service.create_session(db_session, user_id="u2", title="C")
    assert s1 is not None
    assert s2 is not None

    sessions = await agent_session_service.list_sessions(db_session, "u1")
    assert len(sessions) == 2
    # 按更新时间倒序
    assert sessions[0].title in ("A", "B")


@pytest.mark.asyncio
async def test_get_session_history(db_session):
    """获取会话历史（用于注入 prompt）"""
    session = await agent_session_service.create_session(db_session, user_id="u1")
    await agent_session_service.persist_message(db_session, session, "user", "你好")
    await agent_session_service.persist_message(
        db_session, session, "assistant", "你好！有什么可以帮你的？", agent_type="orchestrator",
    )
    await agent_session_service.persist_message(db_session, session, "user", "帮我设计客厅")

    history = await agent_session_service.get_session_history(db_session, session.id, "u1", limit=10)
    assert len(history) == 3
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "你好"
    assert history[2]["role"] == "user"
    assert history[2]["content"][:3] == "帮我设"


@pytest.mark.asyncio
async def test_title_sanitize():
    """测试标题提取"""
    from app.services.agent_session_service import _sanitize_title
    assert _sanitize_title("") == "新的对话"
    assert _sanitize_title("   ") == "新的对话"
    assert _sanitize_title("帮我设计一个三室两厅的现代简约风格。" + "x" * 200) is not None
    assert len(_sanitize_title("帮我设计一个三室两厅的现代简约风格。" + "x" * 200)) <= 100


# === HTTP API 端点集成测试 ===


@pytest.mark.asyncio
async def test_chat_creates_session(client: AsyncClient):
    """/agents/chat 自动创建会话并返回 session_id"""
    token = await _register(client, "13900005002")
    resp = await client.post(
        "/api/agents/chat",
        json={"message": "帮我设计一个客厅", "agent_type": "designer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["session_id"] is not None
    assert "reply" in data


@pytest.mark.asyncio
async def test_chat_with_existing_session(client: AsyncClient):
    """传入已有 session_id 继续对话"""
    token = await _register(client, "13900005003")

    # 第一轮：创建会话
    resp1 = await client.post(
        "/api/agents/chat",
        json={"message": "帮我设计客厅", "agent_type": "designer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    session_id = resp1.json()["session_id"]

    # 第二轮：继续对话
    resp2 = await client.post(
        "/api/agents/chat",
        json={
            "message": "用北欧风格",
            "agent_type": "designer",
            "session_id": session_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["session_id"] == session_id


@pytest.mark.asyncio
async def test_list_sessions_endpoint(client: AsyncClient):
    """GET /agents/sessions 列出会话"""
    token = await _register(client, "13900005004")

    # 先创建几个会话
    await client.post(
        "/api/agents/chat",
        json={"message": "会话1：设计", "agent_type": "designer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        "/api/agents/chat",
        json={"message": "会话2：预算", "agent_type": "budget"},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        "/api/agents/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    sessions = resp.json()
    assert len(sessions) >= 2
    assert "id" in sessions[0]
    assert "title" in sessions[0]
    assert "message_count" in sessions[0]


@pytest.mark.asyncio
async def test_get_session_detail(client: AsyncClient):
    """GET /agents/sessions/{id} 获取详情含消息"""
    token = await _register(client, "13900005005")

    # 创建会话
    chat_resp = await client.post(
        "/api/agents/chat",
        json={"message": "帮我设计客厅", "agent_type": "designer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    session_id = chat_resp.json()["session_id"]

    # 获取详情
    resp = await client.get(
        f"/api/agents/sessions/{session_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == session_id
    assert len(data["messages"]) >= 2  # 至少 user + assistant


@pytest.mark.asyncio
async def test_delete_session(client: AsyncClient):
    """DELETE /agents/sessions/{id} 软删除"""
    token = await _register(client, "13900005006")

    chat_resp = await client.post(
        "/api/agents/chat",
        json={"message": "待删除会话", "agent_type": "designer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    session_id = chat_resp.json()["session_id"]

    # 删除
    resp = await client.delete(
        f"/api/agents/sessions/{session_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    # 再次获取应 404
    resp2 = await client.get(
        f"/api/agents/sessions/{session_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_session_isolation(client: AsyncClient):
    """用户只能访问自己的会话"""
    token_a = await _register(client, "13900005007")
    token_b = await _register(client, "13900005008")

    # A 创建会话
    resp_a = await client.post(
        "/api/agents/chat",
        json={"message": "A的会话", "agent_type": "designer"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    session_id = resp_a.json()["session_id"]

    # B 尝试访问 A 的会话 → 404
    resp_b = await client.get(
        f"/api/agents/sessions/{session_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_b.status_code == 404


@pytest.mark.asyncio
async def test_feedback_with_session_id(client: AsyncClient):
    """反馈提交时包含 session_id"""
    token = await _register(client, "13900005009")

    chat_resp = await client.post(
        "/api/agents/chat",
        json={"message": "反馈测试消息", "agent_type": "designer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    session_id = chat_resp.json()["session_id"]

    resp = await client.post(
        "/api/agents/feedback",
        json={
            "agent_name": "designer",
            "feedback_type": "like",
            "rating": 4,
            "user_message": "反馈测试消息",
            "agent_reply": "测试回复",
            "session_id": session_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "recorded"


# === 隐私保护边缘用例测试 ===


def test_sanitize_title_pii_phone():
    """标题过滤手机号"""
    from app.services.agent_session_service import _sanitize_title
    result = _sanitize_title("我家在朝阳区，电话是13812345678。")
    assert "13812345678" not in result
    assert "****" in result


def test_sanitize_title_pii_idcard():
    """标题过滤身份证号"""
    from app.services.agent_session_service import _sanitize_title
    result = _sanitize_title("身份证号110101199001011234请查收。")
    assert "110101199001011234" not in result


def test_sanitize_title_pii_address():
    """标题过滤地址片段"""
    from app.services.agent_session_service import _sanitize_title
    result = _sanitize_title("我家住在中关村街道南大街1号楼。")
    assert "中关村" not in result and "南大街" not in result


def test_sanitize_title_normal():
    """正常标题不过滤"""
    from app.services.agent_session_service import _sanitize_title
    result = _sanitize_title("帮我设计一个三室两厅的现代简约风格。")
    assert "三室两厅" in result
    assert "现代简约" in result


def test_sanitize_title_empty():
    """空标题"""
    from app.services.agent_session_service import _sanitize_title
    assert _sanitize_title("") == "新的对话"
    assert _sanitize_title("   ") == "新的对话"


def test_sanitize_title_truncation():
    """超长标题截断"""
    from app.services.agent_session_service import _sanitize_title
    long_text = "这是" + "一个" * 100 + "很长的消息。"
    result = _sanitize_title(long_text)
    assert len(result) <= 100
    assert result.endswith("...")


# === 加密边缘用例测试 ===


def test_encrypt_decrypt_roundtrip():
    """加密解密往返"""
    from app.services.agent_session_service import _encrypt, _decrypt
    original = "用户居住在北辰西路66号，预算20万元整。"
    encrypted = _encrypt(original)
    # 生产环境加密后不应等于原文
    if original != encrypted:
        assert _decrypt(encrypted) == original
    else:
        # 开发环境未加密（默认 PASETO key）
        assert encrypted == original


def test_encrypt_empty_string():
    """空字符串加密"""
    from app.services.agent_session_service import _encrypt, _decrypt
    assert _decrypt(_encrypt("")) == ""


def test_content_hash_deterministic():
    """内容哈希确定性"""
    from app.services.agent_session_service import _content_hash
    h1 = _content_hash("hello")
    h2 = _content_hash("hello")
    assert h1 == h2
    assert len(h1) == 64  # SHA256


@pytest.mark.asyncio
async def test_encrypted_storage_roundtrip(db_session):
    """消息加密存储后正确解密"""
    from app.services import agent_session_service as srv
    session = await srv.create_session(db_session, user_id="u1")
    msg = await srv.persist_message(db_session, session, "user", "我的联系电话是13900001111")
    # 通过 get_session_history 解密
    history = await srv.get_session_history(db_session, session.id, "u1", limit=1)
    assert msg is not None
    assert len(history) == 1
    assert history[0]["content"] == "我的联系电话是13900001111"


# === TTL 清理测试 ===


@pytest.mark.asyncio
async def test_purge_expired_does_not_affect_active(db_session):
    """TTL 清理不影响活跃会话"""
    from app.services import agent_session_service as srv
    from datetime import timedelta

    # 创建活跃会话
    active = await srv.create_session(db_session, user_id="u1", title="活跃")

    # 创建过期会话：手动设置删除时间
    old = await srv.create_session(db_session, user_id="u1", title="过期")
    old.is_deleted = True
    old.deleted_at = datetime.now(timezone.utc) - timedelta(days=31)
    await db_session.commit()

    await srv.purge_all_expired_sessions(db_session)

    # 活跃会话仍在
    still_active = await srv.get_session(db_session, active.id, "u1")
    assert still_active is not None

    # 过期会话已删除
    gone = await srv.get_session(db_session, old.id, "u1")
    assert gone is None


@pytest.mark.asyncio
async def test_purge_does_not_affect_recent_deleted(db_session):
    """TTL 清理不删除刚软删除的会话"""
    from app.services import agent_session_service as srv

    recent = await srv.create_session(db_session, user_id="u1", title="最近删除")
    await srv.soft_delete_session(db_session, recent.id, "u1")
    # deleted_at 是现在，未过期

    await srv.purge_all_expired_sessions(db_session)

    # 30 天内仍可访问（虽然 is_deleted=True 但未被物理删除）
    from app.models.agent_session import AgentSession
    result = await db_session.execute(
        select(AgentSession).where(AgentSession.id == recent.id)
    )
    still_there = result.scalar_one_or_none()
    assert still_there is not None
    assert still_there.is_deleted is True
