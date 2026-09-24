"""项目成员授权（F40 三方协作）与受限枚举兜底 —— 2026-09-24 生产交叉验证 C-01/A-1/A-2 修复守护

背景：生产实测发现 ``verify_project_collaborator_access`` 只校验角色、不校验成员关系，
任何 designer/contractor/supplier 可读全平台任意项目（供应商读业主项目 feed 拿到
budget_breakdown 逐项单价与 settlement_summary）。本文件守护修复后的行为：
  1. 非成员协作角色访问协作类端点必须 403（修复前为 200）
  2. 显式加入成员后放行，移除后再次拒绝
  3. owner / admin 行为不变（不得因修复而回归）
  4. 成员管理端点仅 owner / admin 可用
  5. scene_type 非法值 422（schema Literal 兜底）
  6. health_monitors.device_id 接受 BLE MAC（去外键后不再 422）
"""
import uuid

import pytest
from httpx import AsyncClient

from app.auth.paseto_handler import create_token
from app.database import async_session
from app.models.user import User


async def _register(client: AsyncClient, role: str = "homeowner") -> tuple[dict, str]:
    """注册指定角色用户 → (认证 headers, user_id)"""
    resp = await client.post(
        "/api/auth/register",
        json={
            "phone": f"139{uuid.uuid4().int % 100000000:08d}",
            "name": f"成员测试{role}",
            "password": "test123456",
            "role": role,
        },
    )
    assert resp.status_code == 201, resp.text
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    me = await client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    return headers, me.json()["id"]


async def _make_admin_headers() -> dict:
    """直接建 admin 用户并签发令牌（注册端点不产出 admin 角色）"""
    user_id = str(uuid.uuid4())
    async with async_session() as db:
        db.add(User(
            id=user_id,
            phone=f"138{uuid.uuid4().hex[:8]}",
            name="成员测试管理员",
            role="admin",
            hashed_password="x",
        ))
        await db.commit()
    return {"Authorization": f"Bearer {create_token(user_id, 'admin')}"}


async def _create_project(client: AsyncClient, owner_headers: dict) -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": f"成员授权测试项目-{uuid.uuid4().hex[:6]}", "total_area": 88.0},
        headers=owner_headers,
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


async def _add_member(
    client: AsyncClient, owner_headers: dict, project_id: str, user_id: str, role: str
):
    return await client.post(
        f"/api/projects/{project_id}/members",
        json={"user_id": user_id, "role": role},
        headers=owner_headers,
    )


# ── 1. 核心：无成员关系必须拒绝（C-01 直接反证）──


@pytest.mark.asyncio
async def test_collaborator_without_membership_denied(client: AsyncClient):
    """供应商与项目无任何关联时，读协作类端点 feed 必须 403（修复前为 200，即越权）。"""
    owner_headers, _ = await _register(client, "homeowner")
    project_id = await _create_project(client, owner_headers)

    supplier_headers, _ = await _register(client, "supplier")
    resp = await client.get(f"/api/feed/{project_id}", headers=supplier_headers)
    assert resp.status_code == 403, (
        f"非成员协作角色不应访问项目 feed，实际 {resp.status_code}: {resp.text[:200]}"
    )


@pytest.mark.asyncio
async def test_designer_and_contractor_without_membership_denied(client: AsyncClient):
    """designer / contractor 同受约束（原实现三者一并放行）。"""
    owner_headers, _ = await _register(client, "homeowner")
    project_id = await _create_project(client, owner_headers)

    for role in ("designer", "contractor"):
        headers, _ = await _register(client, role)
        resp = await client.get(f"/api/feed/{project_id}", headers=headers)
        assert resp.status_code == 403, f"{role} 非成员应 403，实际 {resp.status_code}"


@pytest.mark.asyncio
async def test_anonymous_denied(client: AsyncClient):
    owner_headers, _ = await _register(client, "homeowner")
    project_id = await _create_project(client, owner_headers)
    resp = await client.get(f"/api/feed/{project_id}")
    assert resp.status_code == 401


# ── 2. 显式授权后放行 / 撤销后拒绝 ──


@pytest.mark.asyncio
async def test_member_granted_then_revoked(client: AsyncClient):
    owner_headers, _ = await _register(client, "homeowner")
    project_id = await _create_project(client, owner_headers)
    supplier_headers, supplier_id = await _register(client, "supplier")

    # 未授权 → 拒绝
    assert (
        await client.get(f"/api/feed/{project_id}", headers=supplier_headers)
    ).status_code == 403

    # 授权为成员 → 放行
    added = await _add_member(client, owner_headers, project_id, supplier_id, "supplier")
    assert added.status_code == 201, added.text
    assert added.json()["role"] == "supplier"
    assert (
        await client.get(f"/api/feed/{project_id}", headers=supplier_headers)
    ).status_code == 200

    # 撤销 → 再次拒绝
    removed = await client.delete(
        f"/api/projects/{project_id}/members/{supplier_id}", headers=owner_headers
    )
    assert removed.status_code == 204, removed.text
    assert (
        await client.get(f"/api/feed/{project_id}", headers=supplier_headers)
    ).status_code == 403


