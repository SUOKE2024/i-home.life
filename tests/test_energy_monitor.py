"""A1 智能家居能耗监测 API 集成测试

覆盖端点:
- POST /api/energy/records              (能耗记录)
- GET  /api/energy/records/scheme/{id}  (按方案)
- GET  /api/energy/records/project/{id} (按项目)
- GET  /api/energy/report/{id}         (能耗报告)
- GET  /api/energy/tips/{id}           (节能建议)
- PATCH /api/energy/tips/{id}/apply    (采纳建议)
"""
import pytest
from httpx import AsyncClient


async def _auth_headers(client: AsyncClient, phone: str = "13900020001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "能耗监测测试", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "能耗监测项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 100.0}, headers=headers,
    )
    return resp.json()["id"]


async def _create_scheme(client: AsyncClient, headers: dict, project_id: str) -> str:
    resp = await client.post(
        "/api/smart-home/schemes",
        json={"project_id": project_id, "room_name": "全屋", "room_type": "living_room"},
        headers=headers,
    )
    return resp.json()["id"]


# ── 能耗记录 ──


@pytest.mark.asyncio
async def test_create_energy_record(client: AsyncClient):
    """创建能耗监测记录 — 自动计算费用和碳排放"""
    headers = await _auth_headers(client, "13900020011")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)

    resp = await client.post(
        "/api/energy/records",
        json={
            "project_id": project_id,
            "scheme_id": scheme_id,
            "period": "daily",
            "total_consumption_kwh": 50.0,
            "device_breakdown": {"light": 10.0, "ac": 30.0, "tv": 10.0},
            "peak_power_w": 5000.0,
            "avg_power_w": 2000.0,
            "standby_consumption_kwh": 3.0,
            "recorded_at": "2026-07-25T00:00:00",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["total_consumption_kwh"] == 50.0
    assert data["estimated_cost"] == 30.0   # 50 kWh × 0.6 元
    assert data["carbon_footprint_kg"] == 29.05  # 50 × 0.581
    assert data["period"] == "daily"


@pytest.mark.asyncio
async def test_get_records_by_scheme(client: AsyncClient):
    """按方案获取能耗记录"""
    headers = await _auth_headers(client, "13900020012")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)

    await client.post(
        "/api/energy/records",
        json={
            "project_id": project_id, "scheme_id": scheme_id,
            "period": "daily", "total_consumption_kwh": 30.0,
            "peak_power_w": 3000, "avg_power_w": 1500,
            "recorded_at": "2026-07-25T00:00:00",
        },
        headers=headers,
    )

    resp = await client.get(
        f"/api/energy/records/scheme/{scheme_id}",
        headers=headers,
    )
    assert resp.status_code == 200
    records = resp.json()
    assert len(records) >= 1
    assert records[0]["total_consumption_kwh"] == 30.0


@pytest.mark.asyncio
async def test_get_records_by_project(client: AsyncClient):
    """按项目获取能耗记录"""
    headers = await _auth_headers(client, "13900020013")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)

    for _ in range(2):
        await client.post(
            "/api/energy/records",
            json={
                "project_id": project_id, "scheme_id": scheme_id,
                "period": "daily", "total_consumption_kwh": 20.0,
                "peak_power_w": 2000, "avg_power_w": 1000,
                "recorded_at": "2026-07-25T00:00:00",
            },
            headers=headers,
        )

    resp = await client.get(
        f"/api/energy/records/project/{project_id}",
        headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# ── 能耗报告 ──


@pytest.mark.asyncio
async def test_generate_energy_report(client: AsyncClient):
    """生成能耗汇总报告"""
    headers = await _auth_headers(client, "13900020014")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)

    await client.post(
        "/api/energy/records",
        json={
            "project_id": project_id, "scheme_id": scheme_id,
            "period": "daily",
            "total_consumption_kwh": 100.0,
            "device_breakdown": {"ac": 60.0, "light": 20.0, "tv": 20.0},
            "peak_power_w": 6000,
            "avg_power_w": 2500,
            "standby_consumption_kwh": 10.0,
            "recorded_at": "2026-07-25T00:00:00",
        },
        headers=headers,
    )

    resp = await client.get(
        f"/api/energy/report/{scheme_id}",
        headers=headers,
    )
    assert resp.status_code == 200
    report = resp.json()
    assert report["total_consumption_kwh"] == 100.0
    assert len(report["device_ranking"]) > 0
    # 待机能耗 10 kWh / 100 kWh = 10%
    assert report["standby_ratio"] > 0


