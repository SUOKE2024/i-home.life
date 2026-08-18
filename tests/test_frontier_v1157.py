"""v1.15.7 第二轮前沿借鉴落地测试 — ATH 信任层 / 记忆衰减+org 共享 / 项目周报 / Robot-Ready

覆盖（对应第二轮 2026 前沿诊断报告执行）：
- P0-A ATH/国标信任层：governance_audit.ath_trust_layer 5 项确定性检查
- P0-B 记忆分级：search_cases 时间衰减重排（flag 开关）+ org 共享记忆（服务/API/403）
- P1-C 项目周报：六段确定性数据 + AI 段 best-effort + 403/404/503 门控
- P1-D Robot-Ready：五项校验 insufficient_data 诚实标注 + 语义导出 schema v0.1
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.config import get_settings
from app.models.agent_case import AgentCase
from app.models.agent_memory import AgentMemory
from app.models.project import Project
from app.models.user import User
from app.services.agent_case_service import search_cases
from app.services.agent_governance_audit import run_governance_audit
from app.services import agent_memory_service

settings = get_settings()


# ════════════════════════════════════════════════════════════════
# P0-A ATH/国标信任层审计
# ════════════════════════════════════════════════════════════════

class TestATHTrustLayer:
    def test_owasp_findings_unchanged(self):
        """OWASP 10 项保持独立（兼容既有断言），ATH 为独立章节"""
        report = run_governance_audit()
        assert len(report["findings"]) == 10
        assert [f["id"] for f in report["findings"]] == [f"AG{i}" for i in range(1, 11)]

    def test_ath_section_five_checks(self):
        report = run_governance_audit()
        ath = report["ath_trust_layer"]
        assert ath is not None
        assert len(ath["findings"]) == 5
        assert [f["id"] for f in ath["findings"]] == [f"ATH{i}" for i in range(1, 6)]
        assert ath["summary"]["total"] == 5
        assert ath["summary"]["score"] == f"{ath['summary']['pass']}/5"
        # 默认全 flag 开启 → 5/5（v1.15.5 信任层 + v1.15.7 审计均为 pass）
        assert ath["summary"]["pass"] == 5

    def test_ath_checks_cover_evidence_chain(self):
        report = run_governance_audit()
        ath3 = next(f for f in report["ath_trust_layer"]["findings"] if f["id"] == "ATH3")
        assert ath3["status"] == "pass"
        assert "trace_id" in ath3["evidence"]

    def test_ath_trace_off_warns(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "agent_trace_persist_enabled", False)
        report = run_governance_audit()
        ath3 = next(f for f in report["ath_trust_layer"]["findings"] if f["id"] == "ATH3")
        assert ath3["status"] == "warn"


# ════════════════════════════════════════════════════════════════
# P0-B 记忆时间衰减 + org 共享记忆
# ════════════════════════════════════════════════════════════════

async def _seed_cases(db_session):
    now = datetime.now(timezone.utc)
    old = AgentCase(
        id=str(uuid.uuid4()), scope="personal", owner_id="user_decay",
        agent_name="designer", task_intent="北欧风格客厅设计", approach="[]",
        outcome="success", quality_score=0.95, created_by="user_decay",
        created_at=now - timedelta(days=365),
    )
    fresh = AgentCase(
        id=str(uuid.uuid4()), scope="personal", owner_id="user_decay",
        agent_name="designer", task_intent="北欧风格客厅设计", approach="[]",
        outcome="success", quality_score=0.8, created_by="user_decay",
        created_at=now,
    )
    db_session.add_all([old, fresh])
    await db_session.flush()
    return old, fresh


class TestMemoryTimeDecay:
    async def test_decay_ranks_fresh_over_old(self, db_session, monkeypatch):
        monkeypatch.setattr(get_settings(), "memory_time_decay_enabled", True)
        monkeypatch.setattr(get_settings(), "memory_decay_half_life_days", 30.0)
        old, fresh = await _seed_cases(db_session)
        results = await search_cases(
            db_session, task_intent="北欧风格客厅设计",
            owner_id="user_decay", scope="personal", limit=5,
        )
        # 一年陈旧的 0.95 衰减后 < 新鲜的 0.8（exp(-365/30)≈5e-6）
        assert results[0].id == fresh.id
        assert results[-1].id == old.id

    async def test_decay_off_old_wins(self, db_session, monkeypatch):
        monkeypatch.setattr(get_settings(), "memory_time_decay_enabled", False)
        old, fresh = await _seed_cases(db_session)
        results = await search_cases(
            db_session, task_intent="北欧风格客厅设计",
            owner_id="user_decay", scope="personal", limit=5,
        )
        assert results[0].id == old.id  # quality-only 排序：0.95 旧 Case 第一


class TestOrgSharedMemory:
    async def test_get_org_memories_service(self, db_session):
        db_session.add(AgentMemory(
            id=str(uuid.uuid4()), user_id="admin_1", category="fact",
            memory_key="platform_guide", memory_value="平台装修指南",
            scope=agent_memory_service.SCOPE_ORG,
        ))
        await db_session.flush()
        rows = await agent_memory_service.get_org_memories(db_session)
        assert any(r.memory_key == "platform_guide" for r in rows)

    async def test_org_list_endpoint(self, client, auth_headers, db_session):
        db_session.add(AgentMemory(
            id=str(uuid.uuid4()), user_id="admin_1", category="fact",
            memory_key="platform_guide", memory_value="平台装修指南",
            scope=agent_memory_service.SCOPE_ORG,
        ))
        await db_session.flush()
        resp = await client.get("/api/agents/memory/org", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert any(i["key"] == "platform_guide" for i in body["items"])

    async def test_org_write_non_admin_403(self, client, auth_headers):
        resp = await client.post(
            "/api/agents/memory", headers=auth_headers,
            json={
                "category": "fact", "key": "spam", "value": "x",
                "scope": "org",
            },
        )
        assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════
# P1-C 用户侧项目周报
# ════════════════════════════════════════════════════════════════

class TestProjectWeeklyBriefing:
    async def _latest_user(self, db_session):
        return (await db_session.execute(
            select(User).order_by(User.created_at.desc()).limit(1)
        )).scalars().first()

    async def _make_project(self, db_session, user_id):
        project = Project(
            id=str(uuid.uuid4()), owner_id=user_id, name="周报测试项目",
            status="active",
        )
        db_session.add(project)
        await db_session.flush()
        return project

    async def test_briefing_owner_ok(self, client, auth_headers, db_session):
        user = await self._latest_user(db_session)
        project = await self._make_project(db_session, user.id)
        resp = await client.get(
            f"/api/agents/projects/{project.id}/weekly-briefing", headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["briefing_type"] == "project_weekly"
        assert body["project_id"] == project.id
        sections = body["sections"]
        for key in ("project", "tasks", "budget", "procurement", "inspections", "milestones"):
            assert key in sections, f"缺数据段 {key}"
        assert sections["project"]["name"] == "周报测试项目"
        assert "source" in sections["project"]
        # AI 段 best-effort：无 key 时 mock 或 error，绝不抛 500
        assert "ai_suggestions" in sections

    async def test_briefing_non_owner_403(self, client, auth_headers, db_session):
        project = await self._make_project(db_session, "other_user_777")
        resp = await client.get(
            f"/api/agents/projects/{project.id}/weekly-briefing", headers=auth_headers,
        )
        assert resp.status_code == 403

    async def test_briefing_not_found_404(self, client, auth_headers):
        resp = await client.get(
            "/api/agents/projects/nonexistent-999/weekly-briefing", headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_briefing_flag_off_503(self, client, auth_headers, db_session, monkeypatch):
        monkeypatch.setattr(get_settings(), "project_weekly_briefing_enabled", False)
        user = await self._latest_user(db_session)
        project = await self._make_project(db_session, user.id)
        resp = await client.get(
            f"/api/agents/projects/{project.id}/weekly-briefing", headers=auth_headers,
        )
        assert resp.status_code == 503


# ════════════════════════════════════════════════════════════════
# P1-D Robot-Ready 校验 + 空间语义导出
# ════════════════════════════════════════════════════════════════

class TestRobotReady:
    async def _latest_user(self, db_session):
        return (await db_session.execute(
            select(User).order_by(User.created_at.desc()).limit(1)
        )).scalars().first()

    async def _make_project(self, db_session, user_id):
        project = Project(
            id=str(uuid.uuid4()), owner_id=user_id, name="机器人友好项目",
            status="active",
        )
        db_session.add(project)
        await db_session.flush()
        return project

    async def test_no_data_all_insufficient(self, client, auth_headers, db_session):
        from app.services.robot_ready_service import ROBOT_READY_CHECKS
        user = await self._latest_user(db_session)
        project = await self._make_project(db_session, user.id)
        resp = await client.get(
            f"/api/construction/projects/{project.id}/robot-readiness", headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["checks"]) == len(ROBOT_READY_CHECKS)
        assert all(c["status"] == "insufficient_data" for c in body["checks"])
        assert "数据不足" in body["summary"]["readiness_note"]
        assert body["summary"]["fail"] == 0  # 全缺不判不合格（诚实降级红线）

    async def test_semantic_fields_judged(self, client, auth_headers, db_session):
        from app.models.floorplan import FloorPlan
        user = await self._latest_user(db_session)
        project = await self._make_project(db_session, user.id)
        fp = FloorPlan(
            id=str(uuid.uuid4()), project_id=project.id, name="方案A", data="{}",
            room_status=json.dumps({"door_width": 0.9, "threshold_free": True}),
        )
        db_session.add(fp)
        await db_session.flush()
        resp = await client.get(
            f"/api/construction/projects/{project.id}/robot-readiness", headers=auth_headers,
        )
        body = resp.json()
        rr1 = next(c for c in body["checks"] if c["id"] == "RR1")
        rr2 = next(c for c in body["checks"] if c["id"] == "RR2")
        assert rr1["status"] == "pass"  # 0.9 ≥ 0.85
        assert rr2["status"] == "pass"

    async def test_narrow_door_fails(self, client, auth_headers, db_session):
        from app.models.floorplan import FloorPlan
        user = await self._latest_user(db_session)
        project = await self._make_project(db_session, user.id)
        db_session.add(FloorPlan(
            id=str(uuid.uuid4()), project_id=project.id, name="方案B", data="{}",
            room_status=json.dumps({"door_width": 0.7}),
        ))
        await db_session.flush()
        resp = await client.get(
            f"/api/construction/projects/{project.id}/robot-readiness", headers=auth_headers,
        )
        rr1 = next(c for c in resp.json()["checks"] if c["id"] == "RR1")
        assert rr1["status"] == "fail"

    async def test_export_schema_v01(self, client, auth_headers, db_session):
        user = await self._latest_user(db_session)
        project = await self._make_project(db_session, user.id)
        resp = await client.get(
            f"/api/construction/projects/{project.id}/robot-ready-export", headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["schema_version"] == "spatial-semantics/0.1"
        assert "floorplans" in body and "rooms" in body
        assert "gaps" in body and len(body["gaps"]) >= 2  # 无数据时诚实标注缺口
        assert body["robot_ready"]["insufficient_data"] == 5

    async def test_export_non_owner_403(self, client, auth_headers, db_session):
        project = await self._make_project(db_session, "other_user_888")
        resp = await client.get(
            f"/api/construction/projects/{project.id}/robot-ready-export", headers=auth_headers,
        )
        assert resp.status_code == 403
