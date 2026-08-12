"""视觉表现层 VR 全景 API 集成测试

覆盖端点:
- POST   /api/vr/panoramas                             (创建全景图)
- GET    /api/vr/panoramas/project/{project_id}         (按项目列全景图)
- GET    /api/vr/panoramas/{panorama_id}                (全景图详情)
- PATCH  /api/vr/panoramas/{panorama_id}                (更新全景图)
- POST   /api/vr/panoramas/{panorama_id}/render          (渲染全景图)
- DELETE /api/vr/panoramas/{panorama_id}                (删除全景图)
- POST   /api/vr/panoramas/{panorama_id}/hotspots        (添加热点)
- GET    /api/vr/panoramas/{panorama_id}/hotspots         (列出热点)
- DELETE /api/vr/hotspots/{panorama_id}/{hotspot_index}   (删除热点)
- POST   /api/vr/scenes                                 (创建 VR 场景)
- GET    /api/vr/scenes/project/{project_id}             (按项目列场景)
- GET    /api/vr/scenes/{scene_id}                       (场景详情)
- PATCH  /api/vr/scenes/{scene_id}                       (更新场景)
- DELETE /api/vr/scenes/{scene_id}                       (删除场景)
"""
import pytest
from httpx import AsyncClient


async def _auth_headers(client: AsyncClient, phone: str = "13960060001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "VR 测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "VR 测试项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 100.0}, headers=headers,
    )
    return resp.json()["id"]


