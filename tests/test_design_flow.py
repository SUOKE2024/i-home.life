"""设计流程编排 API 集成测试

覆盖端点:
- POST   /api/design-flow                            (创建编排会话)
- GET    /api/design-flow/{id}                       (会话详情)
- POST   /api/design-flow/{id}/suppliers/match       (匹配候选供应商)
- POST   /api/design-flow/{id}/suppliers/select      (随机/自选供应商)
- POST   /api/design-flow/{id}/render                (触发渲染)
- POST   /api/design-flow/{id}/adjust                (调整重渲染)
- POST   /api/design-flow/{id}/confirm               (确认 → 可行性分析)
- GET    /api/design-flow/{id}/feasibility           (可行性分析结果)
- POST   /api/design-flow/{id}/suggest               (LLM 建议旁路)
"""
import json

import pytest
from httpx import AsyncClient


async def _auth_headers(client: AsyncClient, phone: str) -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "设计流程测试", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "设计流程项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 80.0}, headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_floorplan(client: AsyncClient, headers: dict, project_id: str) -> str:
    data = {
        "walls": [],
        "rooms": [
            {"name": "客厅", "type": "living", "area": 20.0},
            {"name": "主卧", "type": "bedroom", "area": 15.0},
        ],
    }
    resp = await client.post(
        "/api/floorplans",
        json={
            "project_id": project_id,
            "name": "测试户型",
            "data": json.dumps(data),
            "wall_height": 2.8,
            "total_area": 80.0,
            "room_count": 2,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_supplier(
    client: AsyncClient, headers: dict, name: str, category: str,
    rating: float, styles: list[str], price_tier: str,
) -> str:
    resp = await client.post(
        "/api/procurement/suppliers",
        json={
            "name": name, "category": category, "rating": rating,
            "styles": styles, "price_tier": price_tier,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_flow(
    client: AsyncClient, headers: dict, project_id: str, floorplan_id: str,
    style: str = "modern", budget: float = 200000.0, mode: str = "random",
) -> dict:
    resp = await client.post(
        "/api/design-flow",
        json={
            "project_id": project_id, "floorplan_id": floorplan_id,
            "style": style, "budget": budget, "supplier_selection_mode": mode,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── 前置校验 ──


@pytest.mark.asyncio
async def test_create_flow_requires_active_floorplan(client: AsyncClient):
    headers = await _auth_headers(client, "13970000001")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/design-flow",
        json={"project_id": project_id, "floorplan_id": "nonexistent", "style": "modern", "budget": 200000},
        headers=headers,
    )
    assert resp.status_code == 409


# ── 供应商匹配 ──


@pytest.mark.asyncio
async def test_match_suppliers_filters_by_style_and_price_tier(client: AsyncClient):
    headers = await _auth_headers(client, "13970000002")
    project_id = await _create_project(client, headers)
    floorplan_id = await _create_floorplan(client, headers, project_id)

    await _create_supplier(client, headers, "现代经济A", "flooring", 4.8, ["modern"], "economy")
    await _create_supplier(client, headers, "现代标准B", "flooring", 4.5, ["modern"], "standard")
    await _create_supplier(client, headers, "奶油经济C", "flooring", 4.9, ["nordic"], "economy")

    flow = await _create_flow(client, headers, project_id, floorplan_id, style="modern", budget=80000.0)

    resp = await client.post(f"/api/design-flow/{flow['id']}/suppliers/match", headers=headers)
    assert resp.status_code == 200, resp.text
    candidates = resp.json()
    # budget=80000 / area=80 → 1000 元/㎡ → economy 档
    names = [c["name"] for c in candidates]
    assert "现代经济A" in names
    assert "现代标准B" not in names  # price_tier 不符被过滤
    assert "奶油经济C" not in names  # 风格不符被过滤


# ── 供应商选择 ──


@pytest.mark.asyncio
async def test_select_supplier_random_and_manual(client: AsyncClient):
    headers = await _auth_headers(client, "13970000003")
    project_id = await _create_project(client, headers)
    floorplan_id = await _create_floorplan(client, headers, project_id)

    sid_a = await _create_supplier(client, headers, "随机A", "flooring", 4.8, ["modern"], "standard")
    await _create_supplier(client, headers, "随机B", "flooring", 4.5, ["modern"], "standard")

    flow = await _create_flow(client, headers, project_id, floorplan_id, style="modern", budget=200000.0, mode="random")

    # 随机选择
    resp = await client.post(
        f"/api/design-flow/{flow['id']}/suppliers/select",
        json={"mode": "random"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["stage"] == "supplier_matched"
    assert resp.json()["supplier_id"] in {sid_a}

    # 手动选择非法供应商
    resp = await client.post(
        f"/api/design-flow/{flow['id']}/suppliers/select",
        json={"mode": "manual", "supplier_id": "nonexistent"},
        headers=headers,
    )
    assert resp.status_code == 409


# ── 状态机 ──


@pytest.mark.asyncio
async def test_flow_state_machine_illegal_transition(client: AsyncClient):
    headers = await _auth_headers(client, "13970000004")
    project_id = await _create_project(client, headers)
    floorplan_id = await _create_floorplan(client, headers, project_id)

    flow = await _create_flow(client, headers, project_id, floorplan_id)

    # init 阶段直接 confirm → 409
    resp = await client.post(f"/api/design-flow/{flow['id']}/confirm", headers=headers)
    assert resp.status_code == 409


# ── 渲染 + 全屋漫游 ──


@pytest.mark.asyncio
async def test_render_creates_effect_panoramas_and_scene(client: AsyncClient):
    headers = await _auth_headers(client, "13970000005")
    project_id = await _create_project(client, headers)
    floorplan_id = await _create_floorplan(client, headers, project_id)

    await _create_supplier(client, headers, "渲染供应商", "flooring", 4.8, ["modern"], "standard")
    flow = await _create_flow(client, headers, project_id, floorplan_id, style="modern", budget=200000.0)

    await client.post(f"/api/design-flow/{flow['id']}/suppliers/select", json={"mode": "random"}, headers=headers)

    resp = await client.post(f"/api/design-flow/{flow['id']}/render", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["stage"] == "rendered"
    assert resp.json()["scene_id"] is not None

    # 每房间一张效果图全景（content_source=effect）
    list_resp = await client.get(f"/api/vr/panoramas/project/{project_id}", headers=headers)
    assert list_resp.status_code == 200, list_resp.text
    effect_items = [p for p in list_resp.json() if p["content_source"] == "effect"]
    assert len(effect_items) == 2  # 客厅 + 主卧


# ── 调整重渲染 ──


@pytest.mark.asyncio
async def test_adjust_style_triggers_rerender(client: AsyncClient):
    headers = await _auth_headers(client, "13970000006")
    project_id = await _create_project(client, headers)
    floorplan_id = await _create_floorplan(client, headers, project_id)

    await _create_supplier(client, headers, "风格切换A", "flooring", 4.8, ["modern"], "standard")
    await _create_supplier(client, headers, "风格切换B", "flooring", 4.6, ["nordic"], "standard")
    flow = await _create_flow(client, headers, project_id, floorplan_id, style="modern", budget=200000.0, mode="random")

    await client.post(f"/api/design-flow/{flow['id']}/suppliers/select", json={"mode": "random"}, headers=headers)
    await client.post(f"/api/design-flow/{flow['id']}/render", headers=headers)

    # 换风格 → 重新匹配供应商 + 重渲染
    resp = await client.post(
        f"/api/design-flow/{flow['id']}/adjust",
        json={"style": "nordic"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["stage"] == "rendered"
    assert resp.json()["style"] == "nordic"


# ── 确认 + 可行性分析 ──


@pytest.mark.asyncio
async def test_confirm_generates_feasibility(client: AsyncClient):
    headers = await _auth_headers(client, "13970000007")
    project_id = await _create_project(client, headers)
    floorplan_id = await _create_floorplan(client, headers, project_id)

    await _create_supplier(client, headers, "可行性供应商", "flooring", 4.8, ["modern"], "standard")
    flow = await _create_flow(client, headers, project_id, floorplan_id, style="modern", budget=200000.0)

    await client.post(f"/api/design-flow/{flow['id']}/suppliers/select", json={"mode": "random"}, headers=headers)
    await client.post(f"/api/design-flow/{flow['id']}/render", headers=headers)

    resp = await client.post(f"/api/design-flow/{flow['id']}/confirm", headers=headers)
    assert resp.status_code == 200, resp.text

    feas_resp = await client.get(f"/api/design-flow/{flow['id']}/feasibility", headers=headers)
    assert feas_resp.status_code == 200, feas_resp.text
    data = feas_resp.json()
    assert data["status"] == "completed"
    assert "signal" in data["summary"]
    assert "total_days" in data["duration_analysis"]
    assert "user_budget" in data["budget_analysis"]


# ── LLM 建议降级 ──


@pytest.mark.asyncio
async def test_suggest_unavailable_without_llm(client: AsyncClient):
    headers = await _auth_headers(client, "13970000008")
    project_id = await _create_project(client, headers)
    floorplan_id = await _create_floorplan(client, headers, project_id)

    flow = await _create_flow(client, headers, project_id, floorplan_id)

    resp = await client.post(f"/api/design-flow/{flow['id']}/suggest", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["suggestions"] == []
    assert data["source"] == "unavailable"
