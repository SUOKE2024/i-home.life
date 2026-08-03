"""B2B 装企交付 API 测试（v1.4.x，借鉴"卖结果不卖功能"交付式产品）

覆盖:
- 未认证 → 401
- 正常调用 → 200，整包含 proposals/budget_estimate/construction_plan/sources
- 各交付块 source 诚实标注（design=llm|fallback，budget/construction=estimated）
- 施工计划含 ≥10% 工期缓冲（对齐 HC-004）
- feature flag 关闭 → 403
"""

import pytest
from httpx import AsyncClient

from app.config import get_settings


async def _register(client: AsyncClient, phone: str = "13900007001") -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "B2B装企", "password": "test123456"},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_b2b_delivery_requires_auth(client: AsyncClient):
    """未认证不能调用交付 API"""
    resp = await client.post(
        "/api/b2b/delivery",
        json={"area": 120, "style": "modern"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_b2b_delivery_returns_package(client: AsyncClient):
    """正常调用应返回 设计方案+报价+施工计划 整包，且各块标注来源"""
    token = await _register(client)
    resp = await client.post(
        "/api/b2b/delivery",
        json={
            "name": "三室两厅整装交付",
            "area": 120,
            "style": "modern",
            "budget": 250000,
            "requirements": "主卧带衣帽间",
            "rooms": "客厅,主卧,次卧,厨房,卫生间",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["delivery_id"]
    assert data["name"] == "三室两厅整装交付"
    assert data["summary"]
    # 设计方案：LLM 可用时 2-3 套，fallback 诚实降级为单方案
    assert len(data["proposals"]) >= 1
    # 全部方案必须有标识与来源
    for p in data["proposals"]:
        assert p["proposal_id"]
        assert p["source"] in ("llm", "fallback")
    # 报价估算：四档齐全 + 推荐档
    assert "tiers" in data["budget_estimate"]
    assert data["budget_estimate"]["recommended_tier"] in data["budget_estimate"]["tiers"]
    # 施工计划：阶段 + 总工期
    assert data["construction_plan"]["phases"]
    assert data["construction_plan"]["total_days"] > 0
    # 来源诚实标注
    assert data["sources"]["design"] in ("llm", "fallback")
    assert data["sources"]["budget"] == "estimated"
    assert data["sources"]["construction"] == "estimated"


@pytest.mark.asyncio
async def test_b2b_delivery_budget_tiers_match_area(client: AsyncClient):
    """报价估算应按面积缩放（舒适档 ≈ area × 1600）"""
    token = await _register(client, "13900007002")
    resp = await client.post(
        "/api/b2b/delivery",
        json={"area": 100, "style": "nordic"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    tiers = resp.json()["budget_estimate"]["tiers"]
    assert tiers["comfort"]["total_estimate"] == 100 * 1600


@pytest.mark.asyncio
async def test_b2b_delivery_construction_has_buffer(client: AsyncClient):
    """施工计划总工期应含 ≥10% 缓冲（HC-004）"""
    token = await _register(client, "13900007003")
    resp = await client.post(
        "/api/b2b/delivery",
        json={"area": 120, "style": "modern"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    plan = resp.json()["construction_plan"]
    base_days = sum(p["days"] for p in plan["phases"])
    assert plan["buffer_days"] >= round(base_days * 0.1)
    assert plan["total_days"] == base_days + plan["buffer_days"]


@pytest.mark.asyncio
async def test_b2b_delivery_flag_disabled(client: AsyncClient, monkeypatch):
    """feature flag 关闭时应 403"""
    token = await _register(client, "13900007004")
    monkeypatch.setattr(get_settings(), "b2b_delivery_enabled", False)
    resp = await client.post(
        "/api/b2b/delivery",
        json={"area": 90, "style": "japanese"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


# ── v1.4.x 交付单订单化：落库 / 列表 / 详情 / 状态流转 ──


@pytest.mark.asyncio
async def test_b2b_delivery_persists_order(client: AsyncClient):
    """POST 应落库交付单并返回 delivery_order_id + status=draft"""
    token = await _register(client, "13900007005")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/api/b2b/delivery",
        json={"area": 100, "style": "nordic"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["delivery_order_id"]
    assert data["status"] == "draft"


@pytest.mark.asyncio
async def test_b2b_delivery_list_and_detail(client: AsyncClient):
    """GET 列表与详情应返回已落库的交付单"""
    token = await _register(client, "13900007006")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/api/b2b/delivery",
        json={"name": "订单化测试", "area": 110, "style": "modern"},
        headers=headers,
    )
    order_id = resp.json()["delivery_order_id"]

    # 列表
    resp = await client.get("/api/b2b/delivery", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    assert any(i["delivery_order_id"] == order_id for i in items)
    assert items[0]["status"] == "draft"

    # 详情
    resp = await client.get(f"/api/b2b/delivery/{order_id}", headers=headers)
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["delivery_order_id"] == order_id
    assert detail["area"] == 110
    assert detail["sources"]["budget"] == "estimated"


@pytest.mark.asyncio
async def test_b2b_delivery_order_user_isolation(client: AsyncClient):
    """交付单应强隔离：他人不可见（404）"""
    token_a = await _register(client, "13900007007")
    token_b = await _register(client, "13900007008")
    resp = await client.post(
        "/api/b2b/delivery",
        json={"area": 80, "style": "japanese"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    order_id = resp.json()["delivery_order_id"]

    resp = await client.get(
        f"/api/b2b/delivery/{order_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_b2b_delivery_status_transitions(client: AsyncClient):
    """状态流转：合法链路通过，非法流转 422"""
    token = await _register(client, "13900007009")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/api/b2b/delivery",
        json={"area": 100, "style": "modern"},
        headers=headers,
    )
    order_id = resp.json()["delivery_order_id"]

    # 合法：draft → quoted → accepted
    resp = await client.put(
        f"/api/b2b/delivery/{order_id}/status",
        json={"status": "quoted"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "quoted"

    resp = await client.put(
        f"/api/b2b/delivery/{order_id}/status",
        json={"status": "accepted"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"

    # 非法：accepted 不能直接 completed（须先 in_construction）
    resp = await client.put(
        f"/api/b2b/delivery/{order_id}/status",
        json={"status": "completed"},
        headers=headers,
    )
    assert resp.status_code == 422

    # 非法状态名
    resp = await client.put(
        f"/api/b2b/delivery/{order_id}/status",
        json={"status": "paid"},
        headers=headers,
    )
    assert resp.status_code == 422


# ── v1.4.x 待办落地：对接真实项目 / 真实 BOM 报价 / 异步生成 ──


async def _register_get_user_id(client: AsyncClient, db_session, phone: str) -> tuple[str, str]:
    """注册用户，返回 (token, user_id)"""
    from sqlalchemy import select
    from app.models.user import User
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "B2B待办", "password": "test123456"},
    )
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    row = (await db_session.execute(select(User).where(User.phone == phone))).scalar_one()
    return token, row.id


async def _register_get_user_id_short(client: AsyncClient, phone: str) -> tuple[str, str]:
    """注册用户并返回 (token, user_id) — 用独立短生命周期 session（不常驻连接）。

    异步后台任务需要独占测试库连接（SQLite StaticPool 单连接）；
    此辅助函数写入后立即关闭 session，避免与后台任务竞争同一连接。
    """
    from sqlalchemy import select
    from app.database import async_session
    from app.models.user import User
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "B2B待办", "password": "test123456"},
    )
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    async with async_session() as s:
        row = (await s.execute(select(User).where(User.phone == phone))).scalar_one()
        return token, row.id


async def _create_project(db_session, owner_id: str, name: str = "交付测试项目") -> str:
    from app.models.project import Project
    project = Project(name=name, owner_id=owner_id)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project.id


async def _create_budget(db_session, project_id: str, total: float, lines: list[tuple[str, str, float]]) -> None:
    """为项目写入真实预算（Budget + BudgetLine）"""
    from app.models.budget import Budget, BudgetLine
    budget = Budget(project_id=project_id, total_estimated=total)
    db_session.add(budget)
    await db_session.commit()
    await db_session.refresh(budget)
    for category, name, amount in lines:
        db_session.add(BudgetLine(
            budget_id=budget.id, category=category, name=name,
            estimated_amount=amount, unit="项", quantity=1.0, unit_price=amount,
        ))
    await db_session.commit()


@pytest.mark.asyncio
async def test_b2b_delivery_with_project_no_budget(client: AsyncClient, db_session):
    """关联项目但无真实预算 → 报价诚实降级为 estimated，project_id 落库"""
    token, user_id = await _register_get_user_id(client, db_session, "13900007101")
    project_id = await _create_project(db_session, user_id)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/b2b/delivery",
        json={"area": 100, "style": "modern", "project_id": project_id},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["sources"]["budget"] == "estimated"

    detail = await client.get(f"/api/b2b/delivery/{data['delivery_order_id']}", headers=headers)
    assert detail.json()["project_id"] == project_id


@pytest.mark.asyncio
async def test_b2b_delivery_with_project_real_budget(client: AsyncClient, db_session):
    """关联项目且已有真实 Budget → 报价 source=db，汇总与摘要匹配"""
    token, user_id = await _register_get_user_id(client, db_session, "13900007102")
    project_id = await _create_project(db_session, user_id)
    await _create_budget(db_session, project_id, 200000.0, [
        ("hard_decoration", "水电+墙面", 84000.0),
        ("custom_furniture", "定制柜体", 36000.0),
    ])
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/b2b/delivery",
        json={"area": 100, "style": "modern", "project_id": project_id},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["sources"]["budget"] == "db"
    assert data["budget_estimate"]["total_estimated"] == 200000.0
    assert data["budget_estimate"]["line_count"] == 2
    assert "真实预算" in data["summary"]


@pytest.mark.asyncio
async def test_b2b_delivery_project_not_owned(client: AsyncClient, db_session):
    """他人项目 → 403 无权访问"""
    token_a, user_a = await _register_get_user_id(client, db_session, "13900007103")
    token_b, _ = await _register_get_user_id(client, db_session, "13900007104")
    project_id = await _create_project(db_session, user_a)

    resp = await client.post(
        "/api/b2b/delivery",
        json={"area": 90, "style": "nordic", "project_id": project_id},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_b2b_delivery_project_not_exist(client: AsyncClient):
    """不存在的项目 → 404"""
    token = await _register(client, "13900007105")
    resp = await client.post(
        "/api/b2b/delivery",
        json={"area": 90, "style": "modern", "project_id": "nonexistent-project"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_b2b_delivery_async_mode(client: AsyncClient):
    """async_mode=True → 立即返回 generating，轮询详情至 draft 且整包完整

    注意：本测试不依赖 db_session fixture（SQLite StaticPool 单连接下，
    后台任务需要独占连接，fixture 常驻会与其竞争导致真实预算读取失败）。
    """
    import asyncio
    from app.database import async_session
    token, user_id = await _register_get_user_id_short(client, "13900007106")
    async with async_session() as s:
        project_id = await _create_project(s, user_id)
        await _create_budget(s, project_id, 200000.0, [("hard_decoration", "水电+墙面", 84000.0)])
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/b2b/delivery",
        json={"area": 100, "style": "modern", "project_id": project_id, "async_mode": True},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "generating"
    order_id = data["delivery_order_id"]

    # 轮询详情直至后台任务完成（generating → draft）
    detail = None
    for _ in range(20):
        await asyncio.sleep(0.2)
        resp = await client.get(f"/api/b2b/delivery/{order_id}", headers=headers)
        detail = resp.json()
        if detail["status"] != "generating":
            break
    assert detail["status"] == "draft"
    assert detail["sources"]["budget"] == "db"
    assert detail["construction_plan"]["total_days"] > 0
    assert detail["proposals"]


@pytest.mark.asyncio
async def test_b2b_delivery_generating_status_machine(client: AsyncClient, db_session):
    """generating 状态：只能流转 draft/cancelled，直接 quoted 应 422"""
    from app.models.delivery_order import DeliveryOrder
    token, user_id = await _register_get_user_id(client, db_session, "13900007107")
    headers = {"Authorization": f"Bearer {token}"}
    order = DeliveryOrder(user_id=user_id, name="生成中", area=100, style="modern", status="generating")
    db_session.add(order)
    await db_session.commit()
    await db_session.refresh(order)

    # generating → quoted 非法
    resp = await client.put(
        f"/api/b2b/delivery/{order.id}/status",
        json={"status": "quoted"},
        headers=headers,
    )
    assert resp.status_code == 422
    # generating → draft 合法
    resp = await client.put(
        f"/api/b2b/delivery/{order.id}/status",
        json={"status": "draft"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "draft"
