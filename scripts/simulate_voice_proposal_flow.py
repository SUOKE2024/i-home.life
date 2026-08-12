#!/usr/bin/env python3
"""模拟语音指令测试：帮我设计厨房 → 方案B加中岛（完整 WS 流程）

v1.2.8 讨论式方案交互全链路模拟：
1. 注册/登录测试账号 → 拿 PASETO token
2. 连接 /api/voice/realtime WS（文本输入 = 模拟语音转写结果）
3. 发送「帮我设计厨房」→ 期望 LLM 调用 generate_design_proposals → 收到 proposal_generated
4. 发送「方案B加中岛」→ 期望 LLM 调用 update_design_proposal → 收到 proposal_updated
5. 输出流程验证结果

用法：python scripts/simulate_voice_proposal_flow.py [base_url]
默认 base_url=http://127.0.0.1:8000
"""
import asyncio
import json
import os
import sys
import uuid

import httpx
import websockets

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
WS_URL = BASE_URL.replace("http", "ws", 1) + "/api/voice/realtime"

PHONE = "138" + str(uuid.uuid4().int)[:8]
PASSWORD = "Test@voice2026"


async def register_and_login() -> str:
    """注册测试账号并返回 token"""
    async with httpx.AsyncClient(timeout=30) as client:
        # 注册
        reg = await client.post(f"{BASE_URL}/api/auth/register", json={
            "phone": PHONE,
            "password": PASSWORD,
            "name": "语音流程模拟测试",
        })
        if reg.status_code == 409:
            # 已存在则登录
            login = await client.post(f"{BASE_URL}/api/auth/login", json={
                "phone": PHONE,
                "password": PASSWORD,
            })
            login.raise_for_status()
            token = login.json()["access_token"]
        else:
            reg.raise_for_status()
            token = reg.json()["access_token"]
        print(f"[1] 注册/登录成功 phone={PHONE}")
        return token


async def send_and_collect(ws, text: str, wait_seconds: float = 30.0) -> list[dict]:
    """发送文本指令并收集事件"""
    await ws.send(json.dumps({"type": "text", "content": text}))
    events: list[dict] = []
    try:
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=wait_seconds)
            evt = json.loads(raw)
            etype = evt.get("type", "")
            # 收集所有事件（用于调试）；关键事件触发提前结束
            events.append(evt)
            if etype in ("proposal_generated", "proposal_updated", "error"):
                break
            if etype == "response_done":
                break
    except asyncio.TimeoutError:
        print(f"    ⚠️ 等待事件超时（{wait_seconds}s）")
    return events


def summarize(events: list[dict], full: bool = False) -> None:
    for evt in events:
        etype = evt.get("type", "")
        if full:
            print(f"    · {etype}: {json.dumps(evt, ensure_ascii=False)[:300]}")
            continue
        if etype == "tool_call":
            print(f"    · tool_call: {evt.get('name')} result_keys={list((evt.get('result') or {}).keys())[:6]}")
        elif etype == "proposal_generated":
            props = evt.get("proposals", [])
            print(f"    · proposal_generated: {len(props)} 套方案")
            for p in props:
                print(f"      - [{p.get('proposal_id')}] {p.get('name', '')} 预算={p.get('budget_cny')}元 亮点={str(p.get('highlights', ''))[:60]}")
        elif etype == "proposal_updated":
            p = evt.get("proposal", {})
            print(f"    · proposal_updated: [{p.get('proposal_id')}] name={p.get('name')} 变更={str(p.get('changelog', []))[:80]}")
        elif etype == "error":
            print(f"    · error: {evt.get('message')}")
        elif etype == "reply":
            print(f"    · reply: {str(evt.get('text'))[:80]}")
        elif etype == "transcript_done":
            print(f"    · transcript_done: {str(evt.get('text'))[:80]}")
        elif etype == "response_done":
            print(f"    · response_done: usage={evt.get('usage')}")
        else:
            # 其他事件简要打印（调试用）
            brief = json.dumps(evt, ensure_ascii=False)[:120]
            print(f"    · {etype}: {brief}")


async def main() -> None:
    token = await register_and_login()

    async with websockets.connect(f"{WS_URL}?token={token}", open_timeout=30, ping_interval=20) as ws:
        # 连接欢迎消息
        welcome = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
        print(f"[2] WS 连接成功 mode={welcome.get('mode')} session={welcome.get('session_id')[:8]} "
              f"model={welcome.get('model')} tool_call_enabled={welcome.get('tool_call_enabled')}")

        # ── 第一步：帮我设计厨房 ──
        print("\n[3] 模拟语音指令 → 「帮我设计厨房」")
        events = await send_and_collect(ws, "帮我设计一个现代风格的厨房，要中岛台")
        summarize(events)
        generated = [e for e in events if e.get("type") == "proposal_generated"]
        if not generated:
            print("    ❌ 未收到 proposal_generated 事件，流程中断")
            return
        print("    ✅ 方案生成成功")

        # 清空工具调用后模型的确认响应等挂起事件，避免污染下一条指令
        # 注意：工具执行后 send_function_call_output 会触发 R2（确认响应），
        # R1（function_call 响应）和 R2 各有一个 response.done，须全部消费完。
        print("    （排空所有挂起事件…）")
        drained: list[dict] = []
        try:
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                evt = json.loads(raw)
                drained.append(evt)
        except asyncio.TimeoutError:
            pass
        for evt in drained:
            print(f"    · 已消费: {evt.get('type')}")
        print(f"    · 共排空 {len(drained)} 个挂起事件")

        # ── 第二步：方案B加中岛 ──
        print("\n[4] 模拟语音指令 → 「方案B加中岛」")
        events2 = await send_and_collect(ws, "方案B加一个中岛台", wait_seconds=40)
        summarize(events2, full=True)
        # 打印 response.done 完整内容（含模型实际输出）
        for evt in events2:
            if evt.get("type") == "response_done":
                # 前端事件已简化，无法看到完整 output；此处仅提示
                print("    （前端 response_done 已简化，详情见后端日志）")
        updated = [e for e in events2 if e.get("type") == "proposal_updated"]
        if not updated:
            print("    ❌ 未收到 proposal_updated 事件")
            return
        prop = updated[0].get("proposal", {})
        print(f"    ✅ 方案修订成功 [{prop.get('proposal_id')}] 变更记录: {str(prop.get('changelog'))[:100]}")

    # ── 汇总 ──
    print("\n" + "=" * 50)
    print("🎉 完整流程验证通过：帮我设计厨房 → 方案B加中岛")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
