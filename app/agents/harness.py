"""Agent Harness 统一编排层（v1.2.0）

2026 年行业共识：Agent = Model + Harness。
Harness（驾驭层）是围绕模型的运行时基础设施，决定 Agent 是否可观测、可控制、可评估。

本模块提供：
- AgentRuntime: 统一 Agent 生命周期管理（创建 → 执行 → 追踪 → 评估 → 清理）
- HarnessConfig: 全局 Harness 配置（降级策略、重试策略、超时控制）
- AgentTrace: Agent 执行轨迹记录（token 消耗、工具调用链、延迟追踪）
- AgentEval: Agent 输出的离线评估循环

架构层级：
  ┌─────────────────────────────────────┐
  │         AgentRuntime (Harness)       │
  │  ┌───────┐ ┌──────┐ ┌────────────┐  │
  │  │ Tool  │ │Perm  │ │Trace       │  │
  │  │Registry│ │Model │ │Collector   │  │
  │  └───────┘ └──────┘ └────────────┘  │
  │  ┌───────┐ ┌──────┐ ┌────────────┐  │
  │  │Fallback│ │Retry │ │Observability│  │
  │  │Policy  │ │Policy│ │(Metrics)   │  │
  │  └───────┘ └──────┘ └────────────┘  │
  │  ┌───────┐ ┌──────┐ ┌────────────┐  │
  │  │Context │ │Mem   │ │Eval        │  │
  │  │Manager │ │(5-tier)│ │Loop      │  │
  │  └───────┘ └──────┘ └────────────┘  │
  └─────────────────────────────────────┘
           │           │           │
     DesignerAgent BudgetAgent  ConstructionAgent ...
"""

import asyncio
import json
import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# 枚举与常量
# ════════════════════════════════════════════════════════════════


