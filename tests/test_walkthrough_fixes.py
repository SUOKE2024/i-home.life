"""v1.15.x 全景走查修复回归测试（2026-08-17 walkthrough findings #1-#12）。

每项修复对应一条回归用例，mock 模式（conftest 清空 LLM key）下确定性可回归：
- #1  harness 空回复（finish=tool_calls）降级无工具重试 / 全空走 fallback
- #2  A2A 执行降级 state=failed（不再伪装 completed）+ 商业运营 Agent 角色门控
- #3  designer 89㎡ 不再回退 126㎡ 硬编码文案 + 儿童房适配
- #4  商业运营 Agent 路由（marketing/competitor_research 等）+ 未知 agent_type 422
- #5  finance_recon escrow 模型导入修复
- #6  意图分类：全流程安排请求 → general（不再被「预算」关键词劫持）
- #7  qa_inspector 0 检查项 → insufficient_data（不再输出合格/不合格伪结论）
- #8  concierge FAQ 低分错配修复（阈值 0.4 + 入住/甲醛条目）
- #9  identity 端点普通用户可用（不再 403）
- #10 settlement 聊天注入真实结算台账（_load_settlement_context）
- #12 budget/procurement/construction 结构化字段按 markdown 分节提取
"""

import uuid

import pytest
from httpx import AsyncClient

from app.agents.concierge import ConciergeAgent
from app.agents.designer import DesignerAgent
from app.agents.harness import AgentRuntime, HarnessConfig
from app.agents.qa_inspector import QAInspectorAgent
from app.agents.orchestrator import OrchestratorAgent
from app.api.agents import (
    _load_settlement_context, _pick_section, _split_markdown_sections,
)
from app.services.agent_orchestration_service import (
    AgentTask, _resolve_dependencies, _rule_decompose, validate_dag,
)


# ════════════════════════════════════════════════════════════════
# #1 harness 空回复处理
# ════════════════════════════════════════════════════════════════


class _EmptyToolsAgent:
    """think_with_tools 返回空 final_reply，think 返回真实回复（模拟推理模型
    finish=tool_calls 且 content 为空时的降级路径）。"""
    agent_name = "fake_agent"
    tools = [{"name": "fake_tool"}]
    calls = []

    async def think_with_tools(self, user_message, **kwargs):
        self.calls.append("tools")
        return {"final_reply": "", "tool_calls": [], "rounds": 0, "usage": {}}

    async def think(self, user_message, **kwargs):
        self.calls.append("plain")
        return "无工具降级真实回复"

    async def close(self):
        pass


class _AlwaysEmptyAgent(_EmptyToolsAgent):
    async def think(self, user_message, **kwargs):
        self.calls.append("plain")
        return ""


@pytest.mark.asyncio
async def test_harness_empty_tools_reply_retries_plain_think():
    """#1 工具循环空回复 → 降级无工具 think 重试成功（不再把空回复当成功）。"""
    harness = AgentRuntime(HarnessConfig(
        agent_timeout_seconds=5, max_retries=1,
    ))
    agent = _EmptyToolsAgent()
    result = await harness.run(agent, "测试消息")
    assert result.get("fallback") is not True
    assert result["reply"] == "无工具降级真实回复"
    assert agent.calls == ["tools", "plain"]


@pytest.mark.asyncio
async def test_harness_empty_reply_all_fail_fallback():
    """#1 工具与无工具均空回复 → 统一 fallback 占位（调用方据此诚实标注失败）。"""
    harness = AgentRuntime(HarnessConfig(
        agent_timeout_seconds=5, max_retries=1,
    ))
    agent = _AlwaysEmptyAgent()
    result = await harness.run(agent, "测试消息")
    assert result.get("fallback") is True
    assert "服务暂时不可用" in result["reply"]


# ════════════════════════════════════════════════════════════════
# #2 A2A 状态诚实性 + 商业运营角色门控
# ════════════════════════════════════════════════════════════════


class _StubTrace:
    """harness 轨迹测试桩（v1.15.6 补齐字段：v1.15.5 证据链/轨迹落库路径可能直接访问）"""

    trace_id = ""
    workflow_id = ""
    agent_name = ""
    agent_version = ""
    provider = ""
    model = ""
    status = None
    user_id = ""
    project_id = ""
    scope = ""
    context_source = ""


class _StubFallbackHarness:
    _agent_registry = {"kitchen": type("KitchenAgent", (), {"agent_name": "kitchen"})}

    def start_trace(self, *a, **k):
        return _StubTrace()

    def finish_trace(self, *a, **k):
        pass

    async def run(self, **kwargs):
        return {"reply": "[kitchen] 服务暂时不可用，请稍后重试。", "fallback": True, "trace": {}}


