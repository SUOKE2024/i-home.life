"""Agent Case 自进化管线测试（v1.10.2 借鉴 EverMind EverOS Agent Memory + SkillCorpus + HarnessBank）

覆盖：
- Case 提取：_is_goal_directed 过滤 / _compress_trajectory 压缩 / extract_case_from_trace（flag 门控 + mock LLM）
- Case 检索：search_cases scope 隔离 / build_case_context 格式化
- Skill 蒸馏：distill_skill_from_cases 阈值 + 合并相似（mock LLM）
- Skill 进化：record_skill_outcome 计数 / evaluate_skill_quality 三维质控 + auto-archive/activate
- 诊断归因：diagnose_credit_skill_patch 配对显著性检验（z≥1.96）
- JSON 解析：_parse_case_json / _parse_skill_json 边界
- Harness 集成：_maybe_extract_case flag 关闭 → no-op
- BaseAgent 注入：flag 关闭 → 无注入无报错

测试隔离：monkeypatch.setattr(get_settings(), "flag", value)，teardown 自动还原
（禁止 get_settings.cache_clear()——v1.1.29 教训：致跨文件测试隔离失败）
"""
import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.config import get_settings
from app.models.agent_case import AgentCase
from app.models.agent_skill import AgentSkill, STATUS_DRAFT, STATUS_ACTIVE, STATUS_ARCHIVED
from app.services.agent_case_service import (
    _is_goal_directed, _compress_trajectory, extract_case_from_trace,
    search_cases, build_case_context, _parse_case_json, TOKEN_ESTIMATE_DIVISOR,
)
from app.services.agent_skill_evolution_service import (
    record_skill_outcome, evaluate_skill_quality, diagnose_credit_skill_patch,
    distill_skill_from_cases, get_skill_for_injection, _parse_skill_json,
    _find_similar_skill,
)


# ── 辅助 ──


async def _register(client: AsyncClient, phone: str = "13900008001") -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "Case测试", "password": "test123456"},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


def _make_trace_dict(
    user_message: str = "帮我设计一个北欧风格的客厅方案，预算5万",
    response: str = "好的，根据您的需求，我推荐以下方案...",
    agent_name: str = "designer",
) -> dict:
    return {
        "trace_id": "test_trace_001",
        "agent_name": agent_name,
        "user_message": user_message,
        "user_message_truncated": user_message[:200],
        "response": response,
        "response_truncated": response[:200],
        "tool_calls": [{"name": "get_material_list"}, {"name": "calculate_budget"}],
        "status": "success",
    }


# ── _is_goal_directed ──


def test_is_goal_directed_filters_chitchat():
    """闲聊/简单 Q&A 不入 Case"""
    assert not _is_goal_directed("你好")
    assert not _is_goal_directed("hi")
    assert not _is_goal_directed("谢谢")
    assert not _is_goal_directed("你好世界")  # <8 字符
    assert not _is_goal_directed("")


def test_is_goal_directed_keeps_tasks():
    """目标导向对话入 Case"""
    assert _is_goal_directed("帮我设计一个北欧风格的客厅方案")
    assert _is_goal_directed("计算一下120平米房子的装修预算")
    assert _is_goal_directed("我想采购一批瓷砖，请推荐供应商")


# ── _compress_trajectory ──


def test_compress_trajectory_preserves_key_parts():
    trace = _make_trace_dict()
    compressed = _compress_trajectory(trace)
    assert "帮我设计" in compressed
    assert "get_material_list" in compressed
    assert "好的，根据" in compressed


def test_compress_trajectory_truncates_long():
    trace = _make_trace_dict(
        user_message="x" * 1000,
        response="y" * 2000,
    )
    compressed = _compress_trajectory(trace)
    assert len(compressed) <= 2100  # 阈值 + 截断标记


def test_compress_trajectory_empty_dict():
    """空 dict 安全降级为空字符串"""
    assert _compress_trajectory({}) == ""


def test_compress_trajectory_tool_calls_not_list():
    """tool_calls 非列表时安全降级（不抛异常）"""
    # 字符串类型（不应崩溃）
    result = _compress_trajectory({"user_message": "test", "tool_calls": "not a list"})
    assert isinstance(result, str)
    # 非字典元素列表（不应崩溃）
    result2 = _compress_trajectory({"user_message": "test", "tool_calls": [1, 2, 3]})
    assert isinstance(result2, str)


# ── extract_case_from_trace ──


@pytest.mark.asyncio
async def test_extract_case_flag_off_returns_none(db_session, monkeypatch):
    """flag 关闭时返回 None（诚实降级）"""
    monkeypatch.setattr(get_settings(), "agent_case_extraction_enabled", False)
    trace = _make_trace_dict()
    result = await extract_case_from_trace(
        trace, db_session, owner_id="user_1", created_by="user_1",
    )
    assert result is None


@pytest.mark.asyncio
async def test_extract_case_filters_non_goal_directed(db_session, monkeypatch):
    """非目标导向对话被过滤"""
    monkeypatch.setattr(get_settings(), "agent_case_extraction_enabled", True)
    trace = _make_trace_dict(user_message="你好")
    result = await extract_case_from_trace(
        trace, db_session, owner_id="user_1", created_by="user_1",
    )
    assert result is None


@pytest.mark.asyncio
async def test_extract_case_creates_case_with_mock_llm(db_session, monkeypatch):
    """flag 开启 + mock LLM → Case 创建"""
    monkeypatch.setattr(get_settings(), "agent_case_extraction_enabled", True)

    mock_case_json = json.dumps({
        "task_intent": "设计北欧风格客厅方案，预算5万",
        "approach": [
            {"step": 1, "attempted": "获取材料清单", "tool": "get_material_list", "result": "成功", "revised": False},
            {"step": 2, "attempted": "计算预算", "tool": "calculate_budget", "result": "5万内", "revised": False},
        ],
        "outcome": "success",
        "quality_score": 0.85,
    })

    async def fake_chat(self, messages, **kwargs):
        return mock_case_json

    with patch("app.agents.base.BaseAgent._chat", fake_chat):
        with patch("app.agents.base.BaseAgent.close", new_callable=AsyncMock):
            trace = _make_trace_dict()
            result = await extract_case_from_trace(
                trace, db_session, owner_id="user_1", created_by="user_1",
            )

    assert result is not None
    assert result.task_intent == "设计北欧风格客厅方案，预算5万"
    assert result.quality_score == 0.85
    assert result.outcome == "success"
    assert result.agent_name == "designer"
    assert result.scope == "personal"
    assert result.owner_id == "user_1"


