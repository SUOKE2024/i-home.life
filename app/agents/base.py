
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
    # v1.1.28 新增：fallback chain 第二档（Qwen 阿里云百炼 / DashScope）
    "qwen": {
        "api_base": lambda: settings.qwen_api_base,
        "api_key": lambda: settings.qwen_api_key,
        "model": lambda: settings.qwen_model,
        "chat_path": "/chat/completions",
    },
    # v1.1.28 新增：fallback chain 末端（Doubao 火山引擎 ARK）
    "doubao": {
        "api_base": lambda: settings.doubao_api_base,
        "api_key": lambda: settings.doubao_api_key,
        "model": lambda: settings.doubao_model,
        "chat_path": "/chat/completions",
    },
}

# v1.1.28 多 LLM fallback chain（借鉴索克生活 llm_fallback_chains）
# _chat 失败时按此顺序降级：主供应商 → qwen → glm → doubao
# 受 settings.llm_fallback_enabled feature flag 控制
DEFAULT_FALLBACK_CHAIN = ["qwen", "glm", "doubao"]


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
            api_key = cfg["api_key"]()
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            self._clients[provider] = httpx.AsyncClient(
                base_url=cfg["api_base"](),
                headers=headers,
                # 120s 容纳 DeepSeek-V4-Pro 推理模型的 reasoning + generation
                # v1.1.15 升级: deepseek-v4-pro 推理模型 max_tokens=8192，
                # 单次调用含 reasoning_content 可达 60-180s，Nginx 侧设 300s。
                timeout=httpx.Timeout(180.0),
            )
        return self._clients[provider]

    # ── 核心对话 ──────────────────────────────────────────────

    # content 为空时自动重试的最大次数（仅 finish_reason="length" 时触发）
    _EMPTY_CONTENT_RETRIES = 1

    async def _chat(self, messages: list[dict], max_retries: int = 0, with_tools: bool = False) -> str | dict:
        """调用 LLM，自动按 self.provider 路由到对应供应商。

        v1.1.28 新增：多 LLM fallback chain（借鉴索克生活 llm_fallback_chains）
        当主供应商调用失败（网络错误/5xx）时，按 DEFAULT_FALLBACK_CHAIN 降级到
        qwen → glm → doubao。受 settings.llm_fallback_enabled feature flag 控制。

        Args:
            messages: 对话消息列表
            max_retries: 最大重试次数（默认 0 — 推理模型单次调用可达 60-90s，
                重试会导致总耗时 >120s，对用户不可接受）
            with_tools: 是否启用 FunctionCall 工具调用

        Returns:
            str: 普通对话返回文本
            dict: 启用工具调用时返回 {"content": str, "tool_calls": [...]}

        Note:
            v1.1.1 新增 content 为空自动重试：当 LLM 返回 content="" 且
            finish_reason="length"（reasoning 占满 token 配额）时，自动重试
            ``_EMPTY_CONTENT_RETRIES`` 次。重试时温度降至 0.3 以减少 reasoning
            token 消耗，给 content 输出留出空间。
        """
        # v1.1.28: 构建本次调用的供应商链（主供应商 + fallback chain）
        primary = self.provider
        chain = [primary]
        if settings.llm_fallback_enabled:
            chain += [p for p in DEFAULT_FALLBACK_CHAIN if p != primary and p in PROVIDER_REGISTRY]

        last_error = None
        for provider in chain:
            try:
                return await self._chat_single_provider(
                    provider, messages, max_retries=max_retries, with_tools=with_tools
                )
            except Exception as e:
                last_error = e
                if provider != chain[-1]:
                    logger.warning(
                        "%s._chat: 供应商 %s 失败，降级到下一个 (error=%s)",
                        self.agent_name, provider, e,
                    )
                else:
                    logger.error(
                        "%s._chat: 全部供应商失败 (last=%s, error=%s)",
                        self.agent_name, provider, e,
                    )
        raise last_error

    async def _chat_single_provider(
        self,
        provider: str,
        messages: list[dict],
        max_retries: int = 0,
        with_tools: bool = False,
    ) -> str | dict:
        """单供应商 LLM 调用（_chat 的原始实现，v1.1.28 拆分以支持 fallback）。"""
        cfg = PROVIDER_REGISTRY[provider]

        # 无 API Key 时返回 mock 响应，避免空 Authorization header 或 401 错误
        if not cfg["api_key"]():
            logger.warning(
                "%s._chat: API key 为空，返回 mock 响应 (provider=%s)",
                self.agent_name, provider,
            )
            return f"[mock] {self.agent_name} 响应：API key 未配置"

        client = await self._get_client(provider)

        request_body = {
            "model": cfg["model"](),
            "messages": messages,
            "temperature": 0.7,
            # 8192 tokens 容纳 DeepSeek-V4-Pro 等推理模型的 reasoning_content
            # + 最终输出。2048 会导致 reasoning 占满 token 后输出被截断。
            "max_tokens": 8192,
        }

        if with_tools and self.tools:
            request_body["tools"] = self.tools
            request_body["tool_choice"] = "auto"

        last_error = None
        # 总尝试次数 = 网络错误重试 + content 为空重试 + 首次尝试
        total_attempts = max_retries + 1 + self._EMPTY_CONTENT_RETRIES
        empty_content_retries_used = 0
        for attempt in range(total_attempts):
            try:
                response = await client.post(cfg["chat_path"], json=request_body)
                response.raise_for_status()
                data = response.json()
                choice = data["choices"][0]
                msg = choice.get("message", {})

                # DeepSeek-V4-Pro / GLM-4.5+ 等 reasoning 模型可能将内容放在
                # reasoning_content 字段，content 字段为空。reasoning_content 是
                # LLM 内部思维链，不应作为用户回复返回。
                content = msg.get("content") or ""
                if not content:
                    reasoning_len = len(msg.get("reasoning_content", "") or "")
                    finish = choice.get("finish_reason")
                    logger.warning(
                        "%s._chat: content 为空 (attempt=%d, reasoning_len=%d, finish=%s)",
                        self.agent_name, attempt, reasoning_len, finish,
                    )
                    # v1.1.1: finish_reason="length" 表示 reasoning 占满 token，
                    # 降温重试可给 content 输出留出空间
                    if (finish == "length"
                            and empty_content_retries_used < self._EMPTY_CONTENT_RETRIES):
                        request_body["temperature"] = 0.3
                        empty_content_retries_used += 1
                        continue
                    content = (
                        "抱歉，AI 推理超时，请稍后重试或简化您的问题。"
                        f"(finish_reason={finish})"
                    )

                if with_tools:
                    result = {"content": content, "tool_calls": []}
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
                return content
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    import asyncio
                    await asyncio.sleep(1)
        raise last_error

    async def think(self, user_message: str, context: str = "", db=None, project_id: str = "") -> str:
        """高层封装：自动拼接 system prompt + 上下文 → LLM 调用。

        v1.1.28 新增：
        - AgenticRAG 证据检索（借鉴索克生活）：db 传入时前置检索知识库证据注入上下文
        - Model Spec HC 硬约束校验（借鉴索克生活 rebuttal_engine）：输出违规时注入反驳重生成
        """
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        # v1.1.28: AgenticRAG 证据注入
        evidence_context = ""
        if settings.agentic_rag_enabled and db is not None:
            try:
                from app.services.agentic_rag import agentic_rag
                evidence = await agentic_rag.retrieve(user_message, db=db, project_id=project_id)
                evidence_context = agentic_rag.build_evidence_context(evidence)
                if evidence_context:
                    messages.append({"role": "system", "content": evidence_context})
            except Exception as e:
                logger.debug("%s.think: AgenticRAG 检索失败（降级到无 RAG）: %s", self.agent_name, e)

        if context:
            messages.append({"role": "assistant", "content": context})
        messages.append({"role": "user", "content": user_message})

        reply = await self._chat(messages)

        # v1.1.28: Model Spec HC 硬约束校验 + 反驳重生成
        # v1.1.31 FP-9（S6）：升级为 check_output_with_semantic（关键词预筛 + LLM 语义兜底）
        if settings.model_spec_enabled and isinstance(reply, str):
            try:
                from app.services.rebuttal_engine import (
                    check_output_with_semantic, build_rebuttal_context,
                )
                result = await check_output_with_semantic(self.agent_name, reply, agent=self)
                if result["violated"]:
                    rebuttal = build_rebuttal_context(result["violations"])
                    logger.info(
                        "%s.think: HC 违规 %s，注入反驳重生成",
                        self.agent_name, [v["constraint_id"] for v in result["violations"]],
                    )
                    messages.append({"role": "assistant", "content": reply})
                    messages.append({"role": "system", "content": rebuttal})
                    reply = await self._chat(messages)
            except Exception as e:
                logger.debug("%s.think: rebuttal 校验失败（跳过）: %s", self.agent_name, e)

        return reply

    async def _chat_stream(self, messages: list[dict]):
        """流式调用 LLM，逐 chunk 产出 content 文本。

        使用 OpenAI 兼容的 ``stream: true`` 参数，服务端以 SSE 格式
        （``data: {json}\\n\\n``）推送增量 token。本方法仅 yield ``content``
        字段的增量文本，跳过 reasoning_content（推理模型的内部思维链）。
        """
        provider = self.provider
        cfg = PROVIDER_REGISTRY[provider]

        # 无 API Key 时返回 mock 流，避免 401 错误
        if not cfg["api_key"]():
            logger.warning(
                "%s._chat_stream: API key 为空，返回 mock 流 (provider=%s)",
                self.agent_name, provider,
            )
            yield f"[mock] {self.agent_name} 流式响应：API key 未配置"
            return

        client = await self._get_client(provider)

        request_body = {
            "model": cfg["model"](),
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 8192,
            "stream": True,
        }

        response = await client.send(
            client.build_request("POST", cfg["chat_path"], json=request_body),
            stream=True,
        )
        response.raise_for_status()

        async for line in response.aiter_lines():
            if not line or not line.startswith("data: "):
                continue
            payload = line[6:].strip()
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
            except (json.JSONDecodeError, TypeError):
                continue
            choice = chunk.get("choices", [{}])[0]
            delta = choice.get("delta", {})
            # 仅采集 content 字段，跳过 reasoning_content（内部思维链）
            piece = delta.get("content") or ""
            if piece:
                yield piece

    async def think_stream(self, user_message: str, context: str = ""):
        """流式版 think()：拼接 system prompt + 上下文 → 逐 chunk 产出。

        Usage::

            async for chunk in agent.think_stream("帮我设计客厅"):
                print(chunk, end="", flush=True)
        """
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        if context:
            messages.append({"role": "assistant", "content": context})
        messages.append({"role": "user", "content": user_message})
        async for chunk in self._chat_stream(messages):
            yield chunk

    async def think_with_tools(
        self, user_message: str, context: str = "", max_rounds: int | None = None,
        db=None, project_id: str = "",
    ) -> dict:
        """FunctionCall 增强版对话：支持多轮工具调用。

        v1.1.28 新增：
        - AgenticRAG 证据检索：db 传入时前置检索知识库证据注入上下文
        - Model Spec HC 硬约束校验：最终回复违规时注入反驳重生成

        Args:
            user_message: 用户消息
            context: 对话上下文
            max_rounds: 最大工具调用轮数（防止无限循环）
            db: 异步数据库会话（AgenticRAG 检索用，可选）
            project_id: 项目 ID（AgenticRAG 项目维度过滤，可选）

        Returns:
            {"final_reply": str, "tool_calls": [...], "rounds": int}
        """
        if not settings.agent_function_call_enabled or not self.tools:
            reply = await self.think(user_message, context, db=db, project_id=project_id)
            return {"final_reply": reply, "tool_calls": [], "rounds": 0}

        max_rounds = max_rounds or settings.agent_function_call_max_rounds

        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        # v1.1.28: AgenticRAG 证据注入
        if settings.agentic_rag_enabled and db is not None:
            try:
                from app.services.agentic_rag import agentic_rag
                evidence = await agentic_rag.retrieve(user_message, db=db, project_id=project_id)
                evidence_context = agentic_rag.build_evidence_context(evidence)
                if evidence_context:
                    messages.append({"role": "system", "content": evidence_context})
            except Exception as e:
                logger.debug("%s.think_with_tools: AgenticRAG 检索失败: %s", self.agent_name, e)

        if context:
            messages.append({"role": "assistant", "content": context})
        messages.append({"role": "user", "content": user_message})

        tool_calls_history = []
        rounds = 0

        for _round in range(max_rounds):
            result = await self._chat(messages, with_tools=True)
            tool_calls = result.get("tool_calls", []) if isinstance(result, dict) else []

            if not tool_calls:
                reply = result.get("content", "") if isinstance(result, dict) else result
                reply = await self._rebuttal_check(messages, reply)
                return {
                    "final_reply": reply,
                    "tool_calls": tool_calls_history,
                    "rounds": rounds,
                }

            # 执行工具调用
            def _tool_call_msg(tc):
                return {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc["arguments"], ensure_ascii=False),
                    },
                }

            if result.get("content"):
                messages.append({
                    "role": "assistant",
                    "content": result.get("content"),
                    "tool_calls": [_tool_call_msg(tc) for tc in tool_calls],
                })
            else:
                messages.append({
                    "role": "assistant",
                    "tool_calls": [_tool_call_msg(tc) for tc in tool_calls],
                })

            from app.services.agent_tool_registry import tool_registry

            for tc in tool_calls:
                # v1.1.31 FP-1: 注入隐式上下文 _db / _project_id，让工具 handler
                # 查真实 DB（受 settings.tool_real_data_enabled 控制）
                exec_result = await tool_registry.execute(
                    tc["name"], tc["arguments"],
                    _db=db, _project_id=project_id,
                )
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
        final_reply = await self._rebuttal_check(messages, final_reply)
        return {
            "final_reply": final_reply,
            "tool_calls": tool_calls_history,
            "rounds": rounds,
        }

    async def _rebuttal_check(self, messages: list[dict], reply: str) -> str:
        """v1.1.28: Model Spec HC 硬约束校验 + 反驳重生成（借鉴索克生活 rebuttal_engine）。

        v1.1.31 FP-9（S6）：升级为 check_output_with_semantic（关键词预筛 + LLM 语义兜底）。
        输出违规时注入反驳上下文重新调用 _chat 一次。校验失败或无违规时返回原 reply。
        """
        if not settings.model_spec_enabled or not isinstance(reply, str):
            return reply
        try:
            from app.services.rebuttal_engine import (
                check_output_with_semantic, build_rebuttal_context,
            )
            result = await check_output_with_semantic(self.agent_name, reply, agent=self)
            if result["violated"]:
                rebuttal = build_rebuttal_context(result["violations"])
                logger.info(
                    "%s: HC 违规 %s，注入反驳重生成",
                    self.agent_name, [v["constraint_id"] for v in result["violations"]],
                )
                messages.append({"role": "assistant", "content": reply})
                messages.append({"role": "system", "content": rebuttal})
                return await self._chat(messages)
        except Exception as e:
            logger.debug("%s: rebuttal 校验失败（跳过）: %s", self.agent_name, e)
        return reply

    # ── 资源清理 ──────────────────────────────────────────────

    async def close(self):
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()

    # ── L4 自适应学习（PRD §5.4 Phase 5 末项，提前布局）──

    @staticmethod
    async def get_user_preference_hint(
        user_id: str, agent_name: str, db=None, max_examples: int = 3
    ) -> str:
        """查询用户对该 agent 的历史正向反馈，构造 few-shot 示例提示。

        当 settings.agent_learning_enabled=True 时，由 chat 端点调用并拼接到
        user_message 前，让 LLM 参考用户过往满意回复的风格/内容偏好。

        Args:
            user_id: 用户 ID
            agent_name: Agent 名称（designer/budget/...）
            db: 异步数据库会话；为 None 时返回空字符串（兼容无 DB 场景）
            max_examples: 最大示例数

        Returns:
            few-shot 示例字符串；无正向反馈或未启用学习时返回空字符串
        """
        if not settings.agent_learning_enabled or db is None:
            return ""
        try:
            from sqlalchemy import select, desc
            from app.models.agent_feedback import AgentFeedback
            stmt = (
                select(AgentFeedback)
                .where(
                    AgentFeedback.user_id == user_id,
                    AgentFeedback.agent_name == agent_name,
                    AgentFeedback.feedback_type == "like",
                )
                .order_by(desc(AgentFeedback.created_at))
                .limit(max_examples)
            )
            result = await db.execute(stmt)
            rows = result.scalars().all()
            if not rows:
                return ""
            examples = []
            for r in rows:
                # 截断避免 prompt 过长
                um = r.user_message[:200]
                ar = r.agent_reply[:400]
                examples.append(f"用户: {um}\n优质回复: {ar}")
            return (
                "以下是该用户过往满意回复示例，请参考其风格与内容偏好：\n\n"
                + "\n\n---\n\n".join(examples)
                + "\n\n---\n\n"
            )
        except Exception as e:
            logger.warning("BaseAgent.get_user_preference_hint 失败: %s", e)
            return ""