# ── 节能建议 ──


@pytest.mark.asyncio
async def test_get_energy_tips(client: AsyncClient):
    """获取节能建议 — 高待机能耗自动生成 standby_reduction 建议"""
    headers = await _auth_headers(client, "13900020015")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)

    # 创建高待机能耗记录 (30%)
    await client.post(
        "/api/energy/records",
        json={
            "project_id": project_id, "scheme_id": scheme_id,
            "period": "daily",
            "total_consumption_kwh": 50.0,
            "device_breakdown": {"ac": 30.0, "light": 10.0, "tv": 10.0},
            "peak_power_w": 4000,
            "avg_power_w": 2000,
            "standby_consumption_kwh": 15.0,  # 30% standby
            "recorded_at": "2026-07-25T00:00:00",
        },
        headers=headers,
    )

    resp = await client.get(
        f"/api/energy/tips/{scheme_id}",
        headers=headers,
    )
    assert resp.status_code == 200
    tips = resp.json()
    assert len(tips) >= 1
    # 应该有 standby_reduction 建议
    tip_types = {t["tip_type"] for t in tips}
    assert "standby_reduction" in tip_types


@pytest.mark.asyncio
async def test_apply_energy_tip(client: AsyncClient):
    """采纳节能建议"""
    headers = await _auth_headers(client, "13900020016")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)

    # 创建高待机能耗记录以生成建议
    await client.post(
        "/api/energy/records",
        json={
            "project_id": project_id, "scheme_id": scheme_id,
            "period": "daily",
            "total_consumption_kwh": 50.0,
            "device_breakdown": {"ac": 30.0, "light": 10.0, "tv": 10.0},
            "peak_power_w": 4000,
            "avg_power_w": 2000,
            "standby_consumption_kwh": 15.0,
            "recorded_at": "2026-07-25T00:00:00",
        },
        headers=headers,
    )

    # 获取建议列表
    tips_resp = await client.get(f"/api/energy/tips/{scheme_id}", headers=headers)
    tips = tips_resp.json()
    assert len(tips) > 0

    # 采纳第一条建议
    tip_id = tips[0]["id"]
    resp = await client.patch(
        f"/api/energy/tips/{tip_id}/apply",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "applied"


# ── 越权校验 ──


@pytest.mark.asyncio
async def test_energy_unauthorized(client: AsyncClient):
    """未认证用户不能创建能耗记录"""
    resp = await client.post(
        "/api/energy/records",
        json={
            "project_id": "fake", "scheme_id": "fake",
            "period": "daily", "total_consumption_kwh": 10.0,
            "peak_power_w": 1000, "avg_power_w": 500,
            "recorded_at": "2026-07-25T00:00:00",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_energy_foreign_scheme_blocked(client: AsyncClient):
    """用户不能访问不属于自己的方案的能耗记录"""
    headers_a = await _auth_headers(client, "13900020017")
    headers_b = await _auth_headers(client, "13900020018")
    project_id_a = await _create_project(client, headers_a)
    scheme_id_a = await _create_scheme(client, headers_a, project_id_a)

    resp = await client.get(
        f"/api/energy/records/scheme/{scheme_id_a}",
        headers=headers_b,
    )
    assert resp.status_code == 403