@pytest.mark.asyncio
async def test_extract_case_llm_failure_returns_none(db_session, monkeypatch):
    """LLM 提取失败返回 None（best-effort）"""
    monkeypatch.setattr(get_settings(), "agent_case_extraction_enabled", True)

    async def fake_chat(self, messages, **kwargs):
        raise Exception("LLM 不可用")

    with patch("app.agents.base.BaseAgent._chat", fake_chat):
        with patch("app.agents.base.BaseAgent.close", new_callable=AsyncMock):
            trace = _make_trace_dict()
            result = await extract_case_from_trace(
                trace, db_session, owner_id="user_1", created_by="user_1",
            )

    assert result is None


# ── _parse_case_json ──


def test_parse_case_json_valid():
    data = _parse_case_json('{"task_intent": "test", "quality_score": 0.5, "outcome": "success"}')
    assert data is not None
    assert data["task_intent"] == "test"
    assert data["quality_score"] == 0.5


def test_parse_case_json_markdown_wrapped():
    data = _parse_case_json('```json\n{"task_intent": "test", "quality_score": 0.9}\n```')
    assert data is not None
    assert data["task_intent"] == "test"


def test_parse_case_json_clamps_quality():
    data = _parse_case_json('{"task_intent": "test", "quality_score": 1.5}')
    assert data["quality_score"] == 1.0
    data = _parse_case_json('{"task_intent": "test", "quality_score": -0.5}')
    assert data["quality_score"] == 0.0


def test_parse_case_json_invalid():
    assert _parse_case_json("") is None
    assert _parse_case_json("not json") is None
    assert _parse_case_json('{"no_intent": true}') is None


# ── search_cases ──


@pytest.mark.asyncio
async def test_search_cases_scope_isolation(db_session, monkeypatch):
    """scope 隔离：只返回 owner_id 匹配的 Case"""
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", True)

    c1 = AgentCase(
        id="case_1", scope="personal", owner_id="user_A", agent_name="designer",
        task_intent="设计客厅方案", approach="[]", outcome="success", quality_score=0.8,
        created_by="user_A",
    )
    c2 = AgentCase(
        id="case_2", scope="personal", owner_id="user_B", agent_name="designer",
        task_intent="设计客厅方案", approach="[]", outcome="success", quality_score=0.9,
        created_by="user_B",
    )
    db_session.add_all([c1, c2])
    await db_session.flush()

    results = await search_cases(
        db_session, task_intent="设计客厅方案", owner_id="user_A", scope="personal",
    )
    assert len(results) == 1
    assert results[0].owner_id == "user_A"
    assert results[0].retrieval_count == 1  # 检索后计数+1


@pytest.mark.asyncio
async def test_search_cases_flag_off_returns_empty(db_session, monkeypatch):
    """flag 关闭返回空列表"""
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", False)
    results = await search_cases(
        db_session, task_intent="test", owner_id="user_A",
    )
    assert results == []


@pytest.mark.asyncio
async def test_search_cases_empty_task_intent_returns_empty(db_session, monkeypatch):
    """空 task_intent 不检索（避免无关键词过滤时返回全量 Case）"""
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", True)
    # 空 string
    results = await search_cases(db_session, task_intent="", owner_id="user_A")
    assert results == []
    # 纯空格
    results2 = await search_cases(db_session, task_intent="   ", owner_id="user_A")
    assert results2 == []


# ── build_case_context ──


def test_build_case_context_empty():
    assert build_case_context([]) == ""


def test_build_case_context_formats():
    case = AgentCase(
        id="c1", scope="personal", owner_id="u1", agent_name="designer",
        task_intent="设计客厅", approach='[{"step":1,"attempted":"选材","result":"OK"}]',
        outcome="success", quality_score=0.8, created_by="u1",
    )
    ctx = build_case_context([case])
    assert "历史经验 Case" in ctx
    assert "设计客厅" in ctx
    assert "选材" in ctx


def test_build_case_context_budget_within_limit():
    case = AgentCase(
        id="c1", scope="personal", owner_id="u1", agent_name="designer",
        task_intent="设计客厅", approach='[{"step":1,"attempted":"选材","result":"OK"}]',
        outcome="success", quality_score=0.8, created_by="u1",
    )
    full = build_case_context([case])
    # 预算 ≥ 全量长度 → 不裁剪（旧行为）
    assert build_case_context([case], max_chars=len(full)) == full


def test_build_case_context_budget_cuts_tail():
    # cases 按 quality 降序传入，预算不足时从末尾（低优先级）丢弃
    c1 = AgentCase(
        id="c1", scope="personal", owner_id="u1", agent_name="designer",
        task_intent="设计客厅", approach='[{"step":1,"attempted":"选材","result":"OK"}]',
        outcome="success", quality_score=0.9, created_by="u1",
    )
    c2 = AgentCase(
        id="c2", scope="personal", owner_id="u1", agent_name="designer",
        task_intent="预算超支处理", approach=(
            '[{"step":1,"attempted":"核对项","result":"A"},'
            '{"step":2,"attempted":"调整项","result":"B"},'
            '{"step":3,"attempted":"复审","result":"C"}]'
        ),
        outcome="success", quality_score=0.5, created_by="u1",
    )
    full = build_case_context([c1, c2])
    c1_block = full.split("Case 2")[0]
    footer = "[/历史经验 Case —— 优先采用高质量步骤，避免已记录的失败路径]"
    note = "[其余 1 条 Case 已按上下文预算省略]"
    # 预算 = c1 块 + footer + 省略标注刚好放得下；c2 块更长必被裁
    trimmed = build_case_context([c1, c2], max_chars=len(c1_block) + len(footer) + len(note) + 1)
    assert "设计客厅" in trimmed          # 高优先级 Case 保留
    assert "预算超支处理" not in trimmed   # 低优先级 Case 被裁
    assert "省略" in trimmed             # 诚实标注省略


