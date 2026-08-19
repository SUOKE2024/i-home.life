"""v1.15.8 全量 P2 落地测试 — escrow 意图绑定 / 任务成功率评测 / 周报批量推送 / QA 字段采集

覆盖（对应 docs/frontier-borrowing 文档 P2 路线图落地）：
- P2-1（v1.15.5）escrow 买家付款绑定可验证支付意图 token —— 见 test_procurement_enhanced.py
- P2-4（v1.15.5）终端任务成功率评测 —— 见 test_eval_v1136.py
- P2-3（v1.15.7）周报 FC 批量主动推送（批量端点 + include_ai 省成本 + 鉴权）
- P2-4（v1.15.7）施工 QA 机器人友好字段采集（Robot-Ready QA checklist 端点）
"""
from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.config import get_settings
from app.models.project import Project
from app.models.user import User


# ════════════════════════════════════════════════════════════════
# P2-3 周报 FC 批量主动推送（v1.15.7 轮）
# ════════════════════════════════════════════════════════════════

class TestWeeklyBriefingBatch:
    async def _latest_user(self, db_session):
        return (await db_session.execute(
            select(User).order_by(User.created_at.desc()).limit(1)
        )).scalars().first()

    async def _make_project(self, db_session, user_id, status="active"):
        project = Project(
            id=str(uuid.uuid4()), owner_id=user_id, name="批量周报测试项目",
            status=status,
        )
        db_session.add(project)
        await db_session.flush()
        return project

    async def test_service_include_ai_false_skips_llm(self, db_session):
        """include_ai=False → 确定性数据段 + ai_suggestions.skipped（零 LLM 成本）"""
        from app.agents.orchestrator import OrchestratorAgent

        orch = OrchestratorAgent()
        try:
            result = await orch.generate_project_weekly_briefing(
                db_session, project_id="nonexistent-p2", include_ai=False,
            )
        finally:
            await orch.close()
        assert result["enabled"] is True
        assert result["briefing_type"] == "project_weekly"
        assert result["sections"]["ai_suggestions"]["skipped"] is True

    async def test_batch_endpoint_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/admin/projects/weekly-briefings")
        assert resp.status_code in (401, 403)

    async def test_batch_endpoint_normal_user_forbidden(self, client: AsyncClient):
        resp = await client.post(
            "/api/auth/register",
            json={"phone": "13900008111", "name": "批量周报普通用户", "password": "test123456"},
        )
        token = resp.json()["access_token"]
        resp = await client.get(
            "/api/admin/projects/weekly-briefings",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_batch_endpoint_admin_ok(self, client, db_session):
        """管理员调用 → 200，active 项目产出简报；completed 项目不推送"""
        from app.auth.paseto_handler import create_token

        owner = User(
            id=str(uuid.uuid4()), phone=f"138{uuid.uuid4().hex[:8]}",
            name="批量周报业主", role="user", hashed_password="x",
        )
        db_session.add(owner)
        await db_session.flush()
        active_project = await self._make_project(db_session, owner.id, status="active")
        await self._make_project(db_session, owner.id, status="completed")

        admin = User(
            id=str(uuid.uuid4()), phone=f"138{uuid.uuid4().hex[:8]}",
            name="批量周报管理员", role="admin", hashed_password="x",
        )
        db_session.add(admin)
        await db_session.commit()
        headers = {"Authorization": f"Bearer {create_token(admin.id, 'admin')}"}

        resp = await client.get(
            "/api/admin/projects/weekly-briefings?limit=10", headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["enabled"] is True
        assert body["briefing_type"] == "project_weekly_batch"
        assert body["total"] >= 1
        assert body["succeeded"] >= 1
        # active 项目在列表中，completed 项目不在
        ids = [p["project_id"] for p in body["projects"]]
        assert active_project.id in ids
        assert body["total"] == len(ids)
        # 默认 include_ai=False：AI 段诚实标注 skipped
        our = next(p for p in body["projects"] if p["project_id"] == active_project.id)
        assert our["sections"]["ai_suggestions"]["skipped"] is True

    async def test_batch_endpoint_flag_off(self, client, db_session, monkeypatch):
        """flag 关闭 → enabled=False 诚实标注（不查询不生成）"""
        from app.auth.paseto_handler import create_token

        monkeypatch.setattr(get_settings(), "project_weekly_briefing_enabled", False)
        admin = User(
            id=str(uuid.uuid4()), phone=f"138{uuid.uuid4().hex[:8]}",
            name="批量周报管理员2", role="admin", hashed_password="x",
        )
        db_session.add(admin)
        await db_session.commit()
        headers = {"Authorization": f"Bearer {create_token(admin.id, 'admin')}"}

        resp = await client.get("/api/admin/projects/weekly-briefings", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["enabled"] is False
        assert body["total"] == 0


# ════════════════════════════════════════════════════════════════
# P2-4 施工 QA 机器人友好字段采集（v1.15.7 轮）
# ════════════════════════════════════════════════════════════════

class TestRobotReadyChecklist:
    async def _make_owner_project(self, db_session):
        owner = User(
            id=str(uuid.uuid4()), phone=f"138{uuid.uuid4().hex[:8]}",
            name="QA 采集业主", role="user", hashed_password="x",
        )
        db_session.add(owner)
        await db_session.flush()
        project = Project(
            id=str(uuid.uuid4()), owner_id=owner.id, name="QA 采集测试项目",
            status="active",
        )
        db_session.add(project)
        await db_session.flush()
        return owner, project

    def _auth_headers(self, user_id: str):
        from app.auth.paseto_handler import create_token

        return {"Authorization": f"Bearer {create_token(user_id, 'user')}"}

    async def test_save_without_floorplan_422(self, client, db_session):
        """无户型方案 → 422 诚实标注（采集需先有 floorplan）"""
        owner, project = await self._make_owner_project(db_session)
        headers = self._auth_headers(owner.id)
        resp = await client.put(
            f"/api/construction/projects/{project.id}/robot-ready-checklist",
            json={"door_width": 0.9},
            headers=headers,
        )
        assert resp.status_code == 422
        assert "无户型方案" in resp.json()["detail"]

    async def test_save_and_assess_closed_loop(self, client, db_session):
        """采集 → 落库 → /robot-readiness 从 insufficient_data 变为可判定（闭环）"""
        from app.models.floorplan import FloorPlan

        owner, project = await self._make_owner_project(db_session)
        db_session.add(FloorPlan(
            id=str(uuid.uuid4()), project_id=project.id, name="QA 采集方案",
            data="{}", room_status="{}", is_active=True,
        ))
        await db_session.commit()
        headers = self._auth_headers(owner.id)

        # 1. 采集前评估：全 insufficient_data
        resp = await client.get(
            f"/api/construction/projects/{project.id}/robot-readiness", headers=headers,
        )
        assert resp.status_code == 200
        assert all(c["status"] == "insufficient_data" for c in resp.json()["checks"])

        # 2. 采集五项字段
        resp = await client.put(
            f"/api/construction/projects/{project.id}/robot-ready-checklist",
            json={
                "door_width": 0.9, "threshold_free": True, "outlet_height_ok": True,
                "pathway_width": 1.2, "floor_continuity": True, "note": "QA 巡检实测",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["saved"] is True
        assert body["fields"]["door_width"] == 0.9
        assert body["source"] == "floorplans.data.robot_ready"

        # 3. GET 读取
        resp = await client.get(
            f"/api/construction/projects/{project.id}/robot-ready-checklist", headers=headers,
        )
        assert resp.status_code == 200
        fields = resp.json()["fields"]
        assert fields["door_width"] == 0.9
        assert fields["threshold_free"] is True
        # 只暴露 5 个评估字段（note 属元信息不进入评估字段）
        assert set(fields) == {
            "door_width", "threshold_free", "outlet_height_ok",
            "pathway_width", "floor_continuity",
        }

        # 4. 采集后评估：五项全部 pass（闭环：QA 巡检 → 落库 → 评估可判定）
        resp = await client.get(
            f"/api/construction/projects/{project.id}/robot-readiness", headers=headers,
        )
        assert resp.status_code == 200
        checks = {c["id"]: c["status"] for c in resp.json()["checks"]}
        assert checks["RR1"] == "pass"   # 门洞 0.9 ≥ 0.85
        assert checks["RR2"] == "pass"
        assert checks["RR3"] == "pass"
        assert checks["RR4"] == "pass"   # 动线 1.2 ≥ 1.0
        assert checks["RR5"] == "pass"

    async def test_save_rejects_unknown_fields(self, client, db_session):
        """白名单过滤：未知字段不入库（防污染语义数据）"""
        from app.models.floorplan import FloorPlan

        owner, project = await self._make_owner_project(db_session)
        db_session.add(FloorPlan(
            id=str(uuid.uuid4()), project_id=project.id, name="QA 采集方案2",
            data="{}", room_status="{}", is_active=True,
        ))
        await db_session.commit()
        headers = self._auth_headers(owner.id)

        resp = await client.put(
            f"/api/construction/projects/{project.id}/robot-ready-checklist",
            json={"door_width": 0.9, "evil_field": "x"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert "evil_field" not in resp.json()["fields"]
        assert resp.json()["fields"]["door_width"] == 0.9

    async def test_non_owner_forbidden(self, client, db_session):
        """非项目成员采集 → 403"""
        from app.models.floorplan import FloorPlan

        owner, project = await self._make_owner_project(db_session)
        db_session.add(FloorPlan(
            id=str(uuid.uuid4()), project_id=project.id, name="QA 采集方案3",
            data="{}", room_status="{}", is_active=True,
        ))
        await db_session.commit()
        # 他人用户访问
        other = User(
            id=str(uuid.uuid4()), phone=f"138{uuid.uuid4().hex[:8]}",
            name="路人甲", role="user", hashed_password="x",
        )
        db_session.add(other)
        await db_session.commit()

        resp = await client.put(
            f"/api/construction/projects/{project.id}/robot-ready-checklist",
            json={"door_width": 0.9},
            headers=self._auth_headers(other.id),
        )
        assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════
# P2-4 终端任务成功率评测端点（v1.15.5 轮）
# ════════════════════════════════════════════════════════════════

class TestTaskSuccessEndpoint:
    async def _admin_headers(self, db_session):
        from app.auth.paseto_handler import create_token

        admin = User(
            id=str(uuid.uuid4()), phone=f"138{uuid.uuid4().hex[:8]}",
            name="达成率管理员", role="admin", hashed_password="x",
        )
        db_session.add(admin)
        await db_session.commit()
        return {"Authorization": f"Bearer {create_token(admin.id, 'admin')}"}

    async def test_flag_off_503(self, client, db_session):
        """llm_judge_enabled=False（默认）→ 503 诚实降级"""
        resp = await client.post(
            "/api/eval/llm-judge/task-success",
            json={"sample_size": 3},
            headers=await self._admin_headers(db_session),
        )
        assert resp.status_code == 503
        assert "llm_judge_enabled=False" in resp.json()["detail"]

    async def test_flag_on_no_samples_422(self, client, db_session, monkeypatch):
        """flag 开启但无轨迹样本 → 422 诚实标注（不伪造达成率）"""
        monkeypatch.setattr(get_settings(), "llm_judge_enabled", True)
        resp = await client.post(
            "/api/eval/llm-judge/task-success",
            json={"sample_size": 3},
            headers=await self._admin_headers(db_session),
        )
        assert resp.status_code == 422
        assert "无可评估" in resp.json()["detail"]

    async def test_normal_user_forbidden(self, client, db_session):
        """普通用户访问 → 403（require_admin）"""
        resp = await client.post(
            "/api/auth/register",
            json={"phone": "13900008112", "name": "达成率普通用户", "password": "test123456"},
        )
        token = resp.json()["access_token"]
        resp = await client.post(
            "/api/eval/llm-judge/task-success",
            json={"sample_size": 3},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
