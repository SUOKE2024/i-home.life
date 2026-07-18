"""v1.0.14 IDOR 回归测试 — smart_home / scene_automation 项目归属校验

针对以下修复提供回归保护：
- smart_home.py: list_schemes_by_project / get_scheme / wiring_plan
                 / protocol_advice / compute_price / list_devices / delete_device
  修复前：除 create/delete_scheme 和 auto_recommend/add_device 外，
          其余端点完全缺失项目归属校验 → 任意用户可读取/操作他人智能家居方案
- scene_automation.py: list_scenes_by_project / get_scene / simulate_scene
                       / list_ecosystems_by_project / delete_ecosystem
  修复前：simulate_scene 完全无认证(无 current_user)；
          其余端点缺失项目归属校验 → 任意用户可读取/模拟/删除他人场景
"""

import pytest
from httpx import AsyncClient


async def _register(client: AsyncClient, phone: str, name: str) -> tuple[str, dict]:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": name, "password": "test123456"},
    )
    assert resp.status_code in (200, 201), resp.text
    token = resp.json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


async def _create_project(client: AsyncClient, headers: dict, name: str) -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": name, "total_area": 100.0},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_smart_home_scheme(
    client: AsyncClient, headers: dict, project_id: str
) -> str:
    resp = await client.post(
        "/api/smart-home/schemes",
        json={
            "project_id": project_id,
            "room_name": "客厅",
            "room_type": "living_room",
            "protocol": "zigbee",
            "hub_brand": "xiaomi",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_scene(
    client: AsyncClient, headers: dict, project_id: str, name: str = "回家模式"
) -> str:
    resp = await client.post(
        "/api/scene-automation/scenes",
        json={
            "project_id": project_id,
            "scene_name": name,
            "scene_type": "manual",
            "actions": [{"device_id": "light-1", "action": "turn_on"}],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_ecosystem(
    client: AsyncClient, headers: dict, project_id: str
) -> str:
    resp = await client.post(
        "/api/scene-automation/ecosystems",
        json={
            "project_id": project_id,
            "ecosystem": "mijia",
            "auth_status": "disconnected",
            "device_count": 0,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ── smart_home IDOR 测试 ──


@pytest.mark.asyncio
async def test_smart_home_list_schemes_idor_blocked(client: AsyncClient):
    """用户 B 不能列出用户 A 项目的智能家居方案 (403)"""
    token_a, hdr_a = await _register(client, "13900007001", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    await _create_smart_home_scheme(client, hdr_a, proj_a)

    _, hdr_b = await _register(client, "13900007002", "OwnerB")
    resp = await client.get(
        f"/api/smart-home/schemes/project/{proj_a}",
        headers=hdr_b,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_smart_home_get_scheme_idor_blocked(client: AsyncClient):
    """用户 B 不能获取用户 A 的智能家居方案详情 (403)"""
    token_a, hdr_a = await _register(client, "13900007003", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    scheme_id = await _create_smart_home_scheme(client, hdr_a, proj_a)

    _, hdr_b = await _register(client, "13900007004", "OwnerB")
    resp = await client.get(
        f"/api/smart-home/schemes/{scheme_id}",
        headers=hdr_b,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_smart_home_wiring_plan_idor_blocked(client: AsyncClient):
    """用户 B 不能查看用户 A 方案的布线规划 (403)"""
    _, hdr_a = await _register(client, "13900007005", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    scheme_id = await _create_smart_home_scheme(client, hdr_a, proj_a)

    _, hdr_b = await _register(client, "13900007006", "OwnerB")
    resp = await client.get(
        f"/api/smart-home/schemes/{scheme_id}/wiring",
        headers=hdr_b,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_smart_home_protocol_advice_idor_blocked(client: AsyncClient):
    """用户 B 不能查看用户 A 方案的协议选型建议 (403)"""
    _, hdr_a = await _register(client, "13900007007", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    scheme_id = await _create_smart_home_scheme(client, hdr_a, proj_a)

    _, hdr_b = await _register(client, "13900007008", "OwnerB")
    resp = await client.get(
        f"/api/smart-home/schemes/{scheme_id}/protocol-advice",
        headers=hdr_b,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_smart_home_compute_price_idor_blocked(client: AsyncClient):
    """用户 B 不能查看用户 A 方案的总价 (403)"""
    _, hdr_a = await _register(client, "13900007009", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    scheme_id = await _create_smart_home_scheme(client, hdr_a, proj_a)

    _, hdr_b = await _register(client, "13900007010", "OwnerB")
    resp = await client.get(
        f"/api/smart-home/schemes/{scheme_id}/price",
        headers=hdr_b,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_smart_home_list_devices_idor_blocked(client: AsyncClient):
    """用户 B 不能列出用户 A 方案的设备 (403)"""
    _, hdr_a = await _register(client, "13900007011", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    scheme_id = await _create_smart_home_scheme(client, hdr_a, proj_a)

    _, hdr_b = await _register(client, "13900007012", "OwnerB")
    resp = await client.get(
        f"/api/smart-home/schemes/{scheme_id}/devices",
        headers=hdr_b,
    )
    assert resp.status_code == 403


# ── scene_automation IDOR 测试 ──


@pytest.mark.asyncio
async def test_scene_list_scenes_idor_blocked(client: AsyncClient):
    """用户 B 不能列出用户 A 项目的场景 (403)"""
    _, hdr_a = await _register(client, "13900007013", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    await _create_scene(client, hdr_a, proj_a)

    _, hdr_b = await _register(client, "13900007014", "OwnerB")
    resp = await client.get(
        f"/api/scene-automation/scenes/project/{proj_a}",
        headers=hdr_b,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_scene_get_scene_idor_blocked(client: AsyncClient):
    """用户 B 不能获取用户 A 的场景详情 (403)"""
    _, hdr_a = await _register(client, "13900007015", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    scene_id = await _create_scene(client, hdr_a, proj_a)

    _, hdr_b = await _register(client, "13900007016", "OwnerB")
    resp = await client.get(
        f"/api/scene-automation/scenes/{scene_id}",
        headers=hdr_b,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_scene_simulate_requires_auth(client: AsyncClient):
    """simulate_scene 必须要求认证 (无 token → 401)"""
    resp = await client.post(
        "/api/scene-automation/scenes/any-id/simulate",
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_scene_simulate_idor_blocked(client: AsyncClient):
    """用户 B 不能模拟用户 A 的场景 (403)"""
    _, hdr_a = await _register(client, "13900007017", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    scene_id = await _create_scene(client, hdr_a, proj_a)

    _, hdr_b = await _register(client, "13900007018", "OwnerB")
    resp = await client.post(
        f"/api/scene-automation/scenes/{scene_id}/simulate",
        headers=hdr_b,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_scene_validate_requires_auth(client: AsyncClient):
    """validate_scene 必须要求认证 (无 token → 401)"""
    resp = await client.post(
        "/api/scene-automation/scenes/any-id/validate",
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_scene_validate_idor_blocked(client: AsyncClient):
    """用户 B 不能校验用户 A 的场景 (403)"""
    _, hdr_a = await _register(client, "13900007117", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    scene_id = await _create_scene(client, hdr_a, proj_a)

    _, hdr_b = await _register(client, "13900007118", "OwnerB")
    resp = await client.post(
        f"/api/scene-automation/scenes/{scene_id}/validate",
        headers=hdr_b,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_scene_validate_not_found(client: AsyncClient):
    """校验不存在的场景 → 404"""
    _, hdr = await _register(client, "13900007119", "Owner")
    resp = await client.post(
        "/api/scene-automation/scenes/nonexistent-id/validate",
        headers=hdr,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_scene_validate_owner_returns_schema(client: AsyncClient):
    """owner 校验自身场景返回 {valid: bool, errors: list} (200)"""
    _, hdr_a = await _register(client, "13900007120", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    scene_id = await _create_scene(client, hdr_a, proj_a)

    resp = await client.post(
        f"/api/scene-automation/scenes/{scene_id}/validate",
        headers=hdr_a,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "valid" in body and isinstance(body["valid"], bool)
    assert "errors" in body and isinstance(body["errors"], list)


@pytest.mark.asyncio
async def test_scene_validate_invalid_trigger_returns_errors(client: AsyncClient):
    """校验非法触发条件 → valid=False 且 errors 非空"""
    _, hdr_a = await _register(client, "13900007121", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    # 创建一个触发条件非法的场景 (type=device 但缺少 device_id)
    resp = await client.post(
        "/api/scene-automation/scenes",
        json={
            "project_id": proj_a,
            "scene_name": "非法触发场景",
            "scene_type": "triggered",
            "trigger_condition": {"type": "device"},
            "actions": [],
        },
        headers=hdr_a,
    )
    assert resp.status_code == 201
    scene_id = resp.json()["id"]

    resp = await client.post(
        f"/api/scene-automation/scenes/{scene_id}/validate",
        headers=hdr_a,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
    assert len(body["errors"]) > 0


@pytest.mark.asyncio
async def test_scene_list_ecosystems_idor_blocked(client: AsyncClient):
    """用户 B 不能列出用户 A 项目的生态对接 (403)"""
    _, hdr_a = await _register(client, "13900007019", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    await _create_ecosystem(client, hdr_a, proj_a)

    _, hdr_b = await _register(client, "13900007020", "OwnerB")
    resp = await client.get(
        f"/api/scene-automation/ecosystems/project/{proj_a}",
        headers=hdr_b,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_scene_delete_ecosystem_idor_blocked(client: AsyncClient):
    """用户 B 不能删除用户 A 的生态对接 (403)"""
    _, hdr_a = await _register(client, "13900007021", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    eco_id = await _create_ecosystem(client, hdr_a, proj_a)

    _, hdr_b = await _register(client, "13900007022", "OwnerB")
    resp = await client.delete(
        f"/api/scene-automation/ecosystems/{eco_id}",
        headers=hdr_b,
    )
    assert resp.status_code == 403


# ── 正向回归：owner 自身可访问 ──


@pytest.mark.asyncio
async def test_smart_home_owner_can_access_own_scheme(client: AsyncClient):
    """owner 自身可正常访问方案相关端点 (200) — 防止修复过度"""
    _, hdr_a = await _register(client, "13900007023", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    scheme_id = await _create_smart_home_scheme(client, hdr_a, proj_a)

    # get_scheme
    resp = await client.get(
        f"/api/smart-home/schemes/{scheme_id}",
        headers=hdr_a,
    )
    assert resp.status_code == 200
    # list_schemes_by_project
    resp = await client.get(
        f"/api/smart-home/schemes/project/{proj_a}",
        headers=hdr_a,
    )
    assert resp.status_code == 200
    # wiring_plan
    resp = await client.get(
        f"/api/smart-home/schemes/{scheme_id}/wiring",
        headers=hdr_a,
    )
    assert resp.status_code == 200
    # compute_price
    resp = await client.get(
        f"/api/smart-home/schemes/{scheme_id}/price",
        headers=hdr_a,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_scene_owner_can_access_own_scene(client: AsyncClient):
    """owner 自身可正常访问场景相关端点 (200) — 防止修复过度"""
    _, hdr_a = await _register(client, "13900007024", "OwnerA")
    proj_a = await _create_project(client, hdr_a, "A项目")
    scene_id = await _create_scene(client, hdr_a, proj_a)

    # get_scene
    resp = await client.get(
        f"/api/scene-automation/scenes/{scene_id}",
        headers=hdr_a,
    )
    assert resp.status_code == 200
    # list_scenes_by_project
    resp = await client.get(
        f"/api/scene-automation/scenes/project/{proj_a}",
        headers=hdr_a,
    )
    assert resp.status_code == 200
    # simulate_scene
    resp = await client.post(
        f"/api/scene-automation/scenes/{scene_id}/simulate",
        headers=hdr_a,
    )
    assert resp.status_code == 200
