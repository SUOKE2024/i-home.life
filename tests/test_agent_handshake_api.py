"""ATH 握手凭证 API 端点测试（v1.16.x 起，v1.17.x 补强制握手 + 应用注册表）

覆盖：
- issue / verify / verify-agent 端点认证与结果
- 应用注册表拒签（未登记 app_id / 越权 scope → 400）
- 未认证 401/403、flag 关闭 503 诚实降级
- A2A 强制握手（缺省 403；required=False 回滚）
"""
import pytest
from httpx import AsyncClient

from app.config import get_settings


@pytest.mark.asyncio
async def test_issue_handshake_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/api/agents/handshake/issue",
        json={"app_id": "flutter", "agent_name": "designer"},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_issue_handshake_ok(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/agents/handshake/issue",
        json={"app_id": "flutter", "agent_name": "designer", "scope": "a2a:task"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["token"]
    assert data["app_id"] == "flutter"
    assert data["agent_name"] == "designer"
    assert data["scope"] == "a2a:task"
    assert data["actor_user_id"]


@pytest.mark.asyncio
async def test_verify_handshake_roundtrip(client: AsyncClient, auth_headers: dict):
    issue = await client.post(
        "/api/agents/handshake/issue",
        json={"app_id": "flutter", "agent_name": "designer", "scope": "a2a:task"},
        headers=auth_headers,
    )
    data = issue.json()
    resp = await client.post(
        "/api/agents/handshake/verify",
        json={
            "token": data["token"],
            "app_id": "flutter",
            "agent_name": "designer",
            "actor_user_id": data["actor_user_id"],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["scope"] == "a2a:task"


@pytest.mark.asyncio
async def test_verify_agent_identity_endpoint(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/agents/handshake/verify-agent",
        json={"agent_name": "care"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["verified"] is True
    assert len(data["aid"]) == 28
    assert data["acdl"]["agent"]["name"] == "care"


@pytest.mark.asyncio
async def test_verify_agent_identity_aid_mismatch(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/agents/handshake/verify-agent",
        json={"agent_name": "designer", "expected_aid": "0" * 28},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["verified"] is False


@pytest.mark.asyncio
async def test_handshake_flag_off_503(client: AsyncClient, auth_headers: dict, monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_handshake_enabled", False)
    resp = await client.post(
        "/api/agents/handshake/issue",
        json={"app_id": "flutter", "agent_name": "designer"},
        headers=auth_headers,
    )
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_issue_rejects_unregistered_app_400(client: AsyncClient, auth_headers: dict):
    """应用注册表：未登记 app_id → 400 拒签（应用侧身份不可自报）。"""
    resp = await client.post(
        "/api/agents/handshake/issue",
        json={"app_id": "evil_app", "agent_name": "designer"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "unknown_app" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_issue_rejects_scope_not_allowed_400(client: AsyncClient, auth_headers: dict):
    """最小权限：scope 不在该应用白名单内 → 400 拒签。"""
    resp = await client.post(
        "/api/agents/handshake/issue",
        json={"app_id": "flutter", "agent_name": "designer", "scope": "admin:audit"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "scope_not_allowed" in resp.json()["detail"]


# ════════════════════════════════════════════════════════════════
# v1.16.0：握手凭证接入 A2A send_task 生产链路
# v1.17.x：改为强制握手（缺省拒绝），required=False 为回滚开关
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_a2a_send_task_without_token_403(client: AsyncClient, auth_headers: dict):
    """强制握手：不携带 handshake_token → 403 拒绝（不再兼容放行）。"""
    resp = await client.post(
        "/api/a2a/tasks/send",
        json={"agent_name": "ConciergeAgent", "message": "装修保修期多久"},
        headers=auth_headers,
    )
    assert resp.status_code == 403
    assert "握手凭证缺失" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_a2a_send_task_required_off_backward_compatible(
    client: AsyncClient, auth_headers: dict, monkeypatch
):
    """回滚开关：agent_handshake_required=False → 旧行为（放行 + evidence absent）。"""
    monkeypatch.setattr(get_settings(), "agent_handshake_required", False)
    resp = await client.post(
        "/api/a2a/tasks/send",
        json={"agent_name": "ConciergeAgent", "message": "装修保修期多久"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["evidence"]["handshake"] == "absent"


@pytest.mark.asyncio
async def test_a2a_send_task_with_valid_token_verified(client: AsyncClient, auth_headers: dict):
    """携带合法凭证 → 校验通过，evidence 标注 verified + scope/app_id。"""
    issue = await client.post(
        "/api/agents/handshake/issue",
        json={"app_id": "console", "agent_name": "ConciergeAgent", "scope": "a2a:task"},
        headers=auth_headers,
    )
    cred = issue.json()
    resp = await client.post(
        "/api/a2a/tasks/send",
        json={
            "agent_name": "ConciergeAgent",
            "message": "装修保修期多久",
            "app_id": "console",
            "handshake_token": cred["token"],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    ev = resp.json()["evidence"]
    assert ev["handshake"] == "verified"
    assert ev["handshake_scope"] == "a2a:task"
    assert ev["handshake_app_id"] == "console"


@pytest.mark.asyncio
async def test_a2a_send_task_token_agent_mismatch_403(client: AsyncClient, auth_headers: dict):
    """凭证签给 designer 却用于 concierge → 403 拒绝下发。"""
    issue = await client.post(
        "/api/agents/handshake/issue",
        json={"app_id": "console", "agent_name": "DesignerAgent"},
        headers=auth_headers,
    )
    resp = await client.post(
        "/api/a2a/tasks/send",
        json={
            "agent_name": "ConciergeAgent",
            "message": "hi",
            "app_id": "console",
            "handshake_token": issue.json()["token"],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 403
    assert "agent_mismatch" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_a2a_send_task_token_missing_app_id_403(client: AsyncClient, auth_headers: dict):
    """携带 token 但缺 app_id → 403（无法核验调用方身份）。"""
    issue = await client.post(
        "/api/agents/handshake/issue",
        json={"app_id": "console", "agent_name": "ConciergeAgent"},
        headers=auth_headers,
    )
    resp = await client.post(
        "/api/a2a/tasks/send",
        json={
            "agent_name": "ConciergeAgent",
            "message": "hi",
            "handshake_token": issue.json()["token"],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 403
    assert "app_id" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_a2a_send_task_scope_outside_a2a_403(client: AsyncClient, auth_headers: dict):
    """最小权限：scope 非 a2a:* 域 → 403 拒绝下发任务。"""
    issue = await client.post(
        "/api/agents/handshake/issue",
        json={"app_id": "console", "agent_name": "ConciergeAgent", "scope": "scene:automation"},
        headers=auth_headers,
    )
    resp = await client.post(
        "/api/a2a/tasks/send",
        json={
            "agent_name": "ConciergeAgent",
            "message": "hi",
            "app_id": "console",
            "handshake_token": issue.json()["token"],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 403
    assert "scope 越权" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_a2a_send_task_tampered_token_403(client: AsyncClient, auth_headers: dict):
    issue = await client.post(
        "/api/agents/handshake/issue",
        json={"app_id": "console", "agent_name": "ConciergeAgent"},
        headers=auth_headers,
    )
    resp = await client.post(
        "/api/a2a/tasks/send",
        json={
            "agent_name": "ConciergeAgent",
            "message": "hi",
            "app_id": "console",
            "handshake_token": issue.json()["token"] + "tamper",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 403
    assert "signature" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_a2a_send_task_gate_disabled_honest(client: AsyncClient, auth_headers: dict, monkeypatch):
    """flag 关闭时携带 token 不校验，但 evidence 诚实标注 gate_disabled。"""
    monkeypatch.setattr(get_settings(), "agent_handshake_enabled", False)
    resp = await client.post(
        "/api/a2a/tasks/send",
        json={
            "agent_name": "ConciergeAgent",
            "message": "hi",
            "app_id": "console",
            "handshake_token": "anything",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["evidence"]["handshake"] == "gate_disabled"
