
import asyncio
import json
import logging
import time
from typing import Any

import httpx

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def _record_llm_span(agent: str, provider: str, started_at: float, status: str, fallback: bool) -> None:
    """v1.10.x 全链路诊断：记录 LLM/Agent 子 span（best-effort，失败零影响）。"""
    try:
        from app.services.diagnostics_service import record_llm_span
        record_llm_span(
            agent=agent, provider=provider,
            latency_ms=(time.perf_counter() - started_at) * 1000,
            status=status, fallback=fallback,
        )
    except Exception:
        pass  # 诊断采集失败不应影响业务


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
    # v1.4.x 新增：施工边缘盒子本地推理端点（Ollama/LocalAI 等 OpenAI 兼容）
    # 无 API key 时自动跳过（不产生 mock），由 _resolve_chain 后续供应商接管
    "local": {
        "api_base": lambda: settings.local_llm_api_base,
        "api_key": lambda: settings.local_llm_api_key,
        "model": lambda: settings.local_llm_model,
        "chat_path": "/chat/completions",
    },
}

# v1.1.28 多 LLM fallback chain（借鉴索克生活 llm_fallback_chains）
# _chat 失败时按此顺序降级：主供应商 → qwen → glm → doubao
# 受 settings.llm_fallback_enabled feature flag 控制
DEFAULT_FALLBACK_CHAIN = ["qwen", "glm", "doubao"]


