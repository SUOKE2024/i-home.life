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
        json={"name": "已更新项目", "status": "active"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "已更新项目"
    assert data["status"] == "active"
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


@pytest.mark.asyncio
async def test_create_project_with_collect_fields(client: AsyncClient):
    """创建项目卡片收集的户型/定位/联系方式应落库并随响应返回（v1.3.1 P1-2）"""
    token = await _register_and_get_token(client, phone="13900001002")
    headers = _headers(token)

    response = await client.post(
        "/api/projects",
        json={
            "name": "收集字段项目",
            "description": "三居室整装",
            "house_type": "3室2厅1厨2卫",
            "latitude": 30.5928,
            "longitude": 114.3055,
            "contact_name": "张三",
            "contact_phone": "13912345678",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["description"] == "三居室整装"
    assert data["house_type"] == "3室2厅1厨2卫"
    assert data["latitude"] == 30.5928
    assert data["longitude"] == 114.3055
    assert data["contact_name"] == "张三"
    assert data["contact_phone"] == "13912345678"

    # 详情接口同样返回
    project_id = data["id"]
    detail = await client.get(f"/api/projects/{project_id}", headers=headers)
    assert detail.status_code == 200
    detail_data = detail.json()
    assert detail_data["house_type"] == "3室2厅1厨2卫"
    assert detail_data["contact_phone"] == "13912345678"


@pytest.mark.asyncio
async def test_create_project_invalid_project_type_returns_422(client: AsyncClient):
    """非法 project_type 应被 Literal 校验拦截（P3-2）"""
    token = await _register_and_get_token(client, phone="13900001003")
    headers = _headers(token)

    response = await client.post(
        "/api/projects",
        json={"name": "非法类型项目", "project_type": "bogus_type"},
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_project_invalid_source_returns_422(client: AsyncClient):
    """非法 source 应被 Literal 校验拦截（P3-2）"""
    token = await _register_and_get_token(client, phone="13900001004")
    headers = _headers(token)

    response = await client.post(
        "/api/projects",
        json={"name": "非法来源项目", "source": "hacker"},
        headers=headers,
    )
    assert response.status_code == 422


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
            json={"name": "更新后项目", "status": "active"},
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


# ====================================================================
# 轻量级 schema 迁移回归（v6: projects 项目卡片采集字段）
# ====================================================================
# 背景：description/house_type/latitude/longitude/contact_name/contact_phone
# 已加入 ORM 模型/schema/alembic，但 _run_lightweight_migrations 漏加，
# create_all 不补已有表列 → dev/生产库重启后项目查询 500。
# 本测试模拟生产库缺列状态，验证迁移能补齐。


@pytest.mark.asyncio
async def test_lightweight_migration_adds_project_collect_columns(db_session):
    """模拟 projects 表缺少采集字段，迁移后应补齐 description/house_type 等 6 列"""
    from sqlalchemy import text, inspect
    from app.database import _run_lightweight_migrations

    collect_columns = [
        "description", "house_type", "latitude", "longitude",
        "contact_name", "contact_phone",
    ]
    async with db_session.bind.begin() as conn:
        for col in collect_columns:
            try:
                await conn.execute(text(f"ALTER TABLE projects DROP COLUMN {col}"))
            except Exception:
                pass  # 列可能不存在

        def _cols(sync_conn):
            ins = inspect(sync_conn)
            return [c["name"] for c in ins.get_columns("projects")]

        cols_before = await conn.run_sync(_cols)
        for col in collect_columns:
            assert col not in cols_before, f"列 {col} 应已被删除"

        await conn.commit()

    # force=True 绕过 _schema_migrations 版本检查
    await _run_lightweight_migrations(force=True)

    async with db_session.bind.begin() as conn:
        def _cols(sync_conn):
            ins = inspect(sync_conn)
            return [c["name"] for c in ins.get_columns("projects")]

        cols_after = await conn.run_sync(_cols)
        for col in collect_columns:
            assert col in cols_after, f"迁移后应存在列 {col}"


# ====================================================================
# 生产 FK 约束下删除项目级联清理（回归：DELETE /projects 500）
# ====================================================================
# 背景：v1.13.2 lifecycle_orchestration_enabled=True 时项目创建经 EventBus
# 自动建预算（budgets.project_id FK → projects.id），delete_project 仅删
# projects 行，生产 PostgreSQL 严格 FK 约束报 500（SQLite 测试默认不强制
# FK 未暴露）。修复：_cascade_delete_related 按 FK 依赖逆序级联删除关联数据。
# 本测试启用 SQLite FK 约束模拟生产，验证删除项目成功且关联数据已清空。


@pytest.mark.asyncio
async def test_delete_project_cascades_related_data_with_fk(
    client: AsyncClient, db_session
):
    """FK 约束下删除项目应 204 成功并级联清理预算/预算行/户型等关联数据"""
    from sqlalchemy import event as sa_event, text
    from app.database import engine
    from app.models.budget import Budget, BudgetLine
    from app.models.floorplan import FloorPlan

    # 启用 SQLite FK 约束，模拟生产 PostgreSQL（测试结束移除，避免污染其他用例）
    @sa_event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_conn, rec):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    try:
        token = await _register_and_get_token(client, phone="13900003010")
        headers = _headers(token)
        project_id = await _create_project(client, headers, "FK级联删除项目")

        # 创建关联数据（模拟 EventBus 自动建预算 + 户型 + 预算行）
        budget = Budget(
            project_id=project_id, total_estimated=0, total_actual=0, status="draft"
        )
        db_session.add(budget)
        await db_session.flush()
        db_session.add(BudgetLine(budget_id=budget.id, category="材料", name="测试"))
        db_session.add(FloorPlan(project_id=project_id, name="户型", data="{}"))
        await db_session.commit()

        # 删除项目应成功（回归：此前生产 PostgreSQL 下报 500）
        resp = await client.delete(f"/api/projects/{project_id}", headers=headers)
        assert resp.status_code == 204

        # 项目自身已删除
        r = await db_session.execute(
            text("SELECT COUNT(*) FROM projects WHERE id = :p"), {"p": project_id}
        )
        assert r.scalar() == 0

        # 直接关联表已级联清理
        r = await db_session.execute(
            text("SELECT COUNT(*) FROM budgets WHERE project_id = :p"), {"p": project_id}
        )
        assert r.scalar() == 0
        r = await db_session.execute(
            text("SELECT COUNT(*) FROM floor_plans WHERE project_id = :p"), {"p": project_id}
        )
        assert r.scalar() == 0

        # 二级关联（预算行）经 budget join 已级联清理
        r = await db_session.execute(
            text(
                "SELECT COUNT(*) FROM budget_lines bl "
                "JOIN budgets b ON bl.budget_id = b.id "
                "WHERE b.project_id = :p"
            ),
            {"p": project_id},
        )
        assert r.scalar() == 0
    finally:
        sa_event.remove(engine.sync_engine, "connect", _fk_on)