def test_build_case_context_budget_too_small_returns_empty():
    case = AgentCase(
        id="c1", scope="personal", owner_id="u1", agent_name="designer",
        task_intent="设计客厅", approach='[{"step":1,"attempted":"选材","result":"OK"}]',
        outcome="success", quality_score=0.8, created_by="u1",
    )
    # 预算小到连头部结构都放不下 → 不注入残片（诚实降级）
    assert build_case_context([case], max_chars=10) == ""


def test_build_case_context_max_tokens_truncates():
    # v1.13.5 token 预算：max_tokens 按估算系数换算为字符上限（len//2）
    case = AgentCase(
        id="c1", scope="personal", owner_id="u1", agent_name="designer",
        task_intent="设计客厅", approach='[{"step":1,"attempted":"选材","result":"OK"}]',
        outcome="success", quality_score=0.8, created_by="u1",
    )
    # 换算后字符预算过小 → 不注入残片（与 max_chars 行为一致）
    assert build_case_context([case], max_tokens=1) == ""
    # 换算等价性：max_tokens=N 与 max_chars=N*DIVISOR 严格等价
    full = build_case_context([case])
    n = len(full) // TOKEN_ESTIMATE_DIVISOR
    assert build_case_context([case], max_tokens=n) == build_case_context(
        [case], max_chars=n * TOKEN_ESTIMATE_DIVISOR
    )
    # max_tokens 足够 → 全量注入
    assert build_case_context([case], max_tokens=10**6) == full


def test_build_case_context_max_tokens_overrides_chars():
    # v1.13.5：max_tokens 优先于 max_chars（token 预算是更精确的上下文控制面）
    case = AgentCase(
        id="c1", scope="personal", owner_id="u1", agent_name="designer",
        task_intent="设计客厅", approach='[{"step":1,"attempted":"选材","result":"OK"}]',
        outcome="success", quality_score=0.8, created_by="u1",
    )
    # 同时传超小 max_chars + 超大 max_tokens → 按 max_tokens 全量注入
    full = build_case_context([case])
    assert build_case_context([case], max_chars=1, max_tokens=10**6) == full
    # 同时传超大 max_chars + 超小 max_tokens → 按 max_tokens 截断为空
    assert build_case_context([case], max_chars=10**6, max_tokens=1) == ""


# ── record_skill_outcome ──


