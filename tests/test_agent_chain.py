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


# ════════════════════════════════════════════════════════════════
# v1.13.3 全链路闭环补齐（2026-08-12）
# 断点 A–I 修复验证：think_stream 签名+注入+沉淀 / 三处透传（classify_intent、
# concierge、content_publish）/ Skill outcome 回写 / IM harness 透传 /
# 语音路由透传 / _llm_decompose 注入 / preference hint helper
# ════════════════════════════════════════════════════════════════


async def _seed_project_scope_case_skill(db_session, user_id: str, project_id: str):
    """预置 project scope 的 Case + Skill（读侧注入检索目标），返回 skill_id"""
    from app.models.agent_case import AgentCase
    from app.models.agent_skill import AgentSkill, STATUS_ACTIVE
    import uuid

    case_id = f"v1133_case_{uuid.uuid4().hex[:8]}"
    skill_id = f"v1133_skill_{uuid.uuid4().hex[:8]}"
    db_session.add_all([
        AgentCase(
            id=case_id, scope="project", owner_id=project_id, agent_name="kitchen",
            task_intent="帮我设计厨房布局方案", approach="[]",
            outcome="success", quality_score=0.9, created_by=user_id,
        ),
        AgentSkill(
            id=skill_id, name="厨房动线技能v1133", owner_scope="project", owner_id=project_id,
            agent_name="kitchen", system_prompt="优先推荐 U 型厨房布局", status=STATUS_ACTIVE,
            created_by=user_id, utility_score=0.9,
        ),
    ])
    await db_session.commit()
    return skill_id


@pytest.mark.asyncio
async def test_stream_think_injects_and_persists(client, db_session, monkeypatch):
    """断点 D：think_stream 补签名后，流式路径读侧注入 Case+Skill、
    写侧沉淀 project scope 新 Case（与 think 对齐的全链路闭环）。"""
    import json
    import uuid
    from unittest.mock import patch

    from sqlalchemy import select

    from app.agents.base import BaseAgent
    from app.agents.kitchen_agent import KitchenAgent
    from app.models.agent_case import AgentCase
    from app.models.project import Project
    from app.models.user import User

    monkeypatch.setattr(get_settings(), "agent_case_extraction_enabled", True)
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", True)
    monkeypatch.setattr(get_settings(), "agentic_rag_enabled", False)
    monkeypatch.setattr(get_settings(), "model_spec_enabled", False)
    monkeypatch.setattr(get_settings(), "agent_learning_enabled", False)

    phone = f"136{str(uuid.uuid4().int)[:8]}"
    await _register(client, phone)
    user = (await db_session.execute(
        select(User).where(User.phone == phone)
    )).scalars().first()
    project = Project(name="流式记忆验证项目", owner_id=user.id, project_type="full_renovation")
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    project_id = project.id
    await _seed_project_scope_case_skill(db_session, user.id, project_id)

    captured_msgs: list[dict] = []

    async def fake_chat_stream(self, messages):
        captured_msgs.extend(messages)
        yield "这是第一段"
        yield "流式回复"

    async def fake_chat(self, messages, **kwargs):
        return json.dumps({
            "task_intent": "设计厨房布局方案",
            "approach": [{"step": 1, "attempted": "输出布局", "tool": "", "result": "OK", "revised": False}],
            "outcome": "success",
            "quality_score": 0.85,
        })

    agent = KitchenAgent()
    try:
        with patch.object(BaseAgent, "_chat_stream", fake_chat_stream), \
                patch.object(BaseAgent, "_chat", fake_chat):
            chunks: list[str] = []
            async for c in agent.think_stream(
                "帮我设计厨房布局方案", db=db_session,
                user_id=str(user.id), project_id=project_id,
            ):
                chunks.append(c)
    finally:
        await agent.close()

    assert "".join(chunks) == "这是第一段流式回复"

    # 读侧：注入 project scope Case + Skill
    joined = "\n".join(
        m.get("content", "") for m in captured_msgs if m.get("role") == "system"
    )
    assert "[历史经验 Case" in joined, f"流式未注入 Case: {joined!r}"
    assert "[进化 Skill: 厨房动线技能v1133]" in joined, f"流式未注入 Skill: {joined!r}"

    # 写侧：沉淀 project scope 新 Case
    rows = (await db_session.execute(select(AgentCase))).scalars().all()
    new_cases = [c for c in rows if not c.id.startswith("v1133_case_")]
    assert len(new_cases) == 1, f"流式应沉淀 1 条新 Case，实际 {len(new_cases)}"
    assert new_cases[0].scope == "project"
    assert new_cases[0].owner_id == project_id


