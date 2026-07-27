"""语音处理 API 集成测试

覆盖端点:
- POST /api/voice/process           (关键词匹配语音处理)
- POST /api/voice/process-enhanced  (LLM 语义路由增强处理)
"""
import pytest
from httpx import AsyncClient


async def _auth_headers(client: AsyncClient, phone: str = "13940040001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "语音测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "语音测试项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 100.0}, headers=headers,
    )
    return resp.json()["id"]


# ── Auth ──


@pytest.mark.asyncio
async def test_voice_unauthorized(client: AsyncClient):
    """未认证用户不能调用语音处理"""
    resp = await client.post(
        "/api/voice/process",
        json={"text": "帮我设计客厅"},
    )
    assert resp.status_code == 401


# ── /voice/process (关键词匹配) ──


@pytest.mark.asyncio
async def test_process_basic_design(client: AsyncClient):
    """语音处理 — 设计意图关键词匹配"""
    headers = await _auth_headers(client, "13940040002")

    resp = await client.post(
        "/api/voice/process",
        json={"text": "帮我设计一个客厅布局"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "design"
    assert "transcript" in data
    assert "reply" in data


@pytest.mark.asyncio
async def test_process_basic_budget(client: AsyncClient):
    """语音处理 — 预算意图关键词匹配"""
    headers = await _auth_headers(client, "13940040003")

    resp = await client.post(
        "/api/voice/process",
        json={"text": "我要做装修预算报价"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] in ("budget", "design")


@pytest.mark.asyncio
async def test_process_basic_measurement(client: AsyncClient):
    """语音处理 — 测量意图"""
    headers = await _auth_headers(client, "13940040004")

    resp = await client.post(
        "/api/voice/process",
        json={"text": "我需要测量客厅面积 6米×5米"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    # 测量意图（v1.2.x 细化为 ar_measurement，兼容旧命名）
    assert data["intent"] in ("ar_measurement", "measurement", "design")


# ── /voice/process-enhanced (LLM 语义路由) ──


@pytest.mark.asyncio
async def test_process_enhanced_design(client: AsyncClient):
    """增强语音处理 — 设计意图（LLM 路由）"""
    headers = await _auth_headers(client, "13940040005")

    resp = await client.post(
        "/api/voice/process-enhanced",
        json={"text": "请帮我设计一套现代风格的客厅方案"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["transcript"] == "请帮我设计一套现代风格的客厅方案"
    assert "intent" in data
    assert "reply" in data


@pytest.mark.asyncio
async def test_process_enhanced_procurement(client: AsyncClient):
    """增强语音处理 — 采购意图"""
    headers = await _auth_headers(client, "13940040006")

    resp = await client.post(
        "/api/voice/process-enhanced",
        json={"text": "我需要采购瓷砖和地板材料"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "intent" in data
    assert "reply" in data


@pytest.mark.asyncio
async def test_process_enhanced_general(client: AsyncClient):
    """增强语音处理 — 通用闲聊"""
    headers = await _auth_headers(client, "13940040007")

    resp = await client.post(
        "/api/voice/process-enhanced",
        json={"text": "你好，今天天气怎么样"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "intent" in data
    assert "reply" in data


@pytest.mark.asyncio
async def test_process_enhanced_empty_text(client: AsyncClient):
    """增强语音处理 — 空文本应 422"""
    headers = await _auth_headers(client, "13940040008")

    resp = await client.post(
        "/api/voice/process-enhanced",
        json={"text": ""},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_process_enhanced_with_project(client: AsyncClient):
    """增强语音处理 — 带项目 ID"""
    headers = await _auth_headers(client, "13940040009")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/voice/process-enhanced",
        json={"text": "我的装修进度如何", "project_id": project_id},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "intent" in data


@pytest.mark.asyncio
async def test_process_enhanced_invalid_project(client: AsyncClient):
    """增强语音处理 — 无效项目 ID 应 404"""
    headers = await _auth_headers(client, "13940040010")

    resp = await client.post(
        "/api/voice/process-enhanced",
        json={"text": "我的装修进度如何", "project_id": "nonexistent-id"},
        headers=headers,
    )
    assert resp.status_code == 404
