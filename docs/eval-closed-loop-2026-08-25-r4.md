# 评估闭环执行记录（2026-08-25 四轮，基准-分析-验证-研究-改进）

> 执行日期：2026-08-25 · 依据：用户指令「继续」承接三轮闭环，同日第四轮
> 范围：eval 套件 + 静态检查 + 全量 pytest 回归 · 改进选题由分析结果驱动 · 全自动闭环
> 承接：`docs/eval-closed-loop-2026-08-25-r3.md`（三轮：HC 合规平均可达率 + tool_call 代理标注）
> 前沿出处：Sentrial「Your Evals Are Passing While Your Agent Is Failing Users」
> (2026-05，无数据/占位值失真会误导) / Anthropic「Demystifying Evals for AI Agents」
> (2026-01，评估对象一致性) / 承接 Future AGI per-dimension scoring

---

## 一、基准测试（Benchmark）

### 1.1 全量 pytest

- 前置状态：基准沿用三轮已验证的 **2620 passed**（工作区在三轮收尾后干净）；外部
  suoke_life Flutter 测试在跑但 CPU 占用极低，loadavg 3.19 < ncpu/2（4）。
- 改进后全量：**2624 passed + 2 skipped + 4 xfailed，0 失败**（11m31s，2620 + 4 新增）。

### 1.2 eval 套件

| 项 | 结果 | 说明 |
|---|---|---|
| 工具选择准确率（全工具集） | **100%（56 用例，0 混淆）** | 确定性关键词基线，保持 |
| 工具选择准确率（Minimal 模式） | 100%（12 用例） | 保持 |
| IDOR 越权覆盖率 | **73.75%**（51 covered + 6 admin + 2 public / 80） | 保持 |
| 漂移检测 | 见「分析」 | **本轮改进主因**（延迟无数据被判 0ms 达标） |

---

## 二、分析（Analyze）

**F1 — 延迟/首 token 无数据被当作 0ms（评估诚实度问题）**

- **实证**：构造 10 条 `latency_ms=None` 的轨迹，`detect_agent_drift` 报告
  `avg_latency_ms: current=0.0, status=ok`——「0ms 达标」假象；实际没有任何延迟数据。
- 关键事实（源码核验）：`AgentTraceRecord.latency_ms` 模型为
  `nullable=False, default=0.0`——**DB 中从不存 NULL，「无数据」的占位值是 0.0**
  （首版 `IS NOT NULL` 计数实测恒 = total，方向错误，改为 `> 0` 计数后生效）。
- 三处失真同源：
  1. `detect_agent_drift`：avg_latency=0（全占位）→ 判定 ok；
  2. `_compute_runtime_metrics`：`avg = sum/len` 含 0 占位样本 → 部分轨迹无延迟数据时
     均值被稀释（1000+0 → 500），`latency_p50/p95/p99` 同稀释；
  3. `_compute_dimension_scores` 的 SSE_LATENCY：`avg_latency=0`（无数据）→
     `100 - 0/50 = 100` 满分——「无延迟数据」被显示为「秒回满分」。

---

## 三、验证（Verify）

主代理亲自 Read 源码核验，不采信子代理结论（项目红线）：

1. `app/models/agent_trace.py` L52-53：`latency_ms`/`first_token_latency_ms` 均
   `nullable=False, default=0.0`——占位 0 语义确认（F1 修复前提）。
2. `detect_agent_drift`（L741-835）：`func.avg(latency_ms)` 全 0 时返回 0.0 →
   `_judge` 0 ≤ 15000 → ok——F1 根因确认。
3. `_compute_runtime_metrics`（L299-333）：`avg = sum/len`（含 0 占位）、
   `_percentile(latencies, ...)`（含 0）——F1 稀释根因确认；对照
   `first_tokens_nonzero = [v for v in first_tokens if v > 0]` 已有「>0 过滤」先例。
4. `_compute_dimension_scores` SSE_LATENCY（L357-369）：`ft_p95=0 → 回退 avg/50`，
   avg=0 → 100 满分——F1 满分假象根因确认。
5. 测试约束核验：`test_drift_ok_agent` 等既有 drift 测试均用 `latency_ms=1000`
   （非占位）→ latency_cnt=10 → 正常判定不变；`test_eval_v1136.py` runtime metrics
   测试 latency 值均 >0 → 非零样本聚合与原值一致。兼容。

---