@pytest.mark.asyncio
async def test_think_stream_records_skill_outcome(client, db_session, monkeypatch):
    """反馈闭环：think_stream 注入 Skill 且回复正常 → success_count +1（P1 数据层激活）"""
    import uuid
    from sqlalchemy import select

    from app.agents.kitchen_agent import KitchenAgent
    from app.models.agent_skill import AgentSkill
    from app.models.project import Project
    from app.models.user import User

    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", True)
    monkeypatch.setattr(get_settings(), "agent_case_extraction_enabled", False)
    monkeypatch.setattr(get_settings(), "agentic_rag_enabled", False)
    monkeypatch.setattr(get_settings(), "agent_learning_enabled", False)

    phone = f"135{str(uuid.uuid4().int)[:8]}"
    await _register(client, phone)
    user = (await db_session.execute(
        select(User).where(User.phone == phone)
    )).scalars().first()
    project = Project(name="skill 回写项目", owner_id=user.id, project_type="full_renovation")
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    skill_id = await _seed_project_scope_case_skill(db_session, user.id, project.id)

    agent = KitchenAgent()
    try:
        await agent._inject_evolution_context(
            [], "帮我设计厨房布局方案", str(user.id), db_session, project.id,
        )
        assert agent._injected_skill_id == skill_id, "注入未记录 skill_id"
        await agent._maybe_record_skill_outcome("这是正常回复", db_session)
    finally:
        await agent.close()

    skill = (await db_session.execute(
        select(AgentSkill).where(AgentSkill.id == skill_id)
    )).scalars().first()
    assert skill.success_count == 1, f"success_count 应为 1: {skill.success_count}"
    assert skill.fail_count == 0


@pytest.mark.asyncio
async def test_skill_outcome_records_fail_on_mock_reply(client, db_session, monkeypatch):
    """反馈闭环（v1.13.5）：注入 Skill 后 mock/降级回复计失败，激活失败数据层；
    空 reply（异常路径）跳过不计数，防污染。"""
    import uuid
    from sqlalchemy import select

    from app.agents.kitchen_agent import KitchenAgent
    from app.models.agent_skill import AgentSkill
    from app.models.project import Project
    from app.models.user import User

    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", True)
    monkeypatch.setattr(get_settings(), "agent_case_extraction_enabled", False)
    monkeypatch.setattr(get_settings(), "agentic_rag_enabled", False)

    phone = f"134{str(uuid.uuid4().int)[:8]}"
    await _register(client, phone)
    user = (await db_session.execute(
        select(User).where(User.phone == phone)
    )).scalars().first()
    project = Project(name="skill mock 项目", owner_id=user.id, project_type="full_renovation")
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    skill_id = await _seed_project_scope_case_skill(db_session, user.id, project.id)

    agent = KitchenAgent()
    try:
        await agent._inject_evolution_context(
            [], "帮我设计厨房布局方案", str(user.id), db_session, project.id,
        )
        await agent._maybe_record_skill_outcome("[mock] kitchen 流式响应：API key 未配置", db_session)
        await agent._maybe_record_skill_outcome("", db_session)
        await agent._maybe_record_skill_outcome("Agent 暂时无法响应（服务降级）", db_session)
    finally:
        await agent.close()

    skill = (await db_session.execute(
        select(AgentSkill).where(AgentSkill.id == skill_id)
    )).scalars().first()
    assert skill.success_count == 0, f"mock 不应计成功: {skill.success_count}"
    # mock + 降级占位各记 1 次失败；空 reply（异常路径）跳过
    assert skill.fail_count == 2, f"mock/降级应各记失败: {skill.fail_count}"


