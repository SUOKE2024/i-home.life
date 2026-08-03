"""F46 生态桥接优先级 API 集成测试

覆盖端点:
- GET /api/ecosystem/status    (生态桥接状态报告)
- GET /api/ecosystem/bridges   (生态桥接优先级列表)
"""
import pytest
from httpx import AsyncClient


async def _auth_headers(client: AsyncClient, phone: str = "13950050001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "生态测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── 鉴权 ──


@pytest.mark.asyncio
async def test_ecosystem_unauthorized(client: AsyncClient):
    """未认证用户不能查看生态状态"""
    resp = await client.get("/api/ecosystem/status")
    assert resp.status_code == 401

    resp = await client.get("/api/ecosystem/bridges")
    assert resp.status_code == 401


# ── 状态报告 ──


@pytest.mark.asyncio
async def test_status_report_ecosystems(client: AsyncClient):
    """status 返回 4 个生态，含 configured/status/note 字段"""
    headers = await _auth_headers(client, "13950050002")
    resp = await client.get("/api/ecosystem/status", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["bridges"]) == 4
    for bridge in data["bridges"]:
        assert "configured" in bridge
        assert "status" in bridge
        assert "note" in bridge
        assert "required_env_keys" in bridge
    assert "updated_at" in data
    assert "honest_note" in data


@pytest.mark.asyncio
async def test_status_honest_degradation(client: AsyncClient):
    """测试环境无 env key：configured=False 且 status=requires_api_key，note 诚实标注"""
    headers = await _auth_headers(client, "13950050003")
    resp = await client.get("/api/ecosystem/status", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    for bridge in data["bridges"]:
        assert bridge["configured"] is False
        assert bridge["status"] == "requires_api_key"
        assert "诚实" in bridge["note"] and "501" in bridge["note"]


# ── 优先级列表 ──


@pytest.mark.asyncio
async def test_bridges_priority_order(client: AsyncClient):
    """bridges 按 priority 升序，含优先级策略说明"""
    headers = await _auth_headers(client, "13950050004")
    resp = await client.get("/api/ecosystem/bridges", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    priorities = [b["priority"] for b in data["bridges"]]
    assert priorities == sorted(priorities)
    assert [b["key"] for b in data["bridges"]] == ["mijia", "harmony", "homekit", "tuya"]
    assert "priority_strategy" in data
    assert "米家" in data["priority_strategy"] and "华为鸿蒙" in data["priority_strategy"]
