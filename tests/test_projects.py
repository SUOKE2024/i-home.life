import pytest
from httpx import AsyncClient

from app.ws import ws_manager


async def _register_and_get_token(client: AsyncClient, phone: str = "13900001001") -> str:
    resp = await client.post(
        "/api/auth/register",
        json={
            "phone": phone,
            "name": "项目测试用户",
            "password": "test123456",
        },
    )
    return resp.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "测试项目", area: float = 100.0) -> str:
    """辅助：创建项目并返回 project_id"""
    resp = await client.post(
        "/api/projects",
        json={"name": name, "total_area": area},
        headers=headers,
    )
    return resp.json()["id"]


# ====================================================================
# CRUD 基础测试
# ====================================================================


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient):
    token = await _register_and_get_token(client)
    headers = _headers(token)

    response = await client.post(
        "/api/projects",
        json={
            "name": "测试项目-朝阳小区",
            "address": "北京市朝阳区xx路xx号",
            "total_area": 126.0,
            "floors": [
                {
                    "name": "1层",
                    "floor_number": 1,
                    "area": 126.0,
                    "rooms": [
                        {"name": "客厅", "room_type": "living_room", "area": 35.0},
                        {"name": "主卧", "room_type": "bedroom", "area": 20.0},
                        {"name": "厨房", "room_type": "kitchen", "area": 10.0},
                    ],
                }
            ],
        },
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "测试项目-朝阳小区"
    assert data["total_area"] == 126.0
    assert data["address"] == "北京市朝阳区xx路xx号"
    assert data["status"] == "draft"
    assert len(data["floors"]) == 1
    assert len(data["floors"][0]["rooms"]) == 3
    assert data["floors"][0]["rooms"][0]["room_type"] == "living_room"


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient):
    token = await _register_and_get_token(client)
    headers = _headers(token)

    await client.post(
        "/api/projects",
        json={"name": "项目A", "total_area": 80.0},
        headers=headers,
    )
    await client.post(
        "/api/projects",
        json={"name": "项目B", "total_area": 120.0},
        headers=headers,
    )

    response = await client.get("/api/projects", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # 两个项目都应在列表中（SQLite 秒级精度下不严格断言顺序）
    names = {p["name"] for p in data}
    assert names == {"项目A", "项目B"}


@pytest.mark.asyncio
async def test_get_project_detail(client: AsyncClient):
    token = await _register_and_get_token(client)
    headers = _headers(token)

    create_resp = await client.post(
        "/api/projects",
        json={
            "name": "详情测试项目",
            "total_area": 90.0,
            "floors": [
                {
                    "name": "1层",
                    "floor_number": 1,
                    "area": 90.0,
                    "rooms": [{"name": "客厅", "room_type": "living_room", "area": 30.0}],
                }
            ],
        },
        headers=headers,
    )
    project_id = create_resp.json()["id"]

    response = await client.get(f"/api/projects/{project_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == project_id
    assert data["name"] == "详情测试项目"
    assert data["total_area"] == 90.0
    assert len(data["floors"]) == 1
    assert len(data["floors"][0]["rooms"]) == 1
    assert data["floors"][0]["rooms"][0]["name"] == "客厅"


@pytest.mark.asyncio
async def test_update_project(client: AsyncClient):
    token = await _register_and_get_token(client)
    headers = _headers(token)

    create_resp = await client.post(
        "/api/projects",
        json={"name": "原始项目", "total_area": 100.0},
        headers=headers,
    )
    project_id = create_resp.json()["id"]

    response = await client.patch(
        f"/api/projects/{project_id}",
        json={"name": "已更新项目", "status": "in_progress"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "已更新项目"
    assert data["status"] == "in_progress"
    # 更新后 floors 关系应仍然可访问
    assert "floors" in data


@pytest.mark.asyncio
async def test_delete_project(client: AsyncClient):
    token = await _register_and_get_token(client)
    headers = _headers(token)

    create_resp = await client.post(
        "/api/projects",
        json={"name": "待删除项目", "total_area": 80.0},
        headers=headers,
    )
    project_id = create_resp.json()["id"]

    response = await client.delete(f"/api/projects/{project_id}", headers=headers)
    assert response.status_code == 204

    response = await client.get(f"/api/projects/{project_id}", headers=headers)
    assert response.status_code == 404


# ====================================================================
# 404 资源不存在测试
# ====================================================================


@pytest.mark.asyncio
async def test_get_nonexistent_project_returns_404(client: AsyncClient):
    token = await _register_and_get_token(client)
    headers = _headers(token)

    response = await client.get("/api/projects/nonexistent-id", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "项目不存在"


@pytest.mark.asyncio
async def test_update_nonexistent_project_returns_404(client: AsyncClient):
    token = await _register_and_get_token(client)
    headers = _headers(token)

    response = await client.patch(
        "/api/projects/nonexistent-id",
        json={"name": "不存在"},
        headers=headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "项目不存在"


@pytest.mark.asyncio
async def test_delete_nonexistent_project_returns_404(client: AsyncClient):
    token = await _register_and_get_token(client)
    headers = _headers(token)

    response = await client.delete("/api/projects/nonexistent-id", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "项目不存在"


# ====================================================================
# 401 未认证测试
# ====================================================================


@pytest.mark.asyncio
async def test_list_projects_without_token_returns_401(client: AsyncClient):
    response = await client.get("/api/projects")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_project_without_token_returns_401(client: AsyncClient):
    response = await client.post(
        "/api/projects",
        json={"name": "无认证项目", "total_area": 50.0},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_project_without_token_returns_401(client: AsyncClient):
    response = await client.get("/api/projects/some-id")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_project_without_token_returns_401(client: AsyncClient):
    response = await client.patch(
        "/api/projects/some-id",
        json={"name": "无认证更新"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_project_without_token_returns_401(client: AsyncClient):
    response = await client.delete("/api/projects/some-id")
    assert response.status_code == 401


# ====================================================================
# 403 越权访问测试（owner_id 权限校验）
# ====================================================================


@pytest.mark.asyncio
async def test_get_other_user_project_returns_403(client: AsyncClient):
    """用户 A 不能读取用户 B 的项目"""
    token_a = await _register_and_get_token(client, phone="13900002001")
    headers_a = _headers(token_a)
    project_id = await _create_project(client, headers_a, "用户A的项目")

    token_b = await _register_and_get_token(client, phone="13900002002")
    headers_b = _headers(token_b)

    response = await client.get(f"/api/projects/{project_id}", headers=headers_b)
    assert response.status_code == 403
    assert response.json()["detail"] == "无权访问此项目"


@pytest.mark.asyncio
async def test_update_other_user_project_returns_403(client: AsyncClient):
    """用户 A 不能修改用户 B 的项目"""
    token_a = await _register_and_get_token(client, phone="13900002003")
    headers_a = _headers(token_a)
    project_id = await _create_project(client, headers_a, "用户A的项目")

    token_b = await _register_and_get_token(client, phone="13900002004")
    headers_b = _headers(token_b)

    response = await client.patch(
        f"/api/projects/{project_id}",
        json={"name": "被篡改"},
        headers=headers_b,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "无权访问此项目"


@pytest.mark.asyncio
async def test_delete_other_user_project_returns_403(client: AsyncClient):
    """用户 A 不能删除用户 B 的项目"""
    token_a = await _register_and_get_token(client, phone="13900002005")
    headers_a = _headers(token_a)
    project_id = await _create_project(client, headers_a, "用户A的项目")

    token_b = await _register_and_get_token(client, phone="13900002006")
    headers_b = _headers(token_b)

    response = await client.delete(f"/api/projects/{project_id}", headers=headers_b)
    assert response.status_code == 403
    assert response.json()["detail"] == "无权访问此项目"


@pytest.mark.asyncio
async def test_list_only_returns_own_projects(client: AsyncClient):
    """项目列表只返回当前用户自己的项目"""
    token_a = await _register_and_get_token(client, phone="13900002007")
    headers_a = _headers(token_a)
    await _create_project(client, headers_a, "用户A-项目1")
    await _create_project(client, headers_a, "用户A-项目2")

    token_b = await _register_and_get_token(client, phone="13900002008")
    headers_b = _headers(token_b)
    await _create_project(client, headers_b, "用户B-项目1")

    # 用户 A 只能看到自己的 2 个项目
    resp_a = await client.get("/api/projects", headers=headers_a)
    assert resp_a.status_code == 200
    assert len(resp_a.json()) == 2

    # 用户 B 只能看到自己的 1 个项目
    resp_b = await client.get("/api/projects", headers=headers_b)
    assert resp_b.status_code == 200
    assert len(resp_b.json()) == 1
    assert resp_b.json()[0]["name"] == "用户B-项目1"


# ====================================================================
# 数据校验测试
# ====================================================================


@pytest.mark.asyncio
async def test_create_project_with_invalid_data_returns_422(client: AsyncClient):
    """空名称应返回 422 校验错误"""
    token = await _register_and_get_token(client)
    headers = _headers(token)

    response = await client.post(
        "/api/projects",
        json={"name": "", "total_area": 50.0},
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_project_minimal(client: AsyncClient):
    """仅 name 字段也能成功创建（其余字段可选）"""
    token = await _register_and_get_token(client)
    headers = _headers(token)

    response = await client.post(
        "/api/projects",
        json={"name": "极简项目"},
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "极简项目"
    assert data["status"] == "draft"
    assert data["total_area"] is None
    assert data["floors"] == []


# ====================================================================
# WebSocket 广播测试
# 验证项目变更（创建/更新/删除）会触发 ws_manager.broadcast_to_project
# ====================================================================


def _patch_broadcast_to_record_calls() -> tuple[list, callable]:
    """临时替换 ws_manager.broadcast_to_project 以记录调用，返回 (calls, restore)"""
    original = ws_manager.broadcast_to_project
    calls: list[dict] = []

    async def mock_broadcast(project_id, event, data):
        calls.append({"project_id": project_id, "event": event, "data": data})

    ws_manager.broadcast_to_project = mock_broadcast

    def restore():
        ws_manager.broadcast_to_project = original

    return calls, restore


@pytest.mark.asyncio
async def test_project_creation_triggers_broadcast(client: AsyncClient):
    """创建项目时触发 project.created 广播"""
    calls, restore = _patch_broadcast_to_record_calls()
    try:
        token = await _register_and_get_token(client, phone="13900003001")
        headers = _headers(token)

        resp = await client.post(
            "/api/projects",
            json={"name": "WS广播测试项目", "total_area": 100.0},
            headers=headers,
        )
        assert resp.status_code == 201
        project_id = resp.json()["id"]

        assert len(calls) == 1
        assert calls[0]["project_id"] == project_id
        assert calls[0]["event"] == "project.created"
        assert calls[0]["data"]["name"] == "WS广播测试项目"
    finally:
        restore()


@pytest.mark.asyncio
async def test_project_update_triggers_broadcast(client: AsyncClient):
    """更新项目时触发 project.updated 广播"""
    token = await _register_and_get_token(client, phone="13900003002")
    headers = _headers(token)

    create_resp = await client.post(
        "/api/projects",
        json={"name": "原始项目", "total_area": 80.0},
        headers=headers,
    )
    project_id = create_resp.json()["id"]

    calls, restore = _patch_broadcast_to_record_calls()
    try:
        resp = await client.patch(
            f"/api/projects/{project_id}",
            json={"name": "更新后项目", "status": "in_progress"},
            headers=headers,
        )
        assert resp.status_code == 200

        assert len(calls) == 1
        assert calls[0]["project_id"] == project_id
        assert calls[0]["event"] == "project.updated"
        assert calls[0]["data"]["name"] == "更新后项目"
    finally:
        restore()


@pytest.mark.asyncio
async def test_project_delete_triggers_broadcast(client: AsyncClient):
    """删除项目时触发 project.deleted 广播"""
    token = await _register_and_get_token(client, phone="13900003003")
    headers = _headers(token)

    create_resp = await client.post(
        "/api/projects",
        json={"name": "待删除项目", "total_area": 60.0},
        headers=headers,
    )
    project_id = create_resp.json()["id"]

    calls, restore = _patch_broadcast_to_record_calls()
    try:
        resp = await client.delete(f"/api/projects/{project_id}", headers=headers)
        assert resp.status_code == 204

        assert len(calls) == 1
        assert calls[0]["project_id"] == project_id
        assert calls[0]["event"] == "project.deleted"
        assert calls[0]["data"]["id"] == project_id
    finally:
        restore()


@pytest.mark.asyncio
async def test_project_update_forbidden_no_broadcast(client: AsyncClient):
    """越权更新被拒时不触发广播"""
    token_a = await _register_and_get_token(client, phone="13900003004")
    headers_a = _headers(token_a)
    project_id = await _create_project(client, headers_a, "用户A项目")

    token_b = await _register_and_get_token(client, phone="13900003005")
    headers_b = _headers(token_b)

    calls, restore = _patch_broadcast_to_record_calls()
    try:
        resp = await client.patch(
            f"/api/projects/{project_id}",
            json={"name": "恶意修改"},
            headers=headers_b,
        )
        assert resp.status_code == 403
        assert len(calls) == 0
    finally:
        restore()
