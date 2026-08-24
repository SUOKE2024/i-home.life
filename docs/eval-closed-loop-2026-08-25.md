# 评估闭环执行记录（2026-08-25，基准-分析-验证-研究-改进）

> 执行日期：2026-08-25 · 依据：用户指令「执行完整的基准测试-分析-验证-研究-改进闭环工作流程」
> 范围：全量 pytest + eval 套件 · 改进选题由分析结果驱动 · 全自动闭环
> 承接：`docs/eval-closed-loop-2026-08-20.md`（上一轮：IDOR 覆盖率精确化 + 无数据维度诚实省略）
> 前沿出处：Anthropic「Demystifying Evals for AI Agents」(2026-01，评估对象/判定一致性) /
> Yale·IBM「Survey on Evaluation of LLM-based Agents」(2026-04，细粒度指标缺口) /
> 延续 Sentrial「无数据即失真」(2026-05，诚实标注原则)

---

## 一、基准测试（Benchmark）

### 1.1 全量 pytest

- 命令：`.venv/bin/python -u -m pytest tests/ -v --timeout=60 -n auto`（无缓冲直写日志，禁用管道）
- 结果：**2609 passed + 2 skipped + 4 xfailed，0 失败**（13m39s）
- 对照 `scripts/test_baseline.json`（2609）：**基线未回退**，与 2026-08-21 v1.15.10 校准一致。
- 前置检查：无外部 pytest 进程，loadavg 2.79 < ncpu/2（4），结果可信。

### 1.2 eval 套件

| 项 | 结果 | 说明 |
|---|---|---|
| 工具选择准确率（全工具集） | **100%（56 用例，0 混淆）** | 确定性关键词基线，v1.13.5 保持 |
| 工具选择准确率（Minimal 模式） | 100%（12 用例） | 仅 get_budget/get_design_layout 两工具 |
| IDOR 越权覆盖率 | **73.75%**（51 covered + 6 admin + 2 public / 80） | 与 2026-08-20 审计收尾一致，无新模块回归 |
| IHomeEval（空轨迹 standalone） | 静态维度齐全 + 无数据维度诚实省略 | 上轮 I2 生效，空样本无失真混合 |
| 漂移检测 / feedback / ux | 7 天窗口无轨迹样本 | dev 库轨迹均 08-17 落库，超窗无样本，诚实标注不判定 |

---

## 二、分析（Analyze）

### 2.1 真实 DB 数据（dev 库，8 条轨迹）

- 轨迹均创建于 2026-08-17，**已超出 7 天漂移窗口**（今日 08-25），`detect_agent_drift` 无样本判定。
- 3/8 fallback 全部为 **121s 整的 TimeoutError**（dev 无可用 API Key 的网络超时噪音），同上一轮结论，非生产信号。
- feedback 仅 1 条 like、会话 12 条（窗口内），均样本不足，不据此改进。
- 结论：轨迹侧指标在 dev 环境无判定价值（同上轮），**不据此改进**（避免对噪音过度反应）。

### 2.2 静态检查（确定性，本轮改进依据）

**F1 — 快照趋势 / drift-vs-history 缺失基线用 0 作基数计算 delta（评估诚实度问题）**

- `compute_snapshot_trend`（L1087 旧）：`_delta(m.get(k) or 0, prev_metrics.get(k) or 0)`——前一快照
  缺失某指标（如空轨迹快照无 fallback_rate）时，delta 用 0 作基数，显示「从 0 涨到 X」失真。
- `detect_drift_vs_history`（L1155 旧）：`base.get("success_rate") or 0`——基线快照缺该 Agent
  （新上线 Agent 无历史基线）时，delta = 当前值，显示「+100% 全量跳变」失真。
- 消费方（管理员看 /api/eval/trend、/api/eval/drift/history）无法区分「真实恶化」与「无基线可对比」。

**F2 — per-agent `meets_targets` 未纳入延迟维度，与 drift 判定标准不一致（评估自洽性问题）**

- `_compute_per_agent_scores` 的 `meets` 仅检查 success_rate / fallback_rate / token_budget_hit_rate。
- `detect_agent_drift` 判定还含 avg_latency_ms。
- **实证**：budget agent 平均延迟 120000ms（远超 avg_latency_ms_max=15000）时
  `meets_targets=True`，而 drift 会标 avg_latency critical——同一 Agent 两种结论互相矛盾。

---

## 三、验证（Verify）

主代理亲自 Read 源码核验，不采信子代理结论（项目红线）：

1. `app/eval/ihome_eval.py::compute_snapshot_trend`（L1070-1102）：确认 `_delta(m.get(k) or 0,
   prev_metrics.get(k) or 0)` 与 `_delta(..., first_metrics.get(k) or 0)` 缺失即 0 基数——F1 根因确认。
2. `detect_drift_vs_history`（L1140-1172）：确认 `base.get(...) or 0` 基线缺失即 0——F1 根因确认。
3. `_compute_per_agent_scores`（L440-489）：确认 `meets` 不含延迟维度；`detect_agent_drift`
   （L743-749）含 avg_latency_ms——F2 不一致确认。
