"""实时语音 WebSocket API 集成测试

覆盖端点:
- POST /api/voice/process-enhanced  (增强版语音文本处理 — 情绪检测 + Agent 路由 + 自动工具调用)

注意:
- WebSocket /realtime 端点需要真实的 WebSocket 连接，不在本文件测试
- /process-enhanced 端点与 voice.py 共享路径前缀，测试其增强功能:
  情绪检测、意图分类、Agent 管道路由、工具调用、升级判断
"""
import pytest
from httpx import AsyncClient


async def _auth_headers(client: AsyncClient, phone: str = "13950050001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "实时语音测试", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "实时语音测试项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 100.0}, headers=headers,
    )
    return resp.json()["id"]


# ── Auth ──


@pytest.mark.asyncio
async def test_realtime_unauthorized(client: AsyncClient):
    """未认证用户不能调用实时语音处理"""
    resp = await client.post(
        "/api/voice/process-enhanced",
        json={"text": "帮我计算装修预算"},
    )
    assert resp.status_code == 401


# ── 基本处理 ──


@pytest.mark.asyncio
async def test_process_enhanced_basic(client: AsyncClient):
    """实时语音处理 — 基本调用"""
    headers = await _auth_headers(client, "13950050002")

    resp = await client.post(
        "/api/voice/process-enhanced",
        json={"text": "我想了解一下装修流程"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["transcript"] == "我想了解一下装修流程"
    assert "intent" in data
    assert "reply" in data


@pytest.mark.asyncio
async def test_process_enhanced_budget(client: AsyncClient):
    """实时语音处理 — 预算意图"""
    headers = await _auth_headers(client, "13950050003")

    resp = await client.post(
        "/api/voice/process-enhanced",
        json={"text": "100平米的房子装修预算大概多少钱"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["transcript"] == "100平米的房子装修预算大概多少钱"
    assert "intent" in data
    assert "reply" in data


@pytest.mark.asyncio
async def test_process_enhanced_design(client: AsyncClient):
    """实时语音处理 — 设计意图"""
    headers = await _auth_headers(client, "13950050004")

    resp = await client.post(
        "/api/voice/process-enhanced",
        json={"text": "帮我设计一个北欧风格的客厅"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["transcript"] == "帮我设计一个北欧风格的客厅"
    assert "intent" in data
    assert "reply" in data


@pytest.mark.asyncio
async def test_process_enhanced_construction(client: AsyncClient):
    """实时语音处理 — 施工意图"""
    headers = await _auth_headers(client, "13950050005")

    resp = await client.post(
        "/api/voice/process-enhanced",
        json={"text": "施工进度到哪了"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "intent" in data
    assert "reply" in data


# ── 带项目 ID ──


@pytest.mark.asyncio
async def test_process_enhanced_with_project(client: AsyncClient):
    """实时语音处理 — 带有效项目 ID"""
    headers = await _auth_headers(client, "13950050006")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/voice/process-enhanced",
        json={"text": "查询项目进度", "project_id": project_id},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "intent" in data


@pytest.mark.asyncio
async def test_process_enhanced_invalid_project(client: AsyncClient):
    """实时语音处理 — 无效项目 ID 应 404"""
    headers = await _auth_headers(client, "13950050007")

    resp = await client.post(
        "/api/voice/process-enhanced",
        json={"text": "查询项目进度", "project_id": "nonexistent-id"},
        headers=headers,
    )
    assert resp.status_code == 404


# ── 禁情绪检测 ──


@pytest.mark.asyncio
async def test_process_enhanced_emotion_disabled(client: AsyncClient):
    """实时语音处理 — 禁用情绪检测"""
    headers = await _auth_headers(client, "13950050008")

    resp = await client.post(
        "/api/voice/process-enhanced",
        json={"text": "装修太麻烦了，好焦虑", "emotion_enabled": False},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "intent" in data
    assert "reply" in data


# ── 越权校验 ──


@pytest.mark.asyncio
async def test_process_enhanced_foreign_project_blocked(client: AsyncClient):
    """用户不能使用他人的项目 ID 发起语音会话"""
    headers_a = await _auth_headers(client, "13950050009")
    headers_b = await _auth_headers(client, "13950050010")
    project_id_a = await _create_project(client, headers_a)

    resp = await client.post(
        "/api/voice/process-enhanced",
        json={"text": "查询项目进度", "project_id": project_id_a},
        headers=headers_b,
    )
    assert resp.status_code == 403