@pytest.mark.asyncio
async def test_inject_evolution_context_respects_budget(client, db_session, monkeypatch):
    """Context Engineering（v1.13.5）：注入预算——Skill 蒸馏知识全量优先、
    Case 用剩余预算裁剪（防 context rot），总注入不超过预算"""
    import uuid
    from sqlalchemy import select

    from app.agents.kitchen_agent import KitchenAgent
    from app.models.project import Project
    from app.models.user import User

    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", True)
    monkeypatch.setattr(get_settings(), "agent_case_extraction_enabled", False)
    monkeypatch.setattr(get_settings(), "agentic_rag_enabled", False)

    phone = f"132{str(uuid.uuid4().int)[:8]}"
    await _register(client, phone)
    user = (await db_session.execute(
        select(User).where(User.phone == phone)
    )).scalars().first()
    project = Project(name="预算裁剪项目", owner_id=user.id, project_type="full_renovation")
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    await _seed_project_scope_case_skill(db_session, user.id, project.id)

    skill_block = "[进化 Skill: 厨房动线技能v1133]\n优先推荐 U 型厨房布局"

    # 场景①：预算充足 → Case 全量注入，总长 ≤ 预算
    monkeypatch.setattr(get_settings(), "context_injection_budget_chars", 500)
    agent = KitchenAgent()
    try:
        messages: list[dict] = []
        await agent._inject_evolution_context(
            messages, "帮我设计厨房布局方案", str(user.id), db_session, project.id,
        )
    finally:
        await agent.close()
    injected = "\n".join(m.get("content", "") for m in messages)
    assert "进化 Skill" in injected
    assert "历史经验 Case" in injected
    assert len(injected) <= 500, f"注入超预算: {len(injected)}"

    # 场景②：预算只够 Skill（蒸馏知识高密度全量优先）→ Case 被预算裁剪
    monkeypatch.setattr(get_settings(), "context_injection_budget_chars", len(skill_block) + 5)
    agent2 = KitchenAgent()
    try:
        messages2: list[dict] = []
        await agent2._inject_evolution_context(
            messages2, "帮我设计厨房布局方案", str(user.id), db_session, project.id,
        )
    finally:
        await agent2.close()
    injected2 = "\n".join(m.get("content", "") for m in messages2)
    assert "进化 Skill" in injected2, "Skill 蒸馏知识应全量优先注入"
    assert "历史经验 Case" not in injected2, "Case 应被预算裁剪（剩余预算放不下头部）"
    assert len(injected2) <= len(skill_block) + 5


@pytest.mark.asyncio
async def test_classify_intent_passes_context(db_session, monkeypatch):
    """断点 A：classify_intent 透传 db/user_id/project_id 给 think"""
    from app.agents.orchestrator import OrchestratorAgent

    captured: dict = {}

    async def _spy_think(self, message, context="", db=None, project_id="", user_id=""):
        captured["db"] = db
        captured["project_id"] = project_id
        captured["user_id"] = user_id
        return '{"intent": "general"}'

    monkeypatch.setattr(OrchestratorAgent, "think", _spy_think)
    agent = OrchestratorAgent()
    try:
        result = await agent.classify_intent(
            "测试消息", db=db_session, user_id="u1", project_id="p1",
        )
    finally:
        await agent.close()
    assert result["intent"] == "general"
    assert captured["db"] is db_session
    assert captured["user_id"] == "u1"
    assert captured["project_id"] == "p1"


@pytest.mark.asyncio
async def test_concierge_generate_response_passes_context(db_session, monkeypatch):
    """断点 C：concierge.generate_response 透传 db/user_id/project_id 给 think"""
    from app.agents.concierge import ConciergeAgent

    captured: dict = {}

    async def _spy_think(self, user_message, context="", db=None, project_id="", user_id=""):
        captured["db"] = db
        captured["project_id"] = project_id
        captured["user_id"] = user_id
        return "客服回复"

    monkeypatch.setattr(ConciergeAgent, "think", _spy_think)
    agent = ConciergeAgent()
    try:
        reply = await agent.generate_response(
            "咨询", "上下文", db=db_session, user_id="u1", project_id="p1",
        )
    finally:
        await agent.close()
    assert reply == "客服回复"
    assert captured["db"] is db_session
    assert captured["user_id"] == "u1"
    assert captured["project_id"] == "p1"