4. 测试约束核验：
   - `test_eval_v1136.py::test_snapshot_trend_delta` 仅断言 `success_rate` delta（双侧有值），
     缺失指标 delta 从 0.0 → None 不影响断言；
   - `test_eval_upgrade.py::test_per_agent_scores` 用 latency=1000ms（低于阈值），
     `meets_targets` 断言不受影响；`test_agent_tool_discipline.py` L573-574 预算早停场景不受影响。
5. 边界核验：无延迟数据（latency=0）时 avg/p95=0 ≤ 阈值，不误报 False；`_delta` 调用处
   经条件保证参数非 None，mypy 无类型问题。

---

## 四、研究（Research，定向前沿检索）

选题由分析结果驱动（评估展示层诚实度 + 判定自洽性），检索 2026 前沿对齐：

| 出处 | 要点 | 与本次改进的映射 |
|---|---|---|
| **Anthropic「Demystifying Evals for AI Agents」**(2026-01) | 评估对象一致性：transcript vs outcome、稳定性（多次运行一致性） | F1 改进：对比须有有效基线，无基线 delta=None；F2 改进：同一 Agent 在不同评估层（report vs drift）判定标准须一致 |
| **Yale/IBM「Survey on Evaluation of LLM-based Agents」**(2026-04) | 评估五类关键缺口：细粒度指标、成本效率、可扩展自动化、安全合规、LLM 与 harness 解耦 | 佐证 F1/F2：粗粒度/缺失上下文的指标展示会误导消费方，细粒度诚实标注是评估可信前提 |
| **Sentrial「Your Evals Are Passing While Your Agent Is Failing Users」**(2026-05，承接上轮) | 生产评估必须基于 traces；无数据/失真输出会误导 | 延续诚实标注模式：缺失即省略（None），不伪造「0 基线」 |

**红线对齐**：不引入 K8s/微服务（阿里云 FC 架构）；PASETO 鉴权不变；诚实降级不可移除；
新测试补 `tests/`；改动可回溯本报告。

---

## 五、改进（Improve）

### I1 — 缺失基线 delta 诚实标注（评估诚实度，对齐 F1）

`app/eval/ihome_eval.py`：
- `compute_snapshot_trend`：`delta_prev` / `delta_baseline` 改为逐 key 判定——任一侧指标缺失
  （None）时该指标 delta 输出 **None**（诚实标注无对比），双侧都有值才计算 delta。
- `detect_drift_vs_history`：新增 `_delta_vs_base` helper——基线快照缺该 Agent/指标时
  delta 输出 **None**，不再用 0 伪造「当前值=变化量」。

结果：`/api/eval/trend` 与 `/api/eval/drift/history` 消费方可以区分「真实恶化」与
「无基线可对比」，新上线 Agent 不再显示「+100% 全量跳变」假象。

### I2 — meets_targets 纳入延迟判定（评估自洽性，对齐 F2）

`_compute_per_agent_scores()`：`meets` 新增两项延迟判定：
- `avg_latency <= QUALITY_TARGETS["avg_latency_ms_max"]`（15000ms）
- `latency_p95 <= QUALITY_TARGETS["latency_p95_ms_max"]`（30000ms）

结果：per-agent 报告与 drift 判定标准对齐——延迟远超目标的 Agent `meets_targets=False`
（实证场景：budget 120s 延迟此前 True → 现 False），消除「报告说达标、漂移说超标」矛盾。

### 测试与门禁

- 新增 5 用例：
  - `tests/test_eval_upgrade.py` +3：高延迟 meets_targets=False / 低延迟 True /
    avg 达标但 p95 超限 False（p95 线性插值语义）
  - `tests/test_eval_v1136.py` +2：快照间缺失指标 delta=None / drift-vs-history 基线缺
    Agent delta=None
- 回归：eval 四文件（upgrade/v1136/eval/agent_tool_discipline）**118 passed**。
- flake8（120/15）：通过；mypy（CI 阻塞门禁）：`ihome_eval.py` no issues。
- 全量 pytest：见第六节（2609 + 5 新增）。

### 诚实遗留

- `force_run` 参数在 `GET /api/eval/report` 声明但未使用（死参数，无实际影响）——
  移除会改公共 API 签名，收益不抵风险，暂留不处理（诚实标注）。
- 轨迹侧质量指标（延迟/降级/完成率）在 dev 环境超窗无样本，未据此改进；生产部署后
  漂移检测数据积累即可判定。
- `_tool_call_score` 无工具调用轨迹时回退确定性基线 100%（v1.13.0 有意设计，docstring
  已诚实标注），本轮不改变其行为。

---

## 六、质量门禁记录

- 新增测试：`tests/test_eval_upgrade.py` +3、`tests/test_eval_v1136.py` +2，共 +5 用例
- 回归：eval 四文件 118 用例全绿
- 全量 pytest：**2614 passed + 2 skipped + 4 xfailed，0 失败**（14m17s，2609 + 5 新增）
- 基线：`scripts/test_baseline.json` 2609 → **2614**（同步 CLAUDE.md 门禁数字 collect 2615→2620）

> 注：本轮不 bump 版本（改进均在 eval 框架展示/判定层，非对外行为变更；API 响应字段
> 结构不变，仅 delta 取值语义与 meets_targets 计算逻辑更严谨）。
