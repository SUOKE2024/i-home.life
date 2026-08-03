"""Agent 三档安全 posture 测试（v1.8.0 借鉴 YC QM）

覆盖：
- strict 高危工具拦截：返回 needs_approval + 创建 AgentApproval(pending)
- strict 非高危工具放行：高危清单匹配时非清单工具正常执行
- strict 高危清单为空 = 全部拦截
- auto 模式正常执行（不拦截）
- dangerous 模式全放行
- approve + execute 成功流程
- reject 后 execute 失败
- 过期 expire_outdated
- API：list pending / get / approve / reject / execute / 非 owner 404
"""
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.agent_approval import (
    AgentApproval, STATE_PENDING, STATE_APPROVED, STATE_REJECTED, STATE_EXPIRED,
)
from app.services import agent_approval_service
from app.services.agent_tool_registry import tool_registry


# ── 工具层 posture 检查 ──


@pytest.mark.asyncio
async def test_strict_blocks_high_risk_and_creates_approval(db_session, monkeypatch):
    """strict + 高危清单为空（=全部拦截）→ 返回 needs_approval + 创建 pending approval"""
    monkeypatch.setattr(
        "app.services.agent_tool_registry.settings.agent_strict_high_risk_tools", "",
    )
    result = await tool_registry.execute(
        "get_budget",
        {"area": 100, "style": "modern"},
        _db=db_session,
        _project_id="p-test",
        _user_id="u-strict-1",
        _agent_id="budget",
        _posture="strict",
    )
    assert result["error"] == "needs_approval"
    approval_id = result["approval_id"]
    assert approval_id.startswith("apr_")

    # 数据库中应有一条 pending 记录
    rows = await agent_approval_service.list_pending(db_session, "u-strict-1")
    assert len(rows) == 1
    assert rows[0].approval_id == approval_id
    assert rows[0].state == STATE_PENDING
    assert rows[0].tool_name == "get_budget"


@pytest.mark.asyncio
async def test_strict_blocks_listed_high_risk_tool(db_session, monkeypatch):
    """strict + 高危清单含 get_budget → get_budget 被拦截"""
    monkeypatch.setattr(
        "app.services.agent_tool_registry.settings.agent_strict_high_risk_tools",
        "get_budget,cancel_agent_task",
    )
    result = await tool_registry.execute(
        "get_budget",
        {"area": 80, "style": "nordic"},
        _db=db_session,
        _user_id="u-strict-2",
        _posture="strict",
    )
    assert result["error"] == "needs_approval"


@pytest.mark.asyncio
async def test_strict_passes_non_high_risk_tool(db_session, monkeypatch):
    """strict + 高危清单不含目标工具 → 正常执行（不拦截）"""
    monkeypatch.setattr(
        "app.services.agent_tool_registry.settings.agent_strict_high_risk_tools",
        "cancel_agent_task,delete_project",
    )
    result = await tool_registry.execute(
        "get_budget",
        {"area": 60, "style": "modern"},
        _db=db_session,
        _project_id="p-test",
        _user_id="u-strict-3",
        _posture="strict",
    )
    # 非高危 → 不应返回 needs_approval
    assert result.get("error") != "needs_approval"


@pytest.mark.asyncio
async def test_auto_posture_executes_normally(db_session):
    """auto 模式 → 正常执行，不拦截"""
    result = await tool_registry.execute(
        "get_budget",
        {"area": 100, "style": "modern"},
        _db=db_session,
        _project_id="p-test",
        _user_id="u-auto-1",
        _posture="auto",
    )
    assert result.get("error") != "needs_approval"


@pytest.mark.asyncio
async def test_dangerous_posture_allows_all(db_session):
    """dangerous 模式 → 全放行，不拦截"""
    result = await tool_registry.execute(
        "get_budget",
        {"area": 100, "style": "modern"},
        _db=db_session,
        _project_id="p-test",
        _user_id="u-danger-1",
        _posture="dangerous",
    )
    assert result.get("error") != "needs_approval"


# ── 批准状态机 ──


@pytest.mark.asyncio
async def test_approve_then_execute_success(db_session):
    """approve(pending→approved) → execute_approved 成功执行"""
    approval = await agent_approval_service.create_approval(
        db_session, user_id="u-flow-1", agent_name="budget",
        tool_name="get_budget", arguments={"area": 100, "style": "modern"},
        project_id="p-test",
    )
    assert approval.state == STATE_PENDING

    # 批准
    approved = await agent_approval_service.approve(
        db_session, approval.approval_id, decided_by="u-flow-1", reason="OK",
    )
    assert approved.state == STATE_APPROVED
    assert approved.decided_by == "u-flow-1"

    # 执行
    result = await agent_approval_service.execute_approved(
        db_session, approval.approval_id, "u-flow-1",
    )
    assert result["executed"] is True


@pytest.mark.asyncio
async def test_reject_then_execute_fails(db_session):
    """reject(pending→rejected) → execute_approved 返回失败"""
    approval = await agent_approval_service.create_approval(
        db_session, user_id="u-flow-2", agent_name="budget",
        tool_name="get_budget", arguments={"area": 50},
    )
    rejected = await agent_approval_service.reject(
        db_session, approval.approval_id, decided_by="u-flow-2", reason="不批准",
    )
    assert rejected.state == STATE_REJECTED

    result = await agent_approval_service.execute_approved(
        db_session, approval.approval_id, "u-flow-2",
    )
    assert result["executed"] is False
    assert "approved" in result["error"]


