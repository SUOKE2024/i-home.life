#!/usr/bin/env python3
"""Agent 真实 LLM E2E 测试"""
import asyncio, time
from app.agents.designer import DesignerAgent
from app.agents.budget import BudgetAgent
from app.agents.concierge import ConciergeAgent
from app.agents.settlement import SettlementAgent

async def test():
    agents = [
        ("designer", DesignerAgent(), "一句话描述北欧风格"),
        ("budget", BudgetAgent(), "120平米装修预算范围？简答"),
        ("concierge", ConciergeAgent(), "装修第一步做什么？"),
        ("settlement", SettlementAgent(), "装修完工结算注意什么？"),
    ]
    results = []
    for name, agent, msg in agents:
        t0 = time.time()
        try:
            reply = await agent.think(msg, "测试用户")
            elapsed = int(time.time() - t0)
            print(f"OK  {name:20s} ({elapsed}s, {len(reply)} chars) -> {reply[:100]}")
            results.append((name, True))
        except Exception as e:
            elapsed = int(time.time() - t0)
            print(f"FAIL {name:20s} ({elapsed}s) -> {e}")
            results.append((name, False))
        finally:
            await agent.close()
    passed = sum(1 for _, ok in results if ok)
    print(f"\nAgent E2E: {passed}/{len(results)} passed")
    return passed == len(results)

if __name__ == "__main__":
    ok = asyncio.run(test())
    exit(0 if ok else 1)
