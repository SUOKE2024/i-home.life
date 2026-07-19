"""v1.1.1 IDOR 回归测试 — 验证 construction/procurement_enhanced 端点的项目归属校验

针对以下修复提供回归保护：
- construction.py: resolve_progress_alert / upsert_milestone / complete_milestone
                   / update_quality_issue_status / update_rectification_order_status
  修复前：先 mutate+commit 再 verify_project_access → 越权写入已落库
- procurement_enhanced.py: delete_comparison
  修复前：完全缺少项目归属校验 → 任意用户可删除他人比价报告
- admin.py: update_user_role
  修复前：非 admin 持有 user:write 权限可把任意用户提升为 admin（权限提升）
"""

import pytest
from httpx import AsyncClient
from starlette.routing import Mount

from app.models import procurement_enhanced  # noqa: F401
from app.main import app
from app.api import procurement_enhanced as procurement_enhanced_api

# 确保增强路由已注册（与 test_procurement_enhanced.py 相同的引导逻辑）
_enhanced_registered = any(
    getattr(r, "path", "").startswith("/api/procurement-enhanced") for r in app.routes
)
if not _enhanced_registered:
    _static_mounts = [
        r for r in app.router.routes
        if isinstance(r, Mount) and r.path in ("/", "")
    ]
    app.router.routes = [
        r for r in app.router.routes
        if not (isinstance(r, Mount) and r.path in ("/", ""))
    ]
    app.include_router(procurement_enhanced_api.router, prefix="/api")
    app.router.routes.extend(_static_mounts)


async def _register(client: AsyncClient, phone: str, name: str) -> tuple[str, dict]:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": name, "password": "test123456"},
    )
    assert resp.status_code in (200, 201), resp.text
    token = resp.json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


async def _create_project(client: AsyncClient, headers: dict, name: str) -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": name, "total_area": 100.0},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ── construction.py IDOR 测试 ──


