# 2026 前沿借鉴落地执行记录（第二轮，v1.15.7）

> 执行日期：2026-08-18 · 依据：`第二轮 2026 前沿诊断评估报告`
> 回归测试：`tests/test_frontier_v1157.py` 18 用例（mock 确定性，全绿）
> 前沿出处：信通院 ATH 1.0 + 7 项国标（MCP/A2A/ATH 三协议共建信任层）/
> 信通院可信 AI 记忆能力分级（中兴 Co-Claw 4+ 级首批过评）/ MobileMem 时间衰减 /
> Vinci2 主动服务 / 国盛证券 2026 家用机器人报告（仿真-真实落差 77pct，
> 居家数据采集闭环是 C 端规模化关键）/ 栖息地·海尔·尚品宅配×启元具身化动作

## 一、已落地项

### P0-A ATH/国标信任层审计（认证窗口卡位）

`agent_governance_audit.run_governance_audit` 新增独立章节 `ath_trust_layer`：
5 项确定性检查（ATH1 身份可信声明 / ATH2 握手与任务状态机 / ATH3 执行证据链
可回放 / ATH4 动作可验证意图 / ATH5 MCP 规范对齐），默认配置 **5/5 pass**，
附信通院依据引用（ATH 1.0 / 7 项国标 / 企业级 Claw 类评估）。OWASP 10 项保持
独立（既有断言兼容）。该章节即信通院「企业级专属智能体」评估的自检证据材料。

### P0-B 记忆分级对照（时间衰减 + org 共享记忆）

| 组件 | 改动 | 验证 |
|------|------|------|
| 时间衰减 | `search_cases`：effective = quality × exp(-age/half_life)，候选池 limit×4 供衰减重排；`memory_time_decay_enabled=True` / `memory_decay_half_life_days=30` | 2 用例（一年陈旧 0.95 被新鲜 0.8 超越；flag 关回退 quality-only） |
| org 共享记忆 | `agent_memory_service.get_org_memories` + `GET /agents/memory/org`（全平台成员可读）+ POST scope=org 管理员门控（403） | 3 用例 |

**诚实标注**：team 级共享因项目无 Team 实体暂缓（P2）；org 为平台天然成员域先行。

### P1-C 用户侧项目周报（Long-Horizon 主动服务）

`OrchestratorAgent.generate_project_weekly_briefing` + `GET /api/agents/projects/
{project_id}/weekly-briefing`（owner/admin，flag `project_weekly_briefing_enabled`
默认 True，关闭 503）：项目/任务/预算/采购/验收/里程碑六段确定性数据（逐段标注
数据源表名）+ AI 周度建议（economy 档 best-effort，失败诚实标 error）。验收段经
construction_tasks 关联（Inspection 无直接 project_id），里程碑对齐
milestone_code/actual_percent。4 用例（含 403/404/503）。FC 定时批量拉取做主动
推送为 P2 规划。

### P1-D Robot-Ready 校验 + 空间语义导出 schema（具身数据卡位）

| 组件 | 内容 |
|------|------|
| 校验 | `robot_ready_service.assess_robot_ready`：RR1 门洞通行 ≥0.85m / RR2 无门槛 / RR3 插座 0.3–1.2m / RR4 动线 ≥1.0m（可降级由房间宽度推导并诚实标注）/ RR5 地面连续性——数据缺失逐项 `insufficient_data`，**全缺不判不合格**（诚实降级红线）；`GET /construction/projects/{id}/robot-readiness` |
| 导出 | `export_spatial_semantics`：**spatial-semantics/0.1 先行 schema**（行业无标准）+ gaps 逐项诚实标注；`GET /construction/projects/{id}/robot-ready-export` |

差异化定位：尚品宅配×启元是定制家具数据，本平台是**装修交付链数据**（户型语义
+ 施工 QA 采集），schema v0.1 先行卡位。

## 二、诚实遗留与 P2 路线图（未在本版本落地）

| # | 项 | 现状 |
|---|----|------|
| P2-1 | 信通院认证正式申请 | ATH 自检材料就绪（audit 端点输出），提交时机由团队定 |
| P2-2 | team 级共享记忆 | 无 Team 实体；需先建实体+成员治理再开 team scope 读 |
| P2-3 | 周报主动推送（FC 批量拉取） | ✅ **v1.15.8 已落地**：`GET /api/admin/projects/weekly-briefings` 批量端点（FC 复用 daily-briefing 触发模式，include_ai 省成本） |
| P2-4 | 交付 QA 机器人友好字段采集 | ✅ **v1.15.8 已落地**：`PUT/GET /construction/projects/{id}/robot-ready-checklist` 采集闭环（存入 floorplans.data.robot_ready，评估自动消费） |
| P2-5 | Agent Plugins 化 | 17 工具打包为可安装插件，生态需要时启动 |

### v1.15.8 全量 P2 落地（2026-08-19，CHANGELOG [1.15.8] 详见版本记录）

- **P2-3 周报 FC 批量推送**：批量端点遍历 active 项目复用六段确定性聚合；`include_ai=False` 默认省 LLM 成本（ai_suggestions 标注 skipped，诚实），AI 建议走单项目端点按需生成；FC 触发器复用 daily-briefing 模式（无 K8s/Cron）。
- **P2-4 QA 机器人友好字段采集**：`save_robot_ready_checklist` 白名单写入 floorplans.data.robot_ready（零新表）；`_load_floorplan_semantics` 展开嵌套后 `/robot-readiness` 评估自动从 insufficient_data 转为可判定（采集闭环）。

## 三、质量门禁记录

- 新增测试：`tests/test_frontier_v1157.py` 18 用例全绿
- 回归：governance_audit / agent_case / agent_memory / frontier_v1153 全绿（166 用例）
- 全量 pytest：**2581 passed + 2 skipped + 4 xfailed，0 失败**（含并发批次新增 8 用例）
- 基线：2555 → **2581**（+18 本批次 + 8 并发批次，随 v1.15.7 校准，见 `scripts/test_baseline.json`）

> v1.15.8 更新（2026-08-19）：P2 全量落地新增 `tests/test_frontier_v1158.py` 12 用例 +
> escrow 绑定 1 用例 + 任务达成率 4 用例；全量 **2598 passed + 2 skipped + 4 xfailed，0 失败**
> （基线 2581 → **2598** +17，随 v1.15.8 校准，首跑零重试）。
