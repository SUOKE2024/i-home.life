from typing import AsyncGenerator

import httpx

from app.config import get_settings

settings = get_settings()


class BaseAgent:
    agent_name: str = "base"
    system_prompt: str = ""

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=settings.deepseek_api_base,
                headers={
                    "Authorization": f"Bearer {settings.deepseek_api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(60.0),
            )
        return self._client

    async def _chat(self, messages: list[dict], max_retries: int = 1) -> str:
        client = await self._get_client()
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                response = await client.post(
                    "/v1/chat/completions",
                    json={
                        "model": settings.deepseek_model,
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
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        if context:
            messages.append({"role": "assistant", "content": context})
        messages.append({"role": "user", "content": user_message})
        return await self._chat(messages)

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
