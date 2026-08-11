"""首页 Feed API 测试 — A2UI 8 类卡片并入首页 feed

覆盖：GET /api/feed/{project_id} 从项目现有数据组合出 A2UI 卡片
（alert_card / design_plan / construction_progress / budget_breakdown）。
"""

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": "13900004001", "name": "Feed测试用户", "password": "test123456"},
    )
    return resp.json()["access_token"]


async def _create_project(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": "Feed 测试项目", "total_area": 100.0},
        headers=headers,
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_feed_empty_project(client: AsyncClient):
    """无数据项目：feed 返回空卡片列表 + 诚实标注"""
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)

    resp = await client.get(f"/api/feed/{project_id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["cards"] == []
    assert "source_note" in body


@pytest.mark.asyncio
async def test_feed_composes_cards_from_project_data(client: AsyncClient):
    """有数据项目：feed 组合出 design_plan / construction_progress / alert_card / budget_breakdown"""
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)

    # 户型方案（design_plan 数据源）
    fp_resp = await client.post(
        "/api/floorplans",
        json={
            "project_id": project_id,
            "name": "三室两厅",
            "data": (
                '{"walls":[],"rooms":['
                '{"name":"客厅","room_type":"living_room","area":30.0},'
                '{"name":"主卧","room_type":"bedroom","area":18.0}]}'
            ),
            "wall_height": 2.8,
            "total_area": 96.0,
            "room_count": 2,
            "room_status": {"客厅": "in_progress", "主卧": "not_started"},
        },
        headers=headers,
    )
    assert fp_resp.status_code == 201

    # 里程碑（construction_progress 数据源）
    ms_resp = await client.post(
        "/api/construction/milestones",
        json={
            "project_id": project_id,
            "milestone_code": "mep",
            "name": "水电改造",
            "status": "in_progress",
            "payment_ratio": 0.2,
        },
        headers=headers,
    )
    assert ms_resp.status_code == 200

    # 进度预警（alert_card 数据源）
    alert_resp = await client.post(
        "/api/construction/progress-alerts",
        json={
            "project_id": project_id,
            "phase": "水电改造",
            "severity": "high",
            "message": "水电验收延期 3 天",
            "suggestion": "协调水电班组优先排期",
        },
        headers=headers,
    )
    assert alert_resp.status_code == 201

    # 预算（budget_breakdown 数据源）
    budget_resp = await client.post(
        "/api/budgets",
        json={
            "project_id": project_id,
            "lines": [
                {"category": "硬装", "name": "水电改造", "estimated_amount": 20000.0},
            ],
        },
        headers=headers,
    )
    assert budget_resp.status_code == 201

    # ── feed ──
    resp = await client.get(f"/api/feed/{project_id}", headers=headers)
    assert resp.status_code == 200
    cards = resp.json()["cards"]
    types = {c["type"] for c in cards}

    assert "design_plan" in types
    assert "construction_progress" in types
    assert "alert_card" in types
    assert "budget_breakdown" in types

    design = next(c for c in cards if c["type"] == "design_plan")
    assert design["data"]["total_area"] == 96.0
    assert len(design["data"]["rooms"]) == 2

    alert = next(c for c in cards if c["type"] == "alert_card")
    assert alert["data"]["severity"] == "high"
    assert "水电验收延期" in alert["data"]["message"]
    assert alert["data"]["source_agent"] == "health_os"

    progress = next(c for c in cards if c["type"] == "construction_progress")
    assert progress["data"]["overall_progress"] == 0.0  # 无实际完成
    assert progress["data"]["phases"][0]["name"] == "水电改造"

    budget = next(c for c in cards if c["type"] == "budget_breakdown")
    assert len(budget["data"]["items"]) == 1


@pytest.mark.asyncio
async def test_feed_requires_access(client: AsyncClient):
    """feed 接口校验项目访问权限"""
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/feed/nonexistent-id", headers=headers)
    # 项目不存在/无权限 → 4xx
    assert resp.status_code in (403, 404)