@pytest.mark.asyncio
async def test_record_skill_outcome_increments(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_skill_evolution_enabled", True)
    skill = AgentSkill(
        id="sk1", name="test_skill", owner_scope="personal", owner_id="u1",
        agent_name="designer", system_prompt="test", created_by="u1",
    )
    db_session.add(skill)
    await db_session.flush()

    await record_skill_outcome(db_session, skill_id="sk1", success=True)
    await record_skill_outcome(db_session, skill_id="sk1", success=True)
    await record_skill_outcome(db_session, skill_id="sk1", success=False)
    assert skill.success_count == 2
    assert skill.fail_count == 1


@pytest.mark.asyncio
async def test_record_skill_outcome_flag_off(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_skill_evolution_enabled", False)
    skill = AgentSkill(
        id="sk2", name="test_skill2", owner_scope="personal", owner_id="u1",
        agent_name="designer", system_prompt="test", created_by="u1",
    )
    db_session.add(skill)
    await db_session.flush()
    await record_skill_outcome(db_session, skill_id="sk2", success=True)
    assert skill.success_count == 0  # flag 关闭不计数


# ── _maybe_record_skill_outcome hook（v1.13.5 闭环「只记成功不记失败」遗留）──


@pytest.mark.asyncio
async def test_skill_outcome_hook_mock_marks_fail(db_session, monkeypatch):
    """注入 Skill 后仍降级到 [mock] → 确定性记失败（无需 LLM 成本）"""
    monkeypatch.setattr(get_settings(), "agent_skill_evolution_enabled", True)
    skill = AgentSkill(
        id="skf1", name="fail_skill", owner_scope="personal", owner_id="u1",
        agent_name="designer", system_prompt="test", created_by="u1",
    )
    db_session.add(skill)
    await db_session.flush()

    from app.agents.base import BaseAgent

    agent = BaseAgent()
    agent._injected_skill_id = "skf1"
    await agent._maybe_record_skill_outcome("[mock] designer 响应：API key 未配置", db_session)
    await agent.close()
    assert skill.fail_count == 1, "mock 降级应计失败"
    assert skill.success_count == 0


@pytest.mark.asyncio
async def test_skill_outcome_hook_normal_marks_success(db_session, monkeypatch):
    """注入 Skill 后正常产出 → success=True"""
    monkeypatch.setattr(get_settings(), "agent_skill_evolution_enabled", True)
    skill = AgentSkill(
        id="sks1", name="ok_skill", owner_scope="personal", owner_id="u1",
        agent_name="designer", system_prompt="test", created_by="u1",
    )
    db_session.add(skill)
    await db_session.flush()

    from app.agents.base import BaseAgent

    agent = BaseAgent()
    agent._injected_skill_id = "sks1"
    await agent._maybe_record_skill_outcome("已为您完成客厅方案设计，布局如下…", db_session)
    await agent.close()
    assert skill.success_count == 1
    assert skill.fail_count == 0


@pytest.mark.asyncio
async def test_skill_outcome_hook_reasoning_leak_marks_fail(db_session, monkeypatch):
    """注入 Skill 后回复为思维链泄漏 → 确定性记失败（v1.13.7 闭环遗留）"""
    monkeypatch.setattr(get_settings(), "agent_skill_evolution_enabled", True)
    skill = AgentSkill(
        id="skr1", name="leak_skill", owner_scope="personal", owner_id="u1",
        agent_name="designer", system_prompt="test", created_by="u1",
    )
    db_session.add(skill)
    await db_session.flush()

    from app.agents.base import BaseAgent

    agent = BaseAgent()
    agent._injected_skill_id = "skr1"
    await agent._maybe_record_skill_outcome(
        "我需要理解用户的需求，首先分析户型图，然后生成方案。", db_session,
    )
    await agent.close()
    assert skill.fail_count == 1
    assert skill.success_count == 0


@pytest.mark.asyncio
async def test_skill_outcome_hook_no_skill_skips(db_session, monkeypatch):
    """未注入 Skill 时不计数（无 _injected_skill_id）"""
    monkeypatch.setattr(get_settings(), "agent_skill_evolution_enabled", True)

    from app.agents.base import BaseAgent

    agent = BaseAgent()
    await agent._maybe_record_skill_outcome("[mock] x", db_session)  # 无注入 → 跳过不抛错
    await agent.close()


# ── evaluate_skill_quality ──


@pytest.mark.asyncio
async def test_evaluate_skill_quality_high_success_activates(db_session, monkeypatch):
    """高成功率 DRAFT Skill 自动 active"""
    monkeypatch.setattr(get_settings(), "agent_skill_evolution_enabled", True)
    skill = AgentSkill(
        id="sk3", name="good_skill", owner_scope="personal", owner_id="u1",
        agent_name="designer", system_prompt="test", status=STATUS_DRAFT, created_by="u1",
        success_count=8, fail_count=2,
    )
    db_session.add(skill)
    await db_session.flush()

    result = await evaluate_skill_quality(db_session, skill_id="sk3")
    assert result is not None
    assert result["utility"] > 0.5
    assert skill.status == STATUS_ACTIVE  # 8/10=0.8, overall>=0.6 → active


@pytest.mark.asyncio
async def test_evaluate_skill_quality_low_archives(db_session, monkeypatch):
    """低成功率 Skill 自动 archived"""
    monkeypatch.setattr(get_settings(), "agent_skill_evolution_enabled", True)
    skill = AgentSkill(
        id="sk4", name="bad_skill", owner_scope="personal", owner_id="u1",
        agent_name="designer", system_prompt="test", status=STATUS_ACTIVE, created_by="u1",
        success_count=1, fail_count=9,
    )
    db_session.add(skill)
    await db_session.flush()

    result = await evaluate_skill_quality(db_session, skill_id="sk4")
    assert result is not None
    assert result["overall"] < 0.3
    assert skill.status == STATUS_ARCHIVED


@pytest.mark.asyncio
async def test_evaluate_skill_quality_no_usage(db_session, monkeypatch):
    """无使用记录的 Skill 不自动晋升/淘汰"""
    monkeypatch.setattr(get_settings(), "agent_skill_evolution_enabled", True)
    skill = AgentSkill(
        id="sk5", name="new_skill", owner_scope="personal", owner_id="u1",
        agent_name="designer", system_prompt="test", status=STATUS_DRAFT, created_by="u1",
        success_count=0, fail_count=0,
    )
    db_session.add(skill)
    await db_session.flush()

    result = await evaluate_skill_quality(db_session, skill_id="sk5")
    assert result is not None
    assert skill.status == STATUS_DRAFT  # 无数据不变更


# ── diagnose_credit_skill_patch ──


@pytest.mark.asyncio
async def test_diagnose_credit_significant(db_session, monkeypatch):
    """显著提升被 credited"""
    monkeypatch.setattr(get_settings(), "agent_skill_evolution_enabled", True)
    result = await diagnose_credit_skill_patch(
        db_session, skill_id="sk_x",
        before_success_rate=0.3, after_success_rate=0.7, sample_size=100,
    )
    assert result["delta"] > 0
    assert result["z_score"] >= 1.96
    assert result["credited"] is True


@pytest.mark.asyncio
async def test_diagnose_credit_not_significant(db_session, monkeypatch):
    """不显著提升不被 credited"""
    monkeypatch.setattr(get_settings(), "agent_skill_evolution_enabled", True)
    result = await diagnose_credit_skill_patch(
        db_session, skill_id="sk_x",
        before_success_rate=0.5, after_success_rate=0.52, sample_size=10,
    )
    assert result["credited"] is False


@pytest.mark.asyncio
async def test_diagnose_credit_flag_off(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_skill_evolution_enabled", False)
    result = await diagnose_credit_skill_patch(
        db_session, skill_id="sk_x",
        before_success_rate=0.3, after_success_rate=0.9, sample_size=100,
    )
    assert result["credited"] is False


# ── _parse_skill_json ──


def test_parse_skill_json_valid():
    data = _parse_skill_json('{"name": "test", "system_prompt": "你是设计师", "tools": []}')
    assert data is not None
    assert data["system_prompt"] == "你是设计师"


def test_parse_skill_json_invalid():
    assert _parse_skill_json("") is None
    assert _parse_skill_json('{"no_prompt": true}') is None


# ── distill_skill_from_cases ──


@pytest.mark.asyncio
async def test_distill_skill_below_threshold(db_session, monkeypatch):
    """Case 不足阈值不蒸馏"""
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", True)
    for i in range(2):  # < 3 阈值
        db_session.add(AgentCase(
            id=f"dc_{i}", scope="personal", owner_id="u1", agent_name="designer",
            task_intent=f"设计方案{i}", approach="[]", outcome="success",
            quality_score=0.8, created_by="u1",
        ))
    await db_session.flush()

    result = await distill_skill_from_cases(
        db_session, agent_name="designer", owner_id="u1", created_by="u1",
    )
    assert result is None


@pytest.mark.asyncio
async def test_distill_skill_creates_with_mock_llm(db_session, monkeypatch):
    """达到阈值 + mock LLM → Skill 创建"""
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", True)

    mock_skill_json = json.dumps({
        "name": "design_living_room",
        "description": "客厅设计 Skill",
        "system_prompt": "你是客厅设计师，步骤：1.确认风格 2.选材 3.预算",
        "tools": ["get_material_list"],
        "acceptance_criteria": [{"input": "北欧风", "expected": "返回方案"}],
    })

    async def fake_chat(self, messages, **kwargs):
        return mock_skill_json

    for i in range(4):
        db_session.add(AgentCase(
            id=f"dc2_{i}", scope="personal", owner_id="u1", agent_name="designer",
            task_intent=f"设计客厅方案{i}", approach="[]", outcome="success",
            quality_score=0.8, created_by="u1",
        ))
    await db_session.flush()

    with patch("app.agents.base.BaseAgent._chat", fake_chat):
        with patch("app.agents.base.BaseAgent.close", new_callable=AsyncMock):
            result = await distill_skill_from_cases(
                db_session, agent_name="designer", owner_id="u1", created_by="u1",
            )

    assert result is not None
    assert result.name == "design_living_room"
    assert result.status == STATUS_DRAFT
    assert result.system_prompt == "你是客厅设计师，步骤：1.确认风格 2.选材 3.预算"


@pytest.mark.asyncio
async def test_distill_skill_merges_similar(db_session, monkeypatch):
    """已存在同名 Skill 时合并而非新建"""
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", True)

    existing = AgentSkill(
        id="existing_sk", name="design_living_room", owner_scope="personal", owner_id="u1",
        agent_name="designer", system_prompt="existing", status=STATUS_ACTIVE, created_by="u1",
    )
    db_session.add(existing)
    for i in range(4):
        db_session.add(AgentCase(
            id=f"dc3_{i}", scope="personal", owner_id="u1", agent_name="designer",
            task_intent=f"设计客厅{i}", approach="[]", outcome="success",
            quality_score=0.8, created_by="u1",
        ))
    await db_session.flush()

    mock_skill_json = json.dumps({
        "name": "design_living_room",
        "system_prompt": "new",
        "tools": [],
    })

    async def fake_chat(self, messages, **kwargs):
        return mock_skill_json

    with patch("app.agents.base.BaseAgent._chat", fake_chat):
        with patch("app.agents.base.BaseAgent.close", new_callable=AsyncMock):
            result = await distill_skill_from_cases(
                db_session, agent_name="designer", owner_id="u1", created_by="u1",
            )

    assert result is not None
    assert result.id == "existing_sk"  # 合并到已有
    assert result.system_prompt == "existing"  # 不覆盖已有 prompt


# ── get_skill_for_injection ──


@pytest.mark.asyncio
async def test_get_skill_for_injection_returns_active(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", True)
    skill = AgentSkill(
        id="inj_sk", name="inj_test", owner_scope="personal", owner_id="u1",
        agent_name="designer", system_prompt="inj_prompt", status=STATUS_ACTIVE,
        created_by="u1", utility_score=0.8,
    )
    db_session.add(skill)
    await db_session.flush()

    result = await get_skill_for_injection(
        db_session, agent_name="designer", owner_id="u1",
    )
    assert result is not None
    assert result.id == "inj_sk"


@pytest.mark.asyncio
async def test_get_skill_for_injection_flag_off(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", False)
    result = await get_skill_for_injection(
        db_session, agent_name="designer", owner_id="u1",
    )
    assert result is None


# ── Harness 集成 ──


@pytest.mark.asyncio
async def test_harness_extract_case_flag_off_noop(db_session, monkeypatch):
    """flag 关闭时 _maybe_extract_case 不操作"""
    monkeypatch.setattr(get_settings(), "agent_case_extraction_enabled", False)
    from app.agents.harness import AgentRuntime, AgentTrace, AgentRunStatus

    runtime = AgentRuntime()
    trace = AgentTrace(agent_name="designer", user_message="测试")
    trace.finish(AgentRunStatus.SUCCESS)
    await runtime._maybe_extract_case(trace, {"db": db_session, "user_id": "u1"})
    # 无异常即通过（flag 关闭应直接 return）


# ── BaseAgent 注入 ──


@pytest.mark.asyncio
async def test_baseagent_think_injection_flag_off(client: AsyncClient, monkeypatch):
    """flag 关闭时 think 不注入 Case/Skill，不报错"""
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", False)

    async def fake_chat(self, messages, **kwargs):
        return "mock reply"

    from app.agents.base import BaseAgent

    with patch("app.agents.base.BaseAgent._chat", fake_chat):
        agent = BaseAgent()
        agent.agent_name = "designer"
        agent.system_prompt = "你是设计师"
        reply = await agent.think(
            "帮我设计客厅", db=None, user_id="u1",
        )
        await agent.close()

    assert reply == "mock reply"


@pytest.mark.asyncio
async def test_baseagent_think_with_user_id_param(client: AsyncClient, monkeypatch):
    """think 接受 user_id 参数（向后兼容）"""
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", False)

    async def fake_chat(self, messages, **kwargs):
        return "ok"

    from app.agents.base import BaseAgent

    with patch("app.agents.base.BaseAgent._chat", fake_chat):
        agent = BaseAgent()
        agent.agent_name = "designer"
        # 不传 user_id 也应正常工作（向后兼容）
        reply = await agent.think("设计客厅")
        await agent.close()

    assert reply == "ok"


# ── v1.10.2 边界：LLM 异常返回与空值输入（补覆盖率缺失路径）──


def test_is_goal_directed_chitchat_over_8_chars():
    """≥8 字符含闲聊词 → 非目标导向（覆盖闲聊词命中分支 L61）"""
    assert not _is_goal_directed("你好请问有什么可以帮您")
    assert not _is_goal_directed("thanks for your help")


def test_compress_trajectory_bounded_length():
    """超长输入 → 压缩结果有界（各段截断保证总长 ≤ 2000 不变式）。

    注意：user_msg[:500] + 工具调用[:10] + response[:800] 的上限之和 < 2000，
    故 L93 的 "[已截断]" 分支当前参数下不可达（防御性死代码），仍保持有界。
    """
    trace = {
        "user_message": "设" * 600,  # 截断 500
        "response": "方" * 1200,     # 截断 800
        "tool_calls": [{"name": f"tool_{i}"} for i in range(100)],  # 只取前 10
    }
    compressed = _compress_trajectory(trace)
    assert len(compressed) <= 2000  # 有界不变式
    assert "[用户请求]" in compressed
    assert "[工具调用]" in compressed
    assert "[Agent回复]" in compressed


@pytest.mark.asyncio
async def test_extract_case_trace_with_to_dict(db_session, monkeypatch):
    """trace 对象有 to_dict() 方法 → 走 to_dict 分支（覆盖 L145）"""
    monkeypatch.setattr(get_settings(), "agent_case_extraction_enabled", True)

    class FakeTrace:
        def __init__(self):
            self._data = _make_trace_dict()

        def to_dict(self):
            return self._data

    async def fake_chat(self, messages, **kwargs):
        return json.dumps({
            "task_intent": "测试 to_dict 意图",
            "approach": [], "outcome": "success", "quality_score": 0.5,
        })

    with patch("app.agents.base.BaseAgent._chat", fake_chat):
        with patch("app.agents.base.BaseAgent.close", new_callable=AsyncMock):
            result = await extract_case_from_trace(
                FakeTrace(), db_session, owner_id="user_1", created_by="user_1",
            )

    assert result is not None
    assert result.task_intent == "测试 to_dict 意图"


@pytest.mark.asyncio
async def test_extract_case_unsupported_trace_type(db_session, monkeypatch):
    """trace 类型不支持（int）→ 安全返回 None（覆盖 L149-150）"""
    monkeypatch.setattr(get_settings(), "agent_case_extraction_enabled", True)
    result = await extract_case_from_trace(12345, db_session, owner_id="user_1")
    assert result is None


def test_parse_case_json_substring_extraction():
    """json.loads 失败但含 {…} 子串 → 子串提取成功（覆盖 L231-234 成功分支）"""
    data = _parse_case_json('说明：{"task_intent": "设计客厅", "quality_score": 0.7} 以上')
    assert data is not None
    assert data["task_intent"] == "设计客厅"
    assert data["quality_score"] == 0.7


def test_parse_case_json_substring_extraction_fails():
    """有花括号但子串仍非法 JSON → 返回 None（覆盖子串提取失败分支）"""
    assert _parse_case_json("前缀{这不是合法json}后缀") is None
    assert _parse_case_json("无花括号的内容") is None


def test_parse_case_json_quality_non_numeric():
    """quality_score 非数字 → 降级 0.0（覆盖 L244-245）"""
    data = _parse_case_json('{"task_intent": "test", "quality_score": "abc"}')
    assert data["quality_score"] == 0.0


def test_build_case_context_malformed_approach():
    """approach 非 JSON → 降级 '(步骤解析失败)'（覆盖 L321-322）"""
    case = AgentCase(
        id="c_malformed", scope="personal", owner_id="u1", agent_name="designer",
        task_intent="设计客厅", approach="not json",
        outcome="success", quality_score=0.8, created_by="u1",
    )
    ctx = build_case_context([case])
    assert "(步骤解析失败)" in ctx


@pytest.mark.asyncio
async def test_distill_skill_flag_off_returns_none(db_session, monkeypatch):
    """distill flag 关闭 → None（覆盖 L71）"""
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", False)
    result = await distill_skill_from_cases(
        db_session, agent_name="designer", owner_id="u1",
    )
    assert result is None


@pytest.mark.asyncio
async def test_distill_skill_llm_invalid_json(db_session, monkeypatch):
    """LLM 返回非法 JSON → 蒸馏失败返回 None（覆盖 L102-103 + L228-237）"""
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", True)
    for i in range(3):
        db_session.add(AgentCase(
            id=f"dj_{i}", scope="personal", owner_id="u1", agent_name="designer",
            task_intent=f"设计客厅{i}", approach="[]", outcome="success",
            quality_score=0.8, created_by="u1",
        ))
    await db_session.flush()

    async def fake_chat(self, messages, **kwargs):
        return "这不是 JSON 内容"

    with patch("app.agents.base.BaseAgent._chat", fake_chat):
        with patch("app.agents.base.BaseAgent.close", new_callable=AsyncMock):
            result = await distill_skill_from_cases(
                db_session, agent_name="designer", owner_id="u1", created_by="u1",
            )

    assert result is None


@pytest.mark.asyncio
async def test_distill_skill_llm_error(db_session, monkeypatch):
    """LLM 调用异常 → 返回 None（覆盖 L210-212）"""
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", True)
    for i in range(3):
        db_session.add(AgentCase(
            id=f"de_{i}", scope="personal", owner_id="u1", agent_name="designer",
            task_intent=f"设计{i}", approach="[]", outcome="success",
            quality_score=0.8, created_by="u1",
        ))
    await db_session.flush()

    async def fake_chat(self, messages, **kwargs):
        raise Exception("LLM 不可用")

    with patch("app.agents.base.BaseAgent._chat", fake_chat):
        with patch("app.agents.base.BaseAgent.close", new_callable=AsyncMock):
            result = await distill_skill_from_cases(
                db_session, agent_name="designer", owner_id="u1", created_by="u1",
            )

    assert result is None


@pytest.mark.asyncio
async def test_distill_skill_malformed_approach(db_session, monkeypatch):
    """Case approach 非法 JSON → 蒸馏降级仍成功（覆盖 L190-191）"""
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", True)
    for i in range(3):
        db_session.add(AgentCase(
            id=f"dm_{i}", scope="personal", owner_id="u1", agent_name="designer",
            task_intent=f"设计{i}", approach="not json", outcome="success",
            quality_score=0.8, created_by="u1",
        ))
    await db_session.flush()

    mock_skill_json = json.dumps({
        "name": "distill_malformed", "description": "d",
        "system_prompt": "你是设计师", "tools": [], "acceptance_criteria": [],
    })

    async def fake_chat(self, messages, **kwargs):
        return mock_skill_json

    with patch("app.agents.base.BaseAgent._chat", fake_chat):
        with patch("app.agents.base.BaseAgent.close", new_callable=AsyncMock):
            result = await distill_skill_from_cases(
                db_session, agent_name="designer", owner_id="u1", created_by="u1",
            )

    assert result is not None
    assert result.name == "distill_malformed"


def test_parse_skill_json_substring_extraction():
    """json.loads 失败但含 {…} 子串 → 提取成功（覆盖 L223-225）"""
    data = _parse_skill_json('结果：{"name": "t", "system_prompt": "你是设计师"} 完毕')
    assert data is not None
    assert data["system_prompt"] == "你是设计师"


def test_parse_skill_json_no_braces():
    """无花括号 → 返回 None（覆盖 L228-237）"""
    assert _parse_skill_json("完全没有花括号的内容") is None


def test_parse_skill_json_markdown_wrapped():
    """markdown 代码块包裹 → 正常解析（覆盖 223-224）"""
    data = _parse_skill_json('```json\n{"name": "t", "system_prompt": "你是设计师"}\n```')
    assert data is not None
    assert data["system_prompt"] == "你是设计师"


def test_parse_skill_json_substring_extraction_fails():
    """子串仍非法 JSON → 返回 None（覆盖 234 内层 except）"""
    assert _parse_skill_json("前缀{这不是合法json}后缀") is None


@pytest.mark.asyncio
async def test_find_similar_skill_empty_name(db_session, monkeypatch):
    """name 为空 → 跳过查重返回 None（覆盖 L253）"""
    result = await _find_similar_skill(
        db_session, agent_name="designer", owner_id="u1", scope="personal", name="",
    )
    assert result is None


@pytest.mark.asyncio
async def test_record_skill_outcome_not_found(db_session, monkeypatch):
    """skill_id 不存在 → 安全无操作（覆盖 L292）"""
    monkeypatch.setattr(get_settings(), "agent_skill_evolution_enabled", True)
    await record_skill_outcome(db_session, skill_id="nonexistent", success=True)
    await db_session.flush()  # 不应抛异常


@pytest.mark.asyncio
async def test_evaluate_skill_quality_flag_off(db_session, monkeypatch):
    """flag 关闭 → None（覆盖 L314）"""
    monkeypatch.setattr(get_settings(), "agent_skill_evolution_enabled", False)
    result = await evaluate_skill_quality(db_session, skill_id="sk_x")
    assert result is None


@pytest.mark.asyncio
async def test_evaluate_skill_quality_not_found(db_session, monkeypatch):
    """skill 不存在 → None（覆盖 L320）"""
    monkeypatch.setattr(get_settings(), "agent_skill_evolution_enabled", True)
    result = await evaluate_skill_quality(db_session, skill_id="nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_diagnose_credit_sample_size_zero(db_session, monkeypatch):
    """sample_size=0 → z_score=0（覆盖 L402 if 分支）"""
    monkeypatch.setattr(get_settings(), "agent_skill_evolution_enabled", True)
    result = await diagnose_credit_skill_patch(
        db_session, skill_id="sk_x",
        before_success_rate=0.5, after_success_rate=0.7, sample_size=0,
    )
    assert result["z_score"] == 0.0
    assert result["credited"] is False


@pytest.mark.asyncio
async def test_diagnose_credit_before_rate_max(db_session, monkeypatch):
    """before_success_rate=1.0 → z_score=0（覆盖 L402 if 分支）"""
    monkeypatch.setattr(get_settings(), "agent_skill_evolution_enabled", True)
    result = await diagnose_credit_skill_patch(
        db_session, skill_id="sk_x",
        before_success_rate=1.0, after_success_rate=1.0, sample_size=20,
    )
    assert result["z_score"] == 0.0


# ════════════════════════════════════════════════════════════════
# v1.10.x 全景全量全链路记忆 + 时间/空间感知（2026-08-12）
# 覆盖：项目空间感知（Case/Skill 提取与注入）+ 时间感知（recency 排序）
#      + BaseAgent 内建 Case 沉淀 hook + trace_id 防双提取
# ════════════════════════════════════════════════════════════════


def _mock_case_json(task_intent: str = "设计客厅方案") -> str:
    return json.dumps({
        "task_intent": task_intent,
        "approach": [{"step": 1, "attempted": "获取材料清单", "tool": "get_material_list",
                      "result": "成功", "revised": False}],
        "outcome": "success",
        "quality_score": 0.8,
    })


@pytest.mark.asyncio
async def test_search_cases_recency_newer_first(db_session, monkeypatch):
    """时间感知：quality/热度相同时，近期 Case 优先（recency 排序键）"""
    from datetime import datetime, timezone
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", True)
    old = AgentCase(
        id="case_old", scope="personal", owner_id="u1", agent_name="designer",
        task_intent="设计客厅方案", approach="[]", outcome="success", quality_score=0.8,
        created_by="u1", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    new = AgentCase(
        id="case_new", scope="personal", owner_id="u1", agent_name="designer",
        task_intent="设计客厅方案", approach="[]", outcome="success", quality_score=0.8,
        created_by="u1", created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    db_session.add_all([old, new])
    await db_session.flush()

    results = await search_cases(
        db_session, task_intent="设计客厅方案", owner_id="u1",
    )
    assert [c.id for c in results] == ["case_new", "case_old"]


@pytest.mark.asyncio
async def test_harness_extract_case_project_scope(db_session, monkeypatch):
    """空间感知（写侧）：项目上下文执行沉淀为 project scope Case"""
    from app.agents.harness import AgentRuntime, AgentTrace, AgentRunStatus
    monkeypatch.setattr(get_settings(), "agent_case_extraction_enabled", True)

    async def fake_chat(self, messages, **kwargs):
        return _mock_case_json()

    with patch("app.agents.base.BaseAgent._chat", fake_chat):
        with patch("app.agents.base.BaseAgent.close", new_callable=AsyncMock):
            runtime = AgentRuntime()
            trace = AgentTrace(
                agent_name="designer", user_message="帮我设计客厅方案",
                user_message_truncated="帮我设计客厅方案",
                response="好的，已生成方案",
                response_truncated="好的，已生成方案",
            )
            trace.finish(AgentRunStatus.SUCCESS)
            await runtime._maybe_extract_case(
                trace, {"db": db_session, "user_id": "u1", "project_id": "p1"},
            )

    from sqlalchemy import select
    rows = (await db_session.execute(select(AgentCase))).scalars().all()
    assert len(rows) == 1
    assert rows[0].scope == "project"
    assert rows[0].owner_id == "p1"
    assert rows[0].created_by == "u1"


@pytest.mark.asyncio
async def test_baseagent_think_persists_execution_case(db_session, monkeypatch):
    """全链路写侧：端点直连 think（db+user_id）→ Case 沉淀（内建 hook）"""
    monkeypatch.setattr(get_settings(), "agent_case_extraction_enabled", True)
    # 屏蔽无关链路，聚焦 Case 沉淀 hook
    monkeypatch.setattr(get_settings(), "agentic_rag_enabled", False)
    monkeypatch.setattr(get_settings(), "model_spec_enabled", False)
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", False)

    async def fake_chat(self, messages, **kwargs):
        return _mock_case_json()

    from app.agents.base import BaseAgent
    with patch("app.agents.base.BaseAgent._chat", fake_chat):
        with patch("app.agents.base.BaseAgent.close", new_callable=AsyncMock):
            agent = BaseAgent()
            agent.agent_name = "designer"
            agent.system_prompt = "你是设计师"
            reply = await agent.think(
                "帮我设计客厅方案", db=db_session, user_id="u1",
            )
            await agent.close()

    assert reply == _mock_case_json()
    from sqlalchemy import select
    rows = (await db_session.execute(select(AgentCase))).scalars().all()
    assert len(rows) == 1
    assert rows[0].scope == "personal"
    assert rows[0].owner_id == "u1"
    assert rows[0].agent_name == "designer"


@pytest.mark.asyncio
async def test_baseagent_think_skips_case_in_harness_context(db_session, monkeypatch):
    """harness.run 上下文（_harness_trace 标记）→ 内建 hook 跳过，避免双提取"""
    monkeypatch.setattr(get_settings(), "agentic_rag_enabled", False)
    monkeypatch.setattr(get_settings(), "model_spec_enabled", False)
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", False)
    monkeypatch.setattr(get_settings(), "agent_case_extraction_enabled", True)

    from app.agents.harness import AgentRuntime
    fake_harness = AgentRuntime()
    mock_extract = AsyncMock()
    fake_harness._maybe_extract_case = mock_extract
    monkeypatch.setattr("app.agents.harness.get_harness", lambda: fake_harness)

    async def fake_chat(self, messages, **kwargs):
        return "mock reply"

    from app.agents.base import BaseAgent
    with patch("app.agents.base.BaseAgent._chat", fake_chat):
        agent = BaseAgent()
        agent.agent_name = "designer"
        agent._harness_trace = "T1"  # 模拟 harness.run 已标记
        reply = await agent.think(
            "帮我设计客厅方案", db=db_session, user_id="u1",
        )
        await agent.close()

    assert reply == "mock reply"
    mock_extract.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_case_trace_id_dedup(db_session, monkeypatch):
    """防双提取：同一 trace_id 重复提交 → 第二次跳过"""
    monkeypatch.setattr(get_settings(), "agent_case_extraction_enabled", True)

    async def fake_chat(self, messages, **kwargs):
        return _mock_case_json()

    with patch("app.agents.base.BaseAgent._chat", fake_chat):
        with patch("app.agents.base.BaseAgent.close", new_callable=AsyncMock):
            trace = _make_trace_dict()  # trace_id="test_trace_001"
            first = await extract_case_from_trace(
                trace, db_session, owner_id="u1", created_by="u1",
            )
            second = await extract_case_from_trace(
                trace, db_session, owner_id="u1", created_by="u1",
            )

    assert first is not None
    assert second is None


@pytest.mark.asyncio
async def test_inject_evolution_context_project_scope(db_session, monkeypatch):
    """空间感知（读侧）：project_id 非空 → 按 project scope 检索 Case/Skill"""
    from app.agents.base import BaseAgent
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", True)

    captured: dict = {}

    async def fake_search(db, *, task_intent, owner_id, scope, **kwargs):
        captured["case_owner"] = owner_id
        captured["case_scope"] = scope
        return []

    async def fake_skill(db, *, agent_name, owner_id, scope, **kwargs):
        captured["skill_owner"] = owner_id
        captured["skill_scope"] = scope
        return None

    monkeypatch.setattr("app.services.agent_case_service.search_cases", fake_search)
    monkeypatch.setattr(
        "app.services.agent_skill_evolution_service.get_skill_for_injection", fake_skill,
    )

    agent = BaseAgent()
    agent.agent_name = "designer"
    messages: list = []
    await agent._inject_evolution_context(
        messages, "设计客厅方案", "u1", db_session, project_id="p1",
    )
    assert captured == {"case_owner": "p1", "case_scope": "project",
                        "skill_owner": "p1", "skill_scope": "project"}

    # 无 project_id → personal scope（owner_id=user_id）
    captured.clear()
    await agent._inject_evolution_context(
        messages, "设计客厅方案", "u1", db_session,
    )
    assert captured == {"case_owner": "u1", "case_scope": "personal",
                        "skill_owner": "u1", "skill_scope": "personal"}


@pytest.mark.asyncio
async def test_get_skill_for_injection_recency(db_session, monkeypatch):
    """时间感知：utility 相同时，近期更新的 Skill 优先"""
    from datetime import datetime, timezone
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", True)
    old = AgentSkill(
        id="sk_old", name="old", owner_scope="personal", owner_id="u1",
        agent_name="designer", system_prompt="p", status=STATUS_ACTIVE,
        created_by="u1", utility_score=0.8,
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    new = AgentSkill(
        id="sk_new", name="new", owner_scope="personal", owner_id="u1",
        agent_name="designer", system_prompt="p", status=STATUS_ACTIVE,
        created_by="u1", utility_score=0.8,
        updated_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    db_session.add_all([old, new])
    await db_session.flush()

    result = await get_skill_for_injection(
        db_session, agent_name="designer", owner_id="u1",
    )
    assert result is not None
    assert result.id == "sk_new"
