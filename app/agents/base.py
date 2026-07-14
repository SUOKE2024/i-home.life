
import httpx

from app.config import get_settings

settings = get_settings()

# ── 供应商注册表 ──────────────────────────────────────────────
# 每个供应商约定的 API 路径均为 OpenAI 兼容风格
PROVIDER_REGISTRY = {
    "deepseek": {
        "api_base": lambda: settings.deepseek_api_base,
        "api_key": lambda: settings.deepseek_api_key,
        "model": lambda: settings.deepseek_model,
        "chat_path": "/v1/chat/completions",
    },
    "glm": {
        "api_base": lambda: settings.glm_api_base,
        "api_key": lambda: settings.glm_api_key,
        "model": lambda: settings.glm_model,
        "chat_path": "/chat/completions",
    },
}


class BaseAgent:
    """AI Agent 基类 —— 支持多 LLM 供应商（DeepSeek V4 / GLM-5.2）。

    Usage::

        class MyAgent(BaseAgent):
            agent_name = "designer"
            system_prompt = "你是一个室内设计师..."
            provider = "deepseek"   # 默认；可覆盖为 "glm"

        agent = MyAgent()
        reply = await agent.think("帮我设计一个客厅方案")
        await agent.close()
    """

    agent_name: str = "base"
    system_prompt: str = ""
    provider: str = "deepseek"  # "deepseek" | "glm"

    def __init__(self):
        self._clients: dict[str, httpx.AsyncClient] = {}

    # ── 客户端管理 ────────────────────────────────────────────

    async def _get_client(self, provider: str | None = None) -> httpx.AsyncClient:
        """按供应商惰性创建 httpx.AsyncClient，复用连接。"""
        provider = provider or self.provider
        if provider not in self._clients:
            cfg = PROVIDER_REGISTRY[provider]
            self._clients[provider] = httpx.AsyncClient(
                base_url=cfg["api_base"](),
                headers={
                    "Authorization": f"Bearer {cfg['api_key']()}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(60.0),
            )
        return self._clients[provider]

    # ── 核心对话 ──────────────────────────────────────────────

    async def _chat(self, messages: list[dict], max_retries: int = 1) -> str:
        """调用 LLM，自动按 self.provider 路由到对应供应商。"""
        provider = self.provider
        cfg = PROVIDER_REGISTRY[provider]
        client = await self._get_client(provider)

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                response = await client.post(
                    cfg["chat_path"],
                    json={
                        "model": cfg["model"](),
                        "messages": messages,
                        "temperature": 0.7,
                        "max_tokens": 2048,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    import asyncio

                    await asyncio.sleep(1)
        raise last_error

    async def think(self, user_message: str, context: str = "") -> str:
        """高层封装：自动拼接 system prompt + 上下文 → LLM 调用。"""
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        if context:
            messages.append({"role": "assistant", "content": context})
        messages.append({"role": "user", "content": user_message})
        return await self._chat(messages)

    # ── 资源清理 ──────────────────────────────────────────────

    async def close(self):
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()