async def _create_progress_alert(
    client: AsyncClient, headers: dict, project_id: str
) -> str:
    resp = await client.post(
        "/api/construction/progress-alerts",
        json={
            "project_id": project_id,
            "phase": "masonry",
            "alert_type": "delay",
            "severity": "medium",
            "message": "IDOR 测试预警",
            "delay_days": 2,
            "progress_percent": 30.0,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_milestone(
    client: AsyncClient, headers: dict, project_id: str, code: str = "MS-IDOR-1"
) -> str:
    resp = await client.post(
        "/api/construction/milestones",
        json={
            "project_id": project_id,
            "milestone_code": code,
            "name": "IDOR 测试里程碑",
            "planned_percent": 50.0,
            "actual_percent": 0.0,
            "status": "pending",
            "payment_ratio": 0.3,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _create_quality_issue(
    client: AsyncClient, headers: dict, project_id: str
) -> str:
    resp = await client.post(
        "/api/construction/quality-issues",
        json={
            "project_id": project_id,
            "phase": "masonry",
            "category": "surface",
            "description": "IDOR 测试质量问题",
            "severity": "low",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_rectification_order(
    client: AsyncClient, headers: dict, project_id: str, issue_id: str
) -> str:
    resp = await client.post(
        "/api/construction/rectification-orders",
        json={
            "project_id": project_id,
            "title": "IDOR 测试整改单",
            "phase": "masonry",
            "issue_ids": [issue_id],
            "priority": "medium",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_resolve_progress_alert_idor_blocked(client: AsyncClient):
    """非项目 owner 不能解决他人项目的进度预警"""
    owner_token, owner_h = await _register(client, "13900010101", "IDOR owner 1")
    attacker_token, attacker_h = await _register(client, "13900010102", "IDOR attacker 1")
    proj_id = await _create_project(client, owner_h, "IDOR 项目1")
    alert_id = await _create_progress_alert(client, owner_h, proj_id)

    # 攻击者尝试解决 → 必须 403
    resp = await client.patch(
        f"/api/construction/progress-alerts/{alert_id}/resolve",
        json={"note": "malicious"},
        headers=attacker_h,
    )
    assert resp.status_code == 403, f"IDOR 未拦截: {resp.status_code} {resp.text}"

    # owner 自己解决 → 应成功
    resp = await client.patch(
        f"/api/construction/progress-alerts/{alert_id}/resolve",
        json={"note": "ok"},
        headers=owner_h,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "resolved"


@pytest.mark.asyncio
async def test_upsert_milestone_idor_blocked(client: AsyncClient):
    """非项目 owner 不能为他人项目创建/更新里程碑"""
    owner_token, owner_h = await _register(client, "13900010103", "IDOR owner 2")
    attacker_token, attacker_h = await _register(client, "13900010104", "IDOR attacker 2")
    proj_id = await _create_project(client, owner_h, "IDOR 项目2")

    # 攻击者尝试创建里程碑 → 必须 403
    resp = await client.post(
        "/api/construction/milestones",
        json={
            "project_id": proj_id,
            "milestone_code": "MS-ATTACK",
            "name": "恶意里程碑",
            "planned_percent": 10.0,
            "actual_percent": 0.0,
            "status": "pending",
            "payment_ratio": 0.1,
        },
        headers=attacker_h,
    )
    assert resp.status_code == 403, f"IDOR 未拦截: {resp.status_code} {resp.text}"

    # owner 创建 → 应成功
    await _create_milestone(client, owner_h, proj_id, code="MS-OK-1")

    # 攻击者尝试 upsert 同一 milestone_code 覆盖 owner 数据 → 必须 403
    resp = await client.post(
        "/api/construction/milestones",
        json={
            "project_id": proj_id,
            "milestone_code": "MS-OK-1",
            "name": "被覆盖的里程碑",
            "planned_percent": 99.0,
            "actual_percent": 0.0,
            "status": "pending",
            "payment_ratio": 0.99,
        },
        headers=attacker_h,
    )
    assert resp.status_code == 403, f"IDOR 未拦截: {resp.status_code} {resp.text}"


@pytest.mark.asyncio
async def test_complete_milestone_idor_blocked(client: AsyncClient):
    """非项目 owner 不能标记他人项目的里程碑完成"""
    owner_token, owner_h = await _register(client, "13900010105", "IDOR owner 3")
    attacker_token, attacker_h = await _register(client, "13900010106", "IDOR attacker 3")
    proj_id = await _create_project(client, owner_h, "IDOR 项目3")
    ms_id = await _create_milestone(client, owner_h, proj_id, code="MS-OK-3")

    # 攻击者尝试完成 → 必须 403
    resp = await client.patch(
        f"/api/construction/milestones/{ms_id}/complete",
        json={"actual_percent": 100.0},
        headers=attacker_h,
    )
    assert resp.status_code == 403, f"IDOR 未拦截: {resp.status_code} {resp.text}"

    # owner 完成 → 应成功（先更新到 in_progress）
    resp = await client.patch(
        f"/api/construction/milestones/{ms_id}/status?new_status=in_progress",
        headers=owner_h,
    )
    assert resp.status_code == 200, resp.text
    resp = await client.patch(
        f"/api/construction/milestones/{ms_id}/complete",
        json={"actual_percent": 100.0},
        headers=owner_h,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_update_quality_issue_status_idor_blocked(client: AsyncClient):
    """非项目 owner 不能更新他人项目的质量问题状态"""
    owner_token, owner_h = await _register(client, "13900010107", "IDOR owner 4")
    attacker_token, attacker_h = await _register(client, "13900010108", "IDOR attacker 4")
    proj_id = await _create_project(client, owner_h, "IDOR 项目4")
    issue_id = await _create_quality_issue(client, owner_h, proj_id)

    # 攻击者尝试更新 → 必须 403
    resp = await client.patch(
        f"/api/construction/quality-issues/{issue_id}/status",
        json={"status": "in_progress"},
        headers=attacker_h,
    )
    assert resp.status_code == 403, f"IDOR 未拦截: {resp.status_code} {resp.text}"

    # owner 更新 → 应成功
    resp = await client.patch(
        f"/api/construction/quality-issues/{issue_id}/status",
        json={"status": "in_progress"},
        headers=owner_h,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "in_progress"


@pytest.mark.asyncio
async def test_update_rectification_order_status_idor_blocked(client: AsyncClient):
    """非项目 owner 不能更新他人项目的整改单状态"""
    owner_token, owner_h = await _register(client, "13900010109", "IDOR owner 5")
    attacker_token, attacker_h = await _register(client, "13900010110", "IDOR attacker 5")
    proj_id = await _create_project(client, owner_h, "IDOR 项目5")
    issue_id = await _create_quality_issue(client, owner_h, proj_id)
    order_id = await _create_rectification_order(client, owner_h, proj_id, issue_id)

    # 攻击者尝试更新 → 必须 403
    resp = await client.patch(
        f"/api/construction/rectification-orders/{order_id}/status?new_status=in_progress",
        headers=attacker_h,
    )
    assert resp.status_code == 403, f"IDOR 未拦截: {resp.status_code} {resp.text}"

    # owner 更新 → 应成功
    resp = await client.patch(
        f"/api/construction/rectification-orders/{order_id}/status?new_status=in_progress",
        headers=owner_h,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "in_progress"


# ── procurement_enhanced.py IDOR 测试 ──


async def _create_bom_and_suppliers_for_comparison(
    client: AsyncClient, headers: dict, project_id: str
) -> str:
    """创建物料 + BOM + 供应商，生成比价报告，返回 comparison_id"""
    cat_resp = await client.post(
        "/api/materials/categories",
        json={"name": "IDOR比价分类", "code": "idor_flooring"},
        headers=headers,
    )
    cat_id = cat_resp.json()["id"]
    mat_resp = await client.post(
        "/api/materials",
        json={
            "category_id": cat_id,
            "name": "IDOR比价瓷砖",
            "sku": "IDOR-FLOOR-001",
            "unit": "㎡",
            "unit_price": 200.0,
            "brand": "测试品牌",
            "spec": "800×800mm",
        },
        headers=headers,
    )
    material_id = mat_resp.json()["id"]
    bom_resp = await client.post(
        "/api/materials/bom",
        json={
            "project_id": project_id,
            "material_id": material_id,
            "quantity": 50.0,
            "unit_price": 200.0,
        },
        headers=headers,
    )
    bom_item_id = bom_resp.json()["id"]

    # 创建 2 个供应商
    for idx, (name, rating) in enumerate([
        ("IDOR供应商A", 4.8), ("IDOR供应商B", 4.5),
    ]):
        await client.post(
            "/api/procurement/suppliers",
            json={"name": name, "category": "flooring", "rating": rating},
            headers=headers,
        )

    # 生成比价报告
    resp = await client.post(
        "/api/procurement-enhanced/comparisons",
        json={"project_id": project_id, "bom_id": bom_item_id},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_delete_comparison_idor_blocked(client: AsyncClient):
    """非项目 owner 不能删除他人项目的比价报告"""
    owner_token, owner_h = await _register(client, "13900010111", "IDOR owner 6")
    attacker_token, attacker_h = await _register(client, "13900010112", "IDOR attacker 6")
    proj_id = await _create_project(client, owner_h, "IDOR 项目6")
    comparison_id = await _create_bom_and_suppliers_for_comparison(
        client, owner_h, proj_id
    )

    # 攻击者尝试删除 → 必须 403
    resp = await client.delete(
        f"/api/procurement-enhanced/comparisons/{comparison_id}",
        headers=attacker_h,
    )
    assert resp.status_code == 403, f"IDOR 未拦截: {resp.status_code} {resp.text}"

    # 确认报告仍然存在
    resp = await client.get(
        f"/api/procurement-enhanced/comparisons/{comparison_id}",
        headers=owner_h,
    )
    assert resp.status_code == 200, "比价报告不应被攻击者删除"

    # owner 删除 → 应成功
    resp = await client.delete(
        f"/api/procurement-enhanced/comparisons/{comparison_id}",
        headers=owner_h,
    )
    assert resp.status_code == 204, resp.text


# ── admin.py 权限提升测试 ──


@pytest.mark.asyncio
async def test_admin_role_promotion_blocked_for_non_admin(client: AsyncClient):
    """非 admin 用户即使持有 user:write 权限也不能将他人提升为 admin 角色"""
    # 直接通过数据库创建一个非 admin 但持有 user:write 权限的角色
    # （默认配置中只有 admin 持有 user:write，这里模拟权限被错误配置的场景）
    from app.database import async_session
    from app.models.permission import Permission, RolePermission
    from sqlalchemy import select

    # 1. 注册两个普通用户
    attacker_token, attacker_h = await _register(client, "13900010113", "权限提升攻击者")
    victim_token, victim_h = await _register(client, "13900010114", "被操作用户")

    # 2. 通过 DB 直接给 homeowner 角色授予 user:write 权限（模拟权限误配置）
    async with async_session() as db:
        # 确保权限存在
        result = await db.execute(select(Permission).where(Permission.code == "user:write"))
        perm = result.scalar_one_or_none()
        if not perm:
            perm = Permission(
                code="user:write",
                name="修改用户",
                resource="user",
                action="write",
                description="修改用户角色和状态",
            )
            db.add(perm)
            await db.flush()
        # 给 homeowner 角色授予 user:write
        existing = await db.execute(
            select(RolePermission).where(
                RolePermission.role == "homeowner",
                RolePermission.permission_code == "user:write",
            )
        )
        if not existing.scalar_one_or_none():
            db.add(RolePermission(role="homeowner", permission_code="user:write"))
        # 把攻击者设为 homeowner（已注册的默认是 homeowner）
        await db.commit()

    # 3. 获取 victim 的 user_id
    resp = await client.get("/api/auth/me", headers=victim_h)
    victim_user_id = resp.json()["id"]

    # 4. 攻击者尝试把 victim 提升为 admin → 必须 403（权限提升拦截）
    resp = await client.put(
        f"/api/admin/users/{victim_user_id}/role",
        json={"role": "admin"},
        headers=attacker_h,
    )
    assert resp.status_code == 403, f"权限提升未拦截: {resp.status_code} {resp.text}"
    assert "提升" in resp.json()["detail"] or "admin" in resp.json()["detail"].lower()

    # 5. 确认 victim 仍然是 homeowner
    resp = await client.get("/api/auth/me", headers=victim_h)
    assert resp.json()["role"] == "homeowner", "victim 角色不应被改变"