def _accumulate_usage(total_usage: dict, result: str | dict) -> None:
    """v1.13.1（2026 成本追踪）：累计单轮 LLM usage 到 total_usage。

    with_tools 返回 dict（含 usage 字段）时累加；普通 str 响应跳过。
    """
    if isinstance(result, dict):
        usage = result.get("usage") or {}
        total_usage["prompt_tokens"] += int(usage.get("prompt_tokens", 0) or 0)
        total_usage["completion_tokens"] += int(usage.get("completion_tokens", 0) or 0)
        total_usage["total_tokens"] += int(usage.get("total_tokens", 0) or 0)


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

    # v1.4.x 意图成本路由（借鉴 EY token strategy）：
    # "standard"=默认档（主供应商）；"economy"=低成本档（qwen/glm 优先，
    # 受 settings.cost_tiered_routing_enabled 控制，原主供应商保留兜底）。
    cost_tier: str = "standard"

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
        # v1.4.x: 意图成本路由 — economy 档优先低成本供应商
        chain = self._resolve_chain()

        # v1.12.x: LLM 响应缓存（对齐 2026「缓存确定性 subtask 结果」）
        # 仅缓存非工具调用的确定性请求（相同 agent+messages → 相同回复），
        # TTL 内重复请求直接命中，避免相同确定性子任务重复调用 LLM。
        # 工具调用（with_tools=True）有副作用，一律不缓存。
        # v1.13.5: 抽至 _try_read_llm_cache 以降 _chat 圈复杂度（C901 18→14）。
        cached, cache_key = await self._try_read_llm_cache(messages, with_tools)
        if cached is not None:
            return cached

        last_error = None
        no_key_providers: list[str] = []
        for provider in chain:
            _provider_started = time.perf_counter()
            try:
                result = await self._chat_single_provider(
                    provider, messages, max_retries=max_retries, with_tools=with_tools
                )
                _record_llm_span(self.agent_name, provider, _provider_started, "ok", fallback=False)
                # 成功且为字符串响应 → 写缓存（best-effort）
                await self._try_write_llm_cache(cache_key, result)
                return result
            except ConnectionError as e:
                # v1.13.2: 未配置 API key 的供应商抛 ConnectionError 跳过，
                # 继续 fallback 到链内下一个供应商（不再中断降级链返回 mock）。
                if "API key unset" in str(e):
                    self._record_tier_usage(self.cost_tier, self.agent_name, provider, "no_key")
                    no_key_providers.append(provider)
                    if provider != chain[-1]:
                        logger.warning(
                            "%s._chat: 供应商 %s 未配置 API key，跳过降级 (error=%s)",
                            self.agent_name, provider, e,
                        )
                    continue
                last_error = e
                _record_llm_span(
                    self.agent_name, provider, _provider_started, "error",
                    fallback=provider != chain[-1],
                )
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
            except Exception as e:
                last_error = e
                _record_llm_span(
                    self.agent_name, provider, _provider_started, "error",
                    fallback=provider != chain[-1],
                )
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

        # 整条链全部未配置 API key → 兜底返回 mock（诚实降级标注，不抛异常）
        if no_key_providers and len(no_key_providers) == len(chain) and last_error is None:
            logger.warning(
                "%s._chat: 全部供应商未配置 API key，返回 mock 兜底 (providers=%s)",
                self.agent_name, no_key_providers,
            )
            mock_text = f"[mock] {self.agent_name} 响应：API key 未配置"
            if with_tools:
                return {"content": mock_text, "tool_calls": []}
            return mock_text
        raise last_error

    async def _try_read_llm_cache(self, messages: list[dict], with_tools: bool) -> tuple[str | None, str | None]:
        """读取 LLM 确定性响应缓存（best-effort，v1.13.5 自 _chat 抽出以降圈复杂度）。

        仅缓存非工具调用（with_tools=False）的确定性请求。返回 (cached, cache_key)：
        命中返回 (cached, cache_key)；未命中返回 (None, cache_key) 供成功后回写；
        禁用或异常返回 (None, None) 直通 LLM，不影响主流程。
        """
        if with_tools or not settings.llm_response_cache_enabled or settings.llm_response_cache_ttl <= 0:
            return None, None
        try:
            cache_key = self._build_llm_cache_key(messages)
            from app.services.cache_service import cache
            cached = await cache.get(cache_key)
            if cached is not None:
                self._record_tier_usage(self.cost_tier, self.agent_name, self.provider, "cache_hit")
            return cached, cache_key
        except Exception as e:
            logger.debug("%s._chat: 缓存读取失败（直通 LLM）: %s", self.agent_name, e)
            return None, None

    async def _try_write_llm_cache(self, cache_key: str | None, result: str | dict) -> None:
        """写 LLM 响应缓存（best-effort，v1.13.5 自 _chat 抽出以降圈复杂度）。

        仅写字符串响应；失败仅 debug 日志，不阻断主流程。
        """
        if cache_key is None or not isinstance(result, str):
            return
        try:
            from app.services.cache_service import cache
            await cache.set(cache_key, result, ttl=settings.llm_response_cache_ttl)
        except Exception as e:
            logger.debug("%s._chat: 缓存写入失败（忽略）: %s", self.agent_name, e)

    def _build_llm_cache_key(self, messages: list[dict]) -> str:
        """构造 LLM 响应缓存 key：agent + messages 内容哈希。

        用 build_isolated_key(public=True)：LLM 回复由相同 messages 确定性决定，
        视为公共缓存（用户内容已包含在哈希中，天然按内容隔离）。
        """
        import hashlib
        try:
            payload = json.dumps(messages, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError):
            return ""
        digest = hashlib.sha256(payload.encode()).hexdigest()
        from app.services.cache_service import build_isolated_key
        return build_isolated_key(f"llm:{self.agent_name}:{digest}", public=True)

    def _resolve_chain(self) -> list[str]:
        """按 cost_tier 解析本次 LLM 调用的供应商链（v1.4.x 意图成本路由）。

        standard（默认）：主供应商 + DEFAULT_FALLBACK_CHAIN，行为与 v1.1.28 一致。
        economy + cost_tiered_routing_enabled：低成本供应商优先，
            原主供应商保留在链尾兜底，保证 economy 档不可用时仍能完成解析。
        """
        primary = self.provider
        chain = [primary]
        if settings.llm_fallback_enabled:
            if self.cost_tier == "economy" and settings.cost_tiered_routing_enabled:
                economy = [p for p in settings.economy_provider_list if p in PROVIDER_REGISTRY]
                chain = [p for p in economy if p != primary] or [primary]
                if primary not in chain:
                    chain.append(primary)
            # 其余 DEFAULT_FALLBACK_CHAIN 供应商补足
            chain += [p for p in DEFAULT_FALLBACK_CHAIN if p not in chain and p in PROVIDER_REGISTRY]
        return chain

    @staticmethod
    def _record_tier_usage(tier: str, agent: str, provider: str, status: str) -> None:
        """best-effort 记录成本档位用量指标（llm_tier_usage_total）。"""
        try:
            from app.metrics import llm_tier_usage_total
            llm_tier_usage_total.labels(
                tier=tier, agent=agent, provider=provider, status=status,
            ).inc()
        except Exception:
            pass

    async def _chat_single_provider(
        self,
        provider: str,
        messages: list[dict],
        max_retries: int = 0,
        with_tools: bool = False,
    ) -> str | dict:
        """单供应商 LLM 调用（_chat 的原始实现，v1.1.28 拆分以支持 fallback）。"""
        cfg = PROVIDER_REGISTRY[provider]

        # 无 API Key 时抛 ConnectionError，由 _chat 继续 fallback 到链内下一个供应商
        # v1.13.2 优化：此前非 local 供应商直接返回 mock 会中断降级链（economy 档
        # qwen 无 key 时返回假响应而非降级到 deepseek）。现统一为抛错跳过，
        # 仅当整条链全部无 key 时由 _chat 兜底返回 mock（诚实降级标注）。
        if not cfg["api_key"]():
            raise ConnectionError(
                f"{provider} LLM endpoint not configured (API key unset)"
            )

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
                    # v1.13.1（2026 成本追踪）：提取 LLM usage（token 统计），
                    # 供 harness AgentTrace 落库 / 成本优化评估（此前恒 0）。
                    usage = data.get("usage") or {}
                    result["usage"] = {
                        "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
                        "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
                        "total_tokens": int(usage.get("total_tokens", 0) or 0),
                    }
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
                    self._record_tier_usage(self.cost_tier, self.agent_name, provider, "success")
                    return result
                self._record_tier_usage(self.cost_tier, self.agent_name, provider, "success")
                return content
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    import asyncio
                    await asyncio.sleep(1)
        raise last_error

    async def _inject_evolution_context(
        self, messages: list[dict], user_message: str, user_id: str, db,
        project_id: str = "",
    ) -> None:
        """v1.10.1: 自进化经验注入（借鉴 EverMind EverOS Agent Memory）。

        检索同类 Case + Skill 注入上下文，flag 关闭则降级为无注入。
        v1.10.x 空间感知：project_id 非空时按 project scope 检索（owner_id=project_id），
        项目维度经验只注入该项目（与用户长期记忆 project scope 语义对齐）。
        best-effort：任何失败仅 log debug，不影响主流程。

        v1.13.2 排查日志（evolution.inject.*）：打印开关/空间维度/检索命中/注入结果，
        便于全链路断点排查（grep "evolution.inject"）。
        """
        if not settings.agent_skill_distillation_enabled or not user_id or db is None:
            logger.debug(
                "evolution.inject.skip: agent=%s enabled=%s user_id=%r db=%s",
                self.agent_name, settings.agent_skill_distillation_enabled,
                user_id, db is not None,
            )
            return
        # v1.13.3: 每次注入前重置，防陈旧 skill_id 误记 outcome
        self._injected_skill_id = None
        try:
            from app.services.agent_case_service import search_cases, build_case_context
            from app.services.agent_skill_evolution_service import get_skill_for_injection
            if project_id:
                scope, owner_id = "project", project_id
            else:
                scope, owner_id = "personal", user_id
            logger.debug(
                "evolution.inject.start: agent=%s scope=%s owner_id=%s user_id=%s "
                "project_id=%s message=%r",
                self.agent_name, scope, owner_id, user_id, project_id or "",
                user_message[:80],
            )
            cases = await search_cases(
                db, task_intent=user_message, owner_id=owner_id, scope=scope,
            )
            skill = await get_skill_for_injection(
                db, agent_name=self.agent_name, owner_id=owner_id, scope=scope,
            )
            case_ctx = build_case_context(cases)
            budget = settings.context_injection_budget_chars
            budget_tokens = settings.context_injection_budget_tokens
            if budget > 0 or budget_tokens > 0:
                # v1.13.5（2026 Context Engineering 前沿对齐）：注入预算控制。
                # Skill 蒸馏知识高密度全量优先，Case 用剩余预算——超限从末尾 Case
                # 开始丢弃（cases 已按 quality 降序），防 context rot 淹没关键事实。
                # max_tokens（token 估算，估算系数 len//2）优先于 max_chars。
                if skill and skill.system_prompt:
                    budget -= len(f"[进化 Skill: {skill.name}]\n{skill.system_prompt}")
                case_ctx = build_case_context(
                    cases,
                    max_chars=budget if budget > 0 else None,
                    max_tokens=budget_tokens if budget_tokens > 0 else None,
                )
            if case_ctx:
                messages.append({"role": "system", "content": case_ctx})
                logger.debug(
                    "evolution.inject.case_hit: agent=%s scope=%s owner_id=%s "
                    "case_count=%d ctx_len=%d budget_chars=%s",
                    self.agent_name, scope, owner_id, len(cases), len(case_ctx),
                    settings.context_injection_budget_chars,
                )
            else:
                logger.debug(
                    "evolution.inject.case_miss: agent=%s scope=%s owner_id=%s case_count=0",
                    self.agent_name, scope, owner_id,
                )
            if skill and skill.system_prompt:
                messages.append({
                    "role": "system",
                    "content": f"[进化 Skill: {skill.name}]\n{skill.system_prompt}",
                })
                # v1.13.3: 记录注入的 Skill，供 _maybe_record_skill_outcome 回写成败
                self._injected_skill_id = skill.id
                logger.debug(
                    "evolution.inject.skill_hit: agent=%s scope=%s owner_id=%s "
                    "skill_id=%s skill=%s",
                    self.agent_name, scope, owner_id, skill.id, skill.name,
                )
            else:
                logger.debug(
                    "evolution.inject.skill_miss: agent=%s scope=%s owner_id=%s",
                    self.agent_name, scope, owner_id,
                )
        except Exception as e:
            logger.debug(
                "evolution.inject.failed: agent=%s scope=%s error=%s",
                self.agent_name, project_id and "project" or "personal", e,
            )

    async def _maybe_persist_stream_trace(
        self, user_message: str, reply: Any, db, user_id: str, project_id: str,
        latency_ms: float,
    ) -> None:
        """v1.13.6 流式轨迹落库：端点直连 think_stream 时补 agent_traces 记录。

        主链路流式端点不经过 harness.run（无正式 trace），导致 agent_traces 缺流式
        延迟数据，评估框架首 token / 延迟分位无法覆盖主链路。本 hook 复用
        harness._persist_trace 落一条最小轨迹（含 latency_ms + first_token_latency_ms）。
        best-effort：任何失败仅 log debug，不影响主流程（诚实降级）。
        """
        if db is None or not user_id:
            return
        try:
            from app.agents.harness import AgentTrace, AgentRunStatus, get_harness
            reply_text = reply if isinstance(reply, str) else (
                json.dumps(reply, ensure_ascii=False)[:2000]
            )
            trace = AgentTrace(
                agent_name=self.agent_name or "base",
                user_message=user_message or "",
                user_message_truncated=(user_message or "")[:200],
                response=reply_text,
                response_truncated=reply_text[:800],
                status=AgentRunStatus.SUCCESS,
                user_id=user_id,
                project_id=project_id,
            )
            trace.latency_ms = round(latency_ms, 2)
            trace.first_token_latency_ms = getattr(
                self, "_first_token_latency_ms", 0.0,
            )
            await get_harness()._persist_trace(
                trace, {"db": db, "user_id": user_id, "project_id": project_id},
                agent=self,
            )
        except Exception as e:
            logger.debug(
                "%s._maybe_persist_stream_trace 失败（不影响主流程）: %s",
                self.agent_name, e,
            )

    async def _maybe_persist_execution_case(
        self, user_message: str, reply: Any, db, user_id: str, project_id: str = "",
    ) -> None:
        """v1.10.x 全链路记忆：端点直连 think 时的 Case 沉淀 hook。

        主链路端点不经过 harness.run（无正式 trace），本 hook 用最小 AgentTrace
        走同一 _maybe_extract_case 提取路径，保证「每次 Agent 执行 → Case 沉淀」全链路。
        - harness.run 上下文（self._harness_trace 已标记）跳过，避免双提取
        - best-effort：任何失败仅 log debug，不影响主流程（诚实降级）

        v1.13.2 排查日志（evolution.persist.*）：打印触发条件/跳过原因/提交的 trace
        与空间维度，配合 agent_case_service 的「已沉淀 Case」日志定位断点
        （grep "evolution.persist"）。
        """
        if db is None or not user_id:
            logger.debug(
                "evolution.persist.skip: agent=%s db=%s user_id=%r",
                self.agent_name, db is not None, user_id,
            )
            return
        if getattr(self, "_harness_trace", None) is not None:
            logger.debug(
                "evolution.persist.skip_harness: agent=%s trace_id=%s 由 harness.run 统一提取",
                self.agent_name, getattr(self, "_harness_trace", None),
            )
            return
        try:
            from app.agents.harness import AgentTrace, AgentRunStatus, get_harness
            reply_text = reply if isinstance(reply, str) else (
                json.dumps(reply, ensure_ascii=False)[:2000]
            )
            user_msg = user_message or ""
            # to_dict 仅导出 *_truncated 字段（原始 user_message/response 不入 dict），
            # 故显式填充截断字段供 _compress_trajectory 提取
            trace = AgentTrace(
                agent_name=self.agent_name or "base",
                user_message=user_msg,
                user_message_truncated=user_msg[:200],
                response=reply_text,
                response_truncated=reply_text[:800],
                status=AgentRunStatus.SUCCESS,
            )
            logger.debug(
                "evolution.persist.start: agent=%s trace_id=%s user_id=%s "
                "project_id=%s scope=%s msg_len=%d reply_len=%d",
                self.agent_name, trace.trace_id, user_id, project_id or "",
                "project" if project_id else "personal",
                len(user_msg), len(reply_text),
            )
            await get_harness()._maybe_extract_case(trace, {
                "db": db, "user_id": user_id, "project_id": project_id,
            })
            logger.debug(
                "evolution.persist.done: agent=%s trace_id=%s 已提交提取"
                "（沉淀结果见 agent_case_service 日志）",
                self.agent_name, trace.trace_id,
            )
        except Exception as e:
            logger.debug(
                "evolution.persist.failed: agent=%s error=%s",
                self.agent_name, e,
            )

    # ── v1.13.5 核心功能打磨：Model Spec HC 约束前置声明 ──
    # 与 rebuttal_engine 事后校验互补：输出前把适用于本 Agent 的硬约束注入
    # system 上下文，从源头减少违规输出与重生成成本（Guideline-as-Code 前置化）。

    _MODEL_SPEC_AGENT_ALIASES: dict[str, str] = {
        "door_window": "door_window_waterproof",  # spec applies_to 与 agent_name 映射
    }

    def _model_spec_constraint_prompt(self) -> str:
        """生成适用于本 Agent 的 HC 约束声明段。

        按 agent_name 过滤 ihome_model_spec.json hard_constraints（含别名映射），
        无适用约束或加载失败返回空串（诚实降级，不影响主流程）。
        """
        if not settings.model_spec_enabled:
            return ""
        try:
            from pathlib import Path
            spec = json.loads(
                Path(settings.model_spec_path).read_text(encoding="utf-8")
            )
            spec_name = self._MODEL_SPEC_AGENT_ALIASES.get(
                self.agent_name or "", self.agent_name or "",
            )
            hcs = [
                hc for hc in spec.get("hard_constraints", [])
                if spec_name in (hc.get("applies_to") or [])
            ]
            if not hcs:
                return ""
            lines = ["【Model Spec 硬约束（必须遵守，违反将触发合规校验与重生成）】"]
            for hc in hcs:
                lines.append(f"- {hc['id']} {hc['title']}：{hc['description']}")
            return "\n".join(lines)
        except Exception as e:
            logger.debug(
                "%s: Model Spec 约束声明加载失败（跳过）: %s", self.agent_name, e,
            )
            return ""

    def _append_model_spec_constraint(self, messages: list[dict]) -> None:
        """在 system_prompt 之后注入 HC 约束声明（无适用约束则 no-op）。"""
        constraint = self._model_spec_constraint_prompt()
        if constraint:
            messages.append({"role": "system", "content": constraint})

    async def _maybe_record_skill_outcome(self, reply: Any, db) -> None:
        """v1.13.3: Skill 使用成败回写（best-effort）。

        与 _maybe_persist_execution_case 并列的反馈闭环 hook：当本次执行注入过
        进化 Skill（self._injected_skill_id 非空）时，把执行结果回写
        record_skill_outcome，激活 P1 Skill 进化数据层
        （此前该函数生产路径零调用，success/fail_count 恒 0）。

        确定性判定（无额外 LLM 成本）：
        - reply 非空、非 [mock] 前缀、非降级占位 → success=True（Skill 正常产出）
        - reply 为 [mock] / 降级占位 → success=False（注入 Skill 后仍降级，
          Skill 未产生价值，v1.13.5 闭环「只记成功不记失败」遗留）
        - 空 reply（异常路径）→ 跳过不计数，防污染
        """
        try:
            skill_id = getattr(self, "_injected_skill_id", None)
            if not skill_id or db is None:
                logger.debug(
                    "evolution.outcome.skip: agent=%s skill_id=%r db=%s",
                    self.agent_name, skill_id, db is not None,
                )
                return
            if not isinstance(reply, str) or not reply.strip():
                logger.debug(
                    "evolution.outcome.skip_empty: agent=%s skill_id=%s",
                    self.agent_name, skill_id,
                )
                return
            from app.services.agent_skill_evolution_service import record_skill_outcome
            if reply.startswith("[mock]") or reply.startswith("Agent 暂时无法响应"):
                # v1.13.5: 注入 Skill 后仍降级 → 确定性记失败，激活失败数据层
                await record_skill_outcome(db, skill_id=skill_id, success=False)
                logger.debug(
                    "evolution.outcome.record_fail: agent=%s skill_id=%s reply=%r",
                    self.agent_name, skill_id, reply[:40],
                )
                return
            await record_skill_outcome(db, skill_id=skill_id, success=True)
            logger.debug(
                "evolution.outcome.record: agent=%s skill_id=%s success=True",
                self.agent_name, skill_id,
            )
        except Exception as e:
            logger.debug(
                "evolution.outcome.failed: agent=%s error=%s",
                self.agent_name, e,
            )

    async def think(self, user_message: str, context: str = "", db=None, project_id: str = "",
                    user_id: str = "") -> str:
        """高层封装：自动拼接 system prompt + 上下文 → LLM 调用。

        v1.1.28 新增：
        - AgenticRAG 证据检索（借鉴索克生活）：db 传入时前置检索知识库证据注入上下文
        - Model Spec HC 硬约束校验（借鉴索克生活 rebuttal_engine）：输出违规时注入反驳重生成
        v1.10.1 新增（借鉴 EverMind EverOS Agent Memory）：
        - 自进化经验注入：user_id 传入时检索同类 Case + Skill 注入上下文
          受 agent_skill_distillation_enabled 门控，flag 关闭则降级为无注入（诚实降级）
        """
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        # v1.13.5: Model Spec HC 约束前置声明（Guideline-as-Code，有适用约束才注入）
        self._append_model_spec_constraint(messages)

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

        # v1.10.1: 自进化经验注入（借鉴 EverMind EverOS Agent Memory）
        await self._inject_evolution_context(messages, user_message, user_id, db, project_id)

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

        # v1.10.x 全链路记忆：端点直连 think 时补 Case 沉淀（best-effort）
        await self._maybe_persist_execution_case(
            user_message, reply, db, user_id, project_id,
        )
        # v1.13.3: Skill 成败回写（best-effort，激活 P1 进化数据层）
        await self._maybe_record_skill_outcome(reply, db)
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

        # v1.13.6: 首 token 延迟（TTFT）实测——从发出请求到首个 content chunk 的时间，
        # 回填 self._first_token_latency_ms，供 think_stream 落 agent_traces 首 token 分位。
        self._first_token_latency_ms = 0.0
        started = time.monotonic()
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
                if self._first_token_latency_ms == 0.0:
                    self._first_token_latency_ms = round(
                        (time.monotonic() - started) * 1000, 2,
                    )
                yield piece

    async def think_stream(self, user_message: str, context: str = "", db=None,
                           project_id: str = "", user_id: str = ""):
        """流式版 think()：拼接 system prompt + 上下文 → 逐 chunk 产出。

        v1.13.3（全链路闭环补齐，断点 D）：补 db/project_id/user_id 签名，
        与 think/think_with_tools 对齐注入链——
        - AgenticRAG 证据检索（db 传入时）
        - 自进化经验注入 _inject_evolution_context（Case + Skill）
        - 流结束后 Case 沉淀 + Skill 成败回写（用累积全文）
        流式路径无 Model Spec HC 反驳重生成（诚实标注：生成后才能校验，
        流式下无法在输出前拦截，保持现状）。

        Usage::

            async for chunk in agent.think_stream("帮我设计客厅", db=db,
                                                  user_id=uid, project_id=pid):
                print(chunk, end="", flush=True)
        """
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        # v1.13.5: Model Spec HC 约束前置声明（Guideline-as-Code，有适用约束才注入）
        self._append_model_spec_constraint(messages)

        # v1.13.3: AgenticRAG 证据注入（与 think 一致）
        if settings.agentic_rag_enabled and db is not None:
            try:
                from app.services.agentic_rag import agentic_rag
                evidence = await agentic_rag.retrieve(
                    user_message, db=db, project_id=project_id,
                )
                evidence_context = agentic_rag.build_evidence_context(evidence)
                if evidence_context:
                    messages.append({"role": "system", "content": evidence_context})
            except Exception as e:
                logger.debug(
                    "%s.think_stream: AgenticRAG 检索失败（降级到无 RAG）: %s",
                    self.agent_name, e,
                )

        # v1.13.3: 自进化经验注入（与 think 一致）
        await self._inject_evolution_context(
            messages, user_message, user_id, db, project_id,
        )

        if context:
            messages.append({"role": "assistant", "content": context})
        messages.append({"role": "user", "content": user_message})

        # v1.13.3: 累积完整回复，流结束后用于 Case 沉淀 + Skill 成败回写
        stream_started = time.monotonic()
        chunks: list[str] = []
        async for chunk in self._chat_stream(messages):
            chunks.append(chunk)
            yield chunk
        reply_text = "".join(chunks)
        latency_ms = (time.monotonic() - stream_started) * 1000
        # v1.13.6: 流式轨迹落库（首 token + 总延迟），补齐主链路流式响应速度实测
        await self._maybe_persist_stream_trace(
            user_message, reply_text, db, user_id, project_id, latency_ms,
        )
        await self._maybe_persist_execution_case(
            user_message, reply_text, db, user_id, project_id,
        )
        await self._maybe_record_skill_outcome(reply_text, db)

    # v1.13.0: 并行执行同一轮工具调用（受 parallel_tool_calls_enabled 门控）
    async def _execute_tool_calls(
        self, tool_calls: list[dict], db, project_id: str,
    ) -> list[Any]:
        """执行同一轮的多个 tool_calls。并行（gather）或串行，保持结果顺序。

        v1.13.1 修复（真实回归）：共享 AsyncSession 下并行执行会触发 SQLAlchemy
        ISCE 冲突（"This session is provisioning a new connection; concurrent
        operations are not permitted"），工具 handler 的 DB 查询全部失败并静默
        降级 fallback（真实数据失效）。修复策略（诚实降级优先）：
        - 有 db（DB 查询工具）：串行执行，保证真实数据正确性（SQLite 单连接/
          StaticPool 下并行本就不提速）
        - 无 db（纯计算/外部 API 工具如 search_poi）：并行 gather（真正提速场景）
        """
        from app.services.agent_tool_registry import tool_registry

        if settings.parallel_tool_calls_enabled and len(tool_calls) > 1 and db is None:
            return await asyncio.gather(*[
                tool_registry.execute(
                    tc["name"], tc["arguments"],
                    _db=None, _project_id=project_id,
                    _agent_id=self.agent_name, _model_source=self.provider,
                ) for tc in tool_calls
            ])
        results = []
        for tc in tool_calls:
            results.append(await tool_registry.execute(
                tc["name"], tc["arguments"],
                _db=db, _project_id=project_id,
                _agent_id=self.agent_name, _model_source=self.provider,
            ))
        return results

    async def think_with_tools(
        self, user_message: str, context: str = "", max_rounds: int | None = None,
        db=None, project_id: str = "", user_id: str = "",
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
            reply = await self.think(user_message, context, db=db, project_id=project_id,
                                     user_id=user_id)
            return {"final_reply": reply, "tool_calls": [], "rounds": 0}

        max_rounds = max_rounds or settings.agent_function_call_max_rounds

        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        # v1.13.5: Model Spec HC 约束前置声明（Guideline-as-Code，有适用约束才注入）
        self._append_model_spec_constraint(messages)

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

        # v1.10.1: 自进化经验注入（借鉴 EverMind EverOS Agent Memory）
        await self._inject_evolution_context(messages, user_message, user_id, db, project_id)

        if context:
            messages.append({"role": "assistant", "content": context})
        messages.append({"role": "user", "content": user_message})

        tool_calls_history = []
        rounds = 0
        # v1.13.0（2026 前沿对齐）：Agent loop token 预算（早停规则，第二道闸）。
        # 累计 tool_calls 参数 + 工具结果上下文估算 token，超限提前终止循环，
        # 防止长任务上下文爆炸（max_rounds 之外）。
        est_tokens_used = 0
        max_tool_tokens = getattr(settings, "agent_function_call_max_tool_tokens", 12000)
        # v1.13.1（2026 成本追踪）：累计各轮 LLM usage，随返回透传 harness 落库。
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        for _round in range(max_rounds):
            result = await self._chat(messages, with_tools=True)
            _accumulate_usage(total_usage, result)
            tool_calls = result.get("tool_calls", []) if isinstance(result, dict) else []

            if not tool_calls:
                reply = result.get("content", "") if isinstance(result, dict) else result
                reply = await self._rebuttal_check(messages, reply)
                # v1.10.x 全链路记忆：Case 沉淀 hook（best-effort）
                await self._maybe_persist_execution_case(
                    user_message, reply, db, user_id, project_id,
                )
                # v1.13.3: Skill 成败回写（best-effort）
                await self._maybe_record_skill_outcome(reply, db)
                return {
                    "final_reply": reply,
                    "tool_calls": tool_calls_history,
                    "rounds": rounds,
                    "token_budget_hit": False,
                    "usage": total_usage,
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

            # v1.13.0（2026 前沿对齐）：同一轮多个 tool_calls 并行执行。
            # 2026 工具调用指南（zylos.ai）：并行执行多个独立数据源调用，
            # 5 个 200ms 数据源串行 1000ms → 并行 ≈ 200ms（5x 提速）。
            # 受 parallel_tool_calls_enabled 门控；关闭则回退串行（零回归）。
            exec_results = await self._execute_tool_calls(tool_calls, db, project_id)

            for tc, exec_result in zip(tool_calls, exec_results):
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
                # token 预算累计（估算：参数 JSON + 结果 JSON 的字符数 ≈ token 数）
                est_tokens_used += len(
                    json.dumps(tc["arguments"], ensure_ascii=False)
                ) + len(json.dumps(exec_result, ensure_ascii=False))
                if est_tokens_used >= max_tool_tokens:
                    logger.info(
                        "%s.think_with_tools: token 预算触顶 (est=%d >= %d)，提前终止",
                        self.agent_name, est_tokens_used, max_tool_tokens,
                    )
                    messages.append({
                        "role": "user",
                        "content": "请根据以上工具调用结果给出最终回复。（注意：上下文已接近预算，请直接总结，不要再调用工具。）",
                    })
                    final_reply = await self._chat(messages)
                    _accumulate_usage(total_usage, final_reply)
                    final_reply = await self._rebuttal_check(messages, final_reply)
                    # v1.10.x 全链路记忆：Case 沉淀 hook（best-effort）
                    await self._maybe_persist_execution_case(
                        user_message, final_reply, db, user_id, project_id,
                    )
                    # v1.13.3: Skill 成败回写（best-effort）
                    await self._maybe_record_skill_outcome(final_reply, db)
                    return {
                        "final_reply": final_reply,
                        "tool_calls": tool_calls_history,
                        "rounds": rounds + 1,
                        "token_budget_hit": True,
                        "usage": total_usage,
                    }

            rounds += 1

        # 达到最大轮数仍未完成，强制生成最终回复
        messages.append({"role": "user", "content": "请根据以上工具调用结果给出最终回复。"})
        final_reply = await self._chat(messages)
        _accumulate_usage(total_usage, final_reply)
        final_reply = await self._rebuttal_check(messages, final_reply)
        # v1.10.x 全链路记忆：Case 沉淀 hook（best-effort）
        await self._maybe_persist_execution_case(
            user_message, final_reply, db, user_id, project_id,
        )
        # v1.13.3: Skill 成败回写（best-effort）
        await self._maybe_record_skill_outcome(final_reply, db)
        return {
            "final_reply": final_reply,
            "tool_calls": tool_calls_history,
            "rounds": rounds,
            "token_budget_hit": False,
            "usage": total_usage,
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
        """查询用户对该 agent 的历史反馈，构造 few-shot 示例提示。

        当 settings.agent_learning_enabled=True 时，由 chat 端点调用并拼接到
        user_message 前，让 LLM 参考用户过往满意回复的风格/内容偏好。

        v1.13.1 增强（2026 前沿：偏好学习双向利用正负反馈）：
        - like 反馈 → 正向示例（继续参考的风格/内容）
        - dislike 反馈 → 负向示例（应避免的风格/内容，如用户明确表达不满的回复）
        避免 LLM 仅学正向导致风格漂移，负向提示防止重蹈覆辙。

        Args:
            user_id: 用户 ID
            agent_name: Agent 名称（designer/budget/...）
            db: 异步数据库会话；为 None 时返回空字符串（兼容无 DB 场景）
            max_examples: 最大示例数（like/dislike 各取 max_examples 条）

        Returns:
            few-shot 示例字符串；无任何反馈或未启用学习时返回空字符串
        """
        if not settings.agent_learning_enabled or db is None:
            return ""
        try:
            from sqlalchemy import select, desc
            from app.models.agent_feedback import AgentFeedback

            async def _fetch(feedback_type: str) -> list:
                stmt = (
                    select(AgentFeedback)
                    .where(
                        AgentFeedback.user_id == user_id,
                        AgentFeedback.agent_name == agent_name,
                        AgentFeedback.feedback_type == feedback_type,
                    )
                    .order_by(desc(AgentFeedback.created_at))
                    .limit(max_examples)
                )
                result = await db.execute(stmt)
                return list(result.scalars().all())

            likes = await _fetch("like")
            dislikes = await _fetch("dislike")
            if not likes and not dislikes:
                return ""
            blocks: list[str] = []
            if likes:
                examples = []
                for r in likes:
                    um = r.user_message[:200]
                    ar = r.agent_reply[:400]
                    examples.append(f"用户: {um}\n满意回复: {ar}")
                blocks.append(
                    "以下是该用户过往满意的回复示例，请参考其风格与内容偏好：\n\n"
                    + "\n\n---\n\n".join(examples)
                )
            if dislikes:
                examples = []
                for r in dislikes:
                    um = r.user_message[:200]
                    ar = r.agent_reply[:400]
                    examples.append(f"用户: {um}\n不满意的回复（请避免类似风格）: {ar}")
                blocks.append(
                    "以下是该用户过往不满意的回复示例，请避免相同的问题或风格：\n\n"
                    + "\n\n---\n\n".join(examples)
                )
            return "\n\n---\n\n".join(blocks) + "\n\n---\n\n"
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
