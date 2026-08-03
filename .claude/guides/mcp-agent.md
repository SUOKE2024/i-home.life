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
pytest tests/test_agent_trace_scope.py     # AgentTrace scope
pytest tests/test_tool_audit_fields.py     # 工具审计字段
pytest tests/test_agent_skill.py           # Skill 资产化（v1.8.0）
pytest tests/test_agent_posture.py         # 三档安全 posture（v1.8.0）
```

新增 Agent 必须补测试（参考 `tests/test_agents.py` 模式）。

## v1.4.0 借鉴落地（YC QM / OWLFY / LocalAI）

本节记录 v1.4.0 对三篇行业文章的借鉴落地，所有改动均为 additive API 增强，向后兼容。

### YC QM Scope 治理（4 级作用域贯穿）

YC QM 提出 personal / project / team / org 四级作用域，索克在 v1.4.x 已实现 memory 层，v1.4.0 贯穿到 cache / trace / audit 层：

| 层 | 文件 | scope 体现 |
|----|------|-----------|
| Memory | `app/services/agent_memory_service.py:33-37` `SCOPE_PERSONAL/PROJECT/TEAM/ORG` | 已实现（v1.4.x），唯一约束含 scope/project_id |
| Cache | `app/services/cache_service.py:60` `build_isolated_key(..., scope=None)` | v1.4.0 新增 scope 参数，key 格式 `u:{uid}:p:{pid}:s:{scope}:{base}` |
| Trace | `app/agents/harness.py:118` `AgentTrace.scope` | v1.4.0 新增字段，`start_trace(..., scope="")` 透传 |
| Audit | `app/services/agent_tool_registry.py:846` `execute(..., _scope="", _trace_id="")` | v1.4.0 新增 4 个隐式上下文参数，details 扩展 |

scope 常量统一从 `agent_memory_service` import，不重复定义。cache 的 scope 参数默认 None，维持 v1.3.0 key 格式（向后兼容）。

### OWLFY 端侧零 TOKEN + LocalAI OpenAI 兼容

端云协同已在 v1.4.x 实现，配置见 `.env.example` 的"施工边缘盒子本地推理端点"段：

- `local` provider（`app/agents/base.py:42-48`）：Ollama/LocalAI OpenAI 兼容端点
- 无 `LOCAL_LLM_API_KEY` 时视为不可用，fallback 到 qwen/glm（**不 mock**，符合诚实降级）
- `ECONOMY_PROVIDERS=local,qwen,glm` 后 economy 档优先本地推理，数据不出现场、token 成本归零
- 意图成本路由（`cost_tier` standard/economy）受 `COST_TIERED_ROUTING_ENABLED` 控制

### AI 决策审计可还原（QM"可还原"治理）

`tool_registry.execute()` 的审计 details 扩展为 7 字段：

```python
details = {
    "tool": name, "project_id": _project_id, "category": tool.category,
    "agent_id": _agent_id,       # v1.4.0: 哪个 Agent
    "model_source": _model_source,  # v1.4.0: 用什么模型
    "scope": _scope,             # v1.4.0: 什么作用域
    "trace_id": _trace_id,       # v1.4.0: 对应哪条 trace
}
```

使审计能回答 QM 的核心追问："哪个 Agent、用什么模型、在什么 scope 下、对应哪条 trace 做了工具调用"。`base.py` think_with_tools 透传 `_agent_id=self.agent_name` + `_model_source=self.provider`；voice 路径透传 `_agent_id=f"voice:{func_name}"`。

## v1.8.0 借鉴落地（YC QM 完整版：Scope API 贯通 + Skill 资产化 + 三档 posture）

v1.4.x 完成了 QM 借鉴第一层（scope 到 memory/cache/trace/audit 的 model+service+test），v1.8.0 贯通 API 层并落地两个 P0 能力。所有改动 additive，向后兼容。

### Scope API 贯通（P0-①，完善半成品）

v1.4.x 的 scope 在 service 层齐备但 API 层 4 个调用点未传 scope，`AgentTrace.scope` 从未被赋值。v1.8.0 补齐：

| 调用点 | 文件 | 改动 |
|--------|------|------|
| 记忆 CRUD | `app/api/agent_memory.py` | `MemoryCreateRequest` 加 `scope`/`project_id`，list 支持 scope 过滤 |
| 上下文注入 | `app/services/agent_context_service.py` | `build_memory_context` 按 scope/project_id 查记忆 |
| chat 提取 | `app/api/agents.py` | chat 请求体加 `project_id`，有则按 project scope 提取记忆 |
| A2A trace | `app/api/a2a.py:254` | `start_trace(..., scope="project" if project_id else "personal")` |

### Skill 资产化（P0-②，完整版）

借鉴 QM "scope-owned + 可授权共享 + admin 门控提升 + 版本回退 + skill_pack 导入"。

- **模型** [app/models/agent_skill.py](file:///Users/netsong/Developer/i-home.life/app/models/agent_skill.py) `AgentSkill`：owner_scope(personal/project/team/org) + version + status(draft/active/archived) + share_scope(none/grant/org) + share_grants(JSON) + parent_version_id(回退链)
- **服务** [app/services/agent_skill_service.py](file:///Users/netsong/Developer/i-home.life/app/services/agent_skill_service.py)：CRUD / update(version+1, 旧版 archived) / rollback(复制历史 version 创建新版) / share(grant_to 授权) / promote_to_org(仅 admin) / import_skill_pack(httpx GET raw URL, 字段白名单, 失败 422) / instantiate(`type()` 动态建 BaseAgent 子类)
- **API** [app/api/agent_skills.py](file:///Users/netsong/Developer/i-home.life/app/api/agent_skills.py) 前缀 `/agents/skills`：10 个端点，`agent_skill_enabled` 控制，personal scope 强制 owner_id=当前用户
- **测试** `tests/test_agent_skill.py` 13 例：CRUD / scope 隔离 / 授权共享 / admin 提升 / 版本回退 / git 导入 / instantiate

### 三档安全 posture（P0-③，完整版）

借鉴 QM "strict 每个工具调用暂停等人批准 / auto PII screening / dangerous 全放行"。FC 无状态环境调整为"拒绝-重新触发"模式。

| posture | 行为 | 配置 |
|---------|------|------|
| `strict` | 高危工具拒绝执行 → 创建 `AgentApproval`(pending) → 返回 `needs_approval` | `agent_strict_high_risk_tools`（逗号分隔，空=全部需批准） |
| `auto`（默认） | 正常执行，外部数据过 PII masking | — |
| `dangerous` | 全放行 | 仅 `execute_approved` 内部传 `_posture="dangerous"` 绕过二次批准 |

- **模型** [app/models/agent_approval.py](file:///Users/netsong/Developer/i-home.life/app/models/agent_approval.py) `AgentApproval`：approval_id(`apr_`+12hex) + state(pending/approved/rejected/expired) + arguments(JSON) + expires_at(24h TTL)
- **拦截点** [app/services/agent_tool_registry.py:880](file:///Users/netsong/Developer/i-home.life/app/services/agent_tool_registry.py) `execute(..., _posture="")`：strict + 命中高危 → 创建 approval → 返回 `{"error":"needs_approval","approval_id":...}`
- **服务** [app/services/agent_approval_service.py](file:///Users/netsong/Developer/i-home.life/app/services/agent_approval_service.py)：create / approve / reject / execute_approved(校验 approved+未过期→execute 传 dangerous) / expire_outdated
- **API** [app/api/agent_approvals.py](file:///Users/netsong/Developer/i-home.life/app/api/agent_approvals.py) 前缀 `/agents/approvals`：list pending / get / approve / reject / execute
- **测试** `tests/test_agent_posture.py` 14 例：strict 拦截(高危清单空/匹配) / strict 放行(非高危) / auto / dangerous / approve+execute / reject+execute / 状态机 / 过期 / API 全流程 / 非 owner 404
