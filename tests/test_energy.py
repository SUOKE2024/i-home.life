"""A1 智能家居能耗监测系统 API 集成测试

覆盖端点:
- POST   /api/energy/records                  (创建能耗记录)
- GET    /api/energy/records/{record_id}       (获取单条记录)
- GET    /api/energy/records/scheme/{id}       (按方案查询)
- GET    /api/energy/records/project/{id}      (按项目查询)
- DELETE /api/energy/records/{record_id}       (删除记录)
- GET    /api/energy/report/{scheme_id}        (能耗报告)
- GET    /api/energy/tips/{scheme_id}          (节能建议)
- POST   /api/energy/tips                      (手动创建建议)
- PATCH  /api/energy/tips/{tip_id}/apply       (采纳建议)
- DELETE /api/energy/tips/{tip_id}             (删除建议)
"""
import pytest
from httpx import AsyncClient


async def _auth_headers(client: AsyncClient, phone: str = "13910010001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "能耗测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "能耗测试项目") -> str:
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


async def _create_record(
    client: AsyncClient, headers: dict, project_id: str, scheme_id: str,
    total_kwh: float = 50.0,
) -> dict:
    resp = await client.post(
        "/api/energy/records",
        json={
            "project_id": project_id,
            "scheme_id": scheme_id,
            "period": "daily",
            "total_consumption_kwh": total_kwh,
            "device_breakdown": {"light": 10.0, "ac": 30.0, "tv": 10.0},
            "peak_power_w": 5000.0,
            "avg_power_w": 2000.0,
            "standby_consumption_kwh": 3.0,
            "recorded_at": "2026-07-25T00:00:00",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()


# ── Auth ──


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


# ── 能耗记录 CRUD ──


@pytest.mark.asyncio
async def test_create_energy_record(client: AsyncClient):
    """创建能耗监测记录 — 自动计算费用和碳排放"""
    headers = await _auth_headers(client, "13910010002")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)

    record = await _create_record(client, headers, project_id, scheme_id, 50.0)
    assert record["total_consumption_kwh"] == 50.0
    assert record["estimated_cost"] == 30.0   # 50 kWh * 0.6 元
    assert record["carbon_footprint_kg"] == 29.05  # 50 * 0.581
    assert record["period"] == "daily"


@pytest.mark.asyncio
async def test_get_record_by_id(client: AsyncClient):
    """获取单条能耗记录"""
    headers = await _auth_headers(client, "13910010003")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)

    created = await _create_record(client, headers, project_id, scheme_id, 30.0)
    resp = await client.get(f"/api/energy/records/{created['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total_consumption_kwh"] == 30.0


@pytest.mark.asyncio
async def test_get_records_by_scheme(client: AsyncClient):
    """按方案获取能耗记录"""
    headers = await _auth_headers(client, "13910010004")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)

    await _create_record(client, headers, project_id, scheme_id, 20.0)
    resp = await client.get(f"/api/energy/records/scheme/{scheme_id}", headers=headers)
    assert resp.status_code == 200
    records = resp.json()
    assert len(records) >= 1
    assert records[0]["total_consumption_kwh"] == 20.0


@pytest.mark.asyncio
async def test_get_records_by_project(client: AsyncClient):
    """按项目获取能耗记录"""
    headers = await _auth_headers(client, "13910010005")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)

    for _ in range(2):
        await _create_record(client, headers, project_id, scheme_id, 15.0)

    resp = await client.get(f"/api/energy/records/project/{project_id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_delete_energy_record(client: AsyncClient):
    """删除能耗记录"""
    headers = await _auth_headers(client, "13910010006")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)

    created = await _create_record(client, headers, project_id, scheme_id, 10.0)
    resp = await client.delete(f"/api/energy/records/{created['id']}", headers=headers)
    assert resp.status_code == 204

    # 确认已删除
    resp = await client.get(f"/api/energy/records/{created['id']}", headers=headers)
    assert resp.status_code == 404


# ── 能耗报告 ──


@pytest.mark.asyncio
async def test_generate_energy_report(client: AsyncClient):
    """生成能耗汇总报告"""
    headers = await _auth_headers(client, "13910010007")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)

    await _create_record(client, headers, project_id, scheme_id, 100.0)
    resp = await client.get(f"/api/energy/report/{scheme_id}", headers=headers)
    assert resp.status_code == 200
    report = resp.json()
    assert report["total_consumption_kwh"] == 100.0
    assert "device_ranking" in report


# ── 节能建议 ──


@pytest.mark.asyncio
async def test_get_and_apply_energy_tip(client: AsyncClient):
    """获取节能建议并采纳"""
    headers = await _auth_headers(client, "13910010008")
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
            "standby_consumption_kwh": 15.0,
            "recorded_at": "2026-07-25T00:00:00",
        },
        headers=headers,
    )

    # 获取建议
    tips_resp = await client.get(f"/api/energy/tips/{scheme_id}", headers=headers)
    assert tips_resp.status_code == 200
    tips = tips_resp.json()
    assert len(tips) >= 1
    tip_types = {t["tip_type"] for t in tips}
    assert "standby_reduction" in tip_types

    # 采纳第一条
    resp = await client.patch(f"/api/energy/tips/{tips[0]['id']}/apply", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "applied"


@pytest.mark.asyncio
async def test_create_and_delete_tip(client: AsyncClient):
    """手动创建并删除节能建议"""
    headers = await _auth_headers(client, "13910010009")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)

    # 创建建议
    resp = await client.post(
        "/api/energy/tips",
        json={
            "scheme_id": scheme_id,
            "tip_type": "device_replacement",
            "device_type": "light",
            "device_name": "客厅灯",
            "suggestion": "建议更换为 LED 灯",
            "priority": "high",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    tip = resp.json()
    assert tip["tip_type"] == "device_replacement"

    # 删除建议
    resp = await client.delete(f"/api/energy/tips/{tip['id']}", headers=headers)
    assert resp.status_code == 204


# ── 越权校验 ──


@pytest.mark.asyncio
async def test_energy_cross_user_access_blocked(client: AsyncClient):
    """用户不能访问他人的能耗记录"""
    headers_a = await _auth_headers(client, "13910010010")
    headers_b = await _auth_headers(client, "13910010011")
    project_id_a = await _create_project(client, headers_a)
    scheme_id_a = await _create_scheme(client, headers_a, project_id_a)

    resp = await client.get(
        f"/api/energy/records/scheme/{scheme_id_a}",
        headers=headers_b,
    )
    assert resp.status_code == 403
