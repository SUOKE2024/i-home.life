#!/usr/bin/env python3
"""全量 LLM 连通性测试 — 验证所有 Agent 的 DeepSeek V4 Pro API 调用"""

import asyncio

async def main():
    from app.api.agents import MOCK_MODE
    from app.config import get_settings

    s = get_settings()
    print(f"MOCK_MODE:      {MOCK_MODE}")
    print(f"DeepSeek Key:   {'***' + s.deepseek_api_key[-4:] if s.deepseek_api_key else '(未配置)'}")
    print(f"DeepSeek Model: {s.deepseek_model}")
    print(f"GLM Key:        {'***' + s.glm_api_key[-4:] if s.glm_api_key else '(未配置)'}")
    print()

    # 代理初始化
    from app.agents.designer import DesignerAgent
    from app.agents.budget import BudgetAgent
    from app.agents.procurement import ProcurementAgent
    from app.agents.construction import ConstructionAgent
    from app.agents.settlement import SettlementAgent
    from app.agents.qa_inspector import QAInspectorAgent
    from app.agents.concierge import ConciergeAgent
    from app.agents.orchestrator import OrchestratorAgent

    agents_info = [
        ("designer",      DesignerAgent()),
        ("budget",        BudgetAgent()),
        ("procurement",   ProcurementAgent()),
        ("construction",  ConstructionAgent()),
        ("settlement",    SettlementAgent()),
        ("qa_inspector",  QAInspectorAgent()),
        ("concierge",     ConciergeAgent()),
        ("orchestrator",  OrchestratorAgent()),
    ]

    print(f"{'Agent':20s} {'Provider':12s} {'Tools':>6s} {'Status'}")
    print("-" * 55)
    for name, agent in agents_info:
        tools_count = len(getattr(agent, "tools", []))
        print(f"{name:20s} {agent.provider:12s} {tools_count:6d}  initializing...")

    # 真实 LLM 调用测试 — Designer
    print("\n--- DesignerAgent 真实 LLM 测试 ---")
    des = DesignerAgent()
    try:
        reply = await des.think("请用一句话描述北欧风格装修的特点", "用户: 测试用户")
        print(f"Reply ({len(reply)} chars): {reply[:300]}")
        print("DESIGNER: OK")
    except Exception as e:
        print(f"DESIGNER: FAILED — {e}")
    finally:
        await des.close()

    # BudgetAgent 测试
    print("\n--- BudgetAgent 真实 LLM 测试 ---")
    bud = BudgetAgent()
    try:
        reply = await bud.think("120平米三室两厅北欧风格预算大概多少？", "项目: 北京朝阳区新房装修")
        print(f"Reply ({len(reply)} chars): {reply[:300]}")
        print("BUDGET: OK")
    except Exception as e:
        print(f"BUDGET: FAILED — {e}")
    finally:
        await bud.close()

    # Orchestrator 意图分类测试
    print("\n--- OrchestratorAgent 意图分类测试 ---")
    orch = OrchestratorAgent()
    try:
        # Only test classification, not full chat
        result = await orch.classify_intent("我想设计一个新中式的三室两厅")
        intent = result.get("intent", "unknown")
        print(f"Intent: {intent}   Confidence: {result.get('confidence', 'N/A')}")
        print("ORCHESTRATOR: OK")
    except Exception as e:
        print(f"ORCHESTRATOR: FAILED — {e}")
    finally:
        await orch.close()

    # Concierge 测试
    print("\n--- ConciergeAgent 真实 LLM 测试 ---")
    conc = ConciergeAgent()
    try:
        reply = await conc.generate_response("装修前需要做哪些准备工作？", "业主: 测试用户")
        print(f"Reply ({len(reply)} chars): {reply[:300]}")
        print("CONCIERGE: OK")
    except Exception as e:
        print(f"CONCIERGE: FAILED — {e}")
    finally:
        await conc.close()

    # ProcurementAgent with FunctionCall tools
    print("\n--- ProcurementAgent FunctionCall 测试 ---")
    from app.agents.procurement import ProcurementAgent
    proc = ProcurementAgent()
    try:
        r = await proc.think_with_tools("我需要采购一批北欧风格的实木地板和乳胶漆，帮我推荐供应商", "项目: 120平米新房装修 预算30万")
        print(f"Reply ({len(r['final_reply'])} chars): {r['final_reply'][:250]}")
        if r.get("tool_calls"):
            print(f"Tool calls: {len(r['tool_calls'])}")
        print("PROCUREMENT: OK")
    except Exception as e:
        print(f"PROCUREMENT: FAILED — {e}")
    finally:
        await proc.close()

    # ConstructionAgent with FunctionCall tools
    print("\n--- ConstructionAgent FunctionCall 测试 ---")
    from app.agents.construction import ConstructionAgent
    cons = ConstructionAgent()
    try:
        r = await cons.think_with_tools("水电改造阶段需要注意什么？", "项目: 北京朝阳区新房 施工阶段: 水电改造")
        print(f"Reply ({len(r['final_reply'])} chars): {r['final_reply'][:250]}")
        if r.get("tool_calls"):
            print(f"Tool calls: {len(r['tool_calls'])}")
        print("CONSTRUCTION: OK")
    except Exception as e:
        print(f"CONSTRUCTION: FAILED — {e}")
    finally:
        await cons.close()

    # QAInspectorAgent with FunctionCall tools
    print("\n--- QAInspectorAgent FunctionCall 测试 ---")
    from app.agents.qa_inspector import QAInspectorAgent
    qai = QAInspectorAgent()
    try:
        r = await qai.think_with_tools("墙面刷漆阶段有哪些常见质量问题？", "项目: 120平米精装修 当前阶段: 墙面处理")
        print(f"Reply ({len(r['final_reply'])} chars): {r['final_reply'][:250]}")
        if r.get("tool_calls"):
            print(f"Tool calls: {len(r['tool_calls'])}")
        print("QA_INSPECTOR: OK")
    except Exception as e:
        print(f"QA_INSPECTOR: FAILED — {e}")
    finally:
        await qai.close()

    # SettlementAgent
    print("\n--- SettlementAgent 测试 ---")
    from app.agents.settlement import SettlementAgent
    sett = SettlementAgent()
    try:
        r = await sett.think("装修完工后如何进行最终结算？", "项目: 已完成施工 总预算30万")
        print(f"Reply ({len(r)} chars): {r[:250]}")
        print("SETTLEMENT: OK")
    except Exception as e:
        print(f"SETTLEMENT: FAILED — {e}")
    finally:
        await sett.close()

    print("\n=== 全量 LLM 测试完成 ===")

if __name__ == "__main__":
    asyncio.run(main())