async def _create_panorama(
    client: AsyncClient, headers: dict, project_id: str, room_name: str = "客厅",
) -> dict:
    resp = await client.post(
        "/api/vr/panoramas",
        json={
            "project_id": project_id,
            "room_name": room_name,
            "panorama_type": "equirectangular",
            "resolution": "4K",
            "render_quality": "standard",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()


# ── Auth ──


@pytest.mark.asyncio
async def test_vr_panorama_unauthorized(client: AsyncClient):
    """未认证用户不能创建全景图"""
    resp = await client.post(
        "/api/vr/panoramas",
        json={
            "project_id": "fake", "room_name": "客厅",
            "panorama_type": "equirectangular",
        },
    )
    assert resp.status_code == 401


# ── 全景图 CRUD ──


@pytest.mark.asyncio
async def test_create_and_get_panorama(client: AsyncClient):
    """创建并获取全景图"""
    headers = await _auth_headers(client, "13960060002")
    project_id = await _create_project(client, headers)

    created = await _create_panorama(client, headers, project_id, "客厅")
    assert created["room_name"] == "客厅"
    assert created["panorama_type"] == "equirectangular"
    # v1.2.x 起全景渲染走异步队列，初始状态为 queued
    assert created["status"] in ("queued", "pending", "rendering", "draft", "ready")

    resp = await client.get(f"/api/vr/panoramas/{created['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["room_name"] == "客厅"


@pytest.mark.asyncio
async def test_list_panoramas_by_project(client: AsyncClient):
    """按项目列出全景图"""
    headers = await _auth_headers(client, "13960060003")
    project_id = await _create_project(client, headers)

    await _create_panorama(client, headers, project_id, "客厅")
    await _create_panorama(client, headers, project_id, "主卧")

    resp = await client.get(f"/api/vr/panoramas/project/{project_id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_update_panorama(client: AsyncClient):
    """更新全景图元数据"""
    headers = await _auth_headers(client, "13960060004")
    project_id = await _create_project(client, headers)
    panorama = await _create_panorama(client, headers, project_id, "客厅")

    resp = await client.patch(
        f"/api/vr/panoramas/{panorama['id']}",
        json={"status": "ready"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_render_panorama(client: AsyncClient):
    """触发全景图渲染"""
    headers = await _auth_headers(client, "13960060005")
    project_id = await _create_project(client, headers)
    panorama = await _create_panorama(client, headers, project_id, "客厅")

    resp = await client.post(
        f"/api/vr/panoramas/{panorama['id']}/render",
        json={"quality": "standard"},
        headers=headers,
    )
    # 渲染可能返回 mock 结果
    assert resp.status_code in (200, 201, 202)


# ── 热点 ──


@pytest.mark.asyncio
async def test_add_and_list_hotspots(client: AsyncClient):
    """添加并列出热点"""
    headers = await _auth_headers(client, "13960060006")
    project_id = await _create_project(client, headers)
    panorama = await _create_panorama(client, headers, project_id, "客厅")

    # 添加热点
    resp = await client.post(
        f"/api/vr/panoramas/{panorama['id']}/hotspots",
        json={
            "type": "panorama",
            "position": {"yaw": 45.0, "pitch": 0.0},
            "label": "进入主卧",
            "target_panorama_id": "some-other-panorama",
        },
        headers=headers,
    )
    assert resp.status_code == 200

    # 列出热点
    resp = await client.get(
        f"/api/vr/panoramas/{panorama['id']}/hotspots", headers=headers,
    )
    assert resp.status_code == 200
    hotspots = resp.json()
    assert len(hotspots) >= 1


@pytest.mark.asyncio
async def test_add_exhibit_hotspot_with_material(client: AsyncClient):
    """M4 智能展厅：展品热点（type=exhibit + material_id）创建并透传返回"""
    headers = await _auth_headers(client, "13960060018")
    project_id = await _create_project(client, headers)
    panorama = await _create_panorama(client, headers, project_id, "瓷砖展厅")

    resp = await client.post(
        f"/api/vr/panoramas/{panorama['id']}/hotspots",
        json={
            "type": "exhibit",
            "position": {"yaw": 90.0, "pitch": -5.0},
            "label": "岩板瓷砖",
            "material_id": "mat-example-001",
        },
        headers=headers,
    )
    assert resp.status_code == 200

    resp = await client.get(
        f"/api/vr/panoramas/{panorama['id']}/hotspots", headers=headers,
    )
    hotspots = resp.json()
    exhibit = next((h for h in hotspots if h.get("type") == "exhibit"), None)
    assert exhibit is not None
    assert exhibit["material_id"] == "mat-example-001"
    assert exhibit["label"] == "岩板瓷砖"


@pytest.mark.asyncio
async def test_delete_hotspot(client: AsyncClient):
    """通过索引删除热点"""
    headers = await _auth_headers(client, "13960060007")
    project_id = await _create_project(client, headers)
    panorama = await _create_panorama(client, headers, project_id, "客厅")

    # 添加热点
    await client.post(
        f"/api/vr/panoramas/{panorama['id']}/hotspots",
        json={
            "type": "info",
            "position": {"yaw": 90.0, "pitch": 0.0},
            "label": "插座位置",
        },
        headers=headers,
    )

    resp = await client.delete(
        f"/api/vr/hotspots/{panorama['id']}/0", headers=headers,
    )
    assert resp.status_code == 204

    # 确认已删除
    resp = await client.get(
        f"/api/vr/panoramas/{panorama['id']}/hotspots", headers=headers,
    )
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_delete_panorama(client: AsyncClient):
    """删除全景图"""
    headers = await _auth_headers(client, "13960060008")
    project_id = await _create_project(client, headers)
    panorama = await _create_panorama(client, headers, project_id, "客厅")

    resp = await client.delete(f"/api/vr/panoramas/{panorama['id']}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/vr/panoramas/{panorama['id']}", headers=headers)
    assert resp.status_code == 404


# ── VR 场景 ──


@pytest.mark.asyncio
async def test_create_scene_rejects_invalid_transition(client: AsyncClient):
    """转场类型契约：仅接受 fade/warp/none（v1.14.x Literal 校验）"""
    headers = await _auth_headers(client, "13960060008")
    project_id = await _create_project(client, headers)
    panorama = await _create_panorama(client, headers, project_id, "客厅")

    resp = await client.post(
        "/api/vr/scenes",
        json={
            "project_id": project_id,
            "name": "非法转场",
            "panorama_ids": [panorama["id"]],
            "transition_type": "dissolve",
        },
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_and_delete_scene(client: AsyncClient):
    """创建和删除 VR 场景"""
    headers = await _auth_headers(client, "13960060009")
    project_id = await _create_project(client, headers)
    panorama = await _create_panorama(client, headers, project_id, "客厅")

    # 创建场景
    resp = await client.post(
        "/api/vr/scenes",
        json={
            "project_id": project_id,
            "name": "全屋漫游",
            "panorama_ids": [panorama["id"]],
            "transition_type": "fade",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    scene = resp.json()
    assert scene["name"] == "全屋漫游"

    # 获取场景
    resp = await client.get(f"/api/vr/scenes/{scene['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "全屋漫游"

    # 列出场景
    resp = await client.get(f"/api/vr/scenes/project/{project_id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # 更新场景
    resp = await client.patch(
        f"/api/vr/scenes/{scene['id']}",
        json={"name": "全屋漫游 v2"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "全屋漫游 v2"

    # 删除场景
    resp = await client.delete(f"/api/vr/scenes/{scene['id']}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/vr/scenes/{scene['id']}", headers=headers)
    assert resp.status_code == 404


# ── 越权校验 ──


@pytest.mark.asyncio
async def test_vr_cross_user_access_blocked(client: AsyncClient):
    """用户不能访问他人的全景图"""
    headers_a = await _auth_headers(client, "13960060010")
    headers_b = await _auth_headers(client, "13960060011")
    project_id_a = await _create_project(client, headers_a)
    panorama_a = await _create_panorama(client, headers_a, project_id_a, "客厅")

    resp = await client.get(
        f"/api/vr/panoramas/{panorama_a['id']}",
        headers=headers_b,
    )
    assert resp.status_code == 403
