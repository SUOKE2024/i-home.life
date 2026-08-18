"""供应商每日经营简报测试（v1.15.6，复用 daily-briefing FC 定时触发器模式）

覆盖:
- OrchestratorAgent.generate_supplier_daily_briefing 结构（确定性数据段 + AI 段）
- flag 关闭 → enabled=False 诚实标注
- 端点鉴权：未授权 401/403、普通用户 403、管理员 200
- AI 段 LLM 不可用时不伪造建议（error 段诚实标注）
"""
import uuid

import pytest
from httpx import AsyncClient

from app.config import get_settings
from app.agents.procurement import ProcurementAgent


@pytest.mark.asyncio
async def test_supplier_briefing_structure(monkeypatch, db_session):
    """简报结构：delivery_stats/supplier_ecosystem/escrow_stats 确定性数据段 + AI 段"""
    async def _fake_think(self, prompt, db=None, **kwargs):  # noqa: ANN001
        return "测试建议：优先处理 in_construction 交付单"

    monkeypatch.setattr(ProcurementAgent, "think", _fake_think)

    from app.agents.orchestrator import OrchestratorAgent
    orch = OrchestratorAgent()
    try:
        result = await orch.generate_supplier_daily_briefing(db_session)
    finally:
        await orch.close()

    assert result["enabled"] is True
    assert result["briefing_type"] == "supplier_daily"
    sections = result["sections"]
    assert sections["delivery_stats"]["source"] == "delivery_orders"
    assert isinstance(sections["delivery_stats"]["by_status"], dict)
    assert sections["supplier_ecosystem"]["source"] == "users/suppliers/products"
    assert {"supplier_users", "supplier_records", "product_count"} <= set(sections["supplier_ecosystem"])
    assert sections["escrow_stats"]["source"] == "escrow_payments"
    assert "ai_suggestions" in sections
    assert sections["ai_suggestions"]["content"] == "测试建议：优先处理 in_construction 交付单"


@pytest.mark.asyncio
async def test_supplier_briefing_flag_off(monkeypatch, db_session):
    """flag 关闭 → enabled=False（不查询不生成）"""
    monkeypatch.setattr(get_settings(), "supplier_daily_briefing_enabled", False)

    from app.agents.orchestrator import OrchestratorAgent
    orch = OrchestratorAgent()
    try:
        result = await orch.generate_supplier_daily_briefing(db_session)
    finally:
        await orch.close()

    assert result["enabled"] is False
    assert "supplier_daily_briefing_enabled=False" in result["note"]


@pytest.mark.asyncio
async def test_supplier_briefing_ai_section_honest_error(monkeypatch, db_session):
    """AI 段异常时不伪造建议：error 字段诚实标注"""
    async def _boom(self, prompt, db=None, **kwargs):  # noqa: ANN001
        raise RuntimeError("LLM 不可用")

    monkeypatch.setattr(ProcurementAgent, "think", _boom)

    from app.agents.orchestrator import OrchestratorAgent
    orch = OrchestratorAgent()
    try:
        result = await orch.generate_supplier_daily_briefing(db_session)
    finally:
        await orch.close()

    assert "error" in result["sections"]["ai_suggestions"]
    assert "LLM 不可用" in result["sections"]["ai_suggestions"]["error"]


@pytest.mark.asyncio
async def test_supplier_briefing_endpoint_requires_auth(client: AsyncClient):
    """未授权访问 /api/admin/supplier-daily-briefing → 401/403"""
    resp = await client.get("/api/admin/supplier-daily-briefing")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_supplier_briefing_endpoint_normal_user_forbidden(client: AsyncClient):
    """普通用户访问 → 403（require_platform_manage）"""
    resp = await client.post(
        "/api/auth/register",
        json={"phone": "13900007111", "name": "普通用户", "password": "test123456"},
    )
    token = resp.json()["access_token"]
    resp = await client.get(
        "/api/admin/supplier-daily-briefing",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_supplier_briefing_endpoint_admin_ok(client: AsyncClient, monkeypatch):
    """管理员调用 → 200，含确定性数据段（AI 段隔离 LLM）"""
    async def _fake_think(self, prompt, db=None, **kwargs):  # noqa: ANN001
        return "测试建议"

    monkeypatch.setattr(ProcurementAgent, "think", _fake_think)

    from app.auth.paseto_handler import create_token
    from app.database import async_session
    from app.models.user import User

    user_id = str(uuid.uuid4())
    async with async_session() as db:
        db.add(User(
            id=user_id, phone=f"138{uuid.uuid4().hex[:8]}", name="简报管理员",
            role="admin", hashed_password="x",
        ))
        await db.commit()
    headers = {"Authorization": f"Bearer {create_token(user_id, 'admin')}"}

    resp = await client.get("/api/admin/supplier-daily-briefing", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["briefing_type"] == "supplier_daily"
    assert "delivery_stats" in body["sections"]
