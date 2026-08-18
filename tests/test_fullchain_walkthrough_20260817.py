"""v1.15.2 全景全量全链路走查修复回归测试（2026-08-17 走查 findings）。

覆盖：
- P0-1 采购订单 delivered→completed 不再违反 DB CheckConstraint（此前 500）
- P0-2 预算审批流 5 态（submit/approve/execute/close）不再违反 DB 约束
- P0-3 质检验收 failed→rework 中间态不再违反 DB 约束（验收状态机可达）
- P1-1 以销定产接线：generate-from-bom 端点返回 demand_driven 优先级
- P1-2 结算 mark-paid / mark-disputed 端点（approved→paid / →disputed 可达）
- P1-3 任务 cancel / fail 端点（cancelled / failed 状态可达）
- P1-4 验收状态更新端点（INSPECTION_PASSED 事件链）
- P1-5 MEP 手动添加回路端点（flutter mepAddCircuit 契约）
- P2-1 前端契约对齐（webapp PATCH / console new_status / flutter PUT）
"""

import re
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.config import get_settings
from app.models.budget import Budget
from app.models.material import Material, BOMItem, MaterialCategory
from app.models.procurement import Supplier, ProcurementOrder
from app.models.settlement import Settlement
from app.services import procurement_service


# ════════════════════════════════════════════════════════════════
# 辅助
# ════════════════════════════════════════════════════════════════