@pytest.mark.asyncio
async def test_content_publish_passes_context(db_session, monkeypatch):
    """断点 B：generate_content_publish_reply 透传 db/user_id/project_id 给 think"""
    from app.agents.content_publisher import ContentPublisherAgent

    captured: dict = {}

    async def _spy_think(self, prompt, context="", db=None, project_id="", user_id=""):
        captured["db"] = db
        captured["project_id"] = project_id
        captured["user_id"] = user_id
        return "发布引导"

    monkeypatch.setattr(ContentPublisherAgent, "think", _spy_think)
    agent = ContentPublisherAgent()
    try:
        reply = await agent.generate_content_publish_reply(
            "我要发布瓷砖", "张三", db=db_session, user_id="u1", project_id="p1",
        )
    finally:
        await agent.close()
    assert reply == "发布引导"
    assert captured["db"] is db_session
    assert captured["user_id"] == "u1"
    assert captured["project_id"] == "p1"


@pytest.mark.asyncio
async def test_im_auto_reply_passes_context(monkeypatch):
    """断点 F：IM 群聊 harness.run 透传 db/user_id/project_id"""
    from app.services import chat_service

    class _DummyAgent:
        agent_name = "designer"

        async def close(self):
            pass

    captured: dict = {}

    class _FakeHarness:
        async def run(self, agent, msg, **kwargs):
            captured.update(kwargs)
            return {"reply": "ok"}

    monkeypatch.setattr(chat_service, "_resolve_agent_class", lambda name: _DummyAgent)
    monkeypatch.setattr(
        "app.agents.harness.get_harness", lambda: _FakeHarness(),
    )
    content, annotations = await chat_service._call_agent_auto_reply(
        "designer", "hello", db="db-x", user_id="u1", project_id="p1",
    )
    assert content == "ok"
    assert captured == {"db": "db-x", "user_id": "u1", "project_id": "p1"}


@pytest.mark.asyncio
async def test_voice_route_passes_context(monkeypatch):
    """断点 E：语音路由 _route_voice_to_agent 透传 db/user_id/project_id 给 think"""
    from app.api import voice_realtime
    from app.agents.designer import DesignerAgent

    monkeypatch.setattr(get_settings(), "deepseek_api_key", "fake-key")
    monkeypatch.setattr(get_settings(), "glm_api_key", "fake-key")

    captured: dict = {}

    async def _spy_think(self, user_message, context="", db=None, project_id="", user_id=""):
        captured["db"] = db
        captured["project_id"] = project_id
        captured["user_id"] = user_id
        return '{"reply": "语音设计回复"}'

    monkeypatch.setattr(DesignerAgent, "think", _spy_think)
    reply = await voice_realtime._route_voice_to_agent(
        "帮我设计客厅", "design", "张三", db="db-x", user_id="u1", project_id="p1",
    )
    assert reply == "语音设计回复"
    assert captured["db"] == "db-x"
    assert captured["user_id"] == "u1"
    assert captured["project_id"] == "p1"


@pytest.mark.asyncio
async def test_llm_decompose_injects_evolution(monkeypatch):
    """断点 I：_llm_decompose 调用 _inject_evolution_context（db/user_id/project_id）"""
    from app.agents.orchestrator import OrchestratorAgent
    from app.services import agent_orchestration_service as orch_svc

    calls: list[tuple] = []

    async def _spy_inject(self, messages, user_message, user_id, db, project_id=""):
        calls.append((user_message, user_id, project_id))

    async def _spy_chat(self, messages, **kwargs):
        return '{"tasks": [{"agent": "designer", "task": "设计客厅方案", "depends_on": []}]}'

    monkeypatch.setattr(OrchestratorAgent, "_inject_evolution_context", _spy_inject)
    monkeypatch.setattr(OrchestratorAgent, "_chat", _spy_chat)
    tasks = await orch_svc._llm_decompose(
        "帮我装修客厅", db="db-x", user_id="u1", project_id="p1",
    )
    assert tasks and len(tasks) == 1
    assert tasks[0].agent_name == "designer"
    assert calls and calls[0] == ("帮我装修客厅", "u1", "p1"), f"注入未透传: {calls}"


