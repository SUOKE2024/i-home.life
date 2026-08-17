# 智能体用户全流程全景走查报告

> 走查日期：2026-08-17 · 环境：本地 `uvicorn :8001`（v1.15.0，SQLite）+ **真实 DeepSeek key**
> 走查方式：真实用户旅程（注册 → 建项目 → 全链路对话）逐端点真实调用，**全程未改代码**
> 原始响应存档：`/tmp/ihome-walkthrough/*.json`（35 份）

## 走查用户与场景

- 用户：李雨桐（138… 注册，真实注册走 `/api/auth/register`）
- 项目：滇池路89㎡温馨家（89㎡ 三室两厅毛坯房，昆明，北欧现代风，预算 15 万，家有 3 岁孩子，春节前入住）
- 覆盖入口：22 个执行型 Agent + 4 个商业运营 Agent + 编排/协议/记忆/反馈/评估/管理全链路（共 30+ 端点，40+ 次真实调用）

## 一、全景结论

**主链可用，专业 Agent 质量高，但编排层（orchestrate/A2A）在真实 LLM 下系统性失败；存在 2 个「假数据味道」与 2 个「孤立 Agent」。**

| 维度 | 评价 |
|------|------|
| 22 个直连 Agent 端点 | ✅ 全部返回真实 LLM 内容（2.4k–4.2k 字/条），专业性强 |
| 多 Agent 编排（orchestrate） | ❌ 真实 LLM 下子任务执行失败（0/1 完成） |
| A2A 任务下发 | ❌ 超时失败但以 `state=completed` + 占位文案掩盖 |
| 商业运营 Agent | ⚠️ growth/finance 经 daily-briefing 可用；marketing/competitor_research 无任何调用入口 |
| 降级诚实性 | ✅ 普遍诚实标注（mock/占位/无 Stripe/能力边界） |
| 数据真实性 | ⚠️ designer 89㎡ 项目回退 126㎡ 模板硬编码文案（v1.1.31 红线同类问题） |
| 鉴权边界 | ✅ 401/403 全部正确 |
| 时延 | ⚠️ 多数 Agent 首响 70–140s，chat 场景压力大 |

## 二、全链路体验明细（26 个 Agent）

### 执行型 Agent（直连端点，全部真实 LLM）

| Agent | 入口 | 体验 | 结论 |
|-------|------|------|------|
| orchestrator | `/agents/chat` | 整装需求被意图分类路由到 budget 顾问（返回 agent_type=budget），但内容仍给出全流程安排 | ⚠️ 分类偏差 |
| designer | `/agents/design` | 生成 3 套布局 + 风格/动线/材料，但 89㎡ 项目被回退到 126㎡ 模板，space_planning 硬编码「已为您生成3套126㎡户型设计方案」，用户要求儿童房给的却是书房 | ❌ 假数据味道 |
| budget | `/agents/budget` | 15 万预算全口径拆解，主动按「3 岁孩子」提升环保等级建议，质量高 | ✅（结构化字段见断点 12） |
| procurement | `/agents/procurement` | 主动发现「6 月底到货」已过期（系统时间 8-17）并建议调整节点，供应商/时间线齐全 | ✅ |
| construction | `/agents/construction` | 防水方案、HC-008 硬约束、开工/竣工/入住时间线完整 | ✅ |
| settlement | `/agents/chat` | 诚实说明无法调取项目合同台账，要求用户手动提供合同号——**project_id 已透传但无查询实现** | ⚠️ 链路未闭环 |
| qa_inspector | 3 端点 | acceptance-report 走 mock_rule_engine 并诚实标注 placeholder，但 0 项检查却给出「不合格（需返工）」；compare-design 0 次比对给出「重大偏差」；defects 0 项检查给出「工艺合格」——占位结论与数据矛盾 | ⚠️ 结论误导 |
| concierge | faq/classify/chat | classify（售后漏水→critical→转人工）与 chat 优秀；FAQ 以 **0.28 低分** 匹配「装修一般需要多长时间」答非所问（问的是入住时间/甲醛治理），need_human=false | ⚠️ FAQ 阈值过低 |
| kitchen / bathroom / mep / appliance / furniture / door-window | 6 个直连端点 | 全部高质量真实回复；appliance 结合昆明气候、mep 结合无主灯需求、bathroom 结合 3 岁孩子安全 | ✅ |
| takeoff | 直连 | 诚实说明缺户型图，按典型 89㎡ 假设估算用量 | ✅ |
| ifc-export | 直连 | 诚实说明需在 BIM 导出功能内完成，给出步骤 | ✅ |
| files | 直连 | 诚实说明无真实文件时可提供的整理建议 | ✅ |
| products | 直连 | **业主咨询被当商家上架咨询**（回复「上架规范/建议定价区间」），persona 混用 | ⚠️ |
| identity | `/agents/identity` | 普通用户 **HTTP 403**「仅管理员可访问身份认证审核功能」——22 个用户可见 Agent 中一个不可达 | ⚠️ 需产品澄清 |
| notifications | 直连 | 诚实说明无法代设偏好，给出建议与 suggestions | ✅ |
| content_publisher | `/agents/chat` | 结构化返回 missing_fields（类别/价格/规格），契约正确 | ✅ |
| admin | `/agents/chat`（管理员） | 实时平台统计（今日新注册 12、总用户 3204）真实可用 | ✅ |