async def _create_project(client: AsyncClient, headers: dict, name: str = "走查项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 100.0}, headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


# ════════════════════════════════════════════════════════════════
# P0-1 采购 delivered→completed 约束
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_procurement_order_delivered_to_completed_no_integrity_error(
    client: AsyncClient, auth_headers, db_session,
):
    """#1 delivered→completed 是状态机合法终态，此前 DB 约束缺失导致 500。"""
    project_id = await _create_project(client, auth_headers, name="采购完成项目")
    supplier = Supplier(name="测试供应商", category="走查材料", rating=4.5, is_active=True)
    db_session.add(supplier)
    await db_session.flush()
    order = ProcurementOrder(
        project_id=project_id,
        supplier_id=supplier.id,
        status="delivered",
        total_amount=300.0,
    )
    db_session.add(order)
    await db_session.commit()

    updated = await procurement_service.update_order_status(db_session, order.id, "completed")
    assert updated is not None
    assert updated.status == "completed"


# ════════════════════════════════════════════════════════════════
# P0-2 预算审批流（此前 submitted/executed/closed 违反约束）
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_budget_approval_flow_endpoints(client: AsyncClient, auth_headers, db_session):
    """#2 审批流 draft→submitted→approved→executed→closed 全链路可达且不违反约束。"""
    project_id = await _create_project(client, auth_headers, name="预算审批项目")
    budget = Budget(project_id=project_id)
    db_session.add(budget)
    await db_session.commit()
    await db_session.refresh(budget)
    budget_id = budget.id

    resp = await client.post(f"/api/budgets/{budget_id}/submit", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "submitted"

    resp = await client.post(f"/api/budgets/{budget_id}/approve", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "approved"

    resp = await client.post(f"/api/budgets/{budget_id}/execute", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "executed"

    resp = await client.post(f"/api/budgets/{budget_id}/close", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "closed"


@pytest.mark.asyncio
async def test_budget_approval_illegal_transition_400(client: AsyncClient, auth_headers, db_session):
    """#2 非法流转（draft 直接 approve）应 400 而非 500。"""
    project_id = await _create_project(client, auth_headers, name="预算非法流转项目")
    budget = Budget(project_id=project_id)
    db_session.add(budget)
    await db_session.commit()
    await db_session.refresh(budget)

    resp = await client.post(f"/api/budgets/{budget.id}/approve", headers=auth_headers)
    assert resp.status_code == 400, resp.text


# ════════════════════════════════════════════════════════════════
# P0-3 验收状态机 + P1-4 验收状态更新端点（此前 rework 违反约束 + 零调用）
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_inspection_status_rework_path_endpoint(client: AsyncClient, auth_headers):
    """#3 验收 failed→rework→passed 经新端点可达（此前 rework 写库 500）。"""
    project_id = await _create_project(client, auth_headers, name="验收流转项目")
    resp = await client.post(
        "/api/construction/tasks",
        json={"project_id": project_id, "name": "水电验收"}, headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    task_id = resp.json()["id"]

    resp = await client.post(
        "/api/construction/inspections",
        json={"task_id": task_id, "inspector": "测试监理", "score": 60}, headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    inspection_id = resp.json()["id"]

    resp = await client.patch(
        f"/api/construction/inspections/{inspection_id}/status",
        params={"status": "failed"}, headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "failed"

    # 此前 rework 写库违反 chk_inspection_status → 500
    resp = await client.patch(
        f"/api/construction/inspections/{inspection_id}/status",
        params={"status": "rework"}, headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "rework"

    resp = await client.patch(
        f"/api/construction/inspections/{inspection_id}/status",
        params={"status": "passed"}, headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "passed"


# ════════════════════════════════════════════════════════════════
# P1-2 结算 mark-paid / mark-disputed 端点
# ════════════════════════════════════════════════════════════════


async def _settlement_to_approved(client: AsyncClient, headers: dict, project_id: str):
    resp = await client.post(
        "/api/settlements",
        json={"project_id": project_id, "milestone": "completion"}, headers=headers,
    )
    assert resp.status_code == 201, resp.text
    resp = await client.post(f"/api/settlements/submit/{project_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    resp = await client.post(
        f"/api/settlements/request-review/{project_id}",
        json={"reason": "走查复核"}, headers=headers,
    )
    assert resp.status_code == 200, resp.text
    resp = await client.post(f"/api/settlements/approve-review/{project_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_settlement_mark_paid_endpoint(client: AsyncClient, auth_headers):
    """#4 结算 approved→paid 经新端点可达（此前 paid 状态生产不可达）。"""
    project_id = await _create_project(client, auth_headers, name="结算付款项目")
    await _settlement_to_approved(client, auth_headers, project_id)

    resp = await client.post(f"/api/settlements/{project_id}/mark-paid", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "paid"


@pytest.mark.asyncio
async def test_settlement_mark_disputed_endpoint(client: AsyncClient, auth_headers):
    """#4 结算 →disputed 经新端点可达。"""
    project_id = await _create_project(client, auth_headers, name="结算争议项目")
    resp = await client.post(
        "/api/settlements",
        json={"project_id": project_id, "milestone": "completion"}, headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text

    resp = await client.post(
        f"/api/settlements/{project_id}/mark-disputed",
        params={"reason": "工程量争议"}, headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "disputed"


@pytest.mark.asyncio
async def test_settlement_confirm_after_review_no_false_409(
    client: AsyncClient, auth_headers, db_session,
):
    """#15 confirm 409 条件修复：已复核（reviewed_by 已设）的 in_review 结算可正常确认。

    原条件 `status != "confirmed"`（状态机无此状态，恒真）导致复核后 confirm 永远 409。
    """
    project_id = await _create_project(client, auth_headers, name="结算确认项目")
    resp = await client.get("/api/auth/me", headers=auth_headers)
    user_id = resp.json()["id"]
    settlement = Settlement(project_id=project_id, status="in_review", review_required=True, reviewed_by=user_id)
    db_session.add(settlement)
    await db_session.commit()

    resp = await client.post(f"/api/settlements/confirm/{project_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "approved"


# ════════════════════════════════════════════════════════════════
# P1-3 任务 cancel / fail 端点
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_task_cancel_and_fail_endpoints(client: AsyncClient, auth_headers, db_session):
    """#5 cancelled / failed 状态经新端点可达（此前生产不可达）。

    fail 前置 claim 需实名认证（既有产品规则），直接构造 in_progress 任务经 HTTP 端点验证。
    """
    project_id = await _create_project(client, auth_headers, name="任务状态项目")

    # cancel：pending → cancelled
    resp = await client.post(
        "/api/tasks",
        json={"project_id": project_id, "task_type": "design", "title": "取消测试任务", "assigned_agent": "designer"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    cancel_task_id = resp.json()["id"]
    resp = await client.post(f"/api/tasks/{cancel_task_id}/cancel", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "cancelled"

    # fail：in_progress → failed（HTTP 端点；claim 实名门槛非本次断点）
    from app.models.orchestrator_task import OrchestratorTask
    resp = await client.get("/api/auth/me", headers=auth_headers)
    user_id = resp.json()["id"]
    fail_task = OrchestratorTask(
        project_id=project_id, task_type="construction", title="失败测试任务",
        assigned_agent="construction", status="in_progress", created_by=user_id,
    )
    db_session.add(fail_task)
    await db_session.commit()
    resp = await client.post(
        f"/api/tasks/{fail_task.id}/fail", params={"reason": "供应商缺货"}, headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "failed"


# ════════════════════════════════════════════════════════════════
# P1-1 以销定产接线
# ════════════════════════════════════════════════════════════════


async def _seed_bom(client: AsyncClient, headers: dict, db_session, project_id: str) -> None:
    cat = MaterialCategory(code="walkthrough_mat", name="走查材料")
    db_session.add(cat)
    await db_session.flush()
    material = Material(name="走查瓷砖", category_id=cat.id, unit="㎡", unit_price=50.0, sku="SKU-TILE-1")
    db_session.add(material)
    await db_session.flush()
    db_session.add(BOMItem(
        project_id=project_id, material_id=material.id,
        quantity=20.0, unit_price=50.0, total_price=1000.0, version=1,
    ))
    db_session.add(Supplier(name="走查供应商", category="走查材料", rating=4.5, is_active=True))
    await db_session.commit()


@pytest.mark.asyncio
async def test_generate_from_bom_demand_driven(
    client: AsyncClient, auth_headers, db_session, monkeypatch,
):
    """#6 以销定产默认开启：generate-from-bom 返回 demand_driven + 需求优先级。"""
    monkeypatch.setattr(get_settings(), "procurement_demand_driven_enabled", True)
    project_id = await _create_project(client, auth_headers, name="以销定产项目")
    await _seed_bom(client, auth_headers, db_session, project_id)

    resp = await client.post(f"/api/procurement/generate-from-bom/{project_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("demand_driven") is True
    assert body.get("enabled") is True
    orders = body.get("orders", [])
    assert orders, "应生成采购订单"
    assert "demand_priority" in orders[0], "订单应带需求优先级标注"


@pytest.mark.asyncio
async def test_generate_from_bom_fallback_when_flag_off(
    client: AsyncClient, auth_headers, db_session, monkeypatch,
):
    """#6 flag 关闭时回退原 generate_from_bom 行为（不破坏既有契约）。"""
    monkeypatch.setattr(get_settings(), "procurement_demand_driven_enabled", False)
    project_id = await _create_project(client, auth_headers, name="回退采购项目")
    await _seed_bom(client, auth_headers, db_session, project_id)

    resp = await client.post(f"/api/procurement/generate-from-bom/{project_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "demand_driven" not in body
    assert body.get("orders"), "flag 关闭仍应正常生成订单"


# ════════════════════════════════════════════════════════════════
# P1-5 MEP 手动添加回路
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_mep_manual_circuit_add_and_merge(client: AsyncClient, auth_headers):
    """#7 flutter mepAddCircuit 契约：POST /circuits 落库 + GET 合并手动回路。"""
    project_id = await _create_project(client, auth_headers, name="MEP回路项目")
    resp = await client.post(
        "/api/mep-kb/plans",
        json={"project_id": project_id, "room_name": "厨房", "room_type": "kitchen"},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    plan_id = resp.json()["id"]

    resp = await client.post(
        f"/api/mep-kb/plans/{plan_id}/circuits",
        json={"circuit_number": "K9", "circuit_type": "专用回路", "load": "2200W", "breaker": "20A"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["manual_count"] == 1
    assert any(c["circuit_no"] == "K9" and c.get("source") == "manual" for c in body["circuits"])

    resp = await client.get(f"/api/mep-kb/plans/{plan_id}/circuits", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    merged = resp.json()["circuits"]
    assert any(c["circuit_no"] == "K9" for c in merged), "GET 应合并手动添加的回路"


# ════════════════════════════════════════════════════════════════
# P2-1 前端契约对齐（确定性文件断言）
# ════════════════════════════════════════════════════════════════

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_frontend_contract_webapp_update_project_patch():
    """#8 webapp 更新项目改 PATCH（后端仅注册 PATCH，此前 PUT → 405）。"""
    src = (_REPO_ROOT / "webapp/src/lib/api.js").read_text(encoding="utf-8")
    m = re.search(r"updateProject[\s\S]{0,120}?method: '(PUT|PATCH)'", src)
    assert m, "webapp updateProject 方法未找到"
    assert m.group(1) == "PATCH", f"updateProject 应为 PATCH，实际 {m.group(1)}"


def test_frontend_contract_console_worker_status_param():
    """#8 console 更新工人匹配状态 query 参数名对齐后端 new_status（此前 ?status= → 422）。"""
    src = (_REPO_ROOT / "console-src/src/services/api-client.ts").read_text(encoding="utf-8")
    # query 参数名必须是 new_status（后端 Query(..., alias 无，必填 new_status)）
    seg = re.search(r"/api/workers/matches/\$\{encodeURIComponent\(matchId\)\}/status\?([^'`]+)", src)
    assert seg, "未找到工人匹配状态更新 URL"
    assert seg.group(1).startswith("new_status="), f"query 参数应为 new_status，实际: {seg.group(1)}"


def test_frontend_contract_flutter_survey_put_and_circuit_post():
    """#8 flutter 更新量房改 PUT（后端仅 PUT）；添加回路 POST 契约保留（后端已补端点）。"""
    src = (_REPO_ROOT / "flutter_app/lib/services/api.dart").read_text(encoding="utf-8")
    assert "put('/surveys/$surveyId', body)" in src, "updateSurvey 应为 PUT"
    assert "post('/mep-kb/plans/$planId/circuits', body)" in src, "mepAddCircuit 保持 POST"