class AgentRunStatus(str, Enum):
    """Agent 执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    FALLBACK = "fallback"
    DEGRADED = "degraded"


class FallbackStrategy(str, Enum):
    """降级策略"""
    MOCK_REPLY = "mock_reply"          # 返回预置回复
    RAISE_ERROR = "raise_error"        # 抛出异常
    RETRY_N_TIMES = "retry_n_times"    # 重试 N 次
    DEGRADE_TO_RULE = "degrade_to_rule"  # 降级到规则引擎


# ════════════════════════════════════════════════════════════════
# 数据结构
# ════════════════════════════════════════════════════════════════


def _generate_w3c_trace_context() -> dict:
    """生成 W3C Trace Context（traceparent/tracestate/baggage）。
    traceparent = "00-" + 32位hex trace-id + "-" + 16位hex span-id + "-01"
    tracestate = "gen_ai=v1"；baggage = ""（可空）。
    用 uuid4().hex 截取生成 trace-id/span-id。"""
    trace_id = uuid.uuid4().hex[:32]
    span_id = uuid.uuid4().hex[:16]
    return {
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "tracestate": "gen_ai=v1",
        "baggage": "",
    }


def _serialize_tool_calls_for_trace(tool_calls: list[dict], max_total: int = 4000) -> str | None:
    """将工具调用链序列化为 JSON 字符串（落库前截断，防 PII 扩散 + 体积爆炸）。

    v1.13.8（借鉴 DeepSeek Harness「Every run is traceable」）：轨迹可回放化。
    每条 tool_call 仅保留 tool/arguments/result，arguments 截到 200 字符、
    result 截到 300 字符；整体截到 max_total。无工具调用返回 None（列存 NULL）。
    """
    if not tool_calls:
        return None
    truncated: list[dict] = []
    for tc in tool_calls:
        args = tc.get("arguments")
        result = tc.get("result")
        args_text = args if isinstance(args, str) else json.dumps(args, ensure_ascii=False, default=str)
        result_text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)
        truncated.append({
            "tool": str(tc.get("tool", ""))[:60],
            "arguments": args_text[:200],
            "result": result_text[:300],
        })
    payload = json.dumps(truncated, ensure_ascii=False, default=str)
    if len(payload) > max_total:
        payload = payload[:max_total] + "…"
    return payload


def _build_genai_semconv_meta(trace: "AgentTrace") -> dict:
    """构建 OTel GenAI 语义约定元数据：
    {"traceparent": ..., "tracestate": ..., "baggage": ...,
     "gen_ai": {"system": trace.provider, "model": trace.model,
                "agent.name": trace.agent_name,
                "usage": {"input_tokens": trace.prompt_tokens,
                          "output_tokens": trace.completion_tokens,
                          "total_tokens": trace.total_tokens}}}"""
    return {
        "traceparent": trace.w3c_trace.get("traceparent", ""),
        "tracestate": trace.w3c_trace.get("tracestate", ""),
        "baggage": trace.w3c_trace.get("baggage", ""),
        "gen_ai": {
            "system": trace.provider,
            "model": trace.model,
            "agent.name": trace.agent_name,
            "usage": {
                "input_tokens": trace.prompt_tokens,
                "output_tokens": trace.completion_tokens,
                "total_tokens": trace.total_tokens,
            },
        },
    }


@dataclass
class AgentTrace:
    """Agent 执行轨迹（用于可观测性、离线评估、在线进化）"""
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_name: str = ""
    agent_version: str = ""
    provider: str = ""
    model: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    status: AgentRunStatus = AgentRunStatus.PENDING

    # 输入输出
    user_message: str = ""
    user_message_truncated: str = ""  # 截断到 200 字符
    response: str = ""
    response_truncated: str = ""

    # Token 追踪
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    # 工具调用追踪
    tool_calls: list[dict] = field(default_factory=list)
    tool_call_count: int = 0
    tool_call_rounds: int = 0

    # 降级信息
    fallback_used: bool = False
    fallback_reason: str = ""
    retry_count: int = 0

    # v1.13.0（2026 前沿对齐：Agent loop 早停可观测性）
    # token 预算触顶提前终止（token_budget_hit=True），供评估区分
    # 正常完成 vs 预算早停（早停率高说明工具结果上下文过大需优化）。
    token_budget_hit: bool = False

    # 延迟
    latency_ms: float = 0.0
    first_token_latency_ms: float = 0.0

    # 元数据
    error_message: str = ""
    error_type: str = ""
    user_id: str = ""
    project_id: str = ""
    scope: str = ""  # v1.4.0: QM 作用域（personal/project/team/org），借鉴 YC QM
    workflow_id: str = ""  # v1.12.x: 跨 Agent 协作编排 ID（同一用户请求共享）
    context_source: str = ""  # "harness" | "raw"
    w3c_trace: dict = field(default_factory=dict)  # OTel GenAI SemConv: W3C Trace Context

    def to_dict(self) -> dict:
        result = {
            "trace_id": self.trace_id,
            "agent_name": self.agent_name,
            "agent_version": self.agent_version,
            "provider": self.provider,
            "model": self.model,
            "started_at": (
                datetime.fromtimestamp(self.started_at, tz=timezone.utc).isoformat()
                if self.started_at else None
            ),
            "finished_at": (
                datetime.fromtimestamp(self.finished_at, tz=timezone.utc).isoformat()
                if self.finished_at else None
            ),
            "status": self.status.value,
            "user_message_truncated": self.user_message_truncated,
            "response_truncated": self.response_truncated,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "tool_call_count": self.tool_call_count,
            "tool_call_rounds": self.tool_call_rounds,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "retry_count": self.retry_count,
            "token_budget_hit": self.token_budget_hit,
            "latency_ms": round(self.latency_ms, 2),
            "first_token_latency_ms": round(self.first_token_latency_ms, 2),
            "error_message": self.error_message,
            "error_type": self.error_type,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "scope": self.scope,
            "workflow_id": self.workflow_id,
            "context_source": self.context_source,
        }
        if get_settings().otel_genai_semconv_enabled and self.w3c_trace:
            result["_meta"] = _build_genai_semconv_meta(self)
        return result

    def finish(self, status: AgentRunStatus):
        """标记轨迹结束"""
        self.finished_at = time.time()
        self.latency_ms = (self.finished_at - self.started_at) * 1000
        self.status = status


@dataclass
class HarnessConfig:
    """全局 Harness 配置"""
    # 降级策略
    default_fallback: FallbackStrategy = FallbackStrategy.MOCK_REPLY
    llm_unavailable_fallback: FallbackStrategy = FallbackStrategy.DEGRADE_TO_RULE

    # 重试配置
    max_retries: int = 1
    retry_delay_ms: int = 1000

    # 超时控制
    # v1.15.x 走查修复：推理模型单轮 30-60s + 工具轮次叠加，60s 极易误杀
    # （orchestrate/A2A 的 designer/kitchen 均因此「执行降级/无回复」）。
    # 对齐 config.harness_agent_timeout_seconds（get_harness 时从 settings 注入）。
    agent_timeout_seconds: int = 180
    stream_timeout_seconds: int = 120

    # 追踪配置
    trace_enabled: bool = True
    trace_max_history: int = 500  # 内存中最多保留的轨迹数

    # 上下文管理
    max_context_tokens: int = 8000
    max_history_rounds: int = 10

    # 资源控制
    max_concurrent_agents: int = 20
    agent_ttl_seconds: int = 300  # Agent 实例最大存活时间


# ════════════════════════════════════════════════════════════════
# AgentRuntime — 统一 Harness 层
# ════════════════════════════════════════════════════════════════


class AgentRuntime:
    """Agent 统一运行时（Harness）。

    职责：
    1. 管理 Agent 生命周期（创建 → 执行 → 追踪 → 评估 → 清理）
    2. 统一降级策略（LLM 不可用 → mock/rule fallback）
    3. 收集执行轨迹（供可观测性 + 在线进化）
    4. 评估循环（offline eval）

    Usage::

        harness = AgentRuntime()
        trace = harness.start_trace("designer", user_id="u1")

        try:
            result = await harness.run(
                agent=DesignerAgent(),
                user_message="120平三室两厅北欧风",
                trace=trace,
                mock_fn=lambda msg: {"reply": "已生成3套方案"},
            )
        finally:
            harness.finish_trace(trace, status=AgentRunStatus.SUCCESS)
    """

    def __init__(self, config: HarnessConfig | None = None):
        self.config = config or HarnessConfig()
        self._traces: list[AgentTrace] = []
        self._agent_registry: dict[str, Any] = {}
        self._metrics = {
            "total_runs": 0,
            "success_runs": 0,
            "fallback_runs": 0,
            "failed_runs": 0,
            "total_tokens": 0,
            "total_latency_ms": 0.0,
        }

    # ── 生命周期管理 ──

    def register_agent(self, name: str, agent_cls: type):
        """注册 Agent 类（不在运行时创建实例，仅做类型登记）"""
        self._agent_registry[name] = agent_cls
        logger.debug(f"harness_agent_registered: {name}")

    async def run(
        self,
        agent: Any,  # BaseAgent 实例
        user_message: str,
        trace: AgentTrace | None = None,
        mock_fn: Callable | None = None,
        **kwargs,
    ) -> dict:
        """在 Harness 中运行 Agent。

        Args:
            agent: Agent 实例
            user_message: 用户消息
            trace: 执行轨迹（可选，不传则自动创建）
            mock_fn: mock 模式下的响应函数
            **kwargs: 传递给 agent.think/think_with_tools 的额外参数

        Returns:
            {"reply": str, "trace": AgentTrace, "metadata": {...}}
        """
        trace = trace or self.start_trace(
            agent.agent_name, user_message, getattr(agent, "provider", "unknown"),
            workflow_id=kwargs.get("workflow_id", ""),
        )
        self._metrics["total_runs"] += 1

        try:
            if mock_fn:
                result = mock_fn(user_message)
                trace.response = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
                trace.finish(AgentRunStatus.SUCCESS)
                self._metrics["success_runs"] += 1
                await self._persist_trace(trace, kwargs, agent)
                return {"reply": result if isinstance(result, str) else result.get("reply", ""),
                        "trace": trace.to_dict()}

            # 尝试 LLM 调用
            # v1.12.x: workflow_id 为 harness 级元数据（trace 落库用），
            # 不向 agent.think/think_with_tools 透传（签名不含该参数）
            agent_kwargs = {k: v for k, v in kwargs.items() if k != "workflow_id"}
            # v1.10.x 全链路记忆：标记 harness 上下文中（BaseAgent 内建 Case 沉淀 hook
            # 检测到该标记即跳过，由本方法统一提取，避免同一次执行沉淀两条 Case）
            try:
                agent._harness_trace = trace
            except Exception:
                pass
            # v1.15.x 走查修复：工具循环返回空回复（推理模型 finish=tool_calls 且
            # content 为空）时，下一轮降级为无工具 think 重试——直连 think 路径在
            # 真实环境中稳定返回正文；全部耗尽后走 fallback，调用方诚实标注失败。
            force_plain_think = False
            for attempt in range(self.config.max_retries + 1):
                try:
                    if hasattr(agent, "think_with_tools") and agent.tools and not force_plain_think:
                        result = await asyncio.wait_for(
                            agent.think_with_tools(user_message, **agent_kwargs),
                            timeout=self.config.agent_timeout_seconds,
                        )
                        reply = result.get("final_reply", "")
                        trace.tool_calls = result.get("tool_calls", [])
                        trace.tool_call_count = len(trace.tool_calls)
                        trace.tool_call_rounds = result.get("rounds", 0)
                        # v1.13.0: token 预算早停可观测性
                        trace.token_budget_hit = bool(result.get("token_budget_hit", False))
                        # v1.13.1: LLM usage 成本追踪（累计各轮 token）
                        _usage = result.get("usage") or {}
                        trace.prompt_tokens = int(_usage.get("prompt_tokens", 0) or 0)
                        trace.completion_tokens = int(_usage.get("completion_tokens", 0) or 0)
                        trace.total_tokens = int(_usage.get("total_tokens", 0) or 0)
                    else:
                        reply = await asyncio.wait_for(
                            agent.think(user_message, **agent_kwargs),
                            timeout=self.config.agent_timeout_seconds,
                        )
                    if not (reply or "").strip():
                        logger.warning(
                            "harness_empty_reply: agent=%s attempt=%d "
                            "force_plain_think=%s",
                            agent.agent_name, attempt, force_plain_think,
                        )
                        force_plain_think = True
                        if attempt < self.config.max_retries:
                            await asyncio.sleep(self.config.retry_delay_ms / 1000)
                            continue
                        # 重试耗尽：抛超时进入统一 fallback（不再把空回复当成功）
                        raise asyncio.TimeoutError
                    trace.response = reply
                    trace.finish(AgentRunStatus.SUCCESS)
                    self._metrics["success_runs"] += 1
                    # v1.10.1: 自进化 Case 提取（借鉴 EverMind EverOS Agent Memory）
                    # best-effort：从 kwargs 取 db/user_id，flag 关闭或失败均不影响主流程
                    await self._maybe_extract_case(trace, kwargs)
                    # v1.12.x: 轨迹落库（受 agent_trace_persist_enabled + 采样率门控）
                    await self._persist_trace(trace, kwargs, agent)
                    logger.info(
                        "harness_run_success: agent=%s latency_ms=%.1f workflow_id=%s "
                        "tokens=%d fallback=%s",
                        agent.agent_name, trace.latency_ms or 0.0,
                        trace.workflow_id or kwargs.get("workflow_id", ""),
                        trace.total_tokens or 0, trace.fallback_used,
                    )
                    return {"reply": reply, "trace": trace.to_dict()}

                except asyncio.TimeoutError:
                    trace.retry_count += 1
                    if attempt < self.config.max_retries:
                        logger.warning(
                            "harness_agent_timeout_retry: agent=%s attempt=%d",
                            agent.agent_name, attempt + 1,
                        )
                        await asyncio.sleep(self.config.retry_delay_ms / 1000)
                        continue
                    raise

            # 所有重试都失败 → 降级
            trace.fallback_used = True
            trace.fallback_reason = "all_retries_exhausted"
            fallback_result = self._apply_fallback(agent.agent_name, user_message, trace, mock_fn)
            await self._persist_trace(trace, kwargs, agent)
            logger.info(
                "harness_run_fallback: agent=%s reason=%s latency_ms=%.1f workflow_id=%s",
                agent.agent_name, trace.fallback_reason, trace.latency_ms or 0.0,
                trace.workflow_id or kwargs.get("workflow_id", ""),
            )
            return fallback_result

        except Exception as e:
            trace.error_message = str(e)
            trace.error_type = type(e).__name__
            trace.fallback_used = True
            trace.fallback_reason = f"exception: {type(e).__name__}"
            logger.error(
                "harness_agent_error: agent=%s error=%s",
                agent.agent_name, e,
            )
            fallback_result = self._apply_fallback(agent.agent_name, user_message, trace, mock_fn)
            await self._persist_trace(trace, kwargs, agent)
            logger.info(
                "harness_run_fallback: agent=%s reason=%s latency_ms=%.1f workflow_id=%s",
                agent.agent_name, trace.fallback_reason, trace.latency_ms or 0.0,
                trace.workflow_id or kwargs.get("workflow_id", ""),
            )
            return fallback_result

    def _apply_fallback(
        self,
        agent_name: str,
        user_message: str,
        trace: AgentTrace,
        mock_fn: Callable | None = None,
    ) -> dict:
        """应用降级策略"""
        self._metrics["fallback_runs"] += 1

        if mock_fn:
            try:
                result = mock_fn(user_message)
                reply = result if isinstance(result, str) else result.get("reply", "降级响应")
            except Exception:
                reply = f"[{agent_name}] 服务暂时不可用，请稍后重试。"
        else:
            reply = f"[{agent_name}] 服务暂时不可用，请稍后重试。"

        trace.response = reply
        trace.finish(AgentRunStatus.FALLBACK)
        return {"reply": reply, "trace": trace.to_dict(), "fallback": True}

    # ── 自进化 Case 提取（v1.10.1，借鉴 EverMind EverOS Agent Memory）──

    async def _maybe_extract_case(self, trace: "AgentTrace", kwargs: dict) -> None:
        """best-effort 从执行轨迹提取 Case 并持久化。

        受 agent_case_extraction_enabled 门控；从 kwargs 取 db / user_id。
        任何失败仅 log debug，不影响主流程（诚实降级）。
        """
        settings = get_settings()
        if not settings.agent_case_extraction_enabled:
            return
        db = kwargs.get("db")
        user_id = kwargs.get("user_id", "")
        if db is None or not user_id:
            return
        try:
            from app.services.agent_case_service import extract_case_from_trace
            # v1.10.x 空间感知：项目上下文的执行沉淀为 project scope（对齐用户长期记忆
            # agent_memories 的 project scope 语义，同一用户不同项目经验互不污染）
            project_id = kwargs.get("project_id") or ""
            scope = "project" if project_id else "personal"
            owner_id = project_id or user_id
            await extract_case_from_trace(
                trace, db, owner_id=owner_id, scope=scope, created_by=user_id,
            )
            if db.in_transaction():
                await db.commit()
        except Exception as e:
            logger.debug("harness._maybe_extract_case: Case 提取失败（不影响主流程）: %s", e)

    # ── 轨迹持久化（v1.12.x，对齐 2026 Agent 可观测性 MELT+P）──

    async def _persist_trace(self, trace: "AgentTrace", kwargs: dict, agent: Any) -> None:
        """best-effort 将 AgentTrace 落库到 agent_traces 表。

        受 agent_trace_persist_enabled 总开关 + agent_trace_sample_rate 采样率门控；
        从 kwargs 取 db / user_id / project_id / workflow_id。
        prompt 上下文采样：仅截断记录 system prompt + 用户消息（防 PII 扩散）。
        任何失败仅 log debug，不影响主流程（诚实降级）。
        """
        _settings = get_settings()
        if not _settings.agent_trace_persist_enabled:
            return
        db = kwargs.get("db")
        if db is None:
            return
        try:
            if _settings.agent_trace_sample_rate < 1.0 and random.random() > _settings.agent_trace_sample_rate:
                return
            from app.models.agent_trace import AgentTraceRecord
            record = AgentTraceRecord(
                id=trace.trace_id,
                workflow_id=trace.workflow_id or kwargs.get("workflow_id", ""),
                agent_name=trace.agent_name,
                agent_version=trace.agent_version,
                provider=trace.provider,
                model=trace.model,
                status=trace.status.value,
                user_id=trace.user_id or kwargs.get("user_id", ""),
                project_id=trace.project_id or kwargs.get("project_id", ""),
                scope=trace.scope,
                context_source=trace.context_source,
                latency_ms=trace.latency_ms,
                first_token_latency_ms=trace.first_token_latency_ms,
                prompt_tokens=trace.prompt_tokens,
                completion_tokens=trace.completion_tokens,
                total_tokens=trace.total_tokens,
                tool_call_count=trace.tool_call_count,
                tool_call_rounds=trace.tool_call_rounds,
                tool_calls=_serialize_tool_calls_for_trace(trace.tool_calls),
                token_budget_hit=trace.token_budget_hit,
                fallback_used=trace.fallback_used,
                fallback_reason=trace.fallback_reason or "",
                retry_count=trace.retry_count,
                error_type=trace.error_type,
                error_message=trace.error_message,
                prompt_preview=(getattr(agent, "system_prompt", "") or "")[:500],
                response_preview=(trace.response or "")[:1000],
            )
            db.add(record)
            if db.in_transaction():
                await db.commit()
            from app.metrics import agent_trace_persisted_total
            agent_trace_persisted_total.labels(
                agent=trace.agent_name, status=trace.status.value,
            ).inc()
            logger.info(
                "harness_trace_persisted: agent=%s status=%s workflow_id=%s latency_ms=%.1f",
                trace.agent_name, trace.status.value,
                trace.workflow_id or kwargs.get("workflow_id", ""),
                trace.latency_ms or 0.0,
            )
        except Exception as e:
            logger.warning(
                "harness_trace_persist_failed: agent=%s error=%s（不影响主流程）",
                trace.agent_name, e,
            )

    # ── 追踪管理 ──

    def start_trace(
        self,
        agent_name: str,
        user_message: str,
        provider: str = "",
        user_id: str = "",
        project_id: str = "",
        scope: str = "",
        workflow_id: str = "",
    ) -> AgentTrace:
        """开始新的执行轨迹

        v1.4.0：新增 scope 参数（借鉴 YC QM 四级作用域 personal/project/team/org），
        用于标记本次 Agent 执行所属的作用域，便于审计与可还原追溯。默认空字符串，
        向后兼容。
        v1.12.x：新增 workflow_id 参数（跨 Agent 协作编排 ID），同一用户请求
        的所有 Agent 执行共享同一 workflow_id，便于链路回溯与 per-agent 聚合。
        """
        trace = AgentTrace(
            agent_name=agent_name,
            agent_version=settings.app_version,
            provider=provider,
            model="",
            started_at=time.time(),
            user_message=user_message,
            user_message_truncated=user_message[:200],
            user_id=user_id,
            project_id=project_id,
            scope=scope,
            workflow_id=workflow_id,
            context_source="harness",
        )
        if get_settings().otel_genai_semconv_enabled and not trace.w3c_trace:
            trace.w3c_trace = _generate_w3c_trace_context()
        return trace

    def finish_trace(self, trace: AgentTrace, status: AgentRunStatus):
        """完成轨迹记录"""
        trace.finish(status)
        if self.config.trace_enabled:
            self._traces.append(trace)
            # 限制内存中轨迹数量
            if len(self._traces) > self.config.trace_max_history:
                self._traces = self._traces[-self.config.trace_max_history:]

    def get_traces(
        self,
        agent_name: str | None = None,
        status: AgentRunStatus | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """查询轨迹记录"""
        traces = self._traces
        if agent_name:
            traces = [t for t in traces if t.agent_name == agent_name]
        if status:
            traces = [t for t in traces if t.status == status]
        return [t.to_dict() for t in traces[-limit:]]

    # ── 指标查询 ──

    def get_metrics(self) -> dict:
        """获取 Harness 运行时指标"""
        total = max(self._metrics["total_runs"], 1)
        return {
            **self._metrics,
            "success_rate": round(self._metrics["success_runs"] / total * 100, 1),
            "fallback_rate": round(self._metrics["fallback_runs"] / total * 100, 1),
            "avg_latency_ms": round(
                self._metrics["total_latency_ms"] / total, 2
            ),
            "trace_count": len(self._traces),
            "registered_agents": list(self._agent_registry.keys()),
        }

    # ── 上下文管理（5-tier memory model）──

    _TIER_SIZES = {
        "ephemeral": 1,      # 当前轮次
        "session": 10,       # 当前会话
        "project": 50,       # 当前项目
        "user": 100,         # 当前用户
        "knowledge_base": 0,  # 知识库（无限，RAG 检索）
    }

    def build_context(
        self,
        history: list[dict] | None = None,
        tier: str = "session",
        max_rounds: int | None = None,
    ) -> str:
        """构建 tiered 上下文（5 层记忆模型）。

        Args:
            history: 对话历史
            tier: 上下文层级 (ephemeral/session/project/user/knowledge_base)
            max_rounds: 最大轮数

        Returns:
            格式化的上下文字符串
        """
        if not history:
            return ""

        max_rounds = max_rounds or self._TIER_SIZES.get(tier, self.config.max_history_rounds)
        recent = history[-max_rounds:]
        lines = []
        for h in recent:
            role = h.get("role", "user")
            content = h.get("content", "")[:500]
            agent_t = h.get("agent_type", "")
            prefix = f"[{agent_t}] " if agent_t and role == "assistant" else ""
            lines.append(f"{prefix}{role}: {content}")
        return "\n".join(lines)

    # ── Eval 循环（离线评估）──

    def run_eval(self, traces: list[AgentTrace] | None = None) -> dict:
        """离线评估 Agent 输出质量。

        基于轨迹记录计算：
        - 成功率
        - 平均延迟
        - 降级率
        - Token 效率
        """
        targets = traces or self._traces[-100:]
        if not targets:
            return {"status": "no_data", "metrics": {}}

        total = len(targets)
        success = sum(1 for t in targets if t.status == AgentRunStatus.SUCCESS)
        fallback = sum(1 for t in targets if t.fallback_used)
        avg_latency = sum(t.latency_ms for t in targets if t.latency_ms > 0) / max(total, 1)
        avg_tokens = sum(t.total_tokens for t in targets) / max(total, 1)

        return {
            "status": "ok",
            "sample_size": total,
            "metrics": {
                "success_rate": round(success / total * 100, 1),
                "fallback_rate": round(fallback / total * 100, 1),
                "avg_latency_ms": round(avg_latency, 2),
                "avg_tokens_per_run": round(avg_tokens, 0),
                "total_tokens": sum(t.total_tokens for t in targets),
            },
        }


# ════════════════════════════════════════════════════════════════
# 全局单例
# ════════════════════════════════════════════════════════════════

_harness: AgentRuntime | None = None


def get_harness() -> AgentRuntime:
    """获取全局 Harness 实例"""
    global _harness
    if _harness is None:
        # v1.15.x 走查修复：超时/重试从 settings 注入（此前 HarnessConfig 默认值
        # 60s 与 settings.harness_agent_timeout_seconds 脱节，真实 LLM 下
        # orchestrate/A2A 的工具循环子任务被 60s 误杀）
        _settings = get_settings()
        _harness = AgentRuntime(HarnessConfig(
            agent_timeout_seconds=_settings.harness_agent_timeout_seconds,
            max_retries=_settings.harness_max_retries,
        ))
        # 注册所有已知 Agent
        from app.agents import (
            OrchestratorAgent, DesignerAgent, BudgetAgent,
            ProcurementAgent, ConstructionAgent, SettlementAgent,
            QAInspectorAgent, ConciergeAgent, ContentPublisherAgent,
            AdminAgent,
            KitchenAgent, BathroomAgent, MepAgent, ApplianceAgent,
            FurnitureAgent, DoorWindowAgent, FilesAgent, ProductsAgent,
            IdentityAgent, NotificationsAgent, TakeoffAgent, IfcExportAgent,
        )
        _harness.register_agent("orchestrator", OrchestratorAgent)
        _harness.register_agent("designer", DesignerAgent)
        _harness.register_agent("budget", BudgetAgent)
        _harness.register_agent("procurement", ProcurementAgent)
        _harness.register_agent("construction", ConstructionAgent)
        _harness.register_agent("settlement", SettlementAgent)
        _harness.register_agent("qa_inspector", QAInspectorAgent)
        _harness.register_agent("concierge", ConciergeAgent)
        _harness.register_agent("content_publisher", ContentPublisherAgent)
        _harness.register_agent("admin", AdminAgent)
        # v1.13.x 逐项审计修复：补齐 12 个专用 Agent 注册
        # （此前 a2a.py Agent Card 声称 22 个 Agent，harness 仅注册 10 个 →
        #  A2A 任务与 IM 群聊对 12 个专用 Agent 均返回「未注册」/规则占位）
        _harness.register_agent("kitchen", KitchenAgent)
        _harness.register_agent("bathroom", BathroomAgent)
        _harness.register_agent("mep", MepAgent)
        _harness.register_agent("appliance", ApplianceAgent)
        _harness.register_agent("furniture", FurnitureAgent)
        _harness.register_agent("door_window", DoorWindowAgent)
        _harness.register_agent("files", FilesAgent)
        _harness.register_agent("products", ProductsAgent)
        _harness.register_agent("identity", IdentityAgent)
        _harness.register_agent("notifications", NotificationsAgent)
        _harness.register_agent("takeoff", TakeoffAgent)
        _harness.register_agent("ifc_export", IfcExportAgent)
        # v1.15.x 走查修复：商业运营 Agent（growth/marketing/competitor_research/
        # finance_recon）此前未注册——flag 默认 True 但 A2A/编排/聊天均无入口，
        # 显式 agent_type 被静默路由到 orchestrator/budget 答非所问。
        # 注册后由 API 层做管理员角色门控（平台运营专用，非用户可见技能）。
        from app.agents import (
            GrowthAgent, MarketingAgent, CompetitorResearchAgent, FinanceReconAgent,
        )
        _harness.register_agent("growth", GrowthAgent)
        _harness.register_agent("marketing", MarketingAgent)
        _harness.register_agent("competitor_research", CompetitorResearchAgent)
        _harness.register_agent("finance_recon", FinanceReconAgent)
    return _harness