@pytest.mark.asyncio
async def test_a2a_fallback_state_failed_not_completed(client: AsyncClient, auth_headers, monkeypatch):
    """#2 harness 降级 → A2A state=failed（此前 state=completed 掩盖执行失败）。"""
    monkeypatch.setattr("app.api.a2a.get_harness", lambda: _StubFallbackHarness())
    resp = await client.post(
        "/api/a2a/tasks/send",
        json={"agent_name": "KitchenAgent", "message": "4平米小厨房怎么布局"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "failed"
    assert "降级" in (body.get("error") or "")


@pytest.mark.asyncio
async def test_a2a_business_ops_agent_non_admin_rejected(client: AsyncClient, auth_headers):
    """#4 商业运营 Agent 经 A2A 下发时非管理员 → failed + 仅管理员。"""
    resp = await client.post(
        "/api/a2a/tasks/send",
        json={"agent_name": "MarketingAgent", "message": "分析获客数据"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "failed"
    assert "仅管理员" in (body.get("error") or "")


# ════════════════════════════════════════════════════════════════
# #3 designer 面积硬编码修复
# ════════════════════════════════════════════════════════════════


def test_designer_detect_area_numeric():
    """#3 数字面积解析到最近模板档位（此前 89㎡ 一律回退 126）。"""
    assert DesignerAgent._detect_area("89平米三室两厅") == ("90", 89.0)
    assert DesignerAgent._detect_area("126㎡ 三室两厅") == ("126", 126.0)
    assert DesignerAgent._detect_area("89 平方米") == ("90", 89.0)
    assert DesignerAgent._detect_area("大平层") == ("160", None)
    assert DesignerAgent._detect_area("小户型") == ("90", None)


@pytest.mark.asyncio
async def test_designer_layouts_no_hardcoded_126():
    """#3 89㎡ 回复不再硬编码「126㎡户型设计方案」，诚实标注用户声明面积。"""
    agent = DesignerAgent()
    try:
        r = await agent.generate_layouts("89平米三室两厅，北欧现代风")
    finally:
        await agent.close()
    assert "89" in r["reply"]
    assert "126㎡户型" not in r["reply"]


@pytest.mark.asyncio
async def test_designer_layouts_children_room():
    """#3 用户提到孩子 → 书房调整为儿童房（此前生成书房）。"""
    agent = DesignerAgent()
    try:
        r = await agent.generate_layouts("126平米三室两厅，家里有3岁孩子，儿童房要安全环保")
    finally:
        await agent.close()
    names = [room["name"] for plan in r["plans"] for room in plan["rooms"]]
    assert "儿童房" in names
    assert "书房" not in names


@pytest.mark.asyncio
async def test_design_endpoint_89_honest_area(client: AsyncClient, auth_headers):
    """#3 /agents/design 对 89㎡ 项目不再输出 126㎡ 硬编码文案。"""
    resp = await client.post(
        "/api/agents/design",
        json={
            "message": "89平米三室两厅，北欧现代风，家里有3岁孩子",
            "room_info": "三室两厅一厨一卫 89㎡",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "89" in body["space_planning"]
    assert "126㎡户型" not in body["space_planning"]


# ════════════════════════════════════════════════════════════════
# #4 商业运营 Agent 路由 + 未知 agent_type 422
# ════════════════════════════════════════════════════════════════


async def _admin_headers() -> dict:
    from app.auth.paseto_handler import create_token
    from app.database import async_session
    from app.models.user import User

    user_id = str(uuid.uuid4())
    async with async_session() as db:
        db.add(User(
            id=user_id, phone=f"138{uuid.uuid4().hex[:8]}",
            name="回归管理员", role="admin", hashed_password="x",
        ))
        await db.commit()
    return {"Authorization": f"Bearer {create_token(user_id, 'admin')}"}


@pytest.mark.asyncio
async def test_chat_business_ops_admin_ok(client: AsyncClient):
    """#4 管理员显式 agent_type=marketing → 真实路由到 marketing Agent（mock 回复）。"""
    headers = await _admin_headers()
    resp = await client.post(
        "/api/agents/chat",
        json={"message": "分析一下本周装修平台获客数据", "agent_type": "marketing"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_type"] == "marketing"
    assert body["reply"]


@pytest.mark.asyncio
async def test_chat_business_ops_competitor_admin_ok(client: AsyncClient):
    """#4 管理员显式 agent_type=competitor_research → 不再被路由到 budget。"""
    headers = await _admin_headers()
    resp = await client.post(
        "/api/agents/chat",
        json={"message": "调研本地竞对装修公司的套餐定价", "agent_type": "competitor_research"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_type"] == "competitor_research"
    assert body["reply"]


@pytest.mark.asyncio
async def test_chat_business_ops_non_admin_403(client: AsyncClient, auth_headers):
    """#4 普通用户显式 agent_type=marketing → 403（平台运营专用，不再静默吞掉）。"""
    resp = await client.post(
        "/api/agents/chat",
        json={"message": "分析获客数据", "agent_type": "marketing"},
        headers=auth_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_chat_unknown_agent_type_422(client: AsyncClient, auth_headers):
    """#4 未知 agent_type → 422 诚实报错（此前静默路由到 orchestrator 泛化回答）。"""
    resp = await client.post(
        "/api/agents/chat",
        json={"message": "你好", "agent_type": "no_such_agent"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_chat_stream_unknown_agent_type_422(client: AsyncClient, auth_headers):
    """#4 SSE 流式同样对未知 agent_type 422（校验前置到响应创建前）。"""
    resp = await client.post(
        "/api/agents/chat/stream",
        json={"message": "你好", "agent_type": "no_such_agent"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


# ════════════════════════════════════════════════════════════════
# #5 finance_recon escrow 导入修复
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_finance_recon_escrow_query_fixed(db_session):
    """#5 escrow 统计不再 ImportError（app.models.escrow 不存在 → procurement_enhanced.EscrowPayment）。"""
    from app.agents.finance_recon import FinanceReconAgent

    agent = FinanceReconAgent()
    try:
        report = await agent.generate_recon_report(db_session, days=30)
    finally:
        await agent.close()
    assert "escrow_count" in report
    assert "escrow 表查询失败" not in str(report)
    assert "escrow_payments" in (report.get("escrow_note") or "")


# ════════════════════════════════════════════════════════════════
# #6 意图分类：全流程安排不再被预算关键词劫持
# ════════════════════════════════════════════════════════════════


def test_fallback_classify_process_overview():
    """#6 「帮我安排整个装修流程」+ 预算15万 → general（此前被路由到 budget）。"""
    r = OrchestratorAgent.fallback_classify(
        "你好，我买了89平米毛坯房，预算15万，请帮我安排整个装修流程"
    )
    assert r["intent"] == "general"


def test_fallback_classify_single_domain_unchanged():
    """#6 单领域问题不受流程词影响（回归保护）。"""
    assert OrchestratorAgent.fallback_classify("帮我看看客厅布局怎么设计")["intent"] == "design"
    assert OrchestratorAgent.fallback_classify("装修预算大概多少钱")["intent"] == "budget"


# ════════════════════════════════════════════════════════════════
# #1b 编排链式规则分解 + 依赖重映射
# ════════════════════════════════════════════════════════════════


def test_rule_decompose_chain_multi_task():
    """#1b 链式表述（先…再…然后…最后…）→ 依赖链多任务（此前塌缩单任务）。"""
    tasks = _rule_decompose("先设计客餐厅方案，再根据方案给预算，然后列采购清单，最后排施工计划")
    assert [t.agent_name for t in tasks] == ["designer", "budget", "procurement", "construction"]
    for i in range(1, len(tasks)):
        assert tasks[i].dependencies == [tasks[i - 1].task_id]
    ok, err = validate_dag(tasks)
    assert ok, err


def test_rule_decompose_single_unchanged():
    """#1b 无链式表述保持单任务（回归保护既有行为）。"""
    tasks = _rule_decompose("120平米房子装修预算大概多少钱")
    assert len(tasks) == 1
    assert tasks[0].agent_name == "budget"


def test_resolve_dependencies_remap():
    """#1b LLM 的 task_N/agent 名依赖引用重映射为真实 task_id，DAG 校验通过。"""
    tasks = [
        AgentTask(task_id="t1", agent_name="designer", description="d", dependencies=[]),
        AgentTask(task_id="t2", agent_name="budget", description="d", dependencies=["task_1", "nope"]),
        AgentTask(task_id="t3", agent_name="procurement", description="d", dependencies=["budget", "2"]),
    ]
    _resolve_dependencies(tasks)
    assert tasks[1].dependencies == ["t1"]
    assert tasks[2].dependencies == ["t2"]
    ok, err = validate_dag(tasks)
    assert ok, err


# ════════════════════════════════════════════════════════════════
# #7 qa_inspector 占位结论与 0 检查项矛盾
# ════════════════════════════════════════════════════════════════


def test_qa_acceptance_no_phases_insufficient_data():
    """#7 无 phases → insufficient_data（此前「不合格需返工」）。"""
    agent = QAInspectorAgent()
    report = agent.generate_acceptance_report({"project_id": "P1", "phases": []})
    assert report["overall_verdict"] == "insufficient_data"
    assert "数据不足" in report["overall_verdict_text"]
    assert "数据不足" in report["reply"]


def test_qa_acceptance_chinese_phases_resolved():
    """#7 中文阶段名（水电/泥木/油漆）归一化后真实产生检查项。"""
    agent = QAInspectorAgent()
    report = agent.generate_acceptance_report({
        "project_id": "P1", "project_name": "测试项目",
        "phases": ["水电", "泥木", "油漆"],
        "inspection_results": {},
    })
    assert report["summary"]["total_items"] > 0
    assert report["overall_verdict"] != "insufficient_data"


def test_qa_compare_design_no_data_insufficient():
    """#7 0 可比对项 → insufficient_data（此前「重大偏差需返工」）。"""
    agent = QAInspectorAgent()
    result = agent.compare_with_design({"project_id": "P1", "phase": "masonry", "images": []})
    assert result["verdict"] == "insufficient_data"
    assert "数据不足" in result["verdict_text"]


def test_qa_defects_no_images_insufficient():
    """#7 无现场照片 → insufficient_data（此前「未检出缺陷，工艺合格」）。"""
    agent = QAInspectorAgent()
    result = agent.detect_defects({"project_id": "P1", "phase": "masonry", "images": []})
    assert result["verdict"] == "insufficient_data"
    assert "数据不足" in result["verdict_text"]


# ════════════════════════════════════════════════════════════════
# #8 concierge FAQ 低分错配
# ════════════════════════════════════════════════════════════════


def test_faq_move_in_formaldehyde_answered():
    """#8 入住/甲醛问题命中新增条目（此前以 0.28 低分答成「装修工期」）。"""
    agent = ConciergeAgent()
    result = agent.answer_faq("装修完成后多久可以入住？甲醛怎么治理？")
    assert result["found"] is True
    assert "甲醛" in result["answer"]
    assert result["need_human"] is False


def test_faq_budget_still_found():
    """#8 阈值提升不回退既有高置信匹配（回归保护）。"""
    agent = ConciergeAgent()
    result = agent.answer_faq("装修预算大概多少钱")
    assert result["found"] is True
    assert "预算" in result["answer"]


def test_faq_unknown_still_not_found():
    """#8 无匹配仍返回未找到 + 转人工（回归保护）。"""
    agent = ConciergeAgent()
    result = agent.answer_faq("量子力学基本原理是什么")
    assert result["found"] is False
    assert result["need_human"] is True


# ════════════════════════════════════════════════════════════════
# #9 identity 端点普通用户可用
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_identity_endpoint_non_admin_ok(client: AsyncClient, auth_headers):
    """#9 普通用户访问 identity Agent → 200（此前 403「仅管理员」）。"""
    resp = await client.post(
        "/api/agents/identity",
        json={"message": "实名认证需要准备什么材料"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_type"] == "identity"
    assert body["reply"]


# ════════════════════════════════════════════════════════════════
# #10 settlement 台账注入
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_settlement_context_with_record(db_session):
    """#10 有结算单 → 注入合同金额/状态等真实台账。"""
    from app.models.settlement import Settlement

    db_session.add(Settlement(
        project_id="proj_ctx_1", milestone="completion",
        contract_amount=150000.0, actual_amount=145000.0,
        payable_amount=20000.0, status="pending_review",
    ))
    await db_session.commit()
    ctx = await _load_settlement_context(db_session, "proj_ctx_1")
    assert "150000" in ctx
    assert "pending_review" in ctx


@pytest.mark.asyncio
async def test_settlement_context_without_record(db_session):
    """#10 无结算单 → 诚实引导创建，不再让用户手抄合同信息。"""
    ctx = await _load_settlement_context(db_session, "proj_ctx_missing")
    assert "尚未创建结算单" in ctx


# ════════════════════════════════════════════════════════════════
# #12 结构化字段 markdown 分节提取
# ════════════════════════════════════════════════════════════════


def test_split_markdown_sections_and_pick():
    """#12 分节提取：各结构化字段取自对应小节而非全文复制。"""
    text = (
        "总价 15 万元整。\n\n"
        "## 一、预算明细\n水电 2 万，泥瓦 3 万。\n\n"
        "## 二、省钱建议\n瓷砖可自购省 5%。\n"
    )
    sections = _split_markdown_sections(text)
    assert "一、预算明细" in sections
    assert _pick_section(sections, ("明细",)) == "水电 2 万，泥瓦 3 万。"
    assert _pick_section(sections, ("省钱", "建议")) == "瓷砖可自购省 5%。"
    summary = _pick_section(sections, ("结论", "总价"))
    assert "15 万" in summary
    assert "省钱" not in summary  # summary 不再包含全文


def test_split_markdown_sections_no_heading():
    """#12 无标题回复 → 单节回退（mock/短回复路径）。"""
    sections = _split_markdown_sections("一句话回复")
    assert sections == {"": "一句话回复"}
    assert _pick_section(sections, ("明细",)) == "一句话回复"
