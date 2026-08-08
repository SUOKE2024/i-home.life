# AI 自进化功能使用指南

> i-home.life v1.10.2 — 借鉴 EverMind EverOS Agent Memory + SkillCorpus + HarnessBank

## 一、功能概述

i-home.life 平台的 AI Agent 现在具备**自进化**能力：Agent 会从每次任务执行中自动沉淀经验，并在后续相似任务中复用这些经验，实现"越用越聪明"。

本功能受三个独立 feature flag 控制，**默认全部关闭**，需管理员按需灰度开启：

| Feature Flag | 作用 | 默认值 |
|-------------|------|--------|
| `agent_case_extraction_enabled` | 从 Agent 执行轨迹自动提取结构化经验 Case | False |
| `agent_skill_distillation_enabled` | Case 聚类蒸馏为可复用 Skill + 执行前检索注入 | False |
| `agent_skill_evolution_enabled` | Skill 随成败进化（三维质控 + 诊断归因） | False |

## 二、自进化管线工作原理

```
Agent 执行任务 → 生成执行轨迹（AgentTrace）
    ↓
压缩去噪 → 过滤非目标导向对话 → LLM 提取为 Case
    ↓
Case 持久化（task_intent + approach + quality_score）
    ↓
同主题 Case 积累（≥3条）→ LLM 蒸馏为 Skill
    ↓
Skill 校验 → 高质量 Skill 晋升为 active
    ↓
Agent 执行新任务前 → 检索同类 Case + Skill 注入上下文
    ↓
任务成败回写 Skill → 三维质控评估 → 低质淘汰 / 高质晋升
```

## 三、什么是 Agent Case？

每次 Agent 完成一个目标导向任务后（闲聊/简单问答不入 Case），系统会自动提取一条结构化 Case 记录：

- **task_intent**：自包含的任务意图陈述（如"设计北欧风格客厅方案，预算5万"）
- **approach**：分步执行记录（尝试了什么/用了什么工具/结果如何/是否重试）
- **quality_score**：0-1 的完成质量自评
- **outcome**：success / partial / failed / unknown

Case 按 user_id 强隔离存储，仅在同一用户后续任务中被检索复用。

## 四、什么是 Agent Skill？

当同主题 Case 积累到一定数量（≥3条），系统会自动蒸馏出一个可复用 Skill：

- 包含通用的 system_prompt（何时使用、关键步骤、已知陷阱）
- 包含验收用例（用于后续质量评估）
- 新建时为 draft 状态，质量达标后自动晋升 active

Skill 会在 Agent 执行相似任务时被自动检索注入，让 Agent 不必从零开始。

## 五、Skill 如何进化？

Skill 不是一成不变的，它随使用持续进化：

1. **成败回写**：Agent 使用某 Skill 后任务成败会记录到 Skill 的 success_count / fail_count
2. **三维质控**（借鉴 SkillCorpus）：
   - **Utility（实用性）**：成功率 × 使用频次
   - **Robustness（鲁棒性）**：Wilson 置信区间下界
   - **Safety（安全性）**：失败率反向
3. **自动晋升/淘汰**：
   - 使用≥3次且综合评分≥0.6 → draft 晋升 active
   - 使用≥5次且综合评分<0.3 → 自动 archived 淘汰

## 六、诊断归因循环（借鉴 HarnessBank）

当 Skill 被修改（patch）后，系统采用「诊断-归因分离」原则验证改进是否真实有效：

- **诊断**（LLM）：分析失败 Case 的 (WHERE=哪个环节, WHY=为何失败) 病理
- **归因**（确定性代码）：配对比例显著性检验（z ≥ 1.96 才采纳，95% 置信）
- **抗过拟合**：以 (WHERE×WHY) 病理为键存档，而非以"任务"为键

这确保了 Skill 的每次改进都是统计意义上可靠的，而非测量误差或随机波动。

## 七、如何开启

在 `.env` 或 `.env.production` 中设置：

```bash
# 按需灰度开启（建议先开 P0 Case 提取，观察积累后再开蒸馏）
AGENT_CASE_EXTRACTION_ENABLED=true
AGENT_SKILL_DISTILLATION_ENABLED=true
AGENT_SKILL_EVOLUTION_ENABLED=true
```

回滚：`bash scripts/rollback.sh v1.10.1`（一键关闭三个 flag）

## 八、隐私说明

- Case / Skill 按 user_id 强隔离，A 用户的经验不会被 B 用户检索
- Case 仅存压缩后的步骤摘要，不存原始 PII 明文
- 用户可随时通过 API 查询/删除自己的 Case 和 Skill 数据
- 详见 [Agent 自进化隐私声明](../legal/agent-memory-privacy-notice.md)

## 九、边界情况处理

管线在设计上对所有可能的异常输入做了防御性处理，确保 best-effort 不影响主流程：