@pytest.mark.asyncio
async def test_member_scoped_to_single_project(client: AsyncClient):
    """成员授权只对指定项目生效，不得波及其他项目。"""
    owner_headers, _ = await _register(client, "homeowner")
    project_a = await _create_project(client, owner_headers)
    project_b = await _create_project(client, owner_headers)
    designer_headers, designer_id = await _register(client, "designer")

    assert (
        await _add_member(client, owner_headers, project_a, designer_id, "designer")
    ).status_code == 201

    assert (
        await client.get(f"/api/feed/{project_a}", headers=designer_headers)
    ).status_code == 200
    assert (
        await client.get(f"/api/feed/{project_b}", headers=designer_headers)
    ).status_code == 403


# ── 3. owner / admin 行为不得回归 ──


@pytest.mark.asyncio
async def test_owner_and_admin_still_allowed(client: AsyncClient):
    owner_headers, _ = await _register(client, "homeowner")
    project_id = await _create_project(client, owner_headers)

    assert (
        await client.get(f"/api/feed/{project_id}", headers=owner_headers)
    ).status_code == 200

    admin_headers = await _make_admin_headers()
    assert (
        await client.get(f"/api/feed/{project_id}", headers=admin_headers)
    ).status_code == 200


@pytest.mark.asyncio
async def test_nonexistent_project_404(client: AsyncClient):
    headers, _ = await _register(client, "designer")
    resp = await client.get(f"/api/feed/{uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404


# ── 4. 成员管理端点权限与校验 ──


@pytest.mark.asyncio
async def test_member_endpoints_require_owner_or_admin(client: AsyncClient):
    """非 owner 的 homeowner 不能读写成员表（防越权授予自己访问权）。"""
    owner_headers, _ = await _register(client, "homeowner")
    project_id = await _create_project(client, owner_headers)
    outsider_headers, outsider_id = await _register(client, "homeowner")

    assert (
        await client.get(f"/api/projects/{project_id}/members", headers=outsider_headers)
    ).status_code == 403
    assert (
        await _add_member(client, outsider_headers, project_id, outsider_id, "designer")
    ).status_code == 403
    assert (
        await client.delete(
            f"/api/projects/{project_id}/members/{outsider_id}", headers=outsider_headers
        )
    ).status_code == 403


@pytest.mark.asyncio
async def test_member_endpoints_admin_allowed(client: AsyncClient):
    owner_headers, _ = await _register(client, "homeowner")
    project_id = await _create_project(client, owner_headers)
    admin_headers = await _make_admin_headers()

    listed = await client.get(f"/api/projects/{project_id}/members", headers=admin_headers)
    assert listed.status_code == 200
    assert listed.json() == []


@pytest.mark.asyncio
async def test_add_member_invalid_role_422(client: AsyncClient):
    """role 为受限枚举：owner / admin / 任意串均应 422（schema Literal 兜底）。"""
    owner_headers, _ = await _register(client, "homeowner")
    project_id = await _create_project(client, owner_headers)
    _, designer_id = await _register(client, "designer")

    for bad_role in ("owner", "admin", "wakeup", ""):
        resp = await _add_member(client, owner_headers, project_id, designer_id, bad_role)
        assert resp.status_code == 422, f"role={bad_role!r} 应 422，实际 {resp.status_code}"


@pytest.mark.asyncio
async def test_add_member_non_collaborator_user_422(client: AsyncClient):
    """目标用户角色不是协作角色（homeowner）时应 422，而非静默写入。"""
    owner_headers, _ = await _register(client, "homeowner")
    project_id = await _create_project(client, owner_headers)
    _, other_homeowner_id = await _register(client, "homeowner")

    resp = await _add_member(client, owner_headers, project_id, other_homeowner_id, "designer")
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_add_member_unknown_user_422(client: AsyncClient):
    owner_headers, _ = await _register(client, "homeowner")
    project_id = await _create_project(client, owner_headers)
    resp = await _add_member(client, owner_headers, project_id, str(uuid.uuid4()), "designer")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_add_updates_role_not_duplicates(client: AsyncClient):
    """同用户重复添加应更新角色（uq_project_member_project_user 一人一条），不报错不重复。"""
    owner_headers, _ = await _register(client, "homeowner")
    project_id = await _create_project(client, owner_headers)
    _, user_id = await _register(client, "designer")

    assert (
        await _add_member(client, owner_headers, project_id, user_id, "designer")
    ).status_code == 201
    assert (
        await _add_member(client, owner_headers, project_id, user_id, "contractor")
    ).status_code == 201

    listed = await client.get(f"/api/projects/{project_id}/members", headers=owner_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["role"] == "contractor"


@pytest.mark.asyncio
async def test_remove_unknown_member_404(client: AsyncClient):
    owner_headers, _ = await _register(client, "homeowner")
    project_id = await _create_project(client, owner_headers)
    resp = await client.delete(
        f"/api/projects/{project_id}/members/{uuid.uuid4()}", headers=owner_headers
    )
    assert resp.status_code == 404


# ── 5. scene_type 受限枚举（A-1/B-3）──


@pytest.mark.asyncio
async def test_scene_type_invalid_rejected(client: AsyncClient):
    """scene_type 非法值必须 422（修复前 wakeup/sleep/任意串一律 201 落库）。"""
    owner_headers, _ = await _register(client, "homeowner")
    project_id = await _create_project(client, owner_headers)

    for bad in ("wakeup", "sleep", "QA_GARBAGE_XYZ", ""):
        resp = await client.post(
            "/api/scene-automation/scenes",
            json={"project_id": project_id, "scene_name": "非法枚举探测", "scene_type": bad},
            headers=owner_headers,
        )
        assert resp.status_code == 422, f"scene_type={bad!r} 应 422，实际 {resp.status_code}"


@pytest.mark.asyncio
async def test_scene_type_valid_accepted(client: AsyncClient):
    """四个合法值仍应创建成功（确认收窄未误伤正常路径）。"""
    owner_headers, _ = await _register(client, "homeowner")
    project_id = await _create_project(client, owner_headers)

    for good in ("manual", "scheduled", "triggered", "geo"):
        resp = await client.post(
            "/api/scene-automation/scenes",
            json={"project_id": project_id, "scene_name": f"场景-{good}", "scene_type": good},
            headers=owner_headers,
        )
        assert resp.status_code == 201, f"scene_type={good} 应 201，实际 {resp.status_code}: {resp.text[:200]}"

    # PATCH 亦受约束
    listed = await client.get(
        f"/api/scene-automation/scenes/project/{project_id}", headers=owner_headers
    )
    assert listed.status_code == 200
    scene_id = listed.json()[0]["id"]
    patched = await client.patch(
        f"/api/scene-automation/scenes/{scene_id}",
        json={"scene_type": "wakeup"},
        headers=owner_headers,
    )
    assert patched.status_code == 422, patched.text


# ── 6. health_monitors.device_id 放开外键（A-2）──


@pytest.mark.asyncio
async def test_health_monitor_accepts_ble_mac_device_id(client: AsyncClient):
    """BLE MAC 形式的 device_id 必须可落库（修复前因 FK 恒 422，穿戴康养链路不可用）。"""
    owner_headers, _ = await _register(client, "homeowner")
    project_id = await _create_project(client, owner_headers)

    scheme = await client.post(
        "/api/smart-home/schemes",
        json={"project_id": project_id, "room_name": "主卧", "room_type": "bedroom"},
        headers=owner_headers,
    )
    assert scheme.status_code in (200, 201), scheme.text
    scheme_id = scheme.json()["id"]

    resp = await client.post(
        "/api/health-monitor/records",
        json={
            "project_id": project_id,
            "scheme_id": scheme_id,
            "monitor_type": "heart_rate",
            "value": {"bpm": 72},
            "device_id": "AA:BB:CC:DD:EE:FF",
        },
        headers=owner_headers,
    )
    assert resp.status_code == 201, f"BLE MAC device_id 应可落库，实际 {resp.status_code}: {resp.text[:300]}"
    body = resp.json()
    assert body["device_id"] == "AA:BB:CC:DD:EE:FF"
    assert body["smart_device_id"] is None


@pytest.mark.asyncio
async def test_health_monitor_two_device_columns_separated(client: AsyncClient):
    """两列职责分离的模型级反证（方言无关）。

    ``device_id`` 须无外键（承载 BLE MAC 等外部标识），``smart_device_id`` 须保留
    指向 smart_devices 的外键（承载平台内设备关联）。

    注意：外键「拒绝非法引用」的实际行为取决于方言——SQLite 默认
    ``PRAGMA foreign_keys=OFF``（测试库由 conftest 的 create_all 建表且未开启），
    故测试环境无法复现拒绝；生产 PostgreSQL 会经 IntegrityError 转译为 422。
    因此此处断言模型声明本身，而非依赖 DB 行为。
    """
    from app.models.health_monitor import HealthMonitor

    table = HealthMonitor.__table__
    assert not list(table.c.device_id.foreign_keys), (
        "device_id 必须无外键（BLE MAC 上报依赖此放开，A-2 修复）"
    )
    targets = {fk.target_fullname for fk in table.c.smart_device_id.foreign_keys}
    assert targets == {"smart_devices.id"}, (
        f"smart_device_id 须保留指向 smart_devices 的外键，实际 {targets}"
    )
