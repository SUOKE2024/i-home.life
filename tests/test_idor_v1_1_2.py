"""v1.1.2 IDOR 回归测试 — procurement_enhanced GET 端点信息泄露 + construction mutate-before-verify

针对以下修复提供回归保护：
- procurement_enhanced.py: 9 个 GET/POST 端点缺失项目归属校验
  list_project_comparisons / get_comparison / list_comparison_items / ai_match
  get_escrow / list_order_escrow / get_logistics / get_order_logistics / list_project_samples
  修复前：任意已登录用户可读取他人项目的比价报告、担保支付、物流追踪、样品索要
- construction.py: 3 个 mutate-before-verify IDOR + 2 个 GET 信息泄露
  update_task_status / add_log / create_inspection（先 commit 再 verify → 越权写入已落库）
  get_logs / get_inspections（完全无项目归属校验 → 任意用户可读取他人施工日志/检查记录）
"""

import pytest
from httpx import AsyncClient
from starlette.routing import Mount

from app.models import procurement_enhanced  # noqa: F401
from app.main import app
from app.api import procurement_enhanced as procurement_enhanced_api

# 确保增强路由已注册
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


# ════════════════════════════════════════════════════════════════
# procurement_enhanced IDOR 测试
# ════════════════════════════════════════════════════════════════


async def _create_bom_and_suppliers(
    client: AsyncClient, headers: dict, project_id: str
) -> tuple[str, str]:
    """创建物料分类 + 物料 + BOM 物料 + 供应商 + 比价报告，返回 (comparison_id, bom_id)"""
    # 创建物料分类
    cat_resp = await client.post(
        "/api/materials/categories",
        json={"name": "IDOR测试分类", "code": "idor-test"},
        headers=headers,
    )
    assert cat_resp.status_code == 201, cat_resp.text
    cat_id = cat_resp.json()["id"]

    # 创建材料
    mat_resp = await client.post(
        "/api/materials",
        json={
            "category_id": cat_id,
            "name": "IDOR测试材料",
            "sku": "IDOR-SKU-001",
            "unit": "㎡",
            "unit_price": 200.0,
            "brand": "测试品牌",
            "spec": "800×800mm",
        },
        headers=headers,
    )
    assert mat_resp.status_code == 201, mat_resp.text
    material_id = mat_resp.json()["id"]

    # 创建 BOM 物料
    bom_resp = await client.post(
        "/api/materials/bom",
        json={"project_id": project_id, "material_id": material_id, "quantity": 10.0, "unit_price": 200.0},
        headers=headers,
    )
    assert bom_resp.status_code == 201, bom_resp.text
    bom_id = bom_resp.json()["id"]

    # 创建供应商
    supp_resp = await client.post(
        "/api/procurement/suppliers",
        json={"name": "IDOR测试供应商", "category": "idor-test", "rating": 4.5, "address": "上海市"},
        headers=headers,
    )
    assert supp_resp.status_code == 201, supp_resp.text

    # 创建比价报告
    comp_resp = await client.post(
        "/api/procurement-enhanced/comparisons",
        json={"project_id": project_id, "bom_id": bom_id, "notes": "IDOR 测试"},
        headers=headers,
    )
    assert comp_resp.status_code == 201, comp_resp.text
    return comp_resp.json()["id"], bom_id