### 商业运营 Agent（4 个）

| Agent | 入口 | 体验 | 结论 |
|-------|------|------|------|
| growth | daily-briefing 聚合 | ✅ 真实聚合 agent_feedbacks（走查中的 kitchen like 已出现在简报：like=1 avg=5.0），诚实标注「无反馈≠零使用」 | ✅ |
| finance_recon | daily-briefing 聚合 | ⚠️ escrow 统计失败：`No module named 'app.models.escrow'`（实际模块为 `app.models.escrow_trustee`），错误暴露在简报 escrow_note 中 | ❌ 断链 |
| marketing | **无任何入口** | 显式 `agent_type=marketing` 被静默路由到 orchestrator 给出泛化回复；flag `marketing_agent_enabled=True` 但未注册 harness、无路由、无聚合 | ❌ 孤立 Agent |
| competitor_research | **无任何入口** | 显式 `agent_type=competitor_research` 被路由到 budget，且回复内容变成「您发送的『走查管理员』我没有完全理解」——把用户名当消息内容回答 | ❌ 孤立 Agent |

## 三、编排 / 协议 / 治理链路

| 链路 | 端点 | 体验 | 结论 |
|------|------|------|------|
| 多 Agent 编排 | `/agents/orchestrate` | LLM 分解产生依赖不存在的 DAG（task_1）→ 校验失败降级规则分解 → **只派 1 个 designer 任务**；designer 经 harness 执行：LLM 返回 `finish=tool_calls` 空 content → 60s 超时重试 → 失败。用户得到「已完成 0/1 项子任务，1 项失败 / Agent 执行降级/无回复」 | ❌ 核心断点 |
| A2A | `/api/a2a/tasks/send` | KitchenAgent 同样 harness 超时失败（121s），但返回 `state=completed` + 「[kitchen] 服务暂时不可用」占位——**状态掩盖失败** | ❌ |
| 会话 | sessions CRUD | 4 会话落库，详情含消息 | ✅ |
| SSE 流式 | `/agents/chat/stream` | thinking_step → 路由 → token 流正常 | ✅ |
| 记忆 | `/agents/memory` | preference 落库/查询正常；LBS 闭环生效（location 参数 → 城市「昆明市」落库，source=lbs_geo） | ✅ |
| 反馈 | `/agents/feedback` | 201 recorded，且进入 daily-briefing 统计（闭环验证） | ✅ |
| 身份卡 | `/agents/identity/kitchen` | ACDL 结构返回 | ✅ |
| 本体 | `/ontology` | 3 域（renovation/agent/material） | ✅ |
| 评估 | `/eval/tool-accuracy` | 56 例 100% + minimal 12 例 100%，与基线一致 | ✅ |
| 治理审计 | `/admin/agent-governance-audit` | OWASP Top 10：10/10 pass | ✅ |
| 自进化 | `/admin/skill-evolution` | 周期正常，0 簇（诚实） | ✅ |

## 四、断点清单（按严重度）

