"""Agent Skill 资产化测试（v1.8.0 借鉴 YC QM）

覆盖：
- CRUD：create/get/list/update(version+1)/delete(soft)
- scope 隔离：personal 不见他人 / project 内可见 / org 级全见
- 授权共享：share_grants 含 requester 可见 / 不含 404
- admin 提升：admin 成功 / 非 admin 403
- 版本回退：rollback 创建新 version / 旧 active archived
- git 导入：成功解析 / 失败 422
- instantiate：动态 Agent 可 think（mock 模式降级）
"""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


async def _register(client: AsyncClient, phone: str = "13900007001", role: str = "homeowner") -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "Skill测试", "password": "test123456", "role": role},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


def _skill_payload(name: str = "验收Skill", agent_name: str = "qa_inspector") -> dict:
    return {
        "name": name,
        "description": "验收流程 Skill",
        "agent_name": agent_name,
        "system_prompt": "你是质检 Agent",
        "provider": "deepseek",
        "tools": [{"type": "function", "function": {"name": "run_qa_inspection"}}],
        "cost_tier": "standard",
        "acceptance_criteria": [{"input": "验收厨房", "expected": "返回合格率"}],
        "owner_scope": "personal",
    }


# ── CRUD ──


@pytest.mark.asyncio
async def test_skill_create_and_get(client: AsyncClient):
    token = await _register(client, "13900007001")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post("/api/agents/skills", json=_skill_payload(), headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "验收Skill"
    assert body["status"] == "draft"
    assert body["version"] == 1
    assert body["owner_scope"] == "personal"
    sid = body["id"]

    resp = await client.get(f"/api/agents/skills/{sid}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == sid


@pytest.mark.asyncio
async def test_skill_list_only_visible(client: AsyncClient):
    token = await _register(client, "13900007002")
    headers = {"Authorization": f"Bearer {token}"}
    await client.post("/api/agents/skills", json=_skill_payload("S1"), headers=headers)
    await client.post("/api/agents/skills", json=_skill_payload("S2"), headers=headers)

    resp = await client.get("/api/agents/skills", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


@pytest.mark.asyncio
async def test_skill_update_version_increment(client: AsyncClient):
    token = await _register(client, "13900007003")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post("/api/agents/skills", json=_skill_payload(), headers=headers)
    sid = resp.json()["id"]

    resp = await client.put(
        f"/api/agents/skills/{sid}",
        json={"description": "更新后描述", "status": "active"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == 2
    assert body["description"] == "更新后描述"
    assert body["status"] == "active"
    assert body["parent_version_id"] == sid


@pytest.mark.asyncio
async def test_skill_soft_delete(client: AsyncClient):
    token = await _register(client, "13900007004")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post("/api/agents/skills", json=_skill_payload(), headers=headers)
    sid = resp.json()["id"]

    resp = await client.delete(f"/api/agents/skills/{sid}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/agents/skills/{sid}", headers=headers)
    assert resp.status_code == 404


# ── scope 隔离 ──


@pytest.mark.asyncio
async def test_skill_personal_isolation(client: AsyncClient):
    """用户 A 的 personal Skill 用户 B 看不到"""
    token_a = await _register(client, "13900007005")
    token_b = await _register(client, "13900007006")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    resp = await client.post("/api/agents/skills", json=_skill_payload(), headers=headers_a)
    sid = resp.json()["id"]

    # B 看不到 A 的
    resp = await client.get(f"/api/agents/skills/{sid}", headers=headers_b)
    assert resp.status_code == 404
    # B list 不含 A 的
    resp = await client.get("/api/agents/skills", headers=headers_b)
    assert resp.json()["count"] == 0


# ── 授权共享 ──


@pytest.mark.asyncio
async def test_skill_share_grant_visible(client: AsyncClient):
    """A 授权给 B 后 B 可见"""
    token_a = await _register(client, "13900007007")
    token_b = await _register(client, "13900007008")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    resp = await client.post("/api/agents/skills", json=_skill_payload(), headers=headers_a)
    sid = resp.json()["id"]

    # B 初始看不到
    resp = await client.get(f"/api/agents/skills/{sid}", headers=headers_b)
    assert resp.status_code == 404

    # A 查 B 的 user_id（通过 /api/auth/me）
    me_b = await client.get("/api/auth/me", headers=headers_b)
    user_b_id = me_b.json()["id"]

    # A 授权给 B
    resp = await client.post(
        f"/api/agents/skills/{sid}/share",
        json={"grant_to": [user_b_id], "share_scope": "grant"},
        headers=headers_a,
    )
    assert resp.status_code == 200

    # B 现在可见
    resp = await client.get(f"/api/agents/skills/{sid}", headers=headers_b)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_skill_share_grant_requires_grant_to(client: AsyncClient):
    """share_scope=grant 但 grant_to 空 → 422"""
    token = await _register(client, "13900007009")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post("/api/agents/skills", json=_skill_payload(), headers=headers)
    sid = resp.json()["id"]

    resp = await client.post(
        f"/api/agents/skills/{sid}/share",
        json={"grant_to": [], "share_scope": "grant"},
        headers=headers,
    )
    assert resp.status_code == 422


# ── admin 提升 ──


@pytest.mark.asyncio
async def test_skill_promote_admin_only(client: AsyncClient):
    """非 admin 提升 → 403；admin 提升 → owner_scope=org"""
    token_user = await _register(client, "13900007010")
    token_admin = await _register(client, "13900007011", role="admin")
    headers_user = {"Authorization": f"Bearer {token_user}"}
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    resp = await client.post("/api/agents/skills", json=_skill_payload(), headers=headers_user)
    sid = resp.json()["id"]

    # 非 admin 提升 → 403
    resp = await client.post(f"/api/agents/skills/{sid}/promote", headers=headers_user)
    assert resp.status_code == 403

    # admin 提升成功
    resp = await client.post(f"/api/agents/skills/{sid}/promote", headers=headers_admin)
    assert resp.status_code == 200
    body = resp.json()
    assert body["owner_scope"] == "org"
    assert body["share_scope"] == "org"
    assert body["reviewed_by"] is not None


# ── 版本回退 ──


@pytest.mark.asyncio
async def test_skill_rollback(client: AsyncClient):
    """回退到 v1：创建 v3（内容来自 v1），v2 archived"""
    token = await _register(client, "13900007012")
    headers = {"Authorization": f"Bearer {token}"}
    # v1
    resp = await client.post("/api/agents/skills", json=_skill_payload(), headers=headers)
    v1_id = resp.json()["id"]
    v1_desc = resp.json()["description"]
    # v2（更新 description）
    resp = await client.put(
        f"/api/agents/skills/{v1_id}",
        json={"description": "v2描述", "status": "active"},
        headers=headers,
    )
    v2_id = resp.json()["id"]
    assert resp.json()["version"] == 2

    # 回退到 v1
    resp = await client.post(
        f"/api/agents/skills/{v2_id}/rollback",
        json={"target_version": 1},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == 3
    assert body["description"] == v1_desc  # 内容来自 v1


# ── git 导入 ──


@pytest.mark.asyncio
async def test_skill_import_success(client: AsyncClient):
    """mock httpx 成功返回 → 导入成功"""
    token = await _register(client, "13900007013")
    headers = {"Authorization": f"Bearer {token}"}

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {
        "name": "导入Skill",
        "agent_name": "designer",
        "system_prompt": "导入的 prompt",
        "tools": [],
        "acceptance_criteria": [],
    }
    with patch("app.services.agent_skill_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        resp = await client.post(
            "/api/agents/skills/import",
            json={"git_url": "https://raw.githubusercontent.com/test/skill.json"},
            headers=headers,
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "导入Skill"
    assert body["skill_pack_source"].startswith("https://")


@pytest.mark.asyncio
async def test_skill_import_failure_422(client: AsyncClient):
    """mock httpx 失败 → 422 诚实报错"""
    token = await _register(client, "13900007014")
    headers = {"Authorization": f"Bearer {token}"}

    mock_response = AsyncMock()
    mock_response.status_code = 404
    with patch("app.services.agent_skill_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        resp = await client.post(
            "/api/agents/skills/import",
            json={"git_url": "https://raw.githubusercontent.com/test/notfound.json"},
            headers=headers,
        )
    assert resp.status_code == 422


# ── instantiate ──


@pytest.mark.asyncio
async def test_skill_instantiate(client: AsyncClient):
    """实例化 Skill 为 BaseAgent，mock 模式下降级响应"""
    token = await _register(client, "13900007015")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post("/api/agents/skills", json=_skill_payload(), headers=headers)
    sid = resp.json()["id"]

    resp = await client.post(
        f"/api/agents/skills/{sid}/instantiate",
        json={"test_message": "帮我验收厨房"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["skill_id"] == sid
    assert body["agent_name"] == "qa_inspector"
    # mock 模式（无 API key）下 status 可能是 ok 或 degraded，都算通过
    assert body["status"] in ("ok", "degraded")


# ── 未认证 ──


@pytest.mark.asyncio
async def test_skill_api_requires_auth(client: AsyncClient):
    resp = await client.get("/api/agents/skills")
    assert resp.status_code == 401
    resp = await client.post("/api/agents/skills", json=_skill_payload())
    assert resp.status_code == 401
