"""智能体全链路记忆 + 时间/空间感知闭环测试（2026-08-08 全景评估补测）

背景：全链路记忆此前仅在 /chat 与 /chat/stream 两个端点闭环；专用 Agent 端点
（/kitchen、/budget、/design 等）既不提取记忆（写侧断裂）也不注入时间/空间/
记忆上下文（读侧断裂）。本文件验证修复后的链路：

1. 写侧闭环：专用端点请求后偏好/城市记忆被提取入长期记忆（/agents/memory 可读）
2. 读侧闭环（由既有 test_agent_memory.py 覆盖服务层，此处验证端点不破坏行为）
3. 安全：专用端点 project_id 越权防护（对齐 /chat：他人项目 403 / 不存在 404）
4. 时间感知：运营简报 generated_at 使用北京时间（+08:00，业务时区一致）
"""

import pytest
from httpx import AsyncClient

from app.agents.orchestrator import OrchestratorAgent
from app.config import get_settings


async def _register(client: AsyncClient, phone: str) -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "链路测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201, f"注册失败: {resp.json()}"
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_kitchen_endpoint_extracts_preference(client: AsyncClient, auth_token: str):
    """写侧闭环：/kitchen 请求含偏好句式 → 偏好记忆被提取"""
    resp = await client.post(
        "/api/agents/kitchen",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"message": "我喜欢北欧风格，想要一个开放式的厨房"},
    )
    assert resp.status_code == 200

    mem_resp = await client.get(
        "/api/agents/memory",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert mem_resp.status_code == 200
    items = mem_resp.json()["items"]
    pref = [i for i in items if i["category"] == "preference" and "北欧" in i["value"]]
    assert pref, f"未提取到北欧偏好记忆: {items}"


@pytest.mark.asyncio
async def test_kitchen_endpoint_extracts_and_injects_memory(
    client: AsyncClient, auth_token: str, monkeypatch,
):
    """读侧+写侧闭环：/kitchen 第一轮表达偏好（写侧提取），
    第二轮注入的上下文含长期记忆块 + 时间感知块（读侧注入）。

    通过 spy 捕获 agent.think 收到的 context 断言注入内容；
    通过 GET /agents/memory 断言写侧持久化。
    """
    from app.agents.kitchen_agent import KitchenAgent

    captured: dict = {}

    async def _spy_think(self, user_message, context="", db=None, project_id="", user_id=""):
        captured["context"] = context
        return "[mock] kitchen 响应"

    monkeypatch.setattr(KitchenAgent, "think", _spy_think)
    headers = {"Authorization": f"Bearer {auth_token}"}

    # 第一轮：表达偏好 → 写侧提取入长期记忆
    resp1 = await client.post(
        "/api/agents/kitchen",
        headers=headers,
        json={"message": "我喜欢北欧风格，想要一个开放式的厨房"},
    )
    assert resp1.status_code == 200

    # 第二轮：触发读侧注入（应读取到第一轮提取的记忆）
    resp2 = await client.post(
        "/api/agents/kitchen",
        headers=headers,
        json={"message": "继续看看厨房布局"},
    )
    assert resp2.status_code == 200

    ctx = captured.get("context", "")
    assert "【用户长期记忆】" in ctx, f"未注入长期记忆块: {ctx!r}"
    assert "北欧" in ctx, f"未注入北欧偏好记忆: {ctx!r}"
    assert "当前时间" in ctx, f"未注入时间感知块: {ctx!r}"

    # 写侧持久化校验
    mem_resp = await client.get("/api/agents/memory", headers=headers)
    assert mem_resp.status_code == 200
    items = mem_resp.json()["items"]
    pref = [i for i in items if i["category"] == "preference" and "北欧" in i["value"]]
    assert pref, f"未提取到北欧偏好记忆: {items}"


@pytest.mark.asyncio
async def test_budget_endpoint_extracts_city(client: AsyncClient, auth_token: str):
    """写侧闭环：/budget 请求含城市 → location/city 记忆被提取"""
    resp = await client.post(
        "/api/agents/budget",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"message": "我在昆明，120平装修预算多少", "agent_type": "budget"},
    )
    assert resp.status_code == 200

    mem_resp = await client.get(
        "/api/agents/memory",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    items = mem_resp.json()["items"]
    loc = [i for i in items if i["category"] == "location" and i["key"] == "city"]
    assert loc and "昆明" in loc[0]["value"], f"未提取到昆明城市记忆: {items}"


@pytest.mark.asyncio
async def test_specialized_endpoint_unknown_project_404(client: AsyncClient, auth_token: str):
    """安全：project_id 不存在 → 404（对齐 /chat 行为）"""
    resp = await client.post(
        "/api/agents/kitchen",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"message": "帮我看下厨房方案", "project_id": "no-such-project"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_specialized_endpoint_rejects_other_users_project(client: AsyncClient, auth_token: str):
    """安全：他人项目 project_id → 403（防越权写 project scope 记忆）"""
    proj = await client.post(
        "/api/projects",
        json={"name": "链路越权项目", "total_area": 100.0},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    proj_id = proj.json()["id"]

    other_token = await _register(client, "13900770002")
    resp = await client.post(
        "/api/agents/kitchen",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"message": "帮我看下厨房方案", "project_id": proj_id},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_specialized_endpoint_own_project_passes(client: AsyncClient, auth_token: str):
    """本人项目 project_id 通过归属校验并正常返回"""
    proj = await client.post(
        "/api/projects",
        json={"name": "链路自有项目", "total_area": 100.0},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    proj_id = proj.json()["id"]
    resp = await client.post(
        "/api/agents/kitchen",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"message": "帮我看下厨房方案", "project_id": proj_id},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_daily_briefing_generated_at_beijing_tz(monkeypatch):
    """时间感知：daily briefing generated_at 为北京时间 +08:00"""
    _settings = get_settings()
    monkeypatch.setattr(_settings, "business_ops_orchestrator_enabled", True)

    orch = OrchestratorAgent()
    try:
        result = await orch.generate_daily_briefing(db=None)
        assert result["enabled"] is True
        assert result["generated_at"].endswith("+08:00"), result["generated_at"]
    finally:
        await orch.close()


@pytest.mark.asyncio
async def test_growth_report_generated_at_beijing_tz(monkeypatch, db_session):
    """时间感知：Growth 周报 generated_at 为北京时间 +08:00"""
    from app.agents import growth as growth_mod
    from app.agents.growth import GrowthAgent

    monkeypatch.setattr(growth_mod.settings, "growth_agent_enabled", True)
    agent = GrowthAgent()
    try:
        result = await agent.generate_weekly_report(db=db_session, days=7)
        assert result["generated_at"].endswith("+08:00"), result["generated_at"]
    finally:
        await agent.close()


@pytest.mark.asyncio
async def test_finance_report_generated_at_beijing_tz(monkeypatch, db_session):
    """时间感知：Finance 对账报告 generated_at 为北京时间 +08:00"""
    from app.agents import finance_recon as fin_mod
    from app.agents.finance_recon import FinanceReconAgent

    monkeypatch.setattr(fin_mod.settings, "finance_recon_agent_enabled", True)
    agent = FinanceReconAgent()
    try:
        result = await agent.generate_recon_report(db=db_session, days=30)
        assert result["generated_at"].endswith("+08:00"), result["generated_at"]
    finally:
        await agent.close()


# ── LBS 真实 POI 闭环（v1.9.x）──


@pytest.mark.asyncio
async def test_specialized_endpoint_injects_lbs_poi(
    client: AsyncClient, auth_token: str, monkeypatch,
):
    """LBS 闭环：/kitchen 带 GPS location → 周边真实 POI 注入 + 城市落库长期记忆。

    模拟真实高德 key（is_real_key=True + fake search_nearby_poi/regeo），
    断言：读侧注入城市 + 周边 POI 块；写侧城市记忆落库。
    """
    from app.agents.kitchen_agent import KitchenAgent
    from app.services import amap_service as amap

    monkeypatch.setattr(amap, "is_real_key", lambda: True)

    async def _fake_search(location="", keywords="", radius=3000, limit=10, types=""):
        return {"count": 1, "source": "real",
                "pois": [{"name": "昆明建材市场", "distance": "500"}]}

    async def _fake_regeo(location):
        return {"city": "昆明", "district": "五华区", "source": "real"}

    monkeypatch.setattr(amap, "search_nearby_poi", _fake_search)
    monkeypatch.setattr(amap, "regeo", _fake_regeo)

    captured: dict = {}

    async def _spy_think(self, user_message, context="", db=None, project_id="", user_id=""):
        captured["context"] = context
        return "[mock] kitchen 响应"

    monkeypatch.setattr(KitchenAgent, "think", _spy_think)
    headers = {"Authorization": f"Bearer {auth_token}"}

    resp = await client.post(
        "/api/agents/kitchen",
        headers=headers,
        json={"message": "附近哪里有建材市场", "location": "102.8332,24.8801"},
    )
    assert resp.status_code == 200

    ctx = captured.get("context", "")
    assert "用户所在城市：昆明" in ctx, f"未注入城市上下文: {ctx!r}"
    assert "【用户位置周边POI】" in ctx and "昆明建材市场" in ctx, f"未注入周边POI: {ctx!r}"

    # 写侧：逆地理编码城市落库长期记忆
    mem_resp = await client.get("/api/agents/memory", headers=headers)
    assert mem_resp.status_code == 200
    items = mem_resp.json()["items"]
    loc = [i for i in items if i["category"] == "location" and i["key"] == "city"]
    assert loc and "昆明" in loc[0]["value"], f"未落库昆明城市记忆: {items}"


@pytest.mark.asyncio
async def test_specialized_endpoint_location_validation(
    client: AsyncClient, auth_token: str,
):
    """SimpleAgentRequest.location 格式校验：非法格式/越界经纬度 → 422"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    for bad in ("not-a-coord", "200,100", "102.8332"):
        resp = await client.post(
            "/api/agents/kitchen", headers=headers,
            json={"message": "测试", "location": bad},
        )
        assert resp.status_code == 422, f"location={bad!r} 应返回 422: {resp.text}"


@pytest.mark.asyncio
async def test_lbs_no_key_honest_degrade(
    client: AsyncClient, monkeypatch,
):
    """诚实降级：无高德 key → 带 location 不注入 POI/城市、不落库城市记忆"""
    from app.agents.kitchen_agent import KitchenAgent
    from app.services import amap_service as amap

    monkeypatch.setattr(amap, "is_real_key", lambda: False)
    token = await _register(client, "13900771234")  # 独立用户，环境干净

    captured: dict = {}

    async def _spy_think(self, user_message, context="", db=None, project_id="", user_id=""):
        captured["context"] = context
        return "[mock] kitchen 响应"

    monkeypatch.setattr(KitchenAgent, "think", _spy_think)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/agents/kitchen",
        headers=headers,
        json={"message": "附近哪里有建材市场", "location": "102.8332,24.8801"},
    )
    assert resp.status_code == 200

    ctx = captured.get("context", "")
    assert "周边POI" not in ctx, f"无 key 不应注入 POI: {ctx!r}"
    assert "用户所在城市" not in ctx, f"无 key 不应注入城市: {ctx!r}"

    mem_resp = await client.get("/api/agents/memory", headers=headers)
    items = mem_resp.json()["items"]
    # 只断言 GPS 逆地理编码（source=lbs_geo）未落库；文本提取器（source=chat）
    # 对「附近哪里」句式的位置类提取属另一机制，与本用例无关
    loc = [i for i in items if i["category"] == "location" and i["source"] == "lbs_geo"]
    assert not loc, f"无 key 不应落库 lbs_geo 城市记忆: {items}"


# ════════════════════════════════════════════════════════════════
# v1.13.2 全链路验证：带 project_id 的 mock 请求（2026-08-12）
# 验证新加的「Case 沉淀（写侧）+ 自进化注入（读侧）」在项目空间维度真实生效：
#   ① 读侧：_inject_evolution_context 按 project scope 命中预置 Case+Skill 并注入
#   ② 写侧：think 内建 hook（_maybe_persist_execution_case）沉淀 project scope 新 Case
#   ③ 日志：evolution.inject.* / evolution.persist.*（--log-cli-level=INFO 可见）
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_project_scope_case_persist_and_inject_chain(
    client: AsyncClient, db_session, monkeypatch,
):
    """带 project_id 的 mock 请求 → Case 沉淀 + 注入（项目空间维度）双闭环"""
    import json
    import uuid
    from unittest.mock import patch

    from sqlalchemy import select

    from app.models.agent_case import AgentCase
    from app.models.agent_skill import AgentSkill, STATUS_ACTIVE
    from app.models.project import Project
    from app.models.user import User

    # 屏蔽无关链路，聚焦 Case 沉淀 + 注入
    monkeypatch.setattr(get_settings(), "agent_case_extraction_enabled", True)
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", True)
    monkeypatch.setattr(get_settings(), "agentic_rag_enabled", False)
    monkeypatch.setattr(get_settings(), "model_spec_enabled", False)
    monkeypatch.setattr(get_settings(), "agent_learning_enabled", False)

    # 注册独立用户（唯一手机号，避免并发污染）并创建归属项目
    phone = f"137{str(uuid.uuid4().int)[:8]}"
    token = await _register(client, phone)
    user = (await db_session.execute(
        select(User).where(User.phone == phone)
    )).scalars().first()
    assert user is not None
    project = Project(name="记忆验证项目", owner_id=user.id, project_type="full_renovation")
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    project_id = project.id

    # 预置 project scope 的 Case + Skill（读侧注入的检索目标）
    seed_case = AgentCase(
        id="seed_case_p", scope="project", owner_id=project_id, agent_name="kitchen",
        task_intent="帮我设计厨房布局方案", approach="[]",
        outcome="success", quality_score=0.9, created_by=user.id,
    )
    seed_skill = AgentSkill(
        id="seed_skill_p", name="厨房动线技能", owner_scope="project", owner_id=project_id,
        agent_name="kitchen", system_prompt="优先推荐 U 型厨房布局", status=STATUS_ACTIVE,
        created_by=user.id, utility_score=0.9,
    )
    db_session.add_all([seed_case, seed_skill])
    await db_session.commit()

    # _chat spy：捕获注入到 messages 的上下文 + 返回合法 Case JSON 供写侧提取
    captured_msgs: list[dict] = []

    async def fake_chat(self, messages, **kwargs):
        captured_msgs.extend(messages)
        return json.dumps({
            "task_intent": "设计厨房布局方案",
            "approach": [{"step": 1, "attempted": "输出布局", "tool": "", "result": "OK", "revised": False}],
            "outcome": "success",
            "quality_score": 0.85,
        })

    headers = {"Authorization": f"Bearer {token}"}
    with patch("app.agents.base.BaseAgent._chat", fake_chat):
        resp = await client.post(
            "/api/agents/kitchen",
            headers=headers,
            json={"message": "帮我设计厨房布局方案", "project_id": project_id},
        )
    assert resp.status_code == 200, resp.text

    # ── ① 读侧验证：注入块含 project scope 的 [历史经验 Case + [进化 Skill ──
    joined = "\n".join(
        m.get("content", "") for m in captured_msgs if m.get("role") == "system"
    )
    assert "[历史经验 Case" in joined, f"未注入 Case 上下文: {joined!r}"
    assert "帮我设计厨房布局方案" in joined, f"注入的 Case 非 project scope 命中: {joined!r}"
    assert "[进化 Skill: 厨房动线技能]" in joined, f"未注入 Skill: {joined!r}"

    # ── ② 写侧验证：think 内建 hook 沉淀了 project scope 新 Case ──
    rows = (await db_session.execute(select(AgentCase))).scalars().all()
    new_cases = [c for c in rows if c.id != "seed_case_p"]
    assert len(new_cases) == 1, f"应沉淀 1 条新 Case，实际 {len(new_cases)}"
    assert new_cases[0].scope == "project", f"新 Case scope 应为 project: {new_cases[0].scope}"
    assert new_cases[0].owner_id == project_id, \
        f"新 Case owner_id 应为 project_id: {new_cases[0].owner_id}"
    assert new_cases[0].task_intent == "设计厨房布局方案"
