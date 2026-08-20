# 评估闭环执行记录（2026-08-20，基准-分析-验证-研究-改进）

> 执行日期：2026-08-20 · 依据：用户指令「执行完整的基准测试-分析-验证-研究-改进闭环工作流程」
> 范围：全量 pytest + eval 套件 · 改进选题由分析结果驱动 · 全自动闭环
> 前沿出处：IETF BMWG Agent 安全评估基准（draft-han-bmwg-agent-security-benchmark-00，2026-07，
> 中国移动）静态评估维度 / LangChain Run-Trace-Thread 三层评估（2026-06）/ Sentrial「traces 是
> 生产评估基石，无数据即失真」（2026-05）/ "Prompts Don't Protect"（arXiv:2605.18414，架构化
> 强制优于 prompt 约束）

---

## 一、基准测试（Benchmark）

### 1.1 全量 pytest

- 命令：`.venv/bin/python -u -m pytest tests/ -v --timeout=60 -n auto`（无缓冲直写日志，禁用管道）
- 结果：**2603 passed + 2 skipped + 4 xfailed，0 失败**（16m09s）
- 对照 `scripts/test_baseline.json`（2598 passed）：**基线未回退**，多出 5 个用例为
  2026-08-19 校准后新增（`test_frontier_v1158.py` 等），基线文件待本次校准。
- 前置检查：无外部 pytest 进程，负载 2.84 < ncpu/2（4），结果可信。

### 1.2 eval 套件

| 项 | 结果 | 说明 |
|---|---|---|
| 工具选择准确率（全工具集） | **100%（56 用例，0 混淆）** | 确定性关键词基线，v1.13.5 基线保持 |
| 工具选择准确率（Minimal 模式） | 100% | 仅 get_budget/get_design_layout 两工具 |
| IHomeEval（无轨迹 standalone） | 见「分析」 | **暴露评估失真问题（本轮改进主因）** |
| 漂移检测 / feedback / ux | 8 条轨迹均 insufficient_samples | dev 库 7 天窗口样本不足，诚实标注不判定 |

---

## 二、分析（Analyze）

### 2.1 真实 DB 数据（dev 库，8 条轨迹）

- 降级率 37.5%（3/8 fallback），全部为 **121s 整的 TimeoutError**（retry=2）——dev 环境
  无可用 API Key 的网络超时噪音，非生产信号；但提示「LLM 单次调用超时预算 180s」与质量
  目标（avg ≤15s / p95 ≤30s）之间存在张弛空间（设计取舍，不属本次改动）。
- per-agent：KitchenAgent success 33%/fallback 67%、designer 50%——同因 dev 噪音。
- 会话 UX：task_completion_rate 65.38% < 70% 目标、abandonment 34.62% > 30%（26 会话，
  dev 数据，样本不足）。
- 结论：轨迹侧指标在 dev 环境无判定价值，**不据此改进**（避免对噪音过度反应）。

### 2.2 静态检查（确定性，本轮改进依据）

**F1 — `_idor_score` 启发式把管理员/公开模块误计为越权缺口（评估精度问题）**

- 旧逻辑：统计 `app/api/*.py` 源码含字符串 `verify_project_access` 的占比 → **51.25%**
  （41/80）。
- 实测：39 个未计覆盖模块中，`admin.py` 用 `require_user_read/write/...` 角色门禁、
  `harness_api.py`/`eval.py` 用 `require_admin`、`analytics.py`/`config.py` 为公开端点、
  其余用户态模块均含 `Depends(get_current_user)`——**并非 39 个真实缺口**。粗筛对
  「管理员级控制（强于项目归属）」「公开模块（无用户数据）」两类合法情形误报。

**F2 — 无轨迹样本时数据驱动维度输出失真混合（评估诚实度问题）**

- 实测（standalone `run_ihome_eval()`，无轨迹）：`fallback_rate=100`、`reasoning_leak_rate=100`、
  `sse_latency=100`（看似满分）与 `tool_call_accuracy=0`、`faithfulness=0`、`completeness=0`、
  `sufficiency=0`、`counter_argument_quality=0`（看似零分）**并存**——同一空样本既输出满分
  又输出零分，消费方无法区分「无数据」与「真实失败」。漂移检测已有 insufficient_samples
  诚实标注，但 IHomeEval 维度评分缺失该模式。

**F3 — 基线文件过期**：`scripts/test_baseline.json` 2598 vs 实际 2603（+5 用例未校准）。

---

## 三、验证（Verify）

主代理亲自 Read 源码核验，不采信子代理结论（项目红线）：

1. `app/eval/ihome_eval.py::IHomeEvalRunner.run`（L220-254）：确认仅消费内存 harness 轨迹；
   API 层 `_build_report` 已用 `fetch_agent_traces_as_dicts` 读 DB（v1.13.6 已闭环）——
   故 F1/F2 影响面为「评估报告消费方」而非「API 数据源」。
2. `_compute_runtime_metrics`（L258-295）：空轨迹返回 `{}`；`_compute_dimension_scores`
   空轨迹时反向指标按 0 算满分、正向按 0 算零分——F2 根因确认。
3. `_idor_score`（L461-482）：字符串存在性粗筛——F1 根因确认。
4. `fetch_agent_traces_as_dicts`（L877-909）：字段映射完整（status/fallback/latency/
   tool_call_count/response_preview），DB 轨迹可正常驱动维度计算。
