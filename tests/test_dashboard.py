"""仪表盘聚合 API 测试 —— v1.2.9 Bento Dashboard（/api/dashboard/overview）

覆盖：路由注册（曾缺失导致 404）、无项目空态、单项目聚合、预算汇总。
"""

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, phone: str = "13900000066") -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "仪表盘测试", "password": "test123456"},
    )
    return resp.json()["access_token"]


async def _create_project(client: AsyncClient, token: str, name: str = "仪表盘项目") -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": name, "total_area": 100.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_dashboard_overview_empty(client: AsyncClient):
    """无项目时返回全 0 聚合（路由应已注册，非 404）。"""
    token = await _register_and_login(client)
    response = await client.get(
        "/api/dashboard/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, f"dashboard 路由未注册？实际 {response.status_code}"
    data = response.json()
    assert data["projects"] == {
        "total": 0, "draft": 0, "in_progress": 0, "completed": 0,
    }
    assert data["budget"]["total_estimated"] == 0.0
    assert data["budget"]["total_actual"] == 0.0
    assert data["budget"]["utilization"] == 0.0


@pytest.mark.asyncio
async def test_dashboard_overview_with_project(client: AsyncClient):
    """创建项目后聚合应计入 total/draft，预算联动。"""
    token = await _register_and_login(client)
    proj_id = await _create_project(client, token)

    # 建预算，验证 budget 聚合
    resp = await client.post(
        "/api/budgets",
        json={
            "project_id": proj_id,
            "lines": [
                {
                    "category": "硬装", "name": "墙面处理",
                    "estimated_amount": 20000.0, "unit": "㎡",
                    "quantity": 100, "unit_price": 200,
                },
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201

    response = await client.get(
        "/api/dashboard/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["projects"]["total"] == 1
    assert data["projects"]["draft"] == 1  # 默认 status=draft
    assert data["budget"]["total_estimated"] == 20000.0


@pytest.mark.asyncio
async def test_dashboard_overview_requires_auth(client: AsyncClient):
    """未登录应 401。"""
    response = await client.get("/api/dashboard/overview")
    assert response.status_code == 401
