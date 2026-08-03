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