# ── preference hint 缓存包装（v1.1.27 性能优化）──
# 每次 chat 端点调用 get_user_preference_hint 查 AgentFeedback 表，
# 缓存后避免重复 DB 查询。用户提交新反馈时主动失效。

async def get_pref_hint_cached(
    user_id: str, agent_name: str, db=None, max_examples: int = 3
) -> str:
    """带缓存的 preference hint 查询。

    缓存 key 仅基于 user_id + agent_name + max_examples，忽略 db session。
    TTL 由 settings.pref_hint_cache_ttl 控制（默认 300s）。
    feature flag cache_decorators_enabled=False 或 TTL<=0 时直透不缓存。

    用户提交新反馈后调用 invalidate_pref_hint_cache 主动失效。
    """
    _settings = get_settings()
    if not _settings.cache_decorators_enabled or _settings.pref_hint_cache_ttl <= 0:
        return await BaseAgent.get_user_preference_hint(user_id, agent_name, db, max_examples)

    from app.services.cache_service import cache
    cache_key = f"pref_hint:{user_id}:{agent_name}:{max_examples}"

    cached_val = await cache.get(cache_key)
    if cached_val is not None:
        try:
            from app.metrics import cache_hits_total
            cache_hits_total.labels(key_prefix="pref_hint").inc()
        except Exception:
            pass
        return cached_val

    try:
        from app.metrics import cache_misses_total
        cache_misses_total.labels(key_prefix="pref_hint").inc()
    except Exception:
        pass

    result = await BaseAgent.get_user_preference_hint(user_id, agent_name, db, max_examples)
    await cache.set(cache_key, result, ttl=_settings.pref_hint_cache_ttl)
    return result


async def invalidate_pref_hint_cache(
    user_id: str, agent_name: str, max_examples: int = 3
) -> None:
    """用户提交新反馈后主动失效 preference hint 缓存。

    在 POST /api/agents/feedback 端点 db.commit() 之后调用。
    """
    from app.services.cache_service import cache
    await cache.delete(f"pref_hint:{user_id}:{agent_name}:{max_examples}")
