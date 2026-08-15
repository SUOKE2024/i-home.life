"""Agent 运行时治理安全审计测试（v1.12.x，OWASP Agentic Skills Top 10 对照）

覆盖：
- run_governance_audit：10 个 AG 类别齐全（AG1-AG10），每项含 status/evidence
- 汇总统计：total/pass/warn/fail/score 一致
- 确定性判定：mcp_security_hardening_enabled=True → AG1 pass
- posture=dangerous → AG2 warn（过度自主）
- allow_plaintext_session=True → AG9 warn（PII 明文会话）
- API：/api/admin/agent-governance-audit 非平台管理员 403 / 管理员 200

测试隔离：monkeypatch.setattr(get_settings(), "flag", value)，teardown 自动还原
"""
import pytest
from httpx import AsyncClient

from app.config import get_settings
from app.services.agent_governance_audit import (
    AGENTIC_SKILL_RISKS, run_governance_audit,
)


# ── 确定性审计逻辑 ──


def test_audit_returns_ten_findings():
    report = run_governance_audit()
    findings = report["findings"]
    assert len(findings) == 10
    assert [f["id"] for f in findings] == [f"AG{i}" for i in range(1, 11)]
    for f in findings:
        assert f["status"] in ("pass", "warn", "fail")
        assert f["evidence"]
        assert f["name"]
        assert f["control"]


def test_audit_summary_consistent():
    report = run_governance_audit()
    s = report["summary"]
    statuses = [f["status"] for f in report["findings"]]
    assert s["total"] == 10
    assert s["pass"] == statuses.count("pass")
    assert s["warn"] == statuses.count("warn")
    assert s["fail"] == statuses.count("fail")
    assert s["score"] == f"{s['pass']}/{s['total']}"
    assert report["framework"] == "OWASP Agentic Skills Top 10 (2026)"


def test_audit_ag1_pass_when_hardening_enabled():
    """mcp_security_hardening_enabled=True（默认）→ AG1 提示注入防护 pass"""
    report = run_governance_audit()
    ag1 = next(f for f in report["findings"] if f["id"] == "AG1")
    assert ag1["status"] == "pass"
    assert "mcp_security_hardening_enabled" in ag1["evidence"]


def test_audit_ag2_warn_on_dangerous_posture(monkeypatch):
    """agent_security_posture=dangerous → AG2 过度自主 warn"""
    monkeypatch.setattr(get_settings(), "agent_security_posture", "dangerous")
    report = run_governance_audit()
    ag2 = next(f for f in report["findings"] if f["id"] == "AG2")
    assert ag2["status"] == "warn"
    assert "dangerous" in ag2["evidence"]


def test_audit_ag9_warn_on_plaintext_session(monkeypatch):
    """allow_plaintext_session=True → AG9 敏感信息泄漏 warn"""
    monkeypatch.setattr(get_settings(), "allow_plaintext_session", True)
    report = run_governance_audit()
    ag9 = next(f for f in report["findings"] if f["id"] == "AG9")
    assert ag9["status"] == "warn"
    assert "allow_plaintext_session" in ag9["evidence"]


def test_audit_ag9_pass_when_session_encrypted(monkeypatch):
    """会话加密（allow_plaintext_session=False）+ PII 掩码 → AG9 pass"""
    monkeypatch.setattr(get_settings(), "allow_plaintext_session", False)
    report = run_governance_audit()
    ag9 = next(f for f in report["findings"] if f["id"] == "AG9")
    assert ag9["status"] == "pass"
    assert "pii_masking_enabled" in ag9["evidence"]


def test_risk_definitions_complete():
    """AGENTIC_SKILL_RISKS 定义完整（id/name/desc/control 齐全）"""
    assert len(AGENTIC_SKILL_RISKS) == 10
    for risk in AGENTIC_SKILL_RISKS:
        assert set(risk.keys()) == {"id", "name", "desc", "control"}


# ── API 端点 ──


@pytest.mark.asyncio
async def test_governance_audit_requires_platform_admin(client: AsyncClient, auth_headers: dict):
    """非平台管理员访问返回 403"""
    resp = await client.get("/api/admin/agent-governance-audit", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_governance_audit_admin_ok(client: AsyncClient):
    """平台管理员可获得 10 项审计结果"""
    import uuid as _uuid
    from app.database import async_session
    from app.models.user import User
    from app.auth.paseto_handler import create_token

    user_id = str(_uuid.uuid4())
    async with async_session() as db:
        db.add(User(id=user_id, phone=f"138{_uuid.uuid4().hex[:8]}", name="治理审计管理员", role="admin", hashed_password="x"))
        await db.commit()
    headers = {"Authorization": f"Bearer {create_token(user_id, 'admin')}"}

    resp = await client.get("/api/admin/agent-governance-audit", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["findings"]) == 10
    assert data["summary"]["total"] == 10
    assert "recommendations" in data
    assert "generated_at" in data