@pytest.mark.asyncio
async def test_approve_only_pending(db_session):
    """非 pending 状态不可批准（返回 None）"""
    approval = await agent_approval_service.create_approval(
        db_session, user_id="u-flow-3", agent_name="budget",
        tool_name="get_budget", arguments={},
    )
    await agent_approval_service.approve(db_session, approval.approval_id, "u-flow-3")
    # 再次 approve → None（已 approved）
    again = await agent_approval_service.approve(db_session, approval.approval_id, "u-flow-3")
    assert again is None


@pytest.mark.asyncio
async def test_expire_outdated(db_session):
    """超 TTL 的 pending → expire_outdated 批量置 expired"""
    approval = await agent_approval_service.create_approval(
        db_session, user_id="u-flow-4", agent_name="budget",
        tool_name="get_budget", arguments={},
    )
    # 手动把 expires_at 改到过去
    approval.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await db_session.commit()

    count = await agent_approval_service.expire_outdated(db_session)
    assert count >= 1

    # synchronize_session=False → 会话 identity map 未更新，用 populate_existing 强制从 DB 重读
    stmt = (
        select(AgentApproval)
        .where(AgentApproval.approval_id == approval.approval_id)
        .execution_options(populate_existing=True)
    )
    result = await db_session.execute(stmt)
    refreshed = result.scalar_one()
    assert refreshed.state == STATE_EXPIRED


# ── API 层 ──


async def _register(client: AsyncClient, phone: str = "13900008001", role: str = "homeowner") -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "Posture测试", "password": "test123456", "role": role},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_api_list_and_get_pending(client: AsyncClient, db_session):
    """GET /api/agents/approvals 列出 pending + GET /{id} 获取详情"""
    token = await _register(client, "13900008001")
    headers = {"Authorization": f"Bearer {token}"}
    me = await client.get("/api/auth/me", headers=headers)
    user_id = me.json()["id"]

    # 通过 service 创建一条 pending
    approval = await agent_approval_service.create_approval(
        db_session, user_id=user_id, agent_name="budget",
        tool_name="get_budget", arguments={"area": 100},
    )

    # list
    resp = await client.get("/api/agents/approvals", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["items"][0]["approval_id"] == approval.approval_id
    assert data["items"][0]["state"] == "pending"

    # get
    resp = await client.get(f"/api/agents/approvals/{approval.approval_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["tool_name"] == "get_budget"


@pytest.mark.asyncio
async def test_api_approve_and_execute(client: AsyncClient, db_session):
    """POST /approve → POST /execute 完整流程"""
    token = await _register(client, "13900008002")
    headers = {"Authorization": f"Bearer {token}"}
    me = await client.get("/api/auth/me", headers=headers)
    user_id = me.json()["id"]

    approval = await agent_approval_service.create_approval(
        db_session, user_id=user_id, agent_name="budget",
        tool_name="get_budget", arguments={"area": 100, "style": "modern"},
        project_id="p-test",
    )

    # approve
    resp = await client.post(
        f"/api/agents/approvals/{approval.approval_id}/approve",
        json={"reason": "同意"}, headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["state"] == "approved"

    # execute
    resp = await client.post(
        f"/api/agents/approvals/{approval.approval_id}/execute", headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["executed"] is True


@pytest.mark.asyncio
async def test_api_reject_then_execute_409(client: AsyncClient, db_session):
    """POST /reject → POST /execute 返回 409"""
    token = await _register(client, "13900008003")
    headers = {"Authorization": f"Bearer {token}"}
    me = await client.get("/api/auth/me", headers=headers)
    user_id = me.json()["id"]

    approval = await agent_approval_service.create_approval(
        db_session, user_id=user_id, agent_name="budget",
        tool_name="get_budget", arguments={},
    )

    resp = await client.post(
        f"/api/agents/approvals/{approval.approval_id}/reject",
        json={"reason": "拒绝"}, headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["state"] == "rejected"

    resp = await client.post(
        f"/api/agents/approvals/{approval.approval_id}/execute", headers=headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_api_non_owner_approve_404(client: AsyncClient, db_session):
    """非 owner（非 admin）approve 他人 approval → 404"""
    token_a = await _register(client, "13900008004")
    token_b = await _register(client, "13900008005")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    me_a = await client.get("/api/auth/me", headers=headers_a)
    user_a_id = me_a.json()["id"]

    approval = await agent_approval_service.create_approval(
        db_session, user_id=user_a_id, agent_name="budget",
        tool_name="get_budget", arguments={},
    )

    # B 尝试批准 A 的 approval → 404
    resp = await client.post(
        f"/api/agents/approvals/{approval.approval_id}/approve",
        json={"reason": "冒充"}, headers=headers_b,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_requires_auth(client: AsyncClient):
    """未认证访问 approvals API → 401"""
    resp = await client.get("/api/agents/approvals")
    assert resp.status_code == 401