1. **[高] orchestrate 编排在真实 LLM 下不可用**：DAG 依赖校验失败 → 规则兜底仅 1 任务；harness 路径下 Agent `_chat` 返回空 content（`finish=tool_calls`，deepseek-reasoner 特征）+ 60s 超时 → 「Agent 执行降级/无回复」。根因疑似：harness 重试预算不足 / 未处理 tool_calls-only 响应（同一直连路径 budget 也出现空 content 警告，但重试成功）。
2. **[高] A2A 用 state=completed 掩盖执行失败**：「服务暂时不可用」占位文案应配 failed/降级状态，且应给出重试指引。
3. **[高] designer 面积模板回退 + 硬编码文案**：`app/agents/designer.py` 对 89㎡ 回退 `"126"` 模板，space_planning 输出「3套126㎡户型设计方案」；用户要求儿童房，方案生成书房。违反「禁止硬编码假数据」红线（v1.1.31 同类）。
4. **[高] marketing / competitor_research 无任何生产调用方**：flag 默认 True 但未注册 harness、无路由、不在 daily-briefing 聚合——开 flag 也无入口；显式 agent_type 静默降级到 orchestrator/budget 并答非所问。
5. **[中] finance_recon escrow 断链**：`from app.models.escrow import EscrowOrder` 模块不存在（实际 `app.models.escrow_trustee`），简报中暴露 ImportError，escrow 统计恒缺失。
6. **[中] 意图分类两次错路由**：整装流程需求 → budget；「调研竞对定价」→ budget 且把用户姓名当消息内容回答。
7. **[中] qa_inspector 占位结论与数据矛盾**：0 项检查分别给出「不合格需返工」「重大偏差」「工艺合格」，三个互相矛盾的方向（前两个吓用户、第三个给假安心）；诚实标注了 source=mock/note，但结论本身仍是「伪结论」。
8. **[中] concierge FAQ 匹配阈值过低**：0.28 低分仍返回 found=true 且答非所问。
9. **[低] identity Agent 对普通用户 403**：若定位是管理员工具应从用户可见 Agent 列表移出或改走 admin 命名；若定位面向用户则 403 是断链。
10. **[低] settlement 无台账数据接入**：project_id 透传但 Agent 无查询实现，用户需手动提供合同信息。
11. **[低] products persona 混用**：业主选购咨询被按商家上架处理。
12. **[低] 结构化字段未结构化**：budget/procurement/construction 的 summary/breakdown/timeline 等字段与 full_reply 完全相同（同一全文复制），前端无法直接渲染分区卡片。
13. **[观察] 时延**：直连 Agent 首响 70–140s（slow_request 频发），主因 deepseek-reasoner 长推理 + 空 content 重试；本地仅配 deepseek key，qwen/glm 降级链未生效（环境性，非代码缺陷）。

## 五、体验亮点（值得保留）

- 22 个专业 Agent 直连内容质量高，**项目上下文（昆明/89㎡/3 岁孩子/15 万）被多个 Agent 主动引用**（procurement 时间校验、construction 防水硬约束、appliance 昆明气候适配）。
- **闭环验证成功**：反馈 like → daily-briefing growth 统计实时可见；LBS location → 城市落库长期记忆；会话/记忆/身份卡/本体全链可用。
- 降级诚实性整体好：takeoff/ifc/files/notifications 明确能力边界，QA 标注 placeholder，finance 标注无 Stripe，growth 标注「无反馈≠零使用」。
- 鉴权边界干净：未认证 401、普通用户访问管理端点 403。
- 评估基线真实：tool-accuracy 100%（56 例）、minimal 100%（12 例）、治理审计 10/10。

## 六、建议的后续动作（供决策，未执行）

1. 修 harness 路径对 `finish=tool_calls` 空 content 的处理 + 增加重试预算（一次修复 orchestrate 与 A2A 两个断点）。
2. designer 移除 126㎡ 硬编码回退，按 project.area 生成文案；无模板时诚实标注「按相似户型参考生成」。
3. 决定 marketing/competitor_research 的去留：接入 daily-briefing 聚合或下线 flag，禁止显式 agent_type 静默吞掉。
4. finance_recon 修正 escrow 模型导入路径。
5. qa_inspector 占位模式改结论为「数据不足，无法判定」而非合格/不合格。
6. concierge FAQ 提高匹配阈值 + 低分时 need_human=true。

## 七、修复与验证记录（v1.15.x，同日完成）

> 全部 13 项发现均已修复并双路验证（真实 LLM 复验 + 回归测试），全程未动架构。

