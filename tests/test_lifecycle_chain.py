"""项目全链路（创建→完工验收）断裂修复测试

覆盖 spec docs/superpowers/specs/2026-08-04-lifecycle-chain-fix-design.md 的 10 个验收用例：
1-5 事件总线编排（受 lifecycle_orchestration_enabled flag 门控）
6-7 phase 状态机 + PATCH 不再绕过
8-9 竣工验收强制闸门
10 timeline 读 phase 直接驱动
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.database import async_session
from app.models.budget import Budget, BudgetLine
from app.models.construction import ConstructionTask, Inspection
from app.models.change_order import ChangeOrder
from app.models.material import Material, BOMItem, MaterialCategory
from app.models.procurement import ProcurementOrder
from app.models.quality import QualityIssue
from app.services.orchestration_rules import register_all_rules


# ── 辅助 ──

async def _register_and_get_token(client: AsyncClient, phone: str = "13900002001") -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "全链路测试用户", "password": "test123456"},
    )
    return resp.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "全链路项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 100.0}, headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.fixture(autouse=True)
def _enable_lifecycle(monkeypatch):
    """启用事件总线编排（默认 False，测试中开启）"""
    monkeypatch.setattr("app.services.lifecycle_events._enabled", lambda: True)


@pytest.fixture(scope="module", autouse=True)
def _register_rules():
    """模块级注册编排规则一次（event_bus 单例，避免重复注册）"""
    register_all_rules()


# ====================================================================
# 1-5 事件总线编排
# ====================================================================

@pytest.mark.asyncio
async def test_1_create_project_emits_event_and_auto_creates_budget(client: AsyncClient):
    """断裂 1：项目创建 → 自动建预算（PROJECT_CREATED 事件触发）"""
    token = await _register_and_get_token(client, "13900002011")
    headers = _headers(token)
    project_id = await _create_project(client, headers, name="自动建预算项目")

    # 事件 handler 用 async_session_factory，操作完成后再查
    async with async_session() as db:
        result = await db.execute(select(Budget).where(Budget.project_id == project_id))
        budget = result.scalar_one_or_none()
    assert budget is not None, "项目创建后应自动创建预算"
    assert budget.project_id == project_id


@pytest.mark.asyncio
async def test_2_bom_snapshot_emits_procurement(client: AsyncClient, db_session):
    """断裂 1：BOM 版本定稿 → 自动采购建议（BOM_GENERATED 事件触发）"""
    from app.models.procurement import Supplier
    token = await _register_and_get_token(client, "13900002012")
    headers = _headers(token)
    project_id = await _create_project(client, headers, name="BOM采购项目")

    # 构造 BOM：物料分类+物料+BOMItem + 同品类活跃供应商（generate_from_bom 需匹配）
    cat = MaterialCategory(code="mep_test", name="测试水电材料")
    db_session.add(cat)
    await db_session.flush()
    material = Material(name="PVC管", category_id=cat.id, unit="m", unit_price=10.0, sku="SKU-PVC-1")
    db_session.add(material)
    await db_session.flush()
    db_session.add(BOMItem(
        project_id=project_id, material_id=material.id,
        quantity=10.0, unit_price=10.0, total_price=100.0, version=1,
    ))
    db_session.add(Supplier(name="测试供应商", category="测试水电材料", rating=4.5, is_active=True))
    await db_session.commit()

    # 调用 snapshot_bom_version（发射 BOM_GENERATED 事件）
    from app.services.material_service import snapshot_bom_version
    result = await snapshot_bom_version(db_session, project_id)
    assert result["new_version"] == 2

    # 验证自动生成了采购订单（handler 调 generate_from_bom）
    async with async_session() as db:
        orders = await db.execute(
            select(ProcurementOrder).where(ProcurementOrder.project_id == project_id)
        )
        orders = list(orders.scalars().all())
    assert len(orders) >= 1, "BOM 定稿后应自动生成采购订单"


@pytest.mark.asyncio
async def test_3_material_delivered_advances_task_to_ready(client: AsyncClient, db_session):
    """断裂 1+5：材料到货 → 施工任务就绪（MATERIAL_DELIVERED 事件触发）"""
    from app.models.procurement import Supplier
    token = await _register_and_get_token(client, "13900002013")
    headers = _headers(token)
    project_id = await _create_project(client, headers, name="材料到货项目")

    # 构造 pending 任务 + shipped 采购订单（需先建 supplier）
    task = ConstructionTask(
        project_id=project_id, name="水电任务", phase="mep", status="pending",
    )
    db_session.add(task)
    await db_session.flush()
    supplier = Supplier(name="测试供应商", category="mep")
    db_session.add(supplier)
    await db_session.flush()
    order = ProcurementOrder(
        project_id=project_id, supplier_id=supplier.id, total_amount=100.0,
        status="shipped", construction_task_id=task.id,
    )
    db_session.add(order)
    await db_session.commit()

    # 调 update_order_status → delivered（发射 MATERIAL_DELIVERED 事件）
    from app.services.procurement_service import update_order_status
    await update_order_status(db_session, order.id, "delivered")

    # 验证 task 被推进为 ready
    async with async_session() as db:
        t = await db.execute(select(ConstructionTask).where(ConstructionTask.id == task.id))
        t = t.scalar_one()
    assert t.status == "ready", f"材料到货后任务应为 ready，实际 {t.status}"


@pytest.mark.asyncio
async def test_4_inspection_passed_advances_successor_chain(client: AsyncClient, db_session):
    """断裂 5：验收通过 → 后继任务链推进（原 pass 占位已补全）"""
    token = await _register_and_get_token(client, "13900002014")
    headers = _headers(token)
    project_id = await _create_project(client, headers, name="后继链推进项目")

    # 构造任务链：pred → succ（succ.predecessor_id = pred.id）
    pred = ConstructionTask(project_id=project_id, name="前置任务", phase="mep", status="in_progress")
    db_session.add(pred)
    await db_session.flush()
    succ = ConstructionTask(
        project_id=project_id, name="后继任务", phase="mep", status="pending",
        predecessor_id=pred.id,
    )
    db_session.add(succ)
    await db_session.flush()
    # 给前置任务创建验收记录
    inspection = Inspection(task_id=pred.id, status="pending")
    db_session.add(inspection)
    await db_session.commit()

    # 调 update_inspection_status → passed（发射 INSPECTION_PASSED 事件）
    from app.services.construction_service import update_inspection_status
    await update_inspection_status(db_session, inspection.id, "passed")

    # 验证：pred 标记 completed，succ 推进为 ready
    async with async_session() as db:
        pred_result = await db.execute(select(ConstructionTask).where(ConstructionTask.id == pred.id))
        succ_result = await db.execute(select(ConstructionTask).where(ConstructionTask.id == succ.id))
        pred_db = pred_result.scalar_one()
        succ_db = succ_result.scalar_one()
    assert pred_db.status == "completed", f"前置任务应为 completed，实际 {pred_db.status}"
    assert succ_db.status == "ready", f"后继任务应为 ready，实际 {succ_db.status}"


@pytest.mark.asyncio
async def test_5_change_order_approved_updates_budget(client: AsyncClient, db_session):
    """断裂 1：变更审批通过 → 预算更新（CHANGE_ORDER_APPROVED 事件触发）"""
    token = await _register_and_get_token(client, "13900002015")
    headers = _headers(token)
    project_id = await _create_project(client, headers, name="变更预算项目")

    # 项目创建时 PROJECT_CREATED handler 已自动建预算，直接复用
    from app.services.budget_service import get_budget
    budget = await get_budget(db_session, project_id)
    assert budget is not None, "项目创建后应自动建预算"

    # 创建 reviewing 变更单（直接 db 建到 reviewing，避开 pending→reviewing 状态机）
    change_order = ChangeOrder(
        project_id=project_id, title="增加吊顶", description="客厅增加吊顶",
        status="reviewing", cost_impact=5000.0,
    )
    db_session.add(change_order)
    await db_session.commit()

    # 调 approve_change_order（发射 CHANGE_ORDER_APPROVED 事件）
    from app.services.change_order_service import approve_change_order
    await approve_change_order(db_session, change_order.id, "test-approver")

    # 验证：budget 追加了 change_order 行
    async with async_session() as db:
        lines = await db.execute(
            select(BudgetLine).where(BudgetLine.budget_id == budget.id, BudgetLine.category == "change_order")
        )
        change_lines = list(lines.scalars().all())
    assert len(change_lines) >= 1, "变更审批后应追加 change_order 预算行"
    assert change_lines[0].estimated_amount == 5000.0


# ====================================================================
# 6-7 phase 状态机 + PATCH 不再绕过
# ====================================================================

@pytest.mark.asyncio
async def test_6_phase_state_machine_rejects_backward(client: AsyncClient, db_session):
    """断裂 4：phase 状态机不允许后退或跳跃"""
    token = await _register_and_get_token(client, "13900002016")
    headers = _headers(token)
    project_id = await _create_project(client, headers, name="phase状态机项目")

    # 直接 db 推进 phase
    from app.services.project_service import update_project_phase, ProjectPhaseError
    await update_project_phase(db_session, project_id, "design")
    await update_project_phase(db_session, project_id, "budget")

    # 尝试后退到 design → 应抛 ProjectPhaseError
    raised: Exception | None = None
    try:
        await update_project_phase(db_session, project_id, "design")
    except Exception as e:
        raised = e
    actual_type = type(raised).__name__ if raised else "None"
    assert isinstance(raised, ProjectPhaseError), f"后退应抛 ProjectPhaseError，实际 {actual_type}"

    # 尝试跳跃到 completed → 应抛 ProjectPhaseError
    raised2: Exception | None = None
    try:
        await update_project_phase(db_session, project_id, "completed")
    except Exception as e:
        raised2 = e
    actual_type2 = type(raised2).__name__ if raised2 else "None"
    assert isinstance(raised2, ProjectPhaseError), f"跳跃应抛 ProjectPhaseError，实际 {actual_type2}"


@pytest.mark.asyncio
async def test_7_patch_project_status_uses_state_machine(client: AsyncClient):
    """断裂 2：PATCH /projects/{id} status 变更走状态机校验，不再直绕"""
    token = await _register_and_get_token(client, "13900002017")
    headers = _headers(token)
    project_id = await _create_project(client, headers, name="PATCH状态机项目")

    # draft → completed 非法（draft 仅允许 active/cancelled）→ 应 409
    resp = await client.patch(
        f"/api/projects/{project_id}", json={"status": "completed"}, headers=headers,
    )
    assert resp.status_code == 409, f"非法状态转换应 409，实际 {resp.status_code}: {resp.text}"
    detail = resp.json()["detail"]
    assert detail["reason"] == "ProjectStateError"

    # 验证 project.status 仍为 draft（未被绕过写入 completed）
    get_resp = await client.get(f"/api/projects/{project_id}", headers=headers)
    assert get_resp.json()["status"] == "draft"


# ====================================================================
# 8-9 竣工验收强制闸门
# ====================================================================

@pytest.mark.asyncio
async def test_8_accept_project_blocked_by_open_quality_issues(client: AsyncClient, db_session, monkeypatch):
    """断裂 3：强制闸门 — 有未闭环质量问题 → 409"""
    # 回退模式：避免标准 checklist 匹配复杂度，闸门退化为 issue 状态判定
    # 用 monkeypatch.setattr 直接改单例属性，勿用 cache_clear()——后者会使其他模块
    # import 时的 settings = get_settings() 模块级绑定变成陈旧引用，导致
    # test_webauthn / test_v1129_gap_filling 等依赖单例一致性的测试在全量跑时失败。
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "acceptance_checklist_enabled", False)

    token = await _register_and_get_token(client, "13900002018")
    headers = _headers(token)
    project_id = await _create_project(client, headers, name="闸门阻断项目")

    # 推进 phase 到 quality
    from app.services.project_service import update_project_phase
    await update_project_phase(db_session, project_id, "design")
    await update_project_phase(db_session, project_id, "budget")
    await update_project_phase(db_session, project_id, "procurement")
    await update_project_phase(db_session, project_id, "construction")
    await update_project_phase(db_session, project_id, "quality")

    # 创建一个 open 质量问题
    db_session.add(QualityIssue(
        project_id=project_id, phase="mep", category="水电-插座",
        description="插座位置偏差", severity="medium", status="open",
        detected_by="manual",
    ))
    await db_session.commit()

    resp = await client.post(
        f"/api/projects/{project_id}/accept",
        json={}, headers=headers,
    )
    assert resp.status_code == 409, f"有未闭环质量问题应 409，实际 {resp.status_code}"
    detail = resp.json()["detail"]
    assert detail["reason"] == "open_quality_issues"
    # monkeypatch 会在 teardown 自动还原 acceptance_checklist_enabled，无需手动清理


@pytest.mark.asyncio
async def test_9_accept_project_success(client: AsyncClient, db_session, monkeypatch):
    """断裂 3：闸门通过 → phase→completed / status→completed"""
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "acceptance_checklist_enabled", False)

    token = await _register_and_get_token(client, "13900002019")
    headers = _headers(token)
    project_id = await _create_project(client, headers, name="闸门通过项目")

    # 推进 phase 到 quality
    from app.services.project_service import update_project_phase
    for ph in ("design", "budget", "procurement", "construction", "quality"):
        await update_project_phase(db_session, project_id, ph)

    # 创建一个 verified 质量问题（已验收通过，无 open/in_progress）
    db_session.add(QualityIssue(
        project_id=project_id, phase="mep", category="水电-插座",
        description="插座位置合格", severity="low", status="verified",
        detected_by="manual",
    ))
    await db_session.commit()

    resp = await client.post(
        f"/api/projects/{project_id}/accept",
        json={}, headers=headers,
    )
    assert resp.status_code == 200, f"闸门通过应 200，实际 {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["accepted"] is True
    assert data["phase"] == "completed"
    assert data["status"] == "completed"
    # monkeypatch 会在 teardown 自动还原 acceptance_checklist_enabled，无需手动清理


# ====================================================================
# 10 timeline 读 phase 直接驱动
# ====================================================================

@pytest.mark.asyncio
async def test_10_timeline_reads_phase_directly(client: AsyncClient, db_session):
    """断裂 4：timeline 不再依赖幻影 status，读 phase 直接驱动"""
    token = await _register_and_get_token(client, "13900002020")
    headers = _headers(token)
    project_id = await _create_project(client, headers, name="timeline项目")

    # 推进 phase 到 construction（5）
    from app.services.project_service import update_project_phase
    for ph in ("design", "budget", "procurement", "construction"):
        await update_project_phase(db_session, project_id, ph)

    resp = await client.get(f"/api/projects/{project_id}/timeline", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # 返回 project_phase 字段（不再是幻影 project_status 映射）
    assert data["project_phase"] == "construction"
    # active_stage 对应 construction = 5
    assert data["stats"]["active_stage"] == 5
    # 进度 = (5-1)/7*100 = 57
    assert data["stats"]["progress_pct"] == 57
