"""项目生命周期端到端测试。

覆盖场景：
- 创建项目 → 查看项目详情 → 更新项目信息 → 列出用户项目 → 删除项目
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_e2e_project_full_lifecycle(client: AsyncClient):
    """完整的项目生命周期端到端测试。

    单测试覆盖：创建 → 查看详情 → 更新 → 列出 → 删除 → 确认已删除。
    """
    import uuid

    phone = f"139{str(uuid.uuid4().int)[:8]}"
    password = "test123456"

    # ── 0. 注册并获取认证 token ──
    register_resp = await client.post(
        "/api/auth/register",
        json={
            "phone": phone,
            "name": "E2E 项目生命周期用户",
            "password": password,
        },
    )
    assert register_resp.status_code == 201
    token = register_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # ── Step 1: 创建项目 ──
    create_resp = await client.post(
        "/api/projects",
        json={
            "name": "E2E 端到端测试项目",
            "address": "上海市浦东新区测试路 100 号",
            "total_area": 128.5,
            "project_type": "full_renovation",
            "floors": [
                {
                    "name": "一层",
                    "floor_number": 1,
                    "area": 85.0,
                    "rooms": [
                        {"name": "起居室", "room_type": "living_room", "area": 35.0},
                        {"name": "主卧室", "room_type": "bedroom", "area": 22.0},
                        {"name": "厨房", "room_type": "kitchen", "area": 12.0},
                        {"name": "卫生间", "room_type": "bathroom", "area": 8.0},
                    ],
                },
                {
                    "name": "二层",
                    "floor_number": 2,
                    "area": 43.5,
                    "rooms": [
                        {"name": "次卧", "room_type": "bedroom", "area": 18.0},
                        {"name": "书房", "room_type": "study", "area": 15.0},
                    ],
                },
            ],
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    project_data = create_resp.json()
    project_id = project_data["id"]
    assert project_data["name"] == "E2E 端到端测试项目"
    assert project_data["address"] == "上海市浦东新区测试路 100 号"
    assert project_data["total_area"] == 128.5
    assert project_data["project_type"] == "full_renovation"
    assert project_data["status"] == "draft"
    assert len(project_data["floors"]) == 2
    assert len(project_data["floors"][0]["rooms"]) == 4
    assert len(project_data["floors"][1]["rooms"]) == 2
    assert project_data["floors"][0]["rooms"][0]["room_type"] == "living_room"

    # ── Step 2: 查看项目详情 ──
    detail_resp = await client.get(f"/api/projects/{project_id}", headers=headers)
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["id"] == project_id
    assert detail_data["name"] == "E2E 端到端测试项目"
    assert detail_data["address"] == "上海市浦东新区测试路 100 号"
    assert detail_data["total_area"] == 128.5
    assert len(detail_data["floors"]) == 2
    # 验证嵌套数据完整性
    floor_names = [f["name"] for f in detail_data["floors"]]
    assert "一层" in floor_names
    assert "二层" in floor_names

    # ── Step 3: 更新项目信息 ──
    update_resp = await client.patch(
        f"/api/projects/{project_id}",
        json={
            "name": "E2E 端到端测试项目（已更新）",
            "address": "上海市徐汇区更新路 200 号",
            "status": "active",
            "total_area": 132.0,
        },
        headers=headers,
    )
    assert update_resp.status_code == 200
    update_data = update_resp.json()
    assert update_data["id"] == project_id
    assert update_data["name"] == "E2E 端到端测试项目（已更新）"
    assert update_data["address"] == "上海市徐汇区更新路 200 号"
    assert update_data["status"] == "active"
    assert update_data["total_area"] == 132.0

    # 再次查看确认更新已持久化
    detail_resp2 = await client.get(f"/api/projects/{project_id}", headers=headers)
    assert detail_resp2.status_code == 200
    assert detail_resp2.json()["name"] == "E2E 端到端测试项目（已更新）"
    assert detail_resp2.json()["status"] == "active"

    # ── Step 4: 列出用户项目 ──
    # 再创建一个项目，确保列表返回所有项目
    create_resp2 = await client.post(
        "/api/projects",
        json={
            "name": "第二个 E2E 项目",
            "total_area": 60.0,
            "floors": [
                {
                    "name": "单层",
                    "floor_number": 1,
                    "area": 60.0,
                    "rooms": [{"name": "开放空间", "room_type": "living_room", "area": 45.0}],
                }
            ],
        },
        headers=headers,
    )
    assert create_resp2.status_code == 201
    project_id2 = create_resp2.json()["id"]

    list_resp = await client.get("/api/projects", headers=headers)
    assert list_resp.status_code == 200
    projects = list_resp.json()
    assert len(projects) == 2
    project_names = {p["name"] for p in projects}
    assert project_names == {"E2E 端到端测试项目（已更新）", "第二个 E2E 项目"}

    # ── Step 5: 删除第一个项目 ──
    delete_resp = await client.delete(f"/api/projects/{project_id}", headers=headers)
    assert delete_resp.status_code == 204

    # ── Step 6: 确认项目已删除 ──
    # 6a: 查看已删除项目应返回 404
    detail_resp3 = await client.get(f"/api/projects/{project_id}", headers=headers)
    assert detail_resp3.status_code == 404

    # 6b: 列表只剩下 1 个项目
    list_resp2 = await client.get("/api/projects", headers=headers)
    assert list_resp2.status_code == 200
    assert len(list_resp2.json()) == 1
    assert list_resp2.json()[0]["id"] == project_id2

    # ── Step 7: 清理 —— 删除第二个项目 ──
    delete_resp2 = await client.delete(f"/api/projects/{project_id2}", headers=headers)
    assert delete_resp2.status_code == 204

    # 列表为空
    list_resp3 = await client.get("/api/projects", headers=headers)
    assert list_resp3.status_code == 200
    assert len(list_resp3.json()) == 0


@pytest.mark.asyncio
async def test_e2e_project_minimal_create_and_delete(client: AsyncClient):
    """最小化的项目创建和删除流程：仅 name 字段创建 → 查看 → 删除。"""
    import uuid

    phone = f"139{str(uuid.uuid4().int)[:8]}"
    register_resp = await client.post(
        "/api/auth/register",
        json={
            "phone": phone,
            "name": "最小项目测试用户",
            "password": "test123456",
        },
    )
    token = register_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 创建极简项目
    create_resp = await client.post(
        "/api/projects",
        json={"name": "极简 E2E 项目"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]
    assert create_resp.json()["name"] == "极简 E2E 项目"
    assert create_resp.json()["status"] == "draft"
    assert create_resp.json()["floors"] == []

    # 查看极简项目
    detail_resp = await client.get(f"/api/projects/{project_id}", headers=headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["name"] == "极简 E2E 项目"

    # 删除极简项目
    delete_resp = await client.delete(f"/api/projects/{project_id}", headers=headers)
    assert delete_resp.status_code == 204

    # 确认删除
    detail_resp2 = await client.get(f"/api/projects/{project_id}", headers=headers)
    assert detail_resp2.status_code == 404


@pytest.mark.asyncio
async def test_e2e_project_unauthorized_cannot_access(client: AsyncClient):
    """未认证用户无法进行任何项目操作。"""
    # 未认证列出项目
    resp = await client.get("/api/projects")
    assert resp.status_code == 401

    # 未认证创建项目
    resp = await client.post(
        "/api/projects",
        json={"name": "未认证项目", "total_area": 50.0},
    )
    assert resp.status_code == 401

    # 未认证查看项目
    resp = await client.get("/api/projects/fake-id-123")
    assert resp.status_code == 401

    # 未认证更新项目
    resp = await client.patch(
        "/api/projects/fake-id-123",
        json={"name": "未认证更新"},
    )
    assert resp.status_code == 401

    # 未认证删除项目
    resp = await client.delete("/api/projects/fake-id-123")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_e2e_project_cannot_see_other_users_project(client: AsyncClient):
    """用户不能查看/修改/删除其他用户的项目。"""
    import uuid

    # 用户 A 注册并创建项目
    phone_a = f"139{str(uuid.uuid4().int)[:8]}"
    resp_a = await client.post(
        "/api/auth/register",
        json={
            "phone": phone_a,
            "name": "用户A",
            "password": "test123456",
        },
    )
    token_a = resp_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    create_resp = await client.post(
        "/api/projects",
        json={"name": "用户A 的项目", "total_area": 80.0},
        headers=headers_a,
    )
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]

    # 用户 B 注册
    phone_b = f"139{str(uuid.uuid4().int)[:8]}"
    resp_b = await client.post(
        "/api/auth/register",
        json={
            "phone": phone_b,
            "name": "用户B",
            "password": "test123456",
        },
    )
    token_b = resp_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # B 不能查看 A 的项目
    resp = await client.get(f"/api/projects/{project_id}", headers=headers_b)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "无权访问此项目"

    # B 不能修改 A 的项目
    resp = await client.patch(
        f"/api/projects/{project_id}",
        json={"name": "被 B 篡改"},
        headers=headers_b,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "无权访问此项目"

    # B 不能删除 A 的项目
    resp = await client.delete(f"/api/projects/{project_id}", headers=headers_b)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "无权访问此项目"

    # B 的列表为空
    resp = await client.get("/api/projects", headers=headers_b)
    assert resp.status_code == 200
    assert len(resp.json()) == 0

    # A 的列表仍有项目
    resp = await client.get("/api/projects", headers=headers_a)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