### Case 提取层（P0）

| 边界场景 | 处理方式 |
|---------|---------|
| flag 关闭 | 返回 None，Agent 维持无记忆静态行为 |
| 闲聊/简单 Q&A（"你好"/"hi"/"谢谢"） | `_is_goal_directed` 过滤，不入 Case |
| 消息过短（<8 字符） | 同上，过滤 |
| trace 类型不支持（非 dataclass/dict） | 安全返回 None + log debug |
| LLM 返回非法 JSON | `_parse_case_json` 两级降级：json.loads → 子串提取 → None |
| LLM 返回 quality_score 超范围 | clamp 到 [0.0, 1.0] |
| LLM 返回 outcome 非法值 | 降级为 "unknown" |
| LLM 返回 markdown 代码块包裹 | 自动去除 ``` 包裹后解析 |
| tool_calls 非列表类型 | `isinstance` 检查，安全跳过 |
| user_message 超长（>500 字符） | 截断到 500 字符 |
| 轨迹总长 >2000 字符 | 截断 + "...[已截断]" 标记 |

### Case 检索层（P0）

| 边界场景 | 处理方式 |
|---------|---------|
| 空 task_intent | 返回空列表（避免无关键词过滤时返回全量 Case） |
| 无匹配 Case | 返回空列表 |
| scope 隔离 | 其他用户的 Case 不可检索 |
| Case approach JSON 格式错误 | `build_case_context` 降级显示 "(步骤解析失败)" |

### Skill 蒸馏层（P1）

| 边界场景 | 处理方式 |
|---------|---------|
| Case 不足阈值（<3 条） | 跳过蒸馏，返回 None |
| LLM 蒸馏失败 | 返回 None，不影响已有 Case |
| 已存在同名 Skill | 合并到已有 Skill（SkillCorpus 策展，避免冗余） |
| LLM 返回非法 JSON | `_parse_skill_json` 两级降级 |
| Skill name 为空 | `_find_similar_skill` 跳过查重，直接创建 |

### Skill 进化层（P1）

| 边界场景 | 处理方式 |
|---------|---------|
| Skill 不存在 | `record_skill_outcome` / `evaluate_skill_quality` 安全无操作 |
| 零使用记录（total=0） | safety=1.0（默认安全）/ utility=0.0 / overall=0.333（不晋升不淘汰） |
| 全部成功 | safety=1.0，overall 高分 → DRAFT→ACTIVE |
| 全部失败 | safety=0.0，overall 低分 → auto-archived |
| sample_size=0 | z_score=0，不 credited |
| before_success_rate=1.0 | z_score=0，不 credited |
| 超范围成功率（>1.0 或 <0） | p_pool=0/1 致 se=0 → z=0 安全降级 |

## 十、验证报告

### 端到端验证（66 项全通过）

验证脚本 `scripts/verify_self_evolution.py` 构造模拟 AgentTrace 数据，覆盖管线全链路：

| 验证阶段 | 项数 | 关键验证内容 |
|---------|------|------------|
| 本地服务启动 | 2 | `/api/health` 200 + version=1.10.1 |
| P0 Case 提取 | 11 | flag 门控、LLM 提取(mock)、非目标导向过滤、db=None 降级 |
| P0 Case 检索 | 6 | 关键词匹配、retrieval_count、上下文构建、scope 隔离 |
| P1 Skill 蒸馏 | 9 | Case≥3 聚类、LLM 蒸馏(mock)、DRAFT 状态、Case 回写 |
| P1 Skill 注入 | 5 | ACTIVE 检索、flag 门控、用户隔离 |
| P1 Skill 进化 | 5 | 三维质控、DRAFT→ACTIVE、低质 archived |
| P1 诊断归因 | 5 | z≥1.96 采纳、不显著拒绝、退化拒绝、边界降级 |
| 边界情况 | 25 | JSON 解析、过滤逻辑、压缩截断、malformed data |

### 边界修复记录

验证过程中发现并修复了 2 个边界问题：

1. **空 task_intent 搜索返回全量 Case**（Medium）：`search_cases` 在 `task_intent` 为空时跳过关键词过滤，退化为返回用户所有未蒸馏 Case。修复：增加空值提前返回守卫。
2. **tool_calls 非列表类型致 AttributeError**（Low）：`_compress_trajectory` 在 `tool_calls` 为字符串时抛 `AttributeError`。修复：增加 `isinstance` 类型检查。

## 十一、单元测试覆盖率

基于 `tests/test_agent_case.py` 的 pytest-cov 覆盖率报告（v1.10.2 边界测试补全后，59 用例）：

| 模块 | 语句数 | 缺失 | 覆盖率 | 说明 |
|------|-------|------|--------|------|
| `app/models/agent_case.py` | 26 | 0 | **100%** | 模型定义完全覆盖 |
| `app/services/agent_case_service.py` | 148 | 1 | **99%** | 仅剩 L93 防御性死代码 |
| `app/services/agent_skill_evolution_service.py` | 171 | 0 | **100%** | 含 LLM 异常/空值全部分支 |
| **合计** | **345** | **1** | **99%** | 覆盖前 89% |

**覆盖前缺口**（v1.10.1，89%）：
- `agent_case_service` 91%：JSON 解析 fallback 子串提取（~15 行）、LLM except 分支（~5 行）、
  flag 门控 return（~5 行）、trace 类型分支（~3 行）、边界守卫（~5 行）
- `agent_skill_evolution_service` 85%：LLM 异常处理、JSON 解析 fallback、flag 门控

**剩余 1 行未覆盖**：`_compress_trajectory` L93 "[已截断]" 分支。各段截断上限
（user_msg[:500] + 工具[:10] + response[:800]）之和恒 < 2000 阈值，该分支在当前参数下
**不可达（防御性死代码）**，已由 `test_compress_trajectory_bounded_length` 有界性不变式守护。

> 覆盖率报告生成命令：
> ```bash
> source .venv/bin/activate
> python -m pytest tests/test_agent_case.py \
>   --cov=app.services.agent_case_service \
>   --cov=app.services.agent_skill_evolution_service \
>   --cov=app.models.agent_case \
>   --cov-report=term-missing
> ```

---

## 附录 A：v1.10.2 边界测试补全报告

### 背景

v1.10.1 覆盖率 89%，缺失行全部集中在**防御性错误处理路径**（LLM 异常返回 + 空值输入）。
v1.10.2 新增 22 个边界测试（37→59），将覆盖率提升至 **99%**。

### 新增测试清单（22 个）

**agent_case_service（11 个）**

| 测试 | 覆盖路径 |
|------|---------|
| `test_is_goal_directed_chitchat_over_8_chars` | 闲聊词命中（≥8 字符） |
| `test_compress_trajectory_bounded_length` | 超长输入有界性不变式（L93 死代码守护） |
| `test_extract_case_trace_with_to_dict` | trace 对象 to_dict() 分支 |
| `test_extract_case_unsupported_trace_type` | trace 类型不支持（int）→ None |
| `test_parse_case_json_substring_extraction` | json.loads 失败 → 子串提取成功 |
| `test_parse_case_json_substring_extraction_fails` | 子串仍非法 / 无花括号 → None |
| `test_parse_case_json_quality_non_numeric` | quality_score 非数字 → 0.0 |
| `test_build_case_context_malformed_approach` | approach 非 JSON → "(步骤解析失败)" |
| `test_search_cases_empty_task_intent_returns_empty` | 空 task_intent → [] |

**agent_skill_evolution_service（11 个）**

| 测试 | 覆盖路径 |
|------|---------|
| `test_distill_skill_flag_off_returns_none` | distill flag 关闭 |
| `test_distill_skill_llm_invalid_json` | LLM 返回非法 JSON → None |
| `test_distill_skill_llm_error` | LLM 调用异常 → None |
| `test_distill_skill_malformed_approach` | approach 非法 JSON 蒸馏仍成功 |
| `test_parse_skill_json_markdown_wrapped` | markdown 代码块包裹解析 |
| `test_parse_skill_json_no_braces` / `_substring_extraction_fails` | 子串提取失败路径 |
| `test_find_similar_skill_empty_name` | name 为空跳过查重 |
| `test_record_skill_outcome_not_found` | skill 不存在安全无操作 |
| `test_evaluate_skill_quality_flag_off` / `_not_found` | flag 关闭 / skill 不存在 |
| `test_diagnose_credit_sample_size_zero` / `_before_rate_max` | 显著性检验边界（z=0） |

### 验证过程中发现的 2 个边界问题（已修复）

1. **`search_cases` 空 task_intent 返回全量 Case**（Medium）：空/纯空格 task_intent 时
   `keywords=[]` 跳过关键词过滤，查询退化为返回用户所有未蒸馏 Case。
   **修复**：`agent_case_service.py` 增加空值提前返回守卫。
2. **`_compress_trajectory` tool_calls 非列表类型致 AttributeError**（Low）：
   `tc.get("name")` 在 tool_calls 为字符串时崩溃。
   **修复**：增加 `isinstance(tool_calls, list)` + 元素 `isinstance(tc, dict)` 防御。

### 验证结果

- `tests/test_agent_case.py`：**59 passed**（覆盖率 99%）
- `scripts/verify_self_evolution.py`：**66 项端到端验证全通过**
- flake8 / mypy：0 issues
- 回滚：`bash scripts/rollback.sh v1.10.2`（复用自进化管线 3 flag 回滚清单）
