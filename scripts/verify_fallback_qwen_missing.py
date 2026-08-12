#!/usr/bin/env python3
"""验证 fallback 逻辑：模拟 QWEN_API_KEY 缺失场景，验证降级链真实触发

场景设计：
- qwen_api_key 置空（模拟生产 QWEN_API_KEY 缺失，本地本就为空）
- glm_api_key 注入生产 key（有效但余额不足 → 可证明 GLM 被真实尝试调用）
- doubao_api_key 保持空（未配置，应跳过）
- deepseek_api_key 使用本地有效 key（最终兜底成功）

预期链路：qwen(无key跳过) → glm(尝试调用，余额不足失败) → doubao(无key跳过) → deepseek(成功)
"""
import asyncio
import logging
import sys

sys.path.insert(0, ".")
from app.config import get_settings  # noqa: E402
from app.agents.base import BaseAgent, PROVIDER_REGISTRY  # noqa: E402

# 配置日志输出，便于观察 provider 选择
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
for name in ("app.agents.base", "urllib3", "httpx"):
    lg = logging.getLogger(name)
    lg.setLevel(logging.INFO)


class TestAgent(BaseAgent):
    agent_name = "fallback_test"
    system_prompt = "你是测试助手"
    provider = "deepseek"


async def main() -> None:
    settings = get_settings()

    # ── 构造场景 ──
    # 1. QWEN_API_KEY 缺失（模拟生产配置缺失）
    settings.qwen_api_key = ""
    # 2. GLM 注入生产 key（有效但余额不足，验证真实尝试调用）
    settings.glm_api_key = "cde4e34c5e8143c79038abb2eb3d7999.iZwVDBOk3aYgJ8ef"
    # 3. Doubao 未配置（保持空，应被跳过）
    settings.doubao_api_key = ""
    # 4. Deepseek 使用本地有效 key（兜底）
    #    本地 .env 已配置，无需修改

    print("=" * 60)
    print("场景：QWEN_API_KEY 缺失 | GLM 有key(余额不足) | DOUBAO 无key | DEEPSEEK 有key")
    print(f"  qwen_api_key   = {'<空>' if not settings.qwen_api_key else settings.qwen_api_key[:8]}")
    print(f"  glm_api_key    = {'<空>' if not settings.glm_api_key else settings.glm_api_key[:8]}")
    print(f"  doubao_api_key = {'<空>' if not settings.doubao_api_key else settings.doubao_api_key[:8]}")
    print(f"  deepseek_api_key = {'<空>' if not settings.deepseek_api_key else settings.deepseek_api_key[:8]}")
    print("=" * 60)

    agent = TestAgent()
    # economy 档：链变为 [qwen, glm, deepseek]（qwen/glm 低成本优先，deepseek 兜底），
    # 才能触发「qwen 缺失 → glm → deepseek」的降级路径
    agent.cost_tier = "economy"

    # 验证单供应商：qwen 无 key 应抛 ConnectionError
    print("\n[1] _chat_single_provider('qwen') 无 key → 期望抛 ConnectionError")
    try:
        await agent._chat_single_provider("qwen", [{"role": "user", "content": "hi"}])
        print("    ❌ 未抛异常（不符合预期）")
    except ConnectionError as e:
        print(f"    ✅ 抛 ConnectionError: {e}")

    # 验证完整降级链
    print("\n[2] _chat() 完整降级链 → 期望最终 deepseek 成功返回")
    result = await agent._chat([{"role": "user", "content": "你好，用一句话自我介绍"}])
    print(f"    ✅ 返回: {str(result)[:100]}")
    assert isinstance(result, str) and result, "结果不应为空"
    if "[mock]" in result:
        print("    ⚠️ 返回了 mock（不应出现，deepseek 有 key）")
    else:
        print("    ✅ 非 mock 真实回复，降级链正常结束于 deepseek")

    print("\n" + "=" * 60)
    print("验证完成：查看上方日志确认降级顺序 qwen→glm→(doubao跳过)→deepseek")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
