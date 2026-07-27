"""F29/F30 灯光设计器 API 集成测试

覆盖端点:
- POST   /api/lighting/schemes                           (创建灯光方案)
- GET    /api/lighting/schemes/project/{project_id}       (按项目列方案)
- GET    /api/lighting/schemes/{scheme_id}                (方案详情)
- PATCH  /api/lighting/schemes/{scheme_id}                (更新方案)
- POST   /api/lighting/schemes/{scheme_id}/ai-design      (AI 灯光设计)
- POST   /api/lighting/schemes/{scheme_id}/fixtures        (添加灯具)
- GET    /api/lighting/schemes/{scheme_id}/fixtures         (列出灯具)
- DELETE /api/lighting/fixtures/{fixture_id}               (删除灯具)
- GET    /api/lighting/schemes/{scheme_id}/illuminance     (照度计算)
- DELETE /api/lighting/schemes/{scheme_id}                (删除方案)
"""
import pytest
from httpx import AsyncClient


async def _auth_headers(client: AsyncClient, phone: str = "13930030001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "灯光测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "灯光测试项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 100.0}, headers=headers,
    )
    return resp.json()["id"]


async def _create_scheme(
    client: AsyncClient, headers: dict, project_id: str, room_name: str = "客厅",
) -> dict:
    resp = await client.post(
        "/api/lighting/schemes",
        json={
            "project_id": project_id, "room_name": room_name,
            "scheme_type": "main_light", "room_area": 25.0,
            "ceiling_height": 2.8,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()


# ── Auth ──


@pytest.mark.asyncio
async def test_lighting_unauthorized(client: AsyncClient):
    """未认证用户不能创建灯光方案"""
    resp = await client.post(
        "/api/lighting/schemes",
        json={
            "project_id": "fake", "room_name": "客厅",
            "scheme_type": "main_light", "room_area": 25.0,
        },
    )
    assert resp.status_code == 401


# ── 方案 CRUD ──


@pytest.mark.asyncio
async def test_create_and_get_scheme(client: AsyncClient):
    """创建并获取灯光方案"""
    headers = await _auth_headers(client, "13930030002")
    project_id = await _create_project(client, headers)

    created = await _create_scheme(client, headers, project_id, "客厅")
    assert created["room_name"] == "客厅"
    assert created["scheme_type"] == "main_light"
    assert created["room_area"] == 25.0

    resp = await client.get(f"/api/lighting/schemes/{created['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["room_name"] == "客厅"


@pytest.mark.asyncio
async def test_list_schemes_by_project(client: AsyncClient):
    """按项目列出灯光方案"""
    headers = await _auth_headers(client, "13930030003")
    project_id = await _create_project(client, headers)

    await _create_scheme(client, headers, project_id, "客厅")
    await _create_scheme(client, headers, project_id, "厨房")

    resp = await client.get(f"/api/lighting/schemes/project/{project_id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_update_scheme(client: AsyncClient):
    """更新灯光方案"""
    headers = await _auth_headers(client, "13930030004")
    project_id = await _create_project(client, headers)
    created = await _create_scheme(client, headers, project_id, "客厅")

    resp = await client.patch(
        f"/api/lighting/schemes/{created['id']}",
        json={"scheme_type": "mixed", "color_temp_k": 4000, "cri": 95.0},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["scheme_type"] == "mixed"
    assert data["color_temp_k"] == 4000
    assert data["cri"] == 95.0


# ── 灯具 CRUD ──


@pytest.mark.asyncio
async def test_add_and_list_fixtures(client: AsyncClient):
    """添加和列出灯具"""
    headers = await _auth_headers(client, "13930030005")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id, "客厅")

    # 添加灯具
    resp = await client.post(
        f"/api/lighting/schemes/{scheme['id']}/fixtures",
        json={
            "scheme_id": scheme["id"],
            "fixture_type": "spot",
            "brand": "Philips",
            "model": "Hue White",
            "wattage_w": 9.0,
            "lumens": 800.0,
            "color_temp_k": 4000,
            "quantity": 4,
            "dimmable": True,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    fixture = resp.json()
    assert fixture["fixture_type"] == "spot"
    assert fixture["quantity"] == 4

    # 列出灯具
    resp = await client.get(
        f"/api/lighting/schemes/{scheme['id']}/fixtures", headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_delete_fixture(client: AsyncClient):
    """删除灯具"""
    headers = await _auth_headers(client, "13930030006")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id, "客厅")

    resp = await client.post(
        f"/api/lighting/schemes/{scheme['id']}/fixtures",
        json={
            "scheme_id": scheme["id"],
            "fixture_type": "spot",
            "wattage_w": 5.0,
            "lumens": 400.0,
            "quantity": 2,
        },
        headers=headers,
    )
    fixture_id = resp.json()["id"]

    resp = await client.delete(f"/api/lighting/fixtures/{fixture_id}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(
        f"/api/lighting/schemes/{scheme['id']}/fixtures", headers=headers,
    )
    assert len(resp.json()) == 0


# ── AI 设计 ──


@pytest.mark.asyncio
async def test_ai_design(client: AsyncClient):
    """AI 自动灯光设计"""
    headers = await _auth_headers(client, "13930030007")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id, "卧室")

    resp = await client.post(
        f"/api/lighting/schemes/{scheme['id']}/ai-design",
        json={"room_type": "bedroom", "style": "warm"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    # 卧室推荐无主灯方案（ROOM_SCHEME_TYPE["bedroom"] = "none_main"）
    assert data["scheme_type"] == "none_main"
    # AI 设计应自动创建灯具
    resp = await client.get(
        f"/api/lighting/schemes/{scheme['id']}/fixtures", headers=headers,
    )
    assert len(resp.json()) >= 1


# ── 照度计算 ──


@pytest.mark.asyncio
async def test_compute_illuminance(client: AsyncClient):
    """照度计算结果"""
    headers = await _auth_headers(client, "13930030008")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id, "书房")

    # 添加灯具以产生照度
    await client.post(
        f"/api/lighting/schemes/{scheme['id']}/fixtures",
        json={
            "scheme_id": scheme["id"],
            "fixture_type": "spot",
            "wattage_w": 9.0,
            "lumens": 800.0,
            "quantity": 4,
        },
        headers=headers,
    )

    resp = await client.get(
        f"/api/lighting/schemes/{scheme['id']}/illuminance", headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["scheme_id"] == scheme["id"]
    # 照度字段
    assert "average_lux" in data or "illuminance" in data


# ── 删除方案 ──


@pytest.mark.asyncio
async def test_delete_scheme(client: AsyncClient):
    """删除灯光方案"""
    headers = await _auth_headers(client, "13930030009")
    project_id = await _create_project(client, headers)
    scheme = await _create_scheme(client, headers, project_id, "客厅")

    resp = await client.delete(f"/api/lighting/schemes/{scheme['id']}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/lighting/schemes/{scheme['id']}", headers=headers)
    assert resp.status_code == 404


# ── 越权校验 ──


@pytest.mark.asyncio
async def test_lighting_cross_user_access_blocked(client: AsyncClient):
    """用户不能访问他人的灯光方案"""
    headers_a = await _auth_headers(client, "13930030010")
    headers_b = await _auth_headers(client, "13930030011")
    project_id_a = await _create_project(client, headers_a)
    scheme_a = await _create_scheme(client, headers_a, project_id_a, "客厅")

    resp = await client.get(
        f"/api/lighting/schemes/{scheme_a['id']}",
        headers=headers_b,
    )
    assert resp.status_code == 403
