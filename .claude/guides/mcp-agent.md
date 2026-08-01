# MCP / Agent 开发规范（mcp-agent.md）

> 22 个 AI Agent + MCP 2026-07-28 协议 + A2A 协作规范。所有事实基于当前代码，
> 改代码前先读对应源码。**禁止用硬编码假数据伪装真实能力（v1.1.31 教训）。**

## Agent 体系总览

24 个 Agent 文件在 [app/agents/](file:///Users/netsong/Developer/i-home.life/app/agents/)：

| 类别 | Agent |
|------|-------|
| 核心 | designer / budget / procurement / construction / settlement |
| 空间 | takeoff_agent / ifc_export_agent / mep_agent / kitchen_agent / bathroom_agent / door_window_agent / furniture_agent / appliance_agent |
| 协作 | orchestrator / concierge / qa_inspector / content_publisher / notifications_agent / files_agent / identity_agent / admin / products_agent |
| 编排 | harness（AgentHarness 运行时） |

## BaseAgent 基类

完整实现在 [app/agents/base.py](file:///Users/netsong/Developer/i-home.life/app/agents/base.py)。新建 Agent 必须继承 `BaseAgent`：

```python
from app.agents.base import BaseAgent
from app.services.agent_tool_registry import tool_registry

class DesignerAgent(BaseAgent):
    agent_name = "designer"               # 必填，唯一标识
    provider = "deepseek"                  # 主供应商：deepseek|glm|qwen|doubao
    tools = tool_registry.get_openai_schemas_for_category("design")  # 可选
    system_prompt = """你是索克家居 AI 设计 Agent..."""  # 必填，含输出格式约束

# 调用
agent = DesignerAgent()
reply = await agent.think("帮我设计客厅方案")                    # 普通对话
result = await agent.think_with_tools("120平北欧风预算多少？")   # FunctionCall
await agent.close()
```

**类属性约定**：
- `agent_name: str` — Agent 唯一标识，用于路由/日志/trace
- `system_prompt: str` — 系统指令，**必须含输出格式约束**（如"直接输出 JSON"）
- `provider: str` — 主 LLM 供应商，默认 "deepseek"
- `tools: list[dict]` — FunctionCall 工具 schema，从 `tool_registry` 获取

## LLM 调用与 fallback chain

**禁止**绕过 `BaseAgent._chat()` 直接调 LLM API。fallback chain 实现在 [base.py:124](file:///Users/netsong/Developer/i-home.life/app/agents/base.py)：

```
主供应商 → qwen → glm → doubao（受 settings.llm_fallback_enabled 控制）
```

- `_chat()` 遍历 chain，单供应商失败降级到下一个
- API key 为空时返回 `[mock] {agent_name} 响应：API key 未配置`（诚实降级，非假数据）
- `finish_reason="length"` 时降温 0.3 重试 1 次（推理模型 reasoning 占满 token）
- httpx timeout=180s（容纳推理模型），Nginx 侧 300s
- `max_tokens=8192`（容纳 reasoning_content + 输出）

**供应商注册表** `PROVIDER_REGISTRY`（base.py:13）：deepseek / glm / qwen / doubao，均用 OpenAI 兼容 `/chat/completions` 接口。

## Agent 方法

- `think(user_message, context="", db=None, project_id="")` — 高层封装
  - 自动拼接 system_prompt + 上下文
  - `db` 传入时前置 AgenticRAG 证据检索（`agentic_rag_enabled`）
  - 输出经 Model Spec HC 硬约束校验 + 反驳重生成（`model_spec_enabled`）
- `think_with_tools(user_message, ...)` — 带 FunctionCall
- `_chat(messages, max_retries=0, with_tools=False)` — 底层 LLM 调用
- `close()` — 关闭 httpx 客户端

## AgentHarness 编排

[app/agents/harness.py](file:///Users/netsong/Developer/i-home.life/app/agents/harness.py) 提供统一运行时：

```python
from app.agents.harness import get_harness, AgentRunStatus
harness = get_harness()  # 单例
harness.register_agent("designer", DesignerAgent)
result = await harness.run(agent_name="designer", message="...", ...)
```

- `AgentRunStatus`：running / completed / failed / timeout / fallback
- `FallbackStrategy`：超时/失败时的降级策略
- `AgentTrace`：执行轨迹，`harness_trace_enabled=True` 时记录
- `run_eval()`：评估轨迹，`eval_enabled=True` 时可用
- 配置：`harness_agent_timeout_seconds=60` / `harness_max_retries=1` / `harness_trace_max_history=500`

## Orchestrator 多 Agent 协作

[app/agents/orchestrator.py](file:///Users/netsong/Developer/i-home.life/app/agents/orchestrator.py) `OrchestratorAgent`：

- `classify_intent(message)` — LLM 意图分类（10 类），失败降级到 `fallback_classify` 关键词匹配
- 语音场景：`voice_agent_orchestration_enabled=True` 时 `POST /api/voice/orchestrate` 可用

## 工具注册（FunctionCall）

工具通过 [app/services/agent_tool_registry.py](file:///Users/netsong/Developer/i-home.life/app/services/agent_tool_registry.py) 的 `tool_registry` 单例管理：

```python
# 获取某类别的工具 schema（OpenAI 兼容格式）
tools = tool_registry.get_openai_schemas_for_category("design")
```

- `tool_real_data_enabled=True`（默认）时工具 handler 查真实 DB
- False 时回退硬编码 mock（仅紧急回滚用）
- `agent_function_call_max_rounds=5` 单次对话最大工具调用轮数

## MCP Server（2026-07-28 规范）

完整实现在 [app/mcp/server.py](file:///Users/netsong/Developer/i-home.life/app/mcp/server.py) `MCPServer` 类。**纯 Python dict 实现，不依赖第三方 MCP SDK**。

### 8 项规范对应

| 规范 | 实现位置 |
|------|---------|
| stateless 核心 | `PROTOCOL_VERSION = "2026-07-28"`，无 initialize 握手 / 无 Mcp-Session-Id |
| server/discover RPC | `discover()` 方法（server.py:104） |
| header-routing | `dispatch_method()` 按 JSON-RPC method 路由（server.py:294） |
| cacheable list results | `list_tools_with_cache()` 返回 etag + cache_hint（server.py:195） |
| MRTR 多轮往返 | [app/mcp/mrtr.py](file:///Users/netsong/Developer/i-home.life/app/mcp/mrtr.py) |
| RFC9207 authorization | `get_server_card()` 含 authorization 元数据（server.py:133） |
| Tasks 扩展 | [app/mcp/extensions/tasks.py](file:///Users/netsong/Developer/i-home.life/app/mcp/extensions/tasks.py) `TasksExtension` |
| Server Card | `get_server_card()` + `.well-known` 暴露 |

### 核心 API

```python
from app.mcp.server import MCPServer
server = MCPServer()

# 工具列表（带缓存）
tools_data = server.list_tools_with_cache()  # {tools, etag, cache_hint}

# 调用工具
result = await server.call_tool("tool_name", {"arg": "value"})
# 返回 MCP 格式: {content: [{type:"text", text:"..."}], isError: bool}

# JSON-RPC 2.0 分发
result, error = await server.dispatch_method(method="tools/call", params={...})

# 扩展
server.list_extensions()  # [{"name":"tasks","version":"1.0.0"}]
```

### 关键约束

- `SERVER_VERSION` 必须与 `app/config.py` `app_version` 一致
- `LIST_CACHE_TTL=300` 秒，客户端可据此缓存工具目录
- 工具来源是 `tool_registry` 单例，**禁止**在 MCP 层硬编码工具
- 工具响应必须是 MCP content 格式 `{content: [{type:"text", text}], isError}`

### Tasks 扩展

`TasksExtension`（tasks.py:68，VERSION="1.0.0"）实现任务生命周期：

- `create_task` / `update_task` / `get_task` / `list_tasks` / `cancel_task`
- `_Task` 状态机：submitted / working / completed / failed
- `_cleanup_expired` 清理过期任务

受 `mcp_tasks_extension_enabled` 控制，延迟加载（避免循环导入）。

## A2A 协议

任务持久化模型 [app/models/a2a_task.py](file:///Users/netsong/Developer/i-home.life/app/models/a2a_task.py) `A2ATask`：

- `task_id`：`a2a_` 前缀 + 12 位 hex，唯一索引
- `state`：submitted / working / completed / failed
- `expires_at`：默认 24h TTL（`A2A_TASK_DEFAULT_TTL_HOURS`），过期自动清理
- v1.2.4 从内存 dict 迁移到数据库，进程重启不丢失

端点在 [app/api/a2a.py](file:///Users/netsong/Developer/i-home.life/app/api/a2a.py)，受 `a2a_enabled` 控制。Agent Card 通过 `GET /card` 发布。

## 降级原则（硬约束）

任何 LLM / 外部依赖不可用时**诚实降级**，**禁止**硬编码假数据：

```python
# 正确：诚实降级
if not cfg["api_key"]():
    return f"[mock] {self.agent_name} 响应：API key 未配置"

# 错误：伪装真实能力（v1.1.31 修复 6 处）
return {"confidence": 0.95, "data": hardcoded_fake_data}  # 禁止
```

- 降级路径必须可测试（写测试覆盖降级分支）
- `real_ai_render_enabled=False` 时走 mock 渲染，明确标注
- LLM 不可用时返回明确提示，不返回伪造的设计方案/预算数据

## 在线进化闭环

`agent_evolution_enabled=True` 时（默认）：

- 收集执行轨迹 → 分析失败模式 → 优化 prompt / 降级策略
- `agent_evolution_trace_min_samples=20` 最小样本数
- 轨迹数据来自 `AgentTrace`，勿手动清理

## 质量门禁

```bash
pytest tests/test_agents.py tests/test_agents_llm.py tests/test_a2a.py
pytest tests/test_cache_user_isolation.py  # 缓存隔离
```

新增 Agent 必须补测试（参考 `tests/test_agents.py` 模式）。