## 四、研究（Research，定向前沿检索）

WebSearch 服务本轮未调用（前几轮已两次故障，且本选题与已核验前沿映射一致）：

| 出处 | 要点 | 与本次改进的映射 |
|---|---|---|
| **Sentrial「Your Evals Are Passing While Your Agent Is Failing Users」**(2026-05) | 生产评估基于 traces；无数据/占位值输出会误导 | F1 改进：占位 0 与真实 0ms 不可混淆，无延迟数据须省略/不判定 |
| **Anthropic「Demystifying Evals for AI Agents」**(2026-01) | 评估对象一致性：同一指标在不同评估层口径一致 | F1 改进：drift/per-agent/维度三层延迟口径统一为「非零样本」 |
| **Future AGI「per-dimension scoring」**(2026-05，承接) | 维度独立、细粒度 | 佐证：SSE_LATENCY 无数据省略对齐 budget_accuracy 模式 |

**红线对齐**：不引入 K8s/微服务（阿里云 FC 架构）；PASETO 鉴权不变；诚实降级不可移除；
新测试补 `tests/`；改动可回溯本报告。

---

## 五、改进（Improve）

### I1 — drift 延迟无数据不判定（评估诚实度，对齐 F1-1）

`detect_agent_drift`：
- SQL 新增 `latency_cnt = sum(case(latency_ms > 0, 1))`（模型占位 0 语义，>0 即真实延迟样本）。
- `latency_cnt == 0` 时 `avg_latency_ms` 输出 `status=insufficient_samples, current=None`
  （不判定），不再输出「0ms ok」。

### I2 — 延迟聚合仅基于非零样本（评估精度，对齐 F1-2）

- `_compute_runtime_metrics`：`latencies_nonzero = [v for v in latencies if v > 0]`，
  avg/p50/p95/p99 与 delivery_p95 均基于非零样本（对齐 first_tokens_nonzero 先例）；
  新增 `latency_samples` 字段供消费方区分「无数据」与「0ms」。
- `_compute_per_agent_scores`：`avg_latency` / `latency_p95` 同样基于非零样本
  （避免 meets_targets 被 0 稀释误判达标）。

### I3 — SSE_LATENCY 无延迟数据省略（评估诚实度，对齐 F1-3）

`_compute_dimension_scores`：`ft_p95 > 0` 用首 token；`elif latency_samples > 0` 用
avg 伪代理；两者皆无 → **省略 sse_latency 维度**（对齐 budget_accuracy 无数据省略
模式）——不再输出「无数据 → 100 满分」假象。

### 测试与门禁

- 新增 4 用例（`tests/test_eval_upgrade.py`）：
  - 无延迟数据 drift avg_latency_ms → insufficient_samples（对照：有数据 → ok）
  - runtime metrics 非零样本聚合（1000+0 → avg 1000 而非 500）+ latency_samples
  - SSE_LATENCY 无延迟省略 / 有延迟回退 avg 伪代理
- 回归：eval 四文件 **128 passed**（124 + 4 新增）。
- flake8（120/15）：通过；mypy（CI 阻塞门禁）：`ihome_eval.py` no issues。
- 全量 pytest：见第六节（2620 + 4 新增）。

### 诚实遗留

- `fetch_agent_traces_as_dicts` 仍把 latency_ms 占位 0 原样传给 dict 消费方——本轮在
  消费端（runtime metrics/per-agent）统一用非零样本口径处理；dict 形态保留 0 值
  是为了字段类型稳定（数字），消费端已有 latency_samples 区分。
- **structural Agent 缺失**继续由三个维度交叉暴露（不重复），修正路径仍属产品决策。
- dev 库轨迹超 7 天窗口，轨迹侧指标无判定价值（同前三轮，不据此改进）。

---

## 六、质量门禁记录

- 新增测试：`tests/test_eval_upgrade.py` +4 用例
- 回归：eval 四文件 128 用例全绿
- 全量 pytest：**2624 passed + 2 skipped + 4 xfailed，0 失败**（11m31s，2620 + 4 新增）
- 基线：`scripts/test_baseline.json` 2620 → **2624**（同步 CLAUDE.md 门禁数字 collect 2626→2630）

> 注：本轮不 bump 版本（改进均在 eval 框架延迟口径/判定层，非对外行为变更；API 响应
> 字段新增 latency_samples，drift 的 avg_latency_ms 无数据时 current 输出 null）。
