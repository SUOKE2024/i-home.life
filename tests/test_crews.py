"""Tests for crews API endpoints.

覆盖端点:
- GET  /api/crews                    (列出施工队)
- POST /api/crews                    (创建施工队)
- GET  /api/crews/{crew_id}          (获取施工队详情)
- POST /api/crews/match              (智能匹配)
- GET  /api/crews/matches/{project_id}  (查询匹配记录)
- POST /api/crews/matches/{match_id}/status  (更新匹配状态)
- POST /api/crews/{crew_id}/submit   (提交入驻审核)
- POST /api/crews/{crew_id}/review   (管理员审核入驻)
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.construction_crew import ConstructionCrew

CREW_MATERIALS = {
    "license_no": "91110108MA01ABC123",
    "license_type": "营业执照",
    "insurance_no": "INS20260801001",
}


async def _create_crew(client: AsyncClient, headers: dict, name: str = "审核测试队") -> str:
    resp = await client.post(
        "/api/crews",
        json={
            "name": name,
            "leader": "刘工",
            "city": "北京",
            "district": "朝阳区",
            "specialties": ["mep"],
        },
        headers=headers,
    )
    assert resp.status_code == 201, f"创建失败: {resp.json()}"
    return resp.json()["id"]


async def _create_project(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        "/api/projects", json={"name": "工程队审核测试项目", "total_area": 100.0}, headers=headers,
    )
    assert resp.status_code in (200, 201), f"创建项目失败: {resp.json()}"
    return resp.json()["id"]


async def _register_admin(client: AsyncClient) -> dict:
    """注册管理员用户并返回 auth headers"""
    phone = f"139{str(uuid.uuid4().int)[:8]}"
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "审核管理员", "password": "test123456", "role": "admin"},
    )
    assert resp.status_code == 201, f"注册管理员失败: {resp.json()}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_crews_requires_auth(client: AsyncClient):
    """未认证请求施工队接口返回 401"""
    resp = await client.get("/api/crews")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_crews(client: AsyncClient, auth_headers: dict):
    """列出施工队"""
    resp = await client.get("/api/crews", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_create_crew(client: AsyncClient, auth_headers: dict):
    """创建施工队"""
    resp = await client.post(
        "/api/crews",
        json={
            "name": "精英施工队",
            "leader": "张工",
            "phone": "13800001111",
            "city": "北京",
            "district": "朝阳区",
            "qualification": "A",
            "specialties": ["mep", "masonry"],
            "rating": 4.5,
            "completed_projects": 20,
            "avg_duration": 45,
            "daily_rate": 1200,
            "status": "available",
            "introduction": "专业施工团队，经验丰富",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, f"创建失败: {resp.json()}"
    data = resp.json()
    assert data["name"] == "精英施工队"
    assert data["leader"] == "张工"
    assert "id" in data


@pytest.mark.asyncio
async def test_get_crew_not_found(client: AsyncClient, auth_headers: dict):
    """获取不存在的施工队返回 404"""
    resp = await client.get("/api/crews/nonexistent-crew-id", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_crews_with_city_filter(client: AsyncClient, auth_headers: dict):
    """按城市筛施工队"""
    # 先创建一个上海施工队
    await client.post(
        "/api/crews",
        json={
            "name": "上海施工一队",
            "leader": "李工",
            "city": "上海",
            "district": "浦东新区",
            "specialties": ["carpentry", "painting"],
        },
        headers=auth_headers,
    )
    # 按城市过滤
    resp = await client.get("/api/crews?city=上海", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all(c["city"] == "上海" for c in data if c.get("city"))


@pytest.mark.asyncio
async def test_create_crew_minimal_fields(client: AsyncClient, auth_headers: dict):
    """创建施工队只填必填字段（name + leader）"""
    resp = await client.post(
        "/api/crews",
        json={
            "name": "快速施工队",
            "leader": "王工",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, f"创建失败: {resp.json()}"
    data = resp.json()
    assert data["name"] == "快速施工队"
    assert data["qualification"] == "B"  # 默认值


@pytest.mark.asyncio
async def test_create_crew_empty_name_fails(client: AsyncClient, auth_headers: dict):
    """名称为空应返回 422"""
    resp = await client.post(
        "/api/crews",
        json={"name": "", "leader": "张工"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


# ── F36 入驻审核状态机 ──


@pytest.mark.asyncio
async def test_create_crew_default_review_status_pending(
    client: AsyncClient, auth_headers: dict, db_session,
):
    """F36: 新创建工程队默认 review_status=pending（未审核不可用）"""
    crew_id = await _create_crew(client, auth_headers, "待审核施工队")
    result = await db_session.execute(
        select(ConstructionCrew).where(ConstructionCrew.id == crew_id)
    )
    crew = result.scalar_one()
    assert crew.review_status == "pending"
    assert crew.reviewed_at is None


@pytest.mark.asyncio
async def test_submit_review_missing_materials_400(
    client: AsyncClient, auth_headers: dict,
):
    """F36: 提交审核缺执照/保险必填材料返回 400 并说明缺什么"""
    crew_id = await _create_crew(client, auth_headers, "缺材料施工队")
    resp = await client.post(f"/api/crews/{crew_id}/submit", headers=auth_headers)
    assert resp.status_code == 400, f"应返回 400: {resp.json()}"
    detail = resp.json()["detail"]
    assert "license_no" in detail
    assert "license_type" in detail
    assert "insurance_no" in detail


@pytest.mark.asyncio
async def test_submit_review_with_materials_succeeds(
    client: AsyncClient, auth_headers: dict, db_session,
):
    """F36: 补齐执照/保险材料后提交审核成功，保持 pending 待审核"""
    crew_id = await _create_crew(client, auth_headers, "材料齐全施工队")
    resp = await client.post(
        f"/api/crews/{crew_id}/submit",
        json=CREW_MATERIALS,
        headers=auth_headers,
    )
    assert resp.status_code == 200, f"提交审核失败: {resp.json()}"
    result = await db_session.execute(
        select(ConstructionCrew).where(ConstructionCrew.id == crew_id)
    )
    crew = result.scalar_one()
    assert crew.review_status == "pending"
    assert crew.license_no == CREW_MATERIALS["license_no"]
    assert crew.insurance_no == CREW_MATERIALS["insurance_no"]


@pytest.mark.asyncio
async def test_review_crew_requires_admin(
    client: AsyncClient, auth_headers: dict,
):
    """F36: 非 admin 调审核接口返回 403"""
    crew_id = await _create_crew(client, auth_headers)
    resp = await client.post(
        f"/api/crews/{crew_id}/review",
        json={"action": "approve", "note": "通过"},
        headers=auth_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_crew_approved_appears_in_match(
    client: AsyncClient, auth_headers: dict, db_session,
):
    """F36: admin approve 后工程队出现在匹配结果中"""
    project_id = await _create_project(client, auth_headers)
    crew_id = await _create_crew(client, auth_headers, "审核通过队")
    await client.post(f"/api/crews/{crew_id}/submit", json=CREW_MATERIALS, headers=auth_headers)

    admin_headers = await _register_admin(client)
    resp = await client.post(
        f"/api/crews/{crew_id}/review",
        json={"action": "approve", "note": "资质合规，审核通过"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, f"审核失败: {resp.json()}"
    result = await db_session.execute(
        select(ConstructionCrew).where(ConstructionCrew.id == crew_id)
    )
    assert result.scalar_one().review_status == "approved"

    resp = await client.post(
        "/api/crews/match",
        json={"project_id": project_id, "city": "北京", "district": "朝阳区", "top_n": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    matches = resp.json()
    assert any(m["crew"] and m["crew"]["id"] == crew_id for m in matches), "approved 工程队应出现在匹配中"


@pytest.mark.asyncio
async def test_crew_list_passes_review_status(
    client: AsyncClient, auth_headers: dict,
):
    """list_crews 应透传 review_status，已审核通过工程队不再被误标 pending"""
    crew_id = await _create_crew(client, auth_headers, "审核状态透传队")
    await client.post(f"/api/crews/{crew_id}/submit", json=CREW_MATERIALS, headers=auth_headers)

    admin_headers = await _register_admin(client)
    await client.post(f"/api/crews/{crew_id}/review", json={"action": "approve"}, headers=admin_headers)

    resp = await client.get("/api/crews", headers=auth_headers)
    assert resp.status_code == 200
    crew = next(c for c in resp.json() if c["id"] == crew_id)
    assert crew["review_status"] == "approved"


@pytest.mark.asyncio
async def test_crew_rejected_not_in_match(
    client: AsyncClient, auth_headers: dict,
):
    """F36: admin reject 后工程队不出现（且未出现其他 pending 工程队）在匹配结果中"""
    project_id = await _create_project(client, auth_headers)
    crew_id = await _create_crew(client, auth_headers, "驳回施工队")
    await client.post(f"/api/crews/{crew_id}/submit", json=CREW_MATERIALS, headers=auth_headers)

    admin_headers = await _register_admin(client)
    resp = await client.post(
        f"/api/crews/{crew_id}/review",
        json={"action": "reject", "note": "保险单号无法核验，请补充"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, f"审核失败: {resp.json()}"

    resp = await client.post(
        "/api/crews/match",
        json={"project_id": project_id, "city": "北京", "district": "朝阳区", "top_n": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    matches = resp.json()
    assert all(m["crew"]["id"] != crew_id for m in matches), "rejected 工程队不应出现在匹配中"


@pytest.mark.asyncio
async def test_rejected_crew_resubmit_back_to_pending(
    client: AsyncClient, auth_headers: dict, db_session,
):
    """F36: rejected 工程队可重新提交审核回到 pending"""
    crew_id = await _create_crew(client, auth_headers, "重新提交施工队")
    await client.post(f"/api/crews/{crew_id}/submit", json=CREW_MATERIALS, headers=auth_headers)

    admin_headers = await _register_admin(client)
    resp = await client.post(
        f"/api/crews/{crew_id}/review",
        json={"action": "reject", "note": "材料不符"},
        headers=admin_headers,
    )
    assert resp.status_code == 200

    resp = await client.post(f"/api/crews/{crew_id}/submit", headers=auth_headers)
    assert resp.status_code == 200, f"重新提交审核失败: {resp.json()}"
    result = await db_session.execute(
        select(ConstructionCrew).where(ConstructionCrew.id == crew_id)
    )
    assert result.scalar_one().review_status == "pending"


# ── M4：服务商作品集展厅（showcase_panorama_id，设计 4.3）──


@pytest.mark.asyncio
async def test_admin_set_crew_showcase_panorama(client: AsyncClient, auth_headers: dict):
    """管理员绑定服务商作品集代表作全景，Response/列表透传"""
    crew_id = await _create_crew(client, auth_headers, "作品集展厅队")
    admin_headers = await _register_admin(client)

    resp = await client.patch(
        f"/api/crews/{crew_id}",
        json={"showcase_panorama_id": "pano-showcase-001"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["showcase_panorama_id"] == "pano-showcase-001"

    resp = await client.get("/api/crews", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    match = [c for c in resp.json() if c["id"] == crew_id]
    assert match and match[0]["showcase_panorama_id"] == "pano-showcase-001"


@pytest.mark.asyncio
async def test_non_admin_cannot_update_crew(client: AsyncClient, auth_headers: dict):
    """非管理员无权更新工程队（含作品集绑定）"""
    crew_id = await _create_crew(client, auth_headers, "权限作品集队")
    resp = await client.patch(
        f"/api/crews/{crew_id}",
        json={"showcase_panorama_id": "pano-x"},
        headers=auth_headers,
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_create_crew_with_showcase_panorama(client: AsyncClient, auth_headers: dict):
    """创建工程队时可带作品集代表作全景（透传）"""
    resp = await client.post(
        "/api/crews",
        json={
            "name": "带作品集工程队",
            "leader": "王工",
            "city": "北京",
            "specialties": ["mep"],
            "showcase_panorama_id": "pano-create-001",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["showcase_panorama_id"] == "pano-create-001"


# ── M4 设计 4.3 装修过程透明：工程队作品集聚合（施工进度 + 质检时间线）──


@pytest.mark.asyncio
async def test_crew_portfolio_not_found(client: AsyncClient, auth_headers: dict):
    """作品集聚合：不存在的工程队返回 404"""
    resp = await client.get("/api/crews/no-such-crew/portfolio", headers=auth_headers)
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_crew_portfolio_empty(client: AsyncClient, auth_headers: dict):
    """作品集聚合：无已雇佣项目时 projects 为空列表（诚实标注）"""
    crew_id = await _create_crew(client, auth_headers, "无项目作品集队")
    resp = await client.get(f"/api/crews/{crew_id}/portfolio", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["crew_id"] == crew_id
    assert data["projects"] == []


@pytest.mark.asyncio
async def test_crew_portfolio_with_hired_project(
    client: AsyncClient, auth_headers: dict, db_session,
):
    """作品集聚合：已雇佣项目的施工任务阶段分布 + 质检时间线"""
    project_id = await _create_project(client, auth_headers)
    crew_id = await _create_crew(client, auth_headers, "有项目作品集队")
    await client.post(f"/api/crews/{crew_id}/submit", json=CREW_MATERIALS, headers=auth_headers)

    admin_headers = await _register_admin(client)
    resp = await client.post(
        f"/api/crews/{crew_id}/review",
        json={"action": "approve", "note": "审核通过"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text

    # 匹配 → 入围 → 雇佣（状态机：pending → shortlisted → hired）
    resp = await client.post(
        "/api/crews/match",
        json={"project_id": project_id, "city": "北京", "district": "朝阳区", "top_n": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    matches = resp.json()
    mine = next((m for m in matches if m["crew"] and m["crew"]["id"] == crew_id), None)
    assert mine, "approve 后工程队应出现在匹配中"
    for status in ("shortlisted", "hired"):
        resp = await client.post(
            f"/api/crews/matches/{mine['id']}/status?new_status={status}",
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
    resp = await client.get(f"/api/crews/matches/{project_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert any(m["id"] == mine["id"] and m["status"] == "hired" for m in resp.json()), "match 应已 hired"

    # 施工任务（水电阶段 2 项，1 项完成）
    task_ids = []
    for name in ("水管铺设", "电路改造"):
        resp = await client.post(
            "/api/construction/tasks",
            json={"project_id": project_id, "name": name, "phase": "water_electricity"},
            headers=auth_headers,
        )
        assert resp.status_code == 201, resp.text
        task_ids.append(resp.json()["id"])
    for status_val in ("in_progress", "completed"):
        resp = await client.patch(
            f"/api/construction/tasks/{task_ids[0]}/status?status_val={status_val}",
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text

    # 质检评估（水电阶段通过）
    resp = await client.post(
        "/api/construction/quality-assessments",
        json={
            "project_id": project_id,
            "phase": "water_electricity",
            "total_items": 10,
            "passed": 9,
            "failed": 1,
            "score": 90.0,
            "verdict": "pass",
            "assessor": "测试质检员",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text

    resp = await client.get(f"/api/crews/{crew_id}/portfolio", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["crew_name"] == "有项目作品集队"
    assert len(data["projects"]) == 1
    project = data["projects"][0]
    assert project["project_id"] == project_id
    assert len(project["task_phases"]) == 1
    phase = project["task_phases"][0]
    assert phase["phase"] == "water_electricity"
    assert phase["phase_label"] == "水电阶段"
    assert phase["total"] == 2
    assert phase["completed"] == 1
    assert phase["pending"] == 1
    assert len(project["assessments"]) == 1
    assert project["assessments"][0]["verdict"] == "pass"
    assert project["assessments"][0]["phase_label"] == "水电阶段"


# ── M4 设计 4.3 付费展厅商业闭环：权益兑换 ──


async def _register_user(client: AsyncClient, name: str = "服务商业主") -> tuple[dict, str]:
    """注册普通用户并返回 auth headers + 手机号"""
    phone = f"138{str(uuid.uuid4().int)[:8]}"
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": name, "password": "test123456"},
    )
    assert resp.status_code == 201, f"注册用户失败: {resp.json()}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}, phone


async def _create_benefit_item(db_session, benefit_type: str, name: str, points: int):
    from app.models.points import PointsMallItem

    item = PointsMallItem(
        name=name,
        category="vip",
        points_required=points,
        stock=-1,
        is_active=True,
        validity_days=30,
        benefit_type=benefit_type,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    return item


async def _fund_user(db_session, user_id: str, amount: int):
    from app.services.points_service import earn_points

    await earn_points(db_session, user_id, source="test_action", amount=amount)
    await db_session.commit()


async def _get_user_id(db_session, phone: str) -> str:
    from app.models.user import User

    result = await db_session.execute(select(User).where(User.phone == phone))
    return result.scalar_one().id


@pytest.mark.asyncio
async def test_admin_bind_crew_owner(client: AsyncClient, auth_headers: dict, db_session):
    """管理员平台绑定权益归属账号 owner_id，Response 透传"""
    crew_id = await _create_crew(client, auth_headers, "权益归属队")
    _, phone = await _register_user(client)
    owner_id = await _get_user_id(db_session, phone)
    admin_headers = await _register_admin(client)

    resp = await client.patch(
        f"/api/crews/{crew_id}",
        json={"owner_id": owner_id},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["owner_id"] == owner_id
    assert resp.json()["featured"] is False  # 无权益恒 False（平台授予非自报）


@pytest.mark.asyncio
async def test_redeem_showroom_featured_benefit(
    client: AsyncClient, auth_headers: dict, db_session,
):
    """权益归属账号兑换「作品集置顶」：积分扣减 + crew.featured=True + 权益记录落库 + 列表置顶"""
    crew_id = await _create_crew(client, auth_headers, "付费置顶队")
    owner_headers, phone = await _register_user(client)
    owner_id = await _get_user_id(db_session, phone)
    await client.patch(f"/api/crews/{crew_id}", json={"owner_id": owner_id}, headers=await _register_admin(client))

    item = await _create_benefit_item(db_session, "showroom_featured", "作品集置顶 · 30 天", 2000)
    await _fund_user(db_session, owner_id, 10000)

    resp = await client.post(
        f"/api/crews/{crew_id}/benefits/redeem",
        json={"item_id": item.id},
        headers=owner_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["benefit_type"] == "showroom_featured"
    assert data["points_spent"] == 2000
    assert data["status"] == "active"

    # 工程队置顶（平台授予由权益驱动）
    resp = await client.get(f"/api/crews/{crew_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["featured"] is True

    # 积分扣减（10000 - 2000）
    resp = await client.get("/api/points/account", headers=owner_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["balance"] == 8000

    # 权益记录
    resp = await client.get(f"/api/crews/{crew_id}/benefits", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 1
    assert resp.json()[0]["benefit_type"] == "showroom_featured"

    # 列表置顶：featured 工程队排在最前
    resp = await client.get("/api/crews", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()[0]["id"] == crew_id


@pytest.mark.asyncio
async def test_redeem_benefit_requires_owner(
    client: AsyncClient, auth_headers: dict, db_session,
):
    """非权益归属账号（非 admin）兑换展厅权益返回 403（防止替他人买置顶）"""
    crew_id = await _create_crew(client, auth_headers, "权限权益队")
    owner_headers, phone = await _register_user(client)
    owner_id = await _get_user_id(db_session, phone)
    await client.patch(f"/api/crews/{crew_id}", json={"owner_id": owner_id}, headers=await _register_admin(client))

    stranger_headers, _ = await _register_user(client, "无关用户")
    item = await _create_benefit_item(db_session, "showroom_featured", "置顶权益", 100)

    resp = await client.post(
        f"/api/crews/{crew_id}/benefits/redeem",
        json={"item_id": item.id},
        headers=stranger_headers,
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_redeem_non_benefit_item_rejected(
    client: AsyncClient, auth_headers: dict, db_session,
):
    """普通商城商品（无 benefit_type）不可作为展厅权益兑换 → 400"""
    crew_id = await _create_crew(client, auth_headers, "非权益队")
    owner_headers, phone = await _register_user(client)
    owner_id = await _get_user_id(db_session, phone)
    await client.patch(f"/api/crews/{crew_id}", json={"owner_id": owner_id}, headers=await _register_admin(client))

    item = await _create_benefit_item(db_session, "showroom_featured", "普通商品", 100)
    item.benefit_type = None
    await db_session.commit()

    resp = await client.post(
        f"/api/crews/{crew_id}/benefits/redeem",
        json={"item_id": item.id},
        headers=owner_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "展厅权益商品" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_redeem_duplicate_benefit_rejected(
    client: AsyncClient, auth_headers: dict, db_session,
):
    """同工程队同权益重复兑换 → 400（防重复扣积分）"""
    crew_id = await _create_crew(client, auth_headers, "重复权益队")
    owner_headers, phone = await _register_user(client)
    owner_id = await _get_user_id(db_session, phone)
    await client.patch(f"/api/crews/{crew_id}", json={"owner_id": owner_id}, headers=await _register_admin(client))

    item = await _create_benefit_item(db_session, "showroom_featured", "置顶权益", 100)
    await _fund_user(db_session, owner_id, 1000)

    resp = await client.post(
        f"/api/crews/{crew_id}/benefits/redeem",
        json={"item_id": item.id},
        headers=owner_headers,
    )
    assert resp.status_code == 200, resp.text
    resp = await client.post(
        f"/api/crews/{crew_id}/benefits/redeem",
        json={"item_id": item.id},
        headers=owner_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "已生效" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_redeem_benefit_insufficient_points(
    client: AsyncClient, auth_headers: dict, db_session,
):
    """积分不足兑换权益 → 400（复用积分扣减校验）"""
    crew_id = await _create_crew(client, auth_headers, "低分权益队")
    owner_headers, phone = await _register_user(client)
    owner_id = await _get_user_id(db_session, phone)
    await client.patch(f"/api/crews/{crew_id}", json={"owner_id": owner_id}, headers=await _register_admin(client))

    item = await _create_benefit_item(db_session, "vr_photo", "VR 实拍权益 · 3 套", 5000)
    await _fund_user(db_session, owner_id, 100)

    resp = await client.post(
        f"/api/crews/{crew_id}/benefits/redeem",
        json={"item_id": item.id},
        headers=owner_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "积分不足" in resp.json()["detail"]
