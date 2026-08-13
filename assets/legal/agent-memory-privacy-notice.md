# Agent 自进化功能隐私声明

> i-home.life v1.10.1 — Agent 记忆与自进化数据隐私声明
> 生效日期：2026-08-08

## 一、功能说明

i-home.life 平台的 AI Agent 自进化功能（受 `agent_case_extraction_enabled` / `agent_skill_distillation_enabled` / `agent_skill_evolution_enabled` 三个 feature flag 控制，v1.13.2 起默认全部开启，可灰度关闭）会在 Agent 执行任务时自动收集、处理和存储以下数据：

1. **Agent Case（经验记录）**：Agent 每次完成目标导向任务后，系统自动提取的结构化执行记录，包含任务意图、分步执行摘要、完成质量评分。
2. **Agent Skill（技能资产）**：从多条同类 Case 中蒸馏出的可复用技能，包含通用操作流程和验收标准。
3. **进化统计数据**：Skill 的使用次数、成功/失败计数、三维质控评分。

## 二、数据收集范围

### 收集的数据
- **task_intent**：任务意图陈述（自包含，50-200字，由 LLM 从执行轨迹中提取）
- **approach**：压缩后的分步执行摘要（最多8步，每步含尝试内容、工具、结果）
- **quality_score**：0-1 的完成质量自评
- **outcome**：任务结果（success/partial/failed/unknown）
- **agent_name**：执行 Agent 的名称（如 designer/budget/procurement）
- **trace_id**：关联的执行轨迹 ID（仅 ID，不含原始轨迹数据）

### 不收集的数据
- ❌ 原始用户消息的完整明文（仅截断用于意图提取）
- ❌ Agent 回复的完整内容（仅截断摘要）
- ❌ 用户的个人身份信息（PII）：手机号、身份证、银行卡等（已在审计层 masking）
- ❌ 非目标导向对话（闲聊、简单问答自动过滤，不入 Case）

## 三、数据存储与隔离

### 存储位置
- 数据存储于平台自有数据库（阿里云 PolarDB-PG / SQLite），不传输至第三方
- Agent Case 存储于 `agent_cases` 表，Skill 存储于 `agent_skills` 表

### 数据隔离
- **user_id 强隔离**：Case 和 Skill 按 user_id 严格隔离
- **scope 体系**：支持 personal（仅本人）/ project（项目内）/ team（团队）/ org（全组织）四级作用域
- 默认 scope=personal：A 用户的经验记录不会被 B 用户检索或访问
- 仅当用户显式将 Skill 提升至 org scope 并经 admin 审核后，才全组织可见

### 加密保护
- 数据库传输使用 TLS 加密
- PASETO v4.local 令牌鉴权，禁止使用 JWT
- 会话消息存储受 `allow_plaintext_session=False` 约束（生产环境禁止明文）

## 四、数据使用目的

收集的 Case 和 Skill 数据仅用于：

1. **Agent 经验复用**：在同一用户后续相似任务中检索注入历史经验，提升任务完成质量
2. **Skill 自动进化**：基于使用反馈持续优化 Skill 质量（晋升高质量、淘汰低质量）
3. **诊断归因**：分析失败模式，生成 Skill 改进建议（受显著性检验门控）

**不用于**：用户画像、广告推荐、数据售卖、第三方共享。

## 五、数据保留与删除

### 保留策略
- Agent Case：长期保留，直至用户删除或被蒸馏为 Skill 后标记 `distilled_to_skill_id`
- Agent Skill：长期保留，低质 Skill 自动 archived（软删除，不物理删除）

### 用户权利
用户有权随时：
- **查询**：通过 API 查询自己的所有 Case 和 Skill 数据
- **删除**：通过 API 软删除自己的 Case 和 Skill（设置 `deleted_at`，不再被检索）
- **导出**：通过 API 导出自己的 Case 和 Skill 数据（JSON 格式）
- **关闭**：通过设置 feature flag 为 False 完全关闭自进化功能（已有数据保留但不再新增）

### 管理员权利
- 管理员可查询/管理所有用户的 Case 和 Skill（用于运维和审计）
- org scope 的 Skill 需 admin 审核才能发布（admin gated promotion）

## 六、Feature Flag 控制

自进化功能受三个独立 feature flag 控制，v1.13.2 起默认全部开启（关闭即回退为无记忆无进化的静态 Agent 行为）：

| Flag | 控制范围 | 默认 |
|------|---------|------|
| `agent_case_extraction_enabled` | Case 提取 | True（v1.13.2 起） |
| `agent_skill_distillation_enabled` | Skill 蒸馏 + 检索注入 | True（v1.13.2 起） |
| `agent_skill_evolution_enabled` | Skill 进化 + 诊断归因 | True（v1.13.2 起） |

回滚命令：`bash scripts/rollback.sh v1.13.1`（一键关闭三个 flag，复用自进化管线回滚清单）

## 七、第三方数据流转

- **LLM 调用**：Case 提取和 Skill 蒸馏通过平台多 LLM fallback chain（deepseek → qwen → glm → doubao）调用 LLM，仅传输压缩后的执行摘要，不传输原始 PII
- **无外部记忆服务**：本功能不依赖 EverOS、Raven 等外部记忆基础设施，全部数据在平台自有数据库内处理

## 八、合规声明

- 本功能符合《个人信息保护法》最小必要原则：仅收集 Agent 执行经验所需的最小数据
- 数据隔离符合《数据安全法》要求：user_id 强隔离 + scope 分级
- 用户知情权：本声明公开披露数据收集范围和使用目的
- 用户删除权：支持软删除，用户可随时行使删除权

## 九、联系方式

如对本隐私声明有任何疑问，请联系：

- **邮箱**：<song.xu@icloud.com>

我们将在 1 个工作日内回复您的邮件。
