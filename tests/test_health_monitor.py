"""A2 智能家居健康监测系统 API 集成测试

覆盖端点:
- POST /api/health-monitor/records          (健康监测记录)
- GET  /api/health-monitor/records/project/{id}
- GET  /api/health-monitor/report/{id}
- POST /api/health-monitor/air-quality      (空气质量记录)
- GET  /api/health-monitor/air-quality/{id}
- GET  /api/health-monitor/air-quality/{id}/latest
"""
import pytest
from httpx import AsyncClient


async def _auth_headers(client: AsyncClient, phone: str = "13900010001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "健康监测测试", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "健康监测项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 90.0}, headers=headers,
    )
    return resp.json()["id"]


async def _create_scheme(client: AsyncClient, headers: dict, project_id: str) -> str:
    resp = await client.post(
        "/api/smart-home/schemes",
        json={"project_id": project_id, "room_name": "客厅", "room_type": "living_room"},
        headers=headers,
    )
    return resp.json()["id"]


# ── 健康监测记录 ──


@pytest.mark.asyncio
async def test_create_health_record_sleep(client: AsyncClient):
    """创建睡眠质量监测记录 — 阈值检测触发预警"""
    headers = await _auth_headers(client, "13900010011")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)

    resp = await client.post(
        "/api/health-monitor/records",
        json={
            "project_id": project_id,
            "scheme_id": scheme_id,
            "monitor_type": "sleep_quality",
            "value": {"sleep_score": 55, "deep_sleep_hours": 1.5, "total_sleep_hours": 5.2},
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["monitor_type"] == "sleep_quality"
    assert data["alert_level"] == "warning"
    assert "睡眠分数" in data["alert_message"]
    assert data["value"]["sleep_score"] == 55


@pytest.mark.asyncio
async def test_create_health_record_heart_rate_normal(client: AsyncClient):
    """心率正常不触发预警"""
    headers = await _auth_headers(client, "13900010012")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)

    resp = await client.post(
        "/api/health-monitor/records",
        json={
            "project_id": project_id,
            "scheme_id": scheme_id,
            "monitor_type": "heart_rate",
            "value": {"bpm": 72},
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["monitor_type"] == "heart_rate"
    assert data["alert_level"] == "normal"
    assert data["alert_message"] is None


@pytest.mark.asyncio
async def test_create_health_record_heart_rate_high(client: AsyncClient):
    """心率偏高触发预警"""
    headers = await _auth_headers(client, "13900010013")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)

    resp = await client.post(
        "/api/health-monitor/records",
        json={
            "project_id": project_id,
            "scheme_id": scheme_id,
            "monitor_type": "heart_rate",
            "value": {"bpm": 115},
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["monitor_type"] == "heart_rate"
    assert data["alert_level"] == "warning"
    assert "心率偏高" in data["alert_message"]


@pytest.mark.asyncio
async def test_create_health_record_spo2_critical(client: AsyncClient):
    """血氧严重偏低触发 critical"""
    headers = await _auth_headers(client, "13900010014")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)

    resp = await client.post(
        "/api/health-monitor/records",
        json={
            "project_id": project_id,
            "scheme_id": scheme_id,
            "monitor_type": "spo2",
            "value": {"spo2": 88},
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["monitor_type"] == "spo2"
    assert data["alert_level"] == "critical"
    assert "血氧饱和度严重偏低" in data["alert_message"]


@pytest.mark.asyncio
async def test_create_health_record_fall_detection(client: AsyncClient):
    """跌倒检测触发 critical"""
    headers = await _auth_headers(client, "13900010015")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)

    resp = await client.post(
        "/api/health-monitor/records",
        json={
            "project_id": project_id,
            "scheme_id": scheme_id,
            "monitor_type": "fall_detection",
            "value": {"fall_detected": True, "location": "主卧"},
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["monitor_type"] == "fall_detection"
    assert data["alert_level"] == "critical"


@pytest.mark.asyncio
async def test_list_health_records(client: AsyncClient):
    """按项目列出健康监测记录"""
    headers = await _auth_headers(client, "13900010016")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)

    for _ in range(3):
        await client.post(
            "/api/health-monitor/records",
            json={
                "project_id": project_id, "scheme_id": scheme_id,
                "monitor_type": "heart_rate", "value": {"bpm": 72},
            },
            headers=headers,
        )

    resp = await client.get(
        f"/api/health-monitor/records/project/{project_id}",
        headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_list_health_records_filtered(client: AsyncClient):
    """按类型筛选健康监测记录"""
    headers = await _auth_headers(client, "13900010017")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)

    await client.post(
        "/api/health-monitor/records",
        json={
            "project_id": project_id, "scheme_id": scheme_id,
            "monitor_type": "sleep_quality", "value": {"sleep_score": 80},
        },
        headers=headers,
    )
    await client.post(
        "/api/health-monitor/records",
        json={
            "project_id": project_id, "scheme_id": scheme_id,
            "monitor_type": "heart_rate", "value": {"bpm": 72},
        },
        headers=headers,
    )

    resp = await client.get(
        f"/api/health-monitor/records/project/{project_id}?monitor_type=sleep_quality",
        headers=headers,
    )
    assert resp.status_code == 200
    records = resp.json()
    assert all(r["monitor_type"] == "sleep_quality" for r in records)


# ── 健康报告 ──


@pytest.mark.asyncio
async def test_generate_health_report(client: AsyncClient):
    """生成综合健康报告"""
    headers = await _auth_headers(client, "13900010018")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)

    # 添加多条记录
    await client.post(
        "/api/health-monitor/records",
        json={
            "project_id": project_id, "scheme_id": scheme_id,
            "monitor_type": "sleep_quality", "value": {"sleep_score": 85},
        },
        headers=headers,
    )
    await client.post(
        "/api/health-monitor/records",
        json={
            "project_id": project_id, "scheme_id": scheme_id,
            "monitor_type": "sleep_quality", "value": {"sleep_score": 75},
        },
        headers=headers,
    )
    await client.post(
        "/api/health-monitor/records",
        json={
            "project_id": project_id, "scheme_id": scheme_id,
            "monitor_type": "heart_rate", "value": {"bpm": 110},
        },
        headers=headers,
    )

    resp = await client.get(
        f"/api/health-monitor/report/{project_id}",
        headers=headers,
    )
    assert resp.status_code == 200
    report = resp.json()
    assert report["total_records"] == 3
    assert report["alert_records"] == 1
    assert report["sleep_avg_score"] == 80.0
    assert report["project_id"] == project_id
    assert len(report["recommendations"]) > 0


@pytest.mark.asyncio
async def test_health_report_no_records(client: AsyncClient):
    """无记录时报告仍可生成"""
    headers = await _auth_headers(client, "13900010019")
    project_id = await _create_project(client, headers)

    resp = await client.get(
        f"/api/health-monitor/report/{project_id}",
        headers=headers,
    )
    assert resp.status_code == 200
    report = resp.json()
    assert report["total_records"] == 0
    assert report["alert_records"] == 0
    assert report["sleep_avg_score"] is None


# ── 空气质量记录 ──


@pytest.mark.asyncio
async def test_create_air_quality_record(client: AsyncClient):
    """创建空气质量记录"""
    headers = await _auth_headers(client, "13900010021")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)

    resp = await client.post(
        "/api/health-monitor/air-quality",
        json={
            "project_id": project_id,
            "scheme_id": scheme_id,
            "room_name": "客厅",
            "pm25": 35.0,
            "pm10": 50.0,
            "co2": 600.0,
            "tvoc": 200.0,
            "formaldehyde": 0.03,
            "temperature": 25.0,
            "humidity": 55.0,
            "aqi_index": 80,
            "aqi_level": "good",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["pm25"] == 35.0
    assert data["aqi_level"] == "good"
    assert data["room_name"] == "客厅"


@pytest.mark.asyncio
async def test_list_air_quality_records(client: AsyncClient):
    """列出空气质量记录"""
    headers = await _auth_headers(client, "13900010022")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)

    await client.post(
        "/api/health-monitor/air-quality",
        json={
            "project_id": project_id, "scheme_id": scheme_id,
            "room_name": "客厅", "pm25": 35.0, "pm10": 50.0,
            "co2": 600.0, "tvoc": 200.0, "formaldehyde": 0.03,
            "temperature": 25.0, "humidity": 55.0,
            "aqi_index": 80, "aqi_level": "good",
        },
        headers=headers,
    )
    await client.post(
        "/api/health-monitor/air-quality",
        json={
            "project_id": project_id, "scheme_id": scheme_id,
            "room_name": "主卧", "pm25": 80.0, "pm10": 100.0,
            "co2": 1200.0, "tvoc": 600.0, "formaldehyde": 0.09,
            "temperature": 23.0, "humidity": 60.0,
            "aqi_index": 150, "aqi_level": "unhealthy_sensitive",
        },
        headers=headers,
    )

    resp = await client.get(
        f"/api/health-monitor/air-quality/{project_id}",
        headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_get_latest_air_quality(client: AsyncClient):
    """获取最新空气质量记录"""
    headers = await _auth_headers(client, "13900010023")
    project_id = await _create_project(client, headers)
    scheme_id = await _create_scheme(client, headers, project_id)

    await client.post(
        "/api/health-monitor/air-quality",
        json={
            "project_id": project_id, "scheme_id": scheme_id,
            "room_name": "客厅", "pm25": 35.0, "pm10": 50.0,
            "co2": 600.0, "tvoc": 200.0, "formaldehyde": 0.03,
            "temperature": 25.0, "humidity": 55.0,
            "aqi_index": 80, "aqi_level": "good",
            "recorded_at": "2026-07-24T10:00:00",
        },
        headers=headers,
    )
    await client.post(
        "/api/health-monitor/air-quality",
        json={
            "project_id": project_id, "scheme_id": scheme_id,
            "room_name": "主卧", "pm25": 20.0, "pm10": 30.0,
            "co2": 500.0, "tvoc": 100.0, "formaldehyde": 0.02,
            "temperature": 22.0, "humidity": 50.0,
            "aqi_index": 50, "aqi_level": "good",
            "recorded_at": "2026-07-25T10:00:00",
        },
        headers=headers,
    )

    resp = await client.get(
        f"/api/health-monitor/air-quality/{project_id}/latest",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["room_name"] == "主卧"


@pytest.mark.asyncio
async def test_latest_air_quality_not_found(client: AsyncClient):
    """无空气质量记录时返回 404"""
    headers = await _auth_headers(client, "13900010024")
    project_id = await _create_project(client, headers)

    resp = await client.get(
        f"/api/health-monitor/air-quality/{project_id}/latest",
        headers=headers,
    )
    assert resp.status_code == 404


# ── 越权校验 ──


@pytest.mark.asyncio
async def test_health_record_unauthorized(client: AsyncClient):
    """未认证用户不能创建健康记录"""
    resp = await client.post(
        "/api/health-monitor/records",
        json={
            "project_id": "fake",
            "scheme_id": "fake",
            "monitor_type": "heart_rate",
            "value": {"bpm": 72},
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_health_record_foreign_project_blocked(client: AsyncClient):
    """用户不能访问不属于自己的项目的健康记录"""
    headers_a = await _auth_headers(client, "13900010025")
    headers_b = await _auth_headers(client, "13900010026")
    project_id_a = await _create_project(client, headers_a)

    # 用户 B 尝试访问用户 A 的项目记录
    resp = await client.get(
        f"/api/health-monitor/records/project/{project_id_a}",
        headers=headers_b,
    )
    assert resp.status_code == 403