5. 39 个未覆盖模块逐个核验鉴权方式：admin 门禁族 / 公开端点 / 用户态三类分布如上。
6. 测试约束核验：`test_eval_upgrade.py` 仅断言 `idor_resistance in scores` 与
   `0 < score <= 100`（无具体数值依赖）；`test_v1128_suoke_borrowed.py` L97 用非空
   轨迹断言 `counter_argument_quality > 0`（不受空轨迹改动影响）；`test_eval.py` API
   测试仅断言结构字段。改动兼容。

---

## 四、研究（Research，定向前沿检索）

选题由分析结果驱动（评估精度 + 诚实度），检索 2026 前沿对齐：

| 出处 | 要点 | 与本次改进的映射 |
|---|---|---|
| **IETF BMWG Agent 安全评估基准**（draft-han-bmwg-agent-security-benchmark-00，2026-07，中国移动） | 安全评估含静态评估维度：按控制类型分类识别，55 项二级指标 | F1 改进：`_idor_score` 按 covered/admin_gated/public/needs_review 分类，替代字符串存在性粗筛 |
| **LangChain Run/Trace/Thread 三层评估**（2026-06） | 轨迹级评估是生产代理质量的真实层；89% 组织有可观测性但仅 52% 跑离线评估 | 确认轨迹驱动维度（faithfulness 等）的数据前提 |
| **Sentrial "Your Evals Are Passing While Your Agent Is Failing Users"**（2026-05） | 生产评估必须基于 traces；无数据/离线评估失真会误导 | F2 改进：无样本时省略数据驱动维度 + 诚实标注（对齐 drift 的 insufficient_samples 模式） |
| **"Prompts Don't Protect"**（arXiv:2605.18414，2026-08） | 访问控制应架构化强制（ABAC 过滤），非 prompt 约束 | 佐证 `verify_project_access` 属于架构化控制（Depends 依赖注入），改进后的分类以「控制存在」为准 |

**红线对齐**：不引入 K8s/微服务（阿里云 FC 架构）；PASETO 鉴权不变；诚实降级不可移除；
新测试补 `tests/`；改动可回溯本报告。

---

## 五、改进（Improve）

### I1 — IDOR 越权覆盖率精确化（评估精度）

`app/eval/ihome_eval.py`：
- 新增 `_IDOR_RBAC_DEPS` + `_idor_coverage_details()`：模块级四分类
  - `covered`：含 `verify_project_access`（项目归属校验）
  - `admin_gated`：含 `Depends(require_admin|allow_admin|require_user_*)` RBAC 角色门禁
    （管理员级控制强于项目归属，视为已覆盖）
  - `public`：不含 `get_current_user`（无用户态数据，如埋点/公开配置）
  - `needs_review`：用户态但静态未检出项目归属校验 → **审计候选清单**（非漏洞结论，
    附 note 说明部分模块按用户域隔离如会话/积分无需项目归属）
- `_idor_score()` 改为返回精确化 score；`IHomeEvalReport` 新增 `idor_coverage` 字段并
  入 `to_dict()`；`app/api/eval.py` 的 `EvalReportResponse` 同步新增（向后兼容可选字段）。

结果：**51.25% → 62.5%**（41 covered + 7 admin + 2 public / 80）；30 个模块列入
`needs_review` 审计候选（chat/tasks/voice/agent_memory/…），供人工审计优先级。

### I2 — 无数据维度诚实省略（评估诚实度）

`_compute_dimension_scores()`：无轨迹样本时**不再计算数据驱动维度**（fallback_rate /
reasoning_leak_rate / sse_latency / tool_call_accuracy / faithfulness / completeness /
sufficiency / counter_argument_quality），仅保留静态维度（idor / hc / design_safety /
material）；`run()` 在无轨迹时追加诚实标注 note。既有 `budget_accuracy` 无数据省略
模式（v1.13.7）扩展为全部数据驱动维度。

结果：空样本报告不再出现「降级率 100 / 忠实性 0」失真混合，与漂移检测
insufficient_samples 模式对齐。

### 测试与门禁

- 新增 4 用例（`tests/test_eval_upgrade.py`）：IDOR 四分类断言 / 精确化后分数高于旧
  粗筛 / 空轨迹省略数据维度 + note / 报告含 idor_coverage 明细。
- `tests/test_eval_upgrade.py` + `test_v1128_suoke_borrowed.py` +
  `test_agent_tool_discipline.py`：**107 passed**。
- mypy（CI 阻塞门禁）：无问题；flake8：通过。
- 全量 pytest：见第六节（本批次新增 4 用例）。

### 诚实遗留

- `needs_review` 30 个模块是**审计候选清单**而非漏洞结论；模块级静态分类无法区分
  「用户域隔离合法」与「缺项目归属校验」，人工审计（P2）逐模块确认。
- 轨迹侧质量指标（延迟/降级/完成率）在 dev 环境样本不足，未据此改进；生产部署后
  漂移检测数据积累即可判定。

---

## 六、质量门禁记录

- 新增测试：`tests/test_eval_upgrade.py` +4 用例
- 回归：eval / suoke_borrowed / tool_discipline 107 用例全绿
- 全量 pytest：**2607 passed + 2 skipped + 4 xfailed，0 失败**（2603 + 4 新增）
- 基线：`scripts/test_baseline.json` 2598 → **2607**（含此前未校准的 +5 与本批次 +4）

> 环境性 flake 记录（诚实标注）：第二次全量跑在 19% 出现 8 个 worker 崩溃 ERROR
> （loadavg 15min≈16 高负载所致，同名测试先 PASSED 后 ERROR 双计），8 个用例单独
> 复跑全过（3.13s）；第三次全量（负载回落 2.13）零错误通过。属环境噪音，非代码回归。

> 注：本轮不 bump 版本（改进均在 `eval_enabled` 门控内的评估框架层，非对外行为变更）。
