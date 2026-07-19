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

    # 延迟
    latency_ms: float = 0.0
    first_token_latency_ms: float = 0.0

    # 元数据
    error_message: str = ""
    error_type: str = ""
    user_id: str = ""
    project_id: str = ""
    context_source: str = ""  # "harness" | "raw"

    def to_dict(self) -> dict:
        return {
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
            "latency_ms": round(self.latency_ms, 2),
            "first_token_latency_ms": round(self.first_token_latency_ms, 2),
            "error_message": self.error_message,
            "error_type": self.error_type,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "context_source": self.context_source,
        }

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
    agent_timeout_seconds: int = 60
    stream_timeout_seconds: int = 120

    # 追踪配置
    trace_enabled: bool = True
    trace_max_history: int = 500  # 内存中最多保留的轨迹数
    trace_persist_to_db: bool = False  # 是否持久化到数据库（v1.2.0 默认关闭，后续版本开启）

    # 评估配置
    eval_enabled: bool = False
    eval_sample_rate: float = 0.1  # 采样率

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
            agent.agent_name, user_message, getattr(agent, "provider", "unknown")
        )
        self._metrics["total_runs"] += 1

        try:
            # 检查是否 MOCK_MODE
            from app.main import MOCK_MODE
            if MOCK_MODE and mock_fn:
                result = mock_fn(user_message)
                trace.response = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
                trace.finish(AgentRunStatus.SUCCESS)
                self._metrics["success_runs"] += 1
                return {"reply": result if isinstance(result, str) else result.get("reply", ""),
                        "trace": trace.to_dict()}

            # 尝试 LLM 调用
            for attempt in range(self.config.max_retries + 1):
                try:
                    if hasattr(agent, "think_with_tools") and agent.tools:
                        result = await asyncio.wait_for(
                            agent.think_with_tools(user_message, **kwargs),
                            timeout=self.config.agent_timeout_seconds,
                        )
                        reply = result.get("final_reply", "")
                        trace.tool_calls = result.get("tool_calls", [])
                        trace.tool_call_count = len(trace.tool_calls)
                        trace.tool_call_rounds = result.get("rounds", 0)
                    else:
                        reply = await asyncio.wait_for(
                            agent.think(user_message, **kwargs),
                            timeout=self.config.agent_timeout_seconds,
                        )
                    trace.response = reply
                    trace.finish(AgentRunStatus.SUCCESS)
                    self._metrics["success_runs"] += 1
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
            return self._apply_fallback(agent.agent_name, user_message, trace, mock_fn)

        except Exception as e:
            trace.error_message = str(e)
            trace.error_type = type(e).__name__
            trace.fallback_used = True
            trace.fallback_reason = f"exception: {type(e).__name__}"
            logger.error(
                "harness_agent_error: agent=%s error=%s",
                agent.agent_name, e,
            )
            return self._apply_fallback(agent.agent_name, user_message, trace, mock_fn)

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

    # ── 追踪管理 ──

    def start_trace(
        self,
        agent_name: str,
        user_message: str,
        provider: str = "",
        user_id: str = "",
        project_id: str = "",
    ) -> AgentTrace:
        """开始新的执行轨迹"""
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
            context_source="harness",
        )
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
        _harness = AgentRuntime()
        # 注册所有已知 Agent
        from app.agents import (
            OrchestratorAgent, DesignerAgent, BudgetAgent,
            ProcurementAgent, ConstructionAgent, SettlementAgent,
            QAInspectorAgent, ConciergeAgent, ContentPublisherAgent,
            AdminAgent,
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
    return _harness
