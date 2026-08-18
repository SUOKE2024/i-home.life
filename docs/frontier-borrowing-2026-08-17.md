# 2026 前沿借鉴落地执行记录（v1.15.5）

> 执行日期：2026-08-17 · 依据：`基于 2026 技术前沿的诊断评估报告`（P0/P1 落地 + P2 路线图）
> 回归测试：`tests/test_frontier_v1153.py` 49 用例（mock 确定性，全绿）
> 前沿出处：信通院 2026 智能体十大关键词 / LangChain Long-Horizon Agents /
> Anthropic dreaming / MCP 2026-07-28 信任层（AAIF）/ EdgeBench + ITBench-AA / AP2（FIDO）

## 一、已落地项（本版本代码 + 测试 + 门禁全绿）

### P0-1 失败案例蒸馏闭环（EdgeBench「失败是最贵的学习信号」）

此前失败轨迹（harness FAILED/FALLBACK）完全不沉淀 Case——失败信号被丢弃。

| 组件 | 改动 | 验证 |
|------|------|------|
| 模型 | `agent_cases.failure_type` 列（病理分类键）+ alembic `v1c2d3e4f5a6` + runtime 迁移 v10 | 幂等迁移 |
| 服务 | `agent_case_service.extract_failure_case_from_trace`：失败轨迹**确定性**（零 LLM 成本）沉淀失败 Case；`_classify_failure_type` 病理分类（timeout/empty_reply/fallback/llm_error/tool_loop/unknown） | 7 用例 |
| harness | 降级/异常分支补 `_maybe_extract_case` 调用（此前仅成功分支） | 端到端用例 |
| 进化 | `distill_anti_pattern_skill`：同病理 ≥3 条 → 蒸馏「[反模式] Skill」；`run_skill_evolution_cycle` 新增失败簇蒸馏阶段；`get_anti_pattern_hints`：执行前注入「历史失败教训」警告（ACTIVE 优先，DRAFT 回退） | 5 用例 |
| 配置 | `agent_failure_learning_enabled=True`（关闭即回退失败不沉淀） | flag 用例 |

设计原则：**诊断-归因分离**（HarnessBank）——病理为键而非任务为键，抗过拟合；
反模式与正向 Skill 命名前缀分离，不混入 outcome 回写统计。

### P0-2 协议信任层（AAIF「可验证证据在协议边界」+ AP2「可验证意图」）

| 组件 | 改动 | 验证 |
|------|------|------|
| A2A 证据链 | `A2ATaskResponse` + `a2a_tasks` 表新增 `trace_id`/`evidence`（agent_name/workflow_id/status/duration_ms/degraded）——所有路径（成功/降级/权限拒绝/异常/未注册）均附证据，客户端可凭 trace_id 回放溯源 | 3 用例 |
| 可验证支付意图 | `agent_payment_intent` 服务：HMAC-SHA256 意图 token（复用 PASETO 主密钥，payload=order_id\|amount\|actor\|expires，TTL 600s）；`POST /procurement/orders/{id}/payment-intent`（owner/admin + flag 门控）+ `POST /procurement/payment-intents/verify` | 10 用例（含篡改/过期/字段比对/403/503） |
| 配置 | `agent_payment_intent_enabled=True` + `payment_intent_ttl_seconds=600` | — |

**诚实标注**：意图服务只做签发/验证，不触发任何真实扣款；escrow 担保支付端点绑定
为 P2 路线图下一步（见下文）。绑定前 token 是「可验证付款建议」而非支付凭据。

### P1-3 会话上下文压缩（LangChain 语境工程）

`context_compaction_service.compact_history`：history 超阈值（`chat_context_max_turns=24`，
端点内保留窗口 10 条）时，头部 LLM 摘要为 system 消息 + 尾部保留；摘要失败回退纯截断
（诚实降级，不丢尾部关键消息）。`/chat` 与 `/chat/stream` 双路径接入；摘要走
`BaseAgent` fallback chain（economy 档，不绕降级纪律）。5 用例 + 无 key 环境集成用例。

### P1-4 任务复杂度自适应路由（ARISE 自适应分辨率）

`BaseAgent._estimate_task_complexity` 确定性规则（领域关键词共现 ≥3 / 全流程词 / 长度
>300 → high；≤24 字无领域词 → low）→ `_resolve_chain(complexity)`：standard 档 low 复杂度
低成本供应商优先（省成本降时延，主供应商兜底），high 保持推理模型优先；economy 档与
无参旧调用完全向后兼容（`adaptive_reasoning_routing_enabled=True`）。12 用例。

## 二、诚实遗留与 P2 路线图（未在本版本落地）

| # | 项 | 现状 | 建议触发条件 |
|---|----|------|-------------|
| P2-1 | escrow 支付端点绑定意图 token | 意图服务已就绪，`payment/escrow` 链路未消费 | 采购 Agent 生产代客下单上线前 |
| P2-2 | Long-Horizon 项目生命周期 | sessions/memory 已有，缺 project-scoped 持久任务清单 + 里程碑主动推送（用户侧周报，可复用 daily-briefing FC 触发器模式） | 用户留存数据支持时 |
| P2-3 | 具身数据导出（Robot-Ready Home） | 空间语义底座已有，缺开放 JSON 导出格式 + 施工 QA「机器人友好校验项」（门宽/插座高度/无门槛）；对标尚品宅配×启元机器人同名生态 | 行业具身数据标准明朗后 |
| P2-4 | 终端任务成功率评测 | IHomeEval 为启发式代理指标；ITBench-AA 式「用户目标达成率」需离线 LLM-judge 抽样扩围（llm_judge.py 已有雏形） | 评测预算允许时 |
| 遗留 | `record_skill_outcome` 语义级失败仍需 LLM-judge 信号 | 确定性失败已闭环（v1.13.7 + 本版本 failure_type），语义失败抽样待接 | 同上 |

## 三、质量门禁记录

- 新增测试：`tests/test_frontier_v1153.py` 49 用例全绿
- 回归：agent_case / cost_tier_routing / llm_cost_optimization / sse / a2a 102 用例全绿
- flake8 / mypy / pre-commit 全绿（随版本发布门禁复核）
- 基线：2506 → **2555**（+49，随 v1.15.5 校准，见 `scripts/test_baseline.json`）