@pytest.mark.asyncio
async def test_inject_preference_hint_helper(client, auth_token, db_session, monkeypatch):
    """/chat 与 /chat/stream 共用 helper：注入 like 正向示例 + 保留原上下文"""
    from sqlalchemy import select

    from app.api import agents as agents_api
    from app.models.agent_feedback import AgentFeedback
    from app.models.user import User

    monkeypatch.setattr(get_settings(), "agent_learning_enabled", True)
    user = (await db_session.execute(
        select(User).order_by(User.created_at.desc()).limit(1)
    )).scalars().first()
    db_session.add(AgentFeedback(
        user_id=user.id, agent_name="kitchen", message_hash="h1",
        feedback_type="like", user_message="我喜欢简洁的回复",
        agent_reply="简洁回复示例",
    ))
    await db_session.commit()

    ctx = await agents_api._inject_preference_hint(
        db_session, user.id, "kitchen", "base_ctx",
    )
    assert "base_ctx" in ctx, f"原上下文被覆盖: {ctx!r}"
    assert "过往满意的回复示例" in ctx, f"未注入偏好示例: {ctx!r}"
    assert "我喜欢简洁的回复" in ctx, f"未注入 like 示例内容: {ctx!r}"


@pytest.mark.asyncio
async def test_chat_stream_endpoint_mock_regression(client, auth_token, monkeypatch):
    """断点 D 端点回归：/chat/stream 真流式路径（think_stream 新签名）mock 模式不崩溃"""
    # mock 模式：无 API key（强制置空，避免 .env 真实 key 走真 LLM）
    monkeypatch.setattr(get_settings(), "deepseek_api_key", "")
    monkeypatch.setattr(get_settings(), "glm_api_key", "")
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", False)
    monkeypatch.setattr(get_settings(), "agent_case_extraction_enabled", False)

    resp = await client.post(
        "/api/agents/chat/stream",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"message": "帮我看看厨房方案", "agent_type": "kitchen"},
    )
    assert resp.status_code == 200, resp.text
    assert "[mock]" in resp.text, f"mock 流式内容缺失: {resp.text[:200]}"


# ════════════════════════════════════════════════════════════════
# v1.13.5 核心功能打磨：Model Spec HC 约束前置声明
# （输出前注入适用于本 Agent 的硬约束 → 减少事后反驳重生成成本）
# ════════════════════════════════════════════════════════════════


def _capture_messages(fake_chat_cases: list[dict]):
    async def fake_chat(self, messages, **kwargs):
        fake_chat_cases.extend(messages)
        return "OK"
    return fake_chat


@pytest.mark.asyncio
async def test_think_injects_model_spec_constraints(monkeypatch):
    """think 注入适用于 KitchenAgent 的 HC 约束声明（HC-007 燃气安全适用 kitchen）"""
    from unittest.mock import patch

    from app.agents.base import BaseAgent
    from app.agents.kitchen_agent import KitchenAgent

    monkeypatch.setattr(get_settings(), "model_spec_enabled", True)
    monkeypatch.setattr(get_settings(), "agentic_rag_enabled", False)
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", False)
    monkeypatch.setattr(get_settings(), "agent_case_extraction_enabled", False)

    captured: list[dict] = []
    agent = KitchenAgent()
    try:
        with patch.object(BaseAgent, "_chat", _capture_messages(captured)):
            await agent.think("帮我设计厨房", db=None)
    finally:
        await agent.close()

    joined = "\n".join(
        m.get("content", "") for m in captured if m.get("role") == "system"
    )
    assert "【Model Spec 硬约束" in joined, f"未注入 HC 约束声明: {joined!r}"
    assert "HC-007" in joined, f"kitchen 应含 HC-007 燃气安全约束: {joined!r}"


@pytest.mark.asyncio
async def test_model_spec_constraint_disabled(monkeypatch):
    """model_spec_enabled=False 时不注入约束声明（诚实降级）"""
    from unittest.mock import patch

    from app.agents.base import BaseAgent
    from app.agents.kitchen_agent import KitchenAgent

    monkeypatch.setattr(get_settings(), "model_spec_enabled", False)
    monkeypatch.setattr(get_settings(), "agentic_rag_enabled", False)
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", False)

    captured: list[dict] = []
    agent = KitchenAgent()
    try:
        with patch.object(BaseAgent, "_chat", _capture_messages(captured)):
            await agent.think("帮我设计厨房", db=None)
    finally:
        await agent.close()

    joined = "\n".join(m.get("content", "") for m in captured if m.get("role") == "system")
    assert "【Model Spec 硬约束" not in joined


