import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": "13900004001", "name": "结算测试用户", "password": "test123456"},
    )
    return resp.json()["access_token"]


async def _create_project(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": "结算测试项目", "total_area": 100.0},
        headers=headers,
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_get_settlement_not_found(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)

    response = await client.get(f"/api/settlements/project/{project_id}", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_settlement(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)

    response = await client.post(
        "/api/settlements",
        json={
            "project_id": project_id,
            "milestone": "completion",
            "lines": [
                {
                    "category": "main",
                    "name": "基础工程",
                    "contract_amount": 50000.0,
                    "change_amount": 0.0,
                },
                {
                    "category": "main",
                    "name": "主材",
                    "contract_amount": 80000.0,
                    "change_amount": 5000.0,
                },
            ],
        },
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["project_id"] == project_id
    assert data["milestone"] == "completion"
    assert len(data["lines"]) == 2
    # contract_amount = (50000 + 0) + (80000 + 5000)
    assert data["contract_amount"] == 135000.0


@pytest.mark.asyncio
async def test_get_settlement(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)

    await client.post(
        "/api/settlements",
        json={
            "project_id": project_id,
            "lines": [
                {"category": "main", "name": "测试行", "contract_amount": 10000.0},
            ],
        },
        headers=headers,
    )

    response = await client.get(f"/api/settlements/project/{project_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == project_id
    assert len(data["lines"]) == 1


@pytest.mark.asyncio
async def test_create_settlement_conflict(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)

    payload = {
        "project_id": project_id,
        "lines": [
            {"category": "main", "name": "重复测试", "contract_amount": 1000.0},
        ],
    }
    first = await client.post("/api/settlements", json=payload, headers=headers)
    assert first.status_code == 201

    second = await client.post("/api/settlements", json=payload, headers=headers)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_generate_settlement_from_budget(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)

    # 先创建预算
    budget_resp = await client.post(
        "/api/budgets",
        json={
            "project_id": project_id,
            "lines": [
                {
                    "category": "main",
                    "name": "基础工程",
                    "estimated_amount": 50000.0,
                    "unit": "项",
                    "quantity": 1.0,
                    "unit_price": 50000.0,
                },
                {
                    "category": "main",
                    "name": "主材",
                    "estimated_amount": 80000.0,
                    "unit": "项",
                    "quantity": 1.0,
                    "unit_price": 80000.0,
                },
            ],
        },
        headers=headers,
    )
    assert budget_resp.status_code == 201

    response = await client.post(
        f"/api/settlements/generate-from-budget/{project_id}",
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["project_id"] == project_id
    assert len(data["lines"]) == 2
    # contract_amount 由预算 estimated_amount 汇总
    assert data["contract_amount"] == 130000.0


@pytest.mark.asyncio
async def test_generate_settlement_from_budget_no_budget(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)

    response = await client.post(
        f"/api/settlements/generate-from-budget/{project_id}",
        headers=headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_confirm_settlement(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)

    await client.post(
        "/api/settlements",
        json={
            "project_id": project_id,
            "lines": [
                {"category": "main", "name": "确认测试", "contract_amount": 20000.0},
            ],
        },
        headers=headers,
    )

    response = await client.post(
        f"/api/settlements/confirm/{project_id}",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "confirmed"
    assert data["settled_at"] is not None


@pytest.mark.asyncio
async def test_confirm_settlement_not_found(client: AsyncClient):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    project_id = await _create_project(client, headers)

    response = await client.post(
        f"/api/settlements/confirm/{project_id}",
        headers=headers,
    )
    assert response.status_code == 404
