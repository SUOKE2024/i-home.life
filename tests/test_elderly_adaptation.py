"""F41 适老改造 API 集成测试

覆盖端点:
- POST   /api/elderly-adaptation/schemes                            (创建适老方案)
- GET    /api/elderly-adaptation/schemes/project/{project_id}       (按项目列方案)
- GET    /api/elderly-adaptation/schemes/{scheme_id}                (方案详情)
- PATCH  /api/elderly-adaptation/schemes/{scheme_id}                (更新方案)
- POST   /api/elderly-adaptation/schemes/{scheme_id}/validate       (合规校验)
- POST   /api/elderly-adaptation/check-accessibility                (无障碍动线检查)
- DELETE /api/elderly-adaptation/schemes/{scheme_id}                (删除方案)
"""
import pytest
from httpx import AsyncClient


async def _auth_headers(client: AsyncClient, phone: str = "13950010001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "适老改造测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "适老改造测试项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 100.0}, headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_scheme(
    client: AsyncClient, headers: dict, project_id: str, occupant_type: str = "elderly_living",
) -> dict:
    resp = await client.post(
        "/api/elderly-adaptation/schemes",
        json={"project_id": project_id, "name": "适老改造方案", "occupant_type": occupant_type},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()


# ── Auth ──


@pytest.mark.asyncio
async def test_elderly_adaptation_unauthorized(client: AsyncClient):
    """未认证用户不能创建适老改造方案"""
    resp = await client.post(
        "/api/elderly-adaptation/schemes",
        json={"project_id": "fake", "name": "方案", "occupant_type": "elderly_living"},
    )
    assert resp.status_code == 401


# ── 方案 CRUD ──


@pytest.mark.asyncio
async def test_create_and_get_scheme(client: AsyncClient):
    """创建适老方案并读取详情，items 自动生成"""
    headers = await _auth_headers(client, "13950010002")
    project_id = await _create_project(client, headers)

    created = await _create_scheme(client, headers, project_id)
    assert created["name"] == "适老改造方案"
    assert created["occupant_type"] == "elderly_living"
    assert created["compliance_status"] == "warning"
    # 自动生成适老条目
    assert isinstance(created["items"], list) and len(created["items"]) > 0
    assert any(item["type"] == "grab_bar" for item in created["items"])
    assert any(item["type"] == "anti_slip" for item in created["items"])

    resp = await client.get(f"/api/elderly-adaptation/schemes/{created['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "适老改造方案"


@pytest.mark.asyncio
async def test_nursing_scheme_includes_nursing_devices(client: AsyncClient):
    """失能护理(nursing)方案额外包含护理床垫/移乘设备"""
    headers = await _auth_headers(client, "13950010003")
    project_id = await _create_project(client, headers)

    created = await _create_scheme(client, headers, project_id, occupant_type="nursing")
    locations = [item["location"] for item in created["items"]]
    assert "护理床垫" in locations
    assert "移乘设备" in locations


@pytest.mark.asyncio
async def test_list_schemes_by_project(client: AsyncClient):
    """按项目列出适老改造方案"""
    headers = await _auth_headers(client, "13950010004")
    project_id = await _create_project(client, headers)

    await _create_scheme(client, headers, project_id)
    await _create_scheme(client, headers, project_id, occupant_type="nursing")

    resp = await client.get(
        f"/api/elderly-adaptation/schemes/project/{project_id}", headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_update_scheme(client: AsyncClient):
    """更新适老改造方案（name/occupant_type/notes）"""
    headers = await _auth_headers(client, "13950010005")
    project_id = await _create_project(client, headers)
    created = await _create_scheme(client, headers, project_id)

    resp = await client.patch(
        f"/api/elderly-adaptation/schemes/{created['id']}",
        json={"name": "更新后的适老方案", "notes": "增加阳台扶手"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "更新后的适老方案"
    assert data["notes"] == "增加阳台扶手"


@pytest.mark.asyncio
async def test_delete_scheme(client: AsyncClient):
    """删除适老改造方案"""
    headers = await _auth_headers(client, "13950010006")
    project_id = await _create_project(client, headers)
    created = await _create_scheme(client, headers, project_id)

    resp = await client.delete(f"/api/elderly-adaptation/schemes/{created['id']}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/elderly-adaptation/schemes/{created['id']}", headers=headers)
    assert resp.status_code == 404


# ── 合规校验 ──


@pytest.mark.asyncio
async def test_validate_scheme(client: AsyncClient):
    """validate 返回 compliance_status/score/summary"""
    headers = await _auth_headers(client, "13950010007")
    project_id = await _create_project(client, headers)
    created = await _create_scheme(client, headers, project_id)

    resp = await client.post(
        f"/api/elderly-adaptation/schemes/{created['id']}/validate", headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "compliance_status" in data
    assert "score" in data
    assert "summary" in data
    # 尚未进行动线实测 → 不伪造结论，维持 warning 待复核
    assert data["compliance_status"] == "warning"
    assert data["score"] is None


# ── 无障碍动线检查 ──


@pytest.mark.asyncio
async def test_check_accessibility_reports_narrow_door(client: AsyncClient):
    """窄门(<800mm)应报无障碍违规"""
    headers = await _auth_headers(client, "13950010008")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/elderly-adaptation/check-accessibility",
        json={
            "project_id": project_id,
            "rooms": [
                {"room_type": "bathroom", "door_width_mm": 750, "corridor_width_mm": 950,
                 "level_difference_mm": 0},
                {"room_type": "bedroom", "door_width_mm": 850, "level_difference_mm": 20},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "violations" in data and "score" in data and "compliance" in data
    door_violations = [
        v for v in data["violations"]
        if v["room_type"] == "bathroom" and "门洞" in v["issue"]
    ]
    assert door_violations, f"应报告门洞净宽不足违规, violations={data['violations']}"
    assert data["score"] < 100


@pytest.mark.asyncio
async def test_check_accessibility_compliant_rooms_pass(client: AsyncClient):
    """全部合规的房间 → score 100 / compliance pass"""
    headers = await _auth_headers(client, "13950010009")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/elderly-adaptation/check-accessibility",
        json={
            "project_id": project_id,
            "rooms": [
                {"room_type": "bathroom", "door_width_mm": 850, "corridor_width_mm": 950,
                 "level_difference_mm": 0},
                {"room_type": "corridor", "corridor_width_mm": 1200},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["violations"] == []
    assert data["score"] == 100
    assert data["compliance"] == "pass"


# ── HC-006 逃生通道专项检查 ──


@pytest.mark.asyncio
async def test_check_escape_route_compliant_pass(client: AsyncClient):
    """逃生通道全部合规（入户门 900 / 走廊 1200 无高差 / 逃生窗 700 / 走廊畅通）
    → compliance pass，且响应标注 standard=HC-006"""
    headers = await _auth_headers(client, "13950010012")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/elderly-adaptation/check-accessibility",
        json={
            "project_id": project_id,
            "rooms": [
                {"room_type": "entrance", "door_width_mm": 900},
                {"room_type": "corridor", "room_name": "客餐厅走廊", "corridor_width_mm": 1200,
                 "level_difference_mm": 0, "corridor_blocked": False},
                {"room_type": "bedroom", "room_name": "主卧", "escape_window_width_mm": 700},
                {"room_type": "living", "room_name": "客厅", "escape_window_width_mm": 650},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "escape_route" in data
    er = data["escape_route"]
    assert er["standard"] == "HC-006"
    assert er["compliance"] == "pass"
    assert er["items"], "逃生通道检查项列表不应为空"
    for item in er["items"]:
        assert {"rule", "threshold", "actual", "status", "standard"}.issubset(item.keys())
        assert item["standard"] == "HC-006"
        assert item["status"] == "pass"
    rules = [item["rule"] for item in er["items"]]
    assert any("入户门净宽" in r for r in rules)
    assert any("逃生通道（走廊）净宽" in r for r in rules)
    assert any("逃生通道高差" in r for r in rules)
    assert any("可开启逃生窗净宽" in r for r in rules)
    assert any("禁止封闭走廊" in r for r in rules)


@pytest.mark.asyncio
async def test_check_escape_route_blocked_fail(client: AsyncClient):
    """逃生通道违规：窄入户门 750 / 窄走廊 800 + 高差 30 / 逃生窗 500 /
    走廊被封堵 → compliance fail，逐项结构化标注 fail"""
    headers = await _auth_headers(client, "13950010013")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/elderly-adaptation/check-accessibility",
        json={
            "project_id": project_id,
            "rooms": [
                {"room_type": "entrance", "door_width_mm": 750},
                {"room_type": "corridor", "room_name": "入户走廊", "corridor_width_mm": 800,
                 "level_difference_mm": 30, "corridor_blocked": True},
                {"room_type": "bedroom", "room_name": "次卧", "escape_window_width_mm": 500},
                {"room_type": "living", "room_name": "客厅"},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    er = data["escape_route"]
    assert er["standard"] == "HC-006"
    assert er["compliance"] == "fail"

    fail_rules = [item["rule"] for item in er["items"] if item["status"] == "fail"]
    assert any("入户门净宽" in r for r in fail_rules)
    assert any("逃生通道（走廊）净宽" in r for r in fail_rules)
    assert any("逃生通道高差" in r for r in fail_rules)
    assert any("可开启逃生窗净宽" in r for r in fail_rules)
    assert any("禁止封闭走廊" in r for r in fail_rules)

    # 未提供逃生窗数据的客厅 → 诚实标注 warning，不伪造 fail/pass
    warning_rules = [item["rule"] for item in er["items"] if item["status"] == "warning"]
    assert any("可开启逃生窗净宽" in r and "客厅" in r for r in warning_rules)


# ── 越权校验 ──


@pytest.mark.asyncio
async def test_elderly_adaptation_cross_user_access_blocked(client: AsyncClient):
    """用户不能访问他人的适老改造方案"""
    headers_a = await _auth_headers(client, "13950010010")
    headers_b = await _auth_headers(client, "13950010011")
    project_id_a = await _create_project(client, headers_a)
    scheme_a = await _create_scheme(client, headers_a, project_id_a)

    resp = await client.get(
        f"/api/elderly-adaptation/schemes/{scheme_a['id']}",
        headers=headers_b,
    )
    assert resp.status_code == 403