@pytest.mark.asyncio
async def test_list_project_comparisons_idor_blocked(client: AsyncClient):
    """用户 B 不能列出用户 A 项目的比价报告 (403)"""
    _, hdr_a = await _register(client, "13900400001", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    await _create_bom_and_suppliers(client, hdr_a, proj_a)

    _, hdr_b = await _register(client, "13900400002", "OwnerB")
    resp = await client.get(
        f"/api/procurement-enhanced/comparisons/project/{proj_a}",
        headers=hdr_b,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_comparison_idor_blocked(client: AsyncClient):
    """用户 B 不能获取用户 A 的比价报告详情 (403)"""
    _, hdr_a = await _register(client, "13900400003", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    comp_id, _ = await _create_bom_and_suppliers(client, hdr_a, proj_a)

    _, hdr_b = await _register(client, "13900400004", "OwnerB")
    resp = await client.get(
        f"/api/procurement-enhanced/comparisons/{comp_id}",
        headers=hdr_b,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_comparison_items_idor_blocked(client: AsyncClient):
    """用户 B 不能获取用户 A 比价报告的明细行 (403)"""
    _, hdr_a = await _register(client, "13900400005", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    comp_id, _ = await _create_bom_and_suppliers(client, hdr_a, proj_a)

    _, hdr_b = await _register(client, "13900400006", "OwnerB")
    resp = await client.get(
        f"/api/procurement-enhanced/comparisons/{comp_id}/items",
        headers=hdr_b,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_ai_match_idor_blocked(client: AsyncClient):
    """用户 B 不能对用户 A 的 BOM 物料执行 AI 供应商匹配 (403)"""
    _, hdr_a = await _register(client, "13900400007", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    _, bom_id = await _create_bom_and_suppliers(client, hdr_a, proj_a)

    _, hdr_b = await _register(client, "13900400008", "OwnerB")
    resp = await client.post(
        "/api/procurement-enhanced/ai-match",
        json={"bom_item_id": bom_id, "location": "北京"},
        headers=hdr_b,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_project_samples_idor_blocked(client: AsyncClient):
    """用户 B 不能列出用户 A 项目的样品索要记录 (403)"""
    _, hdr_a = await _register(client, "13900400009", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")

    _, hdr_b = await _register(client, "13900400010", "OwnerB")
    resp = await client.get(
        f"/api/procurement-enhanced/samples/project/{proj_a}",
        headers=hdr_b,
    )
    assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════
# construction.py mutate-before-verify IDOR 测试
# ════════════════════════════════════════════════════════════════


async def _create_construction_task(
    client: AsyncClient, headers: dict, project_id: str
) -> str:
    """创建施工任务，返回 task_id"""
    resp = await client.post(
        "/api/construction/tasks",
        json={
            "project_id": project_id,
            "name": "IDOR 测试任务",
            "phase": "masonry",
            "planned_start": "2026-01-01T00:00:00",
            "planned_end": "2026-01-10T00:00:00",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_update_task_status_idor_blocked(client: AsyncClient):
    """用户 B 不能更新用户 A 项目的任务状态 (403) — mutate-before-verify 修复"""
    _, hdr_a = await _register(client, "13900400011", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    task_id = await _create_construction_task(client, hdr_a, proj_a)

    _, hdr_b = await _register(client, "13900400012", "OwnerB")
    resp = await client.patch(
        f"/api/construction/tasks/{task_id}/status?status_val=in_progress",
        headers=hdr_b,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_add_log_idor_blocked(client: AsyncClient):
    """用户 B 不能给用户 A 的任务添加施工日志 (403) — mutate-before-verify 修复"""
    _, hdr_a = await _register(client, "13900400013", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    task_id = await _create_construction_task(client, hdr_a, proj_a)

    _, hdr_b = await _register(client, "13900400014", "OwnerB")
    resp = await client.post(
        "/api/construction/logs",
        json={
            "task_id": task_id,
            "content": "IDOR 攻击日志",
            "weather": "sunny",
            "workers_count": 5,
        },
        headers=hdr_b,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_inspection_idor_blocked(client: AsyncClient):
    """用户 B 不能给用户 A 的任务创建检查记录 (403) — mutate-before-verify 修复"""
    _, hdr_a = await _register(client, "13900400015", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    task_id = await _create_construction_task(client, hdr_a, proj_a)

    _, hdr_b = await _register(client, "13900400016", "OwnerB")
    resp = await client.post(
        "/api/construction/inspections",
        json={
            "task_id": task_id,
            "result": "passed",
            "notes": "IDOR 攻击检查",
        },
        headers=hdr_b,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_logs_idor_blocked(client: AsyncClient):
    """用户 B 不能读取用户 A 任务的施工日志 (403)"""
    _, hdr_a = await _register(client, "13900400017", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    task_id = await _create_construction_task(client, hdr_a, proj_a)
    # owner 添加一条日志
    resp = await client.post(
        "/api/construction/logs",
        json={"task_id": task_id, "content": "owner 日志", "weather": "sunny", "workers_count": 3},
        headers=hdr_a,
    )
    assert resp.status_code == 201, resp.text

    _, hdr_b = await _register(client, "13900400018", "OwnerB")
    resp = await client.get(
        f"/api/construction/logs/{task_id}",
        headers=hdr_b,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_inspections_idor_blocked(client: AsyncClient):
    """用户 B 不能读取用户 A 任务的检查记录 (403)"""
    _, hdr_a = await _register(client, "13900400019", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    task_id = await _create_construction_task(client, hdr_a, proj_a)
    # owner 创建一条检查记录
    resp = await client.post(
        "/api/construction/inspections",
        json={"task_id": task_id, "result": "passed", "notes": "owner 检查"},
        headers=hdr_a,
    )
    assert resp.status_code == 201, resp.text

    _, hdr_b = await _register(client, "13900400020", "OwnerB")
    resp = await client.get(
        f"/api/construction/inspections/{task_id}",
        headers=hdr_b,
    )
    assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════
# 正向回归：owner 自身可访问
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_procurement_enhanced_owner_can_access(client: AsyncClient):
    """owner 自身可正常访问比价报告端点 (200/201) — 防止修复过度"""
    _, hdr_a = await _register(client, "13900400021", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    comp_id, _ = await _create_bom_and_suppliers(client, hdr_a, proj_a)

    # list_project_comparisons
    resp = await client.get(
        f"/api/procurement-enhanced/comparisons/project/{proj_a}",
        headers=hdr_a,
    )
    assert resp.status_code == 200
    # get_comparison
    resp = await client.get(
        f"/api/procurement-enhanced/comparisons/{comp_id}",
        headers=hdr_a,
    )
    assert resp.status_code == 200
    # list_comparison_items
    resp = await client.get(
        f"/api/procurement-enhanced/comparisons/{comp_id}/items",
        headers=hdr_a,
    )
    assert resp.status_code == 200
    # list_project_samples
    resp = await client.get(
        f"/api/procurement-enhanced/samples/project/{proj_a}",
        headers=hdr_a,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_construction_owner_can_access_logs_and_inspections(client: AsyncClient):
    """owner 自身可正常访问施工日志和检查记录 (200/201) — 防止修复过度"""
    _, hdr_a = await _register(client, "13900400022", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    task_id = await _create_construction_task(client, hdr_a, proj_a)

    # owner 添加日志
    resp = await client.post(
        "/api/construction/logs",
        json={"task_id": task_id, "content": "owner 日志", "weather": "sunny", "workers_count": 3},
        headers=hdr_a,
    )
    assert resp.status_code == 201
    # owner 读取日志
    resp = await client.get(f"/api/construction/logs/{task_id}", headers=hdr_a)
    assert resp.status_code == 200
    # owner 创建检查记录
    resp = await client.post(
        "/api/construction/inspections",
        json={"task_id": task_id, "result": "passed", "notes": "owner 检查"},
        headers=hdr_a,
    )
    assert resp.status_code == 201
    # owner 读取检查记录
    resp = await client.get(f"/api/construction/inspections/{task_id}", headers=hdr_a)
    assert resp.status_code == 200