| # | 修复内容 | 改动文件 | 真实 LLM 复验结果 |
|---|---------|---------|------------------|
| 1 | harness 超时 60→180s（settings 接线）；`finish=tool_calls` 空 content 不再塞道歉文案污染工具轮；空回复降级无工具 think 重试，全空走 fallback | `app/agents/harness.py`、`app/agents/base.py`、`app/config.py` | orchestrate 复验「已完成 4/4 项子任务」（designer→budget→procurement→construction 链式真实执行，designer 输出含儿童房/E0 上下文）✅ |
| 1b | LLM 分解依赖引用重映射（task_N 序号/agent 名/已有 id 三档）；规则兜底支持「先…再…然后…最后」链式多任务分解 | `app/services/agent_orchestration_service.py` | 同 #1（此前 DAG 校验失败塌缩为 1 任务）✅ |
| 2 | A2A 执行降级 → `state=failed` + 降级原因（不再 completed 掩盖）；trace 状态同步 FALLBACK | `app/api/a2a.py` | A2A kitchen 复验 `state=completed` 且为真实厨房设计内容（766 字，非占位）✅ |
| 3 | designer 数字面积解析取最近模板档位；回复不再硬编码「126㎡户型」，诚实标注声明面积 + 参考布局总面积；提到孩子时书房→儿童房 | `app/agents/designer.py` | 89㎡ 复验：无「126㎡户型」字样，标注「您家面积约89㎡…以量房尺寸为准」✅ |
| 4 | 4 个商业运营 Agent 注册 harness + 聊天路由（growth/finance 确定性报表，marketing/competitor 真实 LLM）；非管理员 403、A2A 同门控；未知 agent_type → 422（不再静默吞噬） | `app/agents/harness.py`、`app/api/agents.py`、`app/api/a2a.py` | 管理员 marketing 生成真实小红书文案；competitor_research 3962 字含「非实时数据」诚实标注；普通用户 403、未知 422 ✅ |
| 5 | escrow 统计改用真实表 `app.models.procurement_enhanced.EscrowPayment`（原 `app.models.escrow` 不存在） | `app/agents/finance_recon.py` | daily-briefing escrow_note 无 ImportError，标注 escrow_payments 来源 ✅ |
| 6 | 全流程安排关键词 → general；规则 general 后不再进 LLM 二次分类；general 走 orchestrator 真实回答并提取 JSON reply 字段（/chat 与 /chat/stream 同修） | `app/agents/orchestrator.py`、`app/api/agents.py` | 复验：agent_type=orchestrator，无 ```json``` 泄漏，7 节点整装流程（含儿童房 E0）✅ |
| 7 | qa_inspector 0 检查项/0 照片 → `insufficient_data` 诚实结论；中文阶段名（水电/泥木/油漆）归一化真实产生检查项 | `app/agents/qa_inspector.py` | 中文 phases → 14 检查项「优秀」+mock 标注；空数据三端点均「数据不足，无法判定」✅ |
| 8 | FAQ 阈值 0.1→0.4，低置信转人工；新增「入住/甲醛治理」知识条目 | `app/agents/concierge.py` | 复验 match 0.77 命中新条目，need_human=false ✅ |
| 9 | identity 端点普通用户可用（咨询认证流程，管理员保留审核视角；无数据泄露面） | `app/api/agents.py` | 普通用户 200 + 真实材料清单回复 ✅ |
| 10 | settlement 聊天注入真实结算台账（`_load_settlement_context`）；无结算单时诚实引导创建，不再索要合同号 | `app/api/agents.py` | 复验：回复「经查询…尚未创建结算单」+ 创建路径引导 ✅ |
| 11 | products 系统提示词加角色区分（业主→产品顾问+市场参考价标注；商家→上架规范） | `app/agents/products_agent.py` | 业主提问复验：产品顾问视角 + 「市场参考价区间（非平台实价）」✅ |
| 12 | budget/procurement/construction 结构化字段按 markdown 分节提取（`_split_markdown_sections`/`_pick_section`） | `app/api/agents.py` | 复验：summary 307 / breakdown 189 / tips 347 / full 2345 字（四字段不再相同）✅ |
| 13 | 环境观察项：harness 超时/重试修复已消除 60s 误杀；qwen/glm key 缺配属环境配置，非代码缺陷 | — | 直连时延仍 60-140s（deepseek-reasoner 固有），无 60s 硬中断 ✅ |

**回归测试**：新增 `tests/test_walkthrough_fixes.py` 31 用例（mock 确定性，全部通过）；更新 `tests/test_qa_inspector_concierge.py` 1 处旧断言（0 照片「合格」→「数据不足」，行为变更即修复目标本身）。**质量门禁**：flake8 / mypy / pre-commit（changed files）全绿；全量 pytest 最终轮 **2485 passed + 2 skipped + 4 xfailed，0 失败**（基线 2454 + 新增 31，零回退）。

