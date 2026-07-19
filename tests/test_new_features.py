"""F15 支付 / F28 动线 / F40 IM / F36 工程队 新功能测试"""

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, phone: str = "13900006001") -> tuple[str, dict]:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "新功能测试用户", "password": "test123456"},
    )
    token = resp.json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "新功能测试项目") -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": name, "total_area": 100.0},
        headers=headers,
    )
    return resp.json()["id"]


# ── F15 支付管理 ──

@pytest.mark.asyncio
async def test_payment_full_lifecycle(client: AsyncClient):
    token, headers = await _register_and_login(client, "13900006001")
    project_id = await _create_project(client, headers, "支付测试")

    # 1. 发起支付
    resp = await client.post(
        "/api/payments",
        json={
            "project_id": project_id,
            "milestone_code": "handover",
            "amount": 30000.0,
            "payment_method": "bank_transfer",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    payment = resp.json()
    assert payment["status"] == "pending"
    assert payment["amount"] == 30000.0
    payment_id = payment["id"]

    # 2. 确认支付
    resp = await client.post(
        f"/api/payments/{payment_id}/confirm",
        json={"transaction_id": "TX_TEST_001", "evidence_url": "/files/test.pdf"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "paid"
    assert resp.json()["transaction_id"] == "TX_TEST_001"

    # 3. 列表查询
    resp = await client.get(f"/api/payments/project/{project_id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # 4. 里程碑聚合
    resp = await client.get(f"/api/payments/milestones/{project_id}", headers=headers)
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["total_paid"] == 30000.0
    assert summary["total_pending"] == 0.0
    assert len(summary["milestones"]) == 1
    assert summary["milestones"][0]["milestone_code"] == "handover"
    assert summary["milestones"][0]["paid_amount"] == 30000.0

    # 5. 退款
    resp = await client.post(
        f"/api/payments/{payment_id}/refund",
        json={"refund_amount": 30000.0, "refund_reason": "验收未通过"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "refunded"
    assert resp.json()["refund_amount"] == 30000.0


@pytest.mark.asyncio
async def test_payment_not_found(client: AsyncClient):
    token, headers = await _register_and_login(client, "13900006002")
    resp = await client.get("/api/payments/non-existent-id", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_payment_refund_invalid_state(client: AsyncClient):
    """未支付的订单不能退款"""
    token, headers = await _register_and_login(client, "13900006003")
    project_id = await _create_project(client, headers, "退款失败测试")

    resp = await client.post(
        "/api/payments",
        json={"project_id": project_id, "milestone_code": "completion", "amount": 1000.0},
        headers=headers,
    )
    payment_id = resp.json()["id"]

    resp = await client.post(
        f"/api/payments/{payment_id}/refund",
        json={"refund_amount": 1000.0},
        headers=headers,
    )
    assert resp.status_code == 400


# ── F28 动线分析 ──

@pytest.mark.asyncio
async def test_circulation_analysis_basic(client: AsyncClient):
    token, headers = await _register_and_login(client, "13900006004")
    rooms = [
        {"name": "客厅", "type": "living_room", "x": 0.5, "y": 0.5, "w": 6.0, "h": 4.5},
        {"name": "餐厅", "type": "dining_room", "x": 7.0, "y": 0.5, "w": 3.5, "h": 3.0},
        {"name": "主卧", "type": "bedroom", "x": 0.5, "y": 5.5, "w": 3.5, "h": 3.5},
        {"name": "厨房", "type": "kitchen", "x": 0.5, "y": 9.5, "w": 3.0, "h": 2.0},
        {"name": "卫生间", "type": "bathroom", "x": 4.0, "y": 9.5, "w": 2.5, "h": 2.0},
    ]
    resp = await client.post(
        "/api/agents/design/circulation",
        json={"rooms": rooms},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "circulations" in data
    assert len(data["circulations"]) == 3  # 访客/家务/居住
    assert "overall_score" in data
    assert "rating" in data
    assert "reply" in data
    # 三条动线类型
    types = [c["type"] for c in data["circulations"]]
    assert "visitor" in types
    assert "housework" in types
    assert "living" in types


@pytest.mark.asyncio
async def test_circulation_empty_rooms(client: AsyncClient):
    token, headers = await _register_and_login(client, "13900006005")
    resp = await client.post(
        "/api/agents/design/circulation",
        json={"rooms": []},
        headers=headers,
    )
    assert resp.status_code == 200
    assert "error" in resp.json()


# ── F40 IM 协作 ──

@pytest.mark.asyncio
async def test_chat_full_lifecycle(client: AsyncClient):
    token, headers = await _register_and_login(client, "13900006006")
    project_id = await _create_project(client, headers, "IM 测试")

    # 1. 获取聊天室（自动创建）
    resp = await client.get(f"/api/chat/rooms/{project_id}", headers=headers)
    assert resp.status_code == 200
    room = resp.json()
    assert room["project_id"] == project_id
    assert room["name"] == "项目协作群"

    # 2. 发送消息
    resp = await client.post(
        "/api/chat/messages",
        json={
            "project_id": project_id,
            "content": "大家好，开始协作",
            "message_type": "text",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    msg = resp.json()
    msg_id = msg["id"]
    assert msg["content"] == "大家好，开始协作"
    assert msg["sender_role"] == "homeowner"

    # 3. 发送带 @提及 的消息
    resp = await client.post(
        "/api/chat/messages",
        json={
            "project_id": project_id,
            "content": "@设计师 请查看",
            "mentions": ["user_designer_001"],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["mentions"] == ["user_designer_001"]

    # 4. 消息列表
    resp = await client.get(f"/api/chat/messages/{project_id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    # 5. 标记已读
    resp = await client.post(f"/api/chat/messages/{msg_id}/read", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["read_by"] == [resp.json()["sender_id"]]

    # 6. 未读数（同一用户发送的消息不算未读）
    resp = await client.get(f"/api/chat/unread/{project_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["unread_count"] == 0  # 自己发的消息不算未读


# ── F36 工程队匹配 ──

@pytest.mark.asyncio
async def test_crew_create_and_list(client: AsyncClient):
    token, headers = await _register_and_login(client, "13900006007")

    # 创建工程队
    resp = await client.post(
        "/api/crews",
        json={
            "name": "测试工程队",
            "leader": "张工长",
            "city": "北京",
            "district": "朝阳区",
            "qualification": "A",
            "specialties": ["mep", "masonry"],
            "rating": 4.5,
            "daily_rate": 1000,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    crew_id = resp.json()["id"]

    # 查询
    resp = await client.get(f"/api/crews/{crew_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "测试工程队"
    assert resp.json()["specialties"] == ["mep", "masonry"]

    # 列表
    resp = await client.get("/api/crews", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_crew_match(client: AsyncClient):
    token, headers = await _register_and_login(client, "13900006008")
    project_id = await _create_project(client, headers, "工程队匹配测试")

    # 创建 2 个工程队
    await client.post(
        "/api/crews",
        json={
            "name": "高分匹配队", "leader": "王工长", "city": "北京", "district": "朝阳区",
            "qualification": "A", "specialties": ["mep", "masonry"],
            "rating": 4.8, "daily_rate": 900, "avg_duration": 50,
        },
        headers=headers,
    )
    await client.post(
        "/api/crews",
        json={
            "name": "低分匹配队", "leader": "李工长", "city": "天津",
            "qualification": "C", "specialties": ["masonry"],
            "rating": 3.5, "daily_rate": 1500, "avg_duration": 80,
        },
        headers=headers,
    )

    # 匹配
    resp = await client.post(
        "/api/crews/match",
        json={
            "project_id": project_id,
            "city": "北京",
            "district": "朝阳区",
            "required_specialties": ["mep", "masonry"],
            "budget_daily_rate_max": 1000,
            "expected_duration_days": 60,
            "top_n": 5,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    matches = resp.json()
    assert len(matches) >= 1
    # 第一名应该是高分匹配队（同城+专长全+高分+在预算内）
    top = matches[0]
    assert top["crew"]["name"] == "高分匹配队"
    assert top["match_score"] > 80
    assert "score_breakdown" in top
    assert "recommendation" in top

    # 查询项目匹配记录
    resp = await client.get(f"/api/crews/matches/{project_id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    # 更新状态：入围 → 雇佣
    match_id = matches[0]["id"]
    resp = await client.post(
        f"/api/crews/matches/{match_id}/status?new_status=shortlisted",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "shortlisted"

    resp = await client.post(
        f"/api/crews/matches/{match_id}/status?new_status=hired",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "hired"
