"""变更订单 API 测试

覆盖端点:
- POST /api/change-orders
- GET  /api/change-orders/{project_id}
- GET  /api/change-orders/{project_id}/{id}
- PATCH /api/change-orders/{id}/status
"""
import uuid
import json
import pytest
from httpx import AsyncClient


async def _create_project(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": f"变更测试项目-{uuid.uuid4().hex[:6]}", "total_area": 100.0},
        headers=headers,
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_change_orders_unauthorized(client: AsyncClient):
    """未认证用户无法访问变更订单"""
    resp = await client.get("/api/change-orders/fake-id")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_change_order(auth_headers: dict, client: AsyncClient):
    """创建变更订单"""
    project_id = await _create_project(client, auth_headers)
    resp = await client.post(
        "/api/change-orders",
        json={
            "project_id": project_id,
            "title": "墙面材料变更",
            "change_type": "material",
            "description": "乳胶漆改为艺术漆",
            "cost_change": 5000.0,
        },
        headers=auth_headers,
    )
    assert resp.status_code in (200, 201)


@pytest.mark.asyncio
async def test_list_change_orders(auth_headers: dict, client: AsyncClient):
    """列出项目变更订单"""
    project_id = await _create_project(client, auth_headers)
    await client.post(
        "/api/change-orders",
        json={
            "project_id": project_id,
            "title": "插座移位",
            "change_type": "design",
            "description": "电视墙插座上移20cm",
            "cost_change": 300.0,
        },
        headers=auth_headers,
    )
    resp = await client.get(f"/api/change-orders/project/{project_id}", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_change_order_detail(auth_headers: dict, client: AsyncClient):
    """获取变更订单详情"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/change-orders",
        json={
            "project_id": project_id,
            "title": "吊顶方案变更",
            "change_type": "design",
            "description": "增加无主灯吊顶",
            "cost_change": 8000.0,
        },
        headers=auth_headers,
    )
    co_id = create_resp.json()["id"]
    resp = await client.get(f"/api/change-orders/{co_id}", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_change_order_status(auth_headers: dict, client: AsyncClient):
    """更新变更订单状态"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/change-orders",
        json={
            "project_id": project_id,
            "title": "瓷砖升级",
            "change_type": "material",
            "description": "普通瓷砖升级为大理石",
            "cost_change": 12000.0,
        },
        headers=auth_headers,
    )
    co_id = create_resp.json()["id"]
    # v1.2.x 状态机：pending → review（评审）→ approve（审批），不允许 pending 直接 approve
    review = await client.post(
        f"/api/change-orders/{co_id}/review",
        json={"feasibility": "feasible", "cost_impact": 12000.0},
        headers=auth_headers,
    )
    assert review.status_code == 200
    resp = await client.post(
        f"/api/change-orders/{co_id}/approve",
        headers=auth_headers,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_cross_user_change_order_access(auth_headers: dict, client: AsyncClient):
    """其他用户无法操作非自己项目的变更订单"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/change-orders",
        json={
            "project_id": project_id,
            "title": "跨用户测试",
            "change_type": "material",
            "description": "不应被访问",
            "cost_change": 100.0,
        },
        headers=auth_headers,
    )
    co_id = create_resp.json()["id"]
    reg = await client.post(
        "/api/auth/register",
        json={"phone": f"1396601{uuid.uuid4().int % 10000:04d}", "name": "他人", "password": "test123456"},
    )
    other_headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    resp = await client.post(
        f"/api/change-orders/{co_id}/approve",
        headers=other_headers,
    )
    assert resp.status_code in (403, 404)


# ── F39 变更管理 Agent 自动评估 ──


@pytest.mark.asyncio
async def test_review_manual_assessment_source(auth_headers: dict, client: AsyncClient):
    """人工传入评估字段 → assessment_source=manual（向后兼容路径不变）"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/change-orders",
        json={
            "project_id": project_id,
            "title": "人工评估",
            "change_type": "design",
            "description": "电视墙插座上移",
        },
        headers=auth_headers,
    )
    co_id = create_resp.json()["id"]
    resp = await client.post(
        f"/api/change-orders/{co_id}/review",
        json={"feasibility": "feasible", "feasibility_note": "人工评估：可行", "cost_impact": 500.0},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["assessment_source"] == "manual"
    assert body["feasibility"] == "feasible"
    assert body["cost_impact"] == 500.0
    assert body["status"] == "reviewing"


@pytest.mark.asyncio
async def test_review_auto_assessment_source_agent(auth_headers: dict, client: AsyncClient):
    """未传人工评估字段 → Agent 规则引擎自动评估 → assessment_source=agent"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/change-orders",
        json={
            "project_id": project_id,
            "title": "客厅改造",
            "change_type": "design",
            "description": "126㎡ 客厅改造",
            "items": [
                {
                    "name": "客厅",
                    "action": "modify",
                    "target_type": "room",
                    "after_data": json.dumps(
                        {"name": "客厅", "type": "living_room", "x": 0.5, "y": 0.5, "w": 5.5, "h": 4.5},
                        ensure_ascii=False,
                    ),
                    "quantity": 1,
                    "unit_price": 5000,
                }
            ],
        },
        headers=auth_headers,
    )
    co_id = create_resp.json()["id"]
    resp = await client.post(f"/api/change-orders/{co_id}/review", json={}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["assessment_source"] == "agent"
    assert body["feasibility"] == "feasible"
    assert body["cost_impact"] == 5000.0  # 明细金额汇总（精确）
    assert body["status"] == "reviewing"


@pytest.mark.asyncio
async def test_review_auto_assessment_degraded(auth_headers: dict, client: AsyncClient, monkeypatch):
    """Agent 评估失败 → 诚实降级 assessment_source=unavailable，结论 pending，不伪造"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/change-orders",
        json={
            "project_id": project_id,
            "title": "自动评估失败",
            "change_type": "design",
            "description": "降级测试",
        },
        headers=auth_headers,
    )
    co_id = create_resp.json()["id"]

    async def _boom(_order):
        raise RuntimeError("LLM 不可用")

    monkeypatch.setattr("app.services.change_order_service.auto_assess_change_order", _boom)
    resp = await client.post(f"/api/change-orders/{co_id}/review", json={}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["assessment_source"] == "unavailable"
    assert body["feasibility"] == "pending"
    assert body["status"] == "pending"  # 状态机未推进
    assert body["assessment_note"]
    assert "待人工评估" in body["assessment_note"]
