"""A2A 协议 API 测试

覆盖端点:
- GET  /.well-known/agent-card
- GET  /api/a2a/agents
- POST /api/a2a/tasks/send
- GET  /api/a2a/tasks/{id}
- GET  /api/a2a/tasks/{id}/status
- v1.20.x 安全回归：任务查询跨用户 404（admin 可查）、project_id 归属校验
"""
import uuid

import pytest
from httpx import AsyncClient


async def _register(client: AsyncClient, name: str = "用户") -> dict:
    phone = f"139{str(uuid.uuid4().int)[:8]}"
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": name, "password": "test123456"},
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _admin_headers() -> dict:
    """直接经 DB 创建管理员并签发 token（注册接口禁止自注册 admin）。"""
    from app.auth.paseto_handler import create_token
    from app.database import async_session
    from app.models.user import User

    user_id = str(uuid.uuid4())
    async with async_session() as db:
        db.add(User(
            id=user_id, phone=f"139{uuid.uuid4().hex[:8]}",
            name="A2A 审计管理员", role="admin", hashed_password="x",
        ))
        await db.commit()
    return {"Authorization": f"Bearer {create_token(user_id, 'admin')}"}


async def _send_task(client: AsyncClient, headers: dict, token: str,
                     agent_name: str = "NotExistAgent", **extra) -> dict:
    resp = await client.post(
        "/api/a2a/tasks/send",
        json={
            "agent_name": agent_name, "message": "hi",
            "app_id": "console", "handshake_token": token, **extra,
        },
        headers=headers,
    )
    return resp


@pytest.mark.asyncio
async def test_agent_card_public(client: AsyncClient):
    """Agent Card 公开端点无需认证"""
    resp = await client.get("/.well-known/agent-card")
    assert resp.status_code == 200
    data = resp.json()
    assert "name" in data or "description" in data or "url" in data


@pytest.mark.asyncio
async def test_list_agents_requires_auth(client: AsyncClient):
    """列出 Agent 需要认证"""
    resp = await client.get("/api/a2a/agents")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_agents_authenticated(auth_headers: dict, client: AsyncClient):
    """已认证用户可列出 Agent（序列化 bug 已修复：注册表类对象转为名称/描述结构）"""
    resp = await client.get("/api/a2a/agents", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["agents"], list)
    assert data["count"] == len(data["agents"])
    if data["agents"]:
        assert {"name", "class_name", "description"} <= set(data["agents"][0].keys())


@pytest.mark.asyncio
async def test_send_task_requires_auth(client: AsyncClient):
    """下发任务需要认证"""
    resp = await client.post("/api/a2a/tasks/send", json={"agent_name": "OrchestratorAgent", "message": "测试任务"})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_send_task_authenticated(auth_headers: dict, client: AsyncClient):
    """已认证用户可下发 A2A 任务（v1.17.x 强制 ATH 握手：先签发凭证再携带）。"""
    issue = await client.post(
        "/api/agents/handshake/issue",
        json={"app_id": "console", "agent_name": "DesignerAgent", "scope": "a2a:task"},
        headers=auth_headers,
    )
    assert issue.status_code == 200
    resp = await client.post(
        "/api/a2a/tasks/send",
        json={
            "agent_name": "DesignerAgent",
            "message": "设计吧台",
            "app_id": "console",
            "handshake_token": issue.json()["token"],
        },
        headers=auth_headers,
    )
    assert resp.status_code in (200, 201, 503)


@pytest.mark.asyncio
async def test_send_task_requires_handshake_token(auth_headers: dict, client: AsyncClient):
    """强制握手：已认证但缺凭证 → 403（不再兼容放行）。"""
    resp = await client.post(
        "/api/a2a/tasks/send",
        json={"agent_name": "DesignerAgent", "message": "设计吧台"},
        headers=auth_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_task_not_found(auth_headers: dict, client: AsyncClient):
    """查询不存在的任务返回 404"""
    resp = await client.get("/api/a2a/tasks/nonexistent-123", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_task_status_not_found(auth_headers: dict, client: AsyncClient):
    """查询不存在的任务状态返回 404"""
    resp = await client.get("/api/a2a/tasks/nonexistent-123/status", headers=auth_headers)
    assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════
# v1.20.x 安全回归（ATH 安全管控 / 最小权限维度）
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_task_detail_cross_user_404(client: AsyncClient, a2a_handshake):
    """跨用户读取任务详情/状态 → 404（此前无归属过滤，任意登录用户可读 result/evidence）。"""
    owner = await _register(client, "任务发起人")
    other = await _register(client, "其他用户")
    token = await a2a_handshake(owner, "NotExistAgent")
    sent = await _send_task(client, owner, token)
    assert sent.status_code == 200, sent.text
    task_id = sent.json()["task_id"]

    resp = await client.get(f"/api/a2a/tasks/{task_id}", headers=other)
    assert resp.status_code == 404, resp.text
    resp = await client.get(f"/api/a2a/tasks/{task_id}/status", headers=other)
    assert resp.status_code == 404, resp.text

    # 本人仍可读（回归不误伤）
    resp = await client.get(f"/api/a2a/tasks/{task_id}", headers=owner)
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_task_detail_admin_can_read(client: AsyncClient, a2a_handshake):
    """admin 可查全部任务（对齐项目 admin 口径）。"""
    owner = await _register(client, "任务发起人")
    token = await a2a_handshake(owner, "NotExistAgent")
    sent = await _send_task(client, owner, token)
    task_id = sent.json()["task_id"]

    resp = await client.get(f"/api/a2a/tasks/{task_id}", headers=await _admin_headers())
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_send_task_non_owner_project_403(client: AsyncClient, a2a_handshake):
    """向他人项目下发任务 → 403（project_id 归属校验，此前任意 project_id 均 200）。"""
    owner = await _register(client, "项目业主")
    other = await _register(client, "其他用户")
    proj = await client.post(
        "/api/projects", json={"name": "归属校验项目", "total_area": 88.0}, headers=owner,
    )
    assert proj.status_code in (200, 201), proj.text
    project_id = proj.json()["id"]

    token = await a2a_handshake(other, "NotExistAgent")
    resp = await _send_task(client, other, token, project_id=project_id)
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_send_task_owner_project_ok(client: AsyncClient, a2a_handshake):
    """业主向自己的项目下发任务 → 200（校验不误伤）。"""
    owner = await _register(client, "项目业主")
    proj = await client.post(
        "/api/projects", json={"name": "自有权项目", "total_area": 88.0}, headers=owner,
    )
    project_id = proj.json()["id"]

    token = await a2a_handshake(owner, "NotExistAgent")
    resp = await _send_task(client, owner, token, project_id=project_id)
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_send_task_nonexistent_project_404(client: AsyncClient, a2a_handshake):
    """不存在的 project_id → 404（verify_project_access 单源）。"""
    user = await _register(client, "普通用户")
    token = await a2a_handshake(user, "NotExistAgent")
    resp = await _send_task(client, user, token, project_id=str(uuid.uuid4()))
    assert resp.status_code == 404, resp.text
