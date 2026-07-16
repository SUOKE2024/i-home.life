
import json
import logging

import httpx

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

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
    """AI Agent 基类 —— 支持多 LLM 供应商 + FunctionCall 工具调用。

    Usage::

        class MyAgent(BaseAgent):
            agent_name = "designer"
            system_prompt = "你是一个室内设计师..."
            provider = "deepseek"
            tools = [...]  # 可选，工具列表

        agent = MyAgent()
        reply = await agent.think("帮我设计一个客厅方案")
        # 支持 FunctionCall
        result = await agent.think_with_tools("120平北欧风预算多少？")
        await agent.close()
    """

    agent_name: str = "base"
    system_prompt: str = ""
    provider: str = "deepseek"  # "deepseek" | "glm"
    tools: list[dict] = []       # FunctionCall 工具 schema 列表

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

    async def _chat(self, messages: list[dict], max_retries: int = 1, with_tools: bool = False) -> str | dict:
        """调用 LLM，自动按 self.provider 路由到对应供应商。

        Args:
            messages: 对话消息列表
            max_retries: 最大重试次数
            with_tools: 是否启用 FunctionCall 工具调用

        Returns:
            str: 普通对话返回文本
            dict: 启用工具调用时返回 {"content": str, "tool_calls": [...]}
        """
        provider = self.provider
        cfg = PROVIDER_REGISTRY[provider]
        client = await self._get_client(provider)

        request_body = {
            "model": cfg["model"](),
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2048,
        }

        if with_tools and self.tools:
            request_body["tools"] = self.tools
            request_body["tool_choice"] = "auto"

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                response = await client.post(cfg["chat_path"], json=request_body)
                response.raise_for_status()
                data = response.json()
                choice = data["choices"][0]
                msg = choice.get("message", {})

                if with_tools:
                    result = {"content": msg.get("content", ""), "tool_calls": []}
                    tool_calls = msg.get("tool_calls", [])
                    for tc in tool_calls:
                        func = tc.get("function", {})
                        try:
                            args = json.loads(func.get("arguments", "{}"))
                        except (json.JSONDecodeError, TypeError):
                            args = {}
                        result["tool_calls"].append({
                            "id": tc.get("id", ""),
                            "name": func.get("name", ""),
                            "arguments": args,
                        })
                    return result
                return msg.get("content", "")
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

    async def think_with_tools(
        self, user_message: str, context: str = "", max_rounds: int | None = None
    ) -> dict:
        """FunctionCall 增强版对话：支持多轮工具调用。

        Args:
            user_message: 用户消息
            context: 对话上下文
            max_rounds: 最大工具调用轮数（防止无限循环）

        Returns:
            {"final_reply": str, "tool_calls": [...], "rounds": int}
        """
        if not settings.agent_function_call_enabled or not self.tools:
            reply = await self.think(user_message, context)
            return {"final_reply": reply, "tool_calls": [], "rounds": 0}

        max_rounds = max_rounds or settings.agent_function_call_max_rounds

        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        if context:
            messages.append({"role": "assistant", "content": context})
        messages.append({"role": "user", "content": user_message})

        tool_calls_history = []
        rounds = 0

        for _round in range(max_rounds):
            result = await self._chat(messages, with_tools=True)
            tool_calls = result.get("tool_calls", []) if isinstance(result, dict) else []

            if not tool_calls:
                return {
                    "final_reply": result.get("content", "") if isinstance(result, dict) else result,
                    "tool_calls": tool_calls_history,
                    "rounds": rounds,
                }

            # 执行工具调用
            messages.append({"role": "assistant", "content": result.get("content"), "tool_calls": [
                {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"], ensure_ascii=False)}}
                for tc in tool_calls
            ]} if result.get("content") else {"role": "assistant", "tool_calls": [
                {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"], ensure_ascii=False)}}
                for tc in tool_calls
            ]})

            from app.services.agent_tool_registry import tool_registry

            for tc in tool_calls:
                exec_result = await tool_registry.execute(tc["name"], tc["arguments"])
                tool_calls_history.append({
                    "tool": tc["name"],
                    "arguments": tc["arguments"],
                    "result": exec_result,
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(exec_result, ensure_ascii=False),
                })

            rounds += 1

        # 达到最大轮数仍未完成，强制生成最终回复
        messages.append({"role": "user", "content": "请根据以上工具调用结果给出最终回复。"})
        final_reply = await self._chat(messages)
        return {
            "final_reply": final_reply,
            "tool_calls": tool_calls_history,
            "rounds": rounds,
        }

    # ── 资源清理 ──────────────────────────────────────────────

    async def close(self):
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()