@pytest.mark.asyncio
async def test_door_window_alias_gets_hc008(monkeypatch):
    """别名映射：door_window agent_name → spec applies_to door_window_waterproof（HC-008 防水）"""
    from unittest.mock import patch

    from app.agents.base import BaseAgent
    from app.agents.door_window_agent import DoorWindowAgent

    monkeypatch.setattr(get_settings(), "model_spec_enabled", True)
    monkeypatch.setattr(get_settings(), "agentic_rag_enabled", False)
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", False)

    captured: list[dict] = []
    agent = DoorWindowAgent()
    try:
        with patch.object(BaseAgent, "_chat", _capture_messages(captured)):
            await agent.think("门窗防水怎么做", db=None)
    finally:
        await agent.close()

    joined = "\n".join(m.get("content", "") for m in captured if m.get("role") == "system")
    assert "HC-008" in joined, f"door_window 应经别名注入 HC-008 防水约束: {joined!r}"


@pytest.mark.asyncio
async def test_no_constraints_for_agent_without_spec(monkeypatch):
    """spec 未覆盖的 Agent（concierge）不注入约束声明（无适用约束）"""
    from unittest.mock import patch

    from app.agents.base import BaseAgent
    from app.agents.concierge import ConciergeAgent

    monkeypatch.setattr(get_settings(), "model_spec_enabled", True)
    monkeypatch.setattr(get_settings(), "agentic_rag_enabled", False)
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", False)

    captured: list[dict] = []
    agent = ConciergeAgent()
    try:
        with patch.object(BaseAgent, "_chat", _capture_messages(captured)):
            await agent.think("咨询问题", db=None)
    finally:
        await agent.close()

    joined = "\n".join(m.get("content", "") for m in captured if m.get("role") == "system")
    assert "【Model Spec 硬约束" not in joined


# ════════════════════════════════════════════════════════════════
# v1.13.x 交付体验：persona 人格锚注入（对齐游戏 AI NPC「人格一致」）
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_think_injects_persona(monkeypatch):
    """ConciergeAgent 注入 persona 人格锚（身份 + 服务承诺 + 沟通风格）"""
    from unittest.mock import patch

    from app.agents.base import BaseAgent
    from app.agents.concierge import ConciergeAgent

    monkeypatch.setattr(get_settings(), "model_spec_enabled", False)
    monkeypatch.setattr(get_settings(), "agentic_rag_enabled", False)
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", False)

    captured: list[dict] = []
    agent = ConciergeAgent()
    try:
        with patch.object(BaseAgent, "_chat", _capture_messages(captured)):
            await agent.think("你好", db=None)
    finally:
        await agent.close()

    joined = "\n".join(
        m.get("content", "") for m in captured if m.get("role") == "system"
    )
    assert "【人格锚】" in joined, f"未注入 persona 人格锚: {joined!r}"
    assert "小索" in joined, f"concierge 应注入「小索」身份锚: {joined!r}"


@pytest.mark.asyncio
async def test_persona_noop_for_agent_without_persona(monkeypatch):
    """无 persona 定义的 Agent（KitchenAgent）不注入人格锚（no-op 诚实降级）"""
    from unittest.mock import patch

    from app.agents.base import BaseAgent
    from app.agents.kitchen_agent import KitchenAgent

    monkeypatch.setattr(get_settings(), "model_spec_enabled", False)
    monkeypatch.setattr(get_settings(), "agentic_rag_enabled", False)
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", False)

    captured: list[dict] = []
    agent = KitchenAgent()
    try:
        with patch.object(BaseAgent, "_chat", _capture_messages(captured)):
            await agent.think("帮我设计厨房", db=None)
    finally:
        await agent.close()

    joined = "\n".join(
        m.get("content", "") for m in captured if m.get("role") == "system"
    )
    assert "【人格锚】" not in joined
