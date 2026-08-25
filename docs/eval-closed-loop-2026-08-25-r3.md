# 评估闭环执行记录（2026-08-25 三轮，基准-分析-验证-研究-改进）

> 执行日期：2026-08-25 · 依据：用户指令「继续」承接二轮闭环，同日第三轮
> 范围：eval 套件 + 静态检查 + 全量 pytest 回归 · 改进选题由分析结果驱动 · 全自动闭环
> 承接：`docs/eval-closed-loop-2026-08-25-r2.md`（二轮：design_safety 专项度量 + HC 别名反查）
> 前沿出处：Future AGI「The Definitive Guide to AI Agent Evaluation」(2026-05，per-dimension
> scoring) / Yale·IBM「Survey on Evaluation of LLM-based Agents」(2026-04，细粒度指标) /
> arXiv:2601.04170「Agent Drift」(2026-01，spec-实现协调漂移)
> 诚实标注：本轮 WebSearch 服务两次故障（Error 10000000），研究映射复用前两轮已核验的
> 前沿出处（未伪造检索结果）。

---

## 一、基准测试（Benchmark）

### 1.1 全量 pytest

- 前置状态：基准沿用二轮已验证的 **2617 passed**（工作区在二轮收尾后干净）；外部
  suoke_life Flutter 测试在跑但 CPU 占用极低（0.6%），loadavg 2.94 < ncpu/2（4）。
- 改进后全量：**2620 passed + 2 skipped + 4 xfailed，0 失败**（9m29s，2617 + 3 新增）。

### 1.2 eval 套件

| 项 | 结果 | 说明 |
|---|---|---|
| 工具选择准确率（全工具集） | **100%（56 用例，0 混淆）** | 确定性关键词基线，保持 |
| 工具选择准确率（Minimal 模式） | 100%（12 用例） | 保持 |
| IDOR 越权覆盖率 | **73.75%**（51 covered + 6 admin + 2 public / 80） | 保持 |
| IHomeEval 静态维度 | hc_compliance=100% / design_safety=66.67% / material=100% | **hc_compliance 为本轮改进主因** |

---

## 二、分析（Analyze）

**F1 — `hc_compliance_score` 用「至少命中一个真实 Agent 即 wired」粗粒度（评估精度问题）**

- `_hc_compliance_score`（L582-610）当前口径：每条 HC 的 applies_to 与真实 Agent 集合
  **只要非空交集**即计为 wired，`wired / 总 HC 数`。
- 逐条实测可达率：
  - HC-001（承重结构）2/3 = 66.67%（structural 缺失）
  - HC-006（逃生通道）1/2 = **50%**（structural 缺失）
  - 其余 7 条 100%
- **wired 口径 = 100%（9/9 都有交集）**，掩盖了 HC-001/HC-006 的部分可达缺口——
  逃生通道约束实际只覆盖一半目标 Agent，报告仍显示 100% 合规。

**F2 — `tool_call_accuracy` 无工具调用轨迹时用基线代理但未标注（评估诚实度小缺口）**

- `_tool_call_score` 在 traces 非空但全无工具调用时回退确定性关键词基线（100%），
  docstring 已诚实标注，但 report.notes 未告知消费方该分数是「基线代理」而非真实
  轨迹工具调用度量——消费方可能误读为「生产轨迹工具调用 100% 准确」。

---

## 三、验证（Verify）

主代理亲自 Read 源码核验，不采信子代理结论（项目红线）：

1. `_hc_compliance_score`（L582-610）：wired 口径逐行确认——F1 根因确认。
2. 逐条 HC 可达率量化脚本：9 条 HC 中 HC-001 2/3、HC-006 1/2，平均可达率
   = 816.67/9 = **90.74%**（wired 口径 100%）——F1 影响面量化确认。
3. `_tool_call_score`（L380+）：无工具调用轨迹回退 `get_tool_accuracy_report()["metrics"]
   ["accuracy"]`（100%）——F2 根因确认；`run()`（L251-272）仅空轨迹时追加 note，
   无「有轨迹但无工具调用」的标注分支——F2 确认。
4. 测试约束核验：
   - `test_eval_upgrade.py::test_hc_compliance_score_measures_wiring` 断言 100.0
     → 本轮需更新为 90.74（预期行为变化）；
   - `test_eval_upgrade.py::test_design_safety_score_measures_hc001` 断言
     `hc == 100.0` → 需更新（design_safety 66.67 不变）；
   - 其余测试无 hc_compliance / tool_call 代理标注相关数值断言，兼容。

---

## 四、研究（Research，定向前沿检索）

WebSearch 服务故障（两次 Error 10000000），复用前两轮已核验前沿映射（诚实标注）：

| 出处 | 要点 | 与本次改进的映射 |
|---|---|---|
| **Future AGI「The Definitive Guide to AI Agent Evaluation」**(2026-05) | 每维度独立评分；「Aggregate alone hides which dimension regressed」 | F1 改进：wired 全有全无口径 → 平均可达率（细粒度，暴露部分可达缺口） |
| **Yale/IBM「Survey on Evaluation of LLM-based Agents」**(2026-04) | 细粒度指标是评估体系五大关键缺口之一 | 佐证：平均可达率比二值 wired 更细粒度 |
| **arXiv:2601.04170「Agent Drift」**(2026-01) | spec-实现协调漂移应被量化监测 | 佐证：HC-006 逃生通道 50% 可达是 spec(HC 声明)与实现(Agent 清单)漂移的量化暴露 |

**红线对齐**：不引入 K8s/微服务（阿里云 FC 架构）；PASETO 鉴权不变；诚实降级不可移除；
新测试补 `tests/`；改动可回溯本报告。

---

## 五、改进（Improve）

### I1 — HC 合规率改平均可达率（评估精度，对齐 F1）

`_hc_compliance_score()`：从「至少命中一个即 wired 计数」改为**平均可达率**——
每条 HC 计算（真实命中 Agent 数 / 声明目标 Agent 数），全部分数取平均。

结果：**100% → 90.74%**——HC-001（承重结构 2/3）与 HC-006（逃生通道 1/2）的
structural 缺失缺口如实暴露，不再被二值口径掩盖。

### I2 — tool_call_accuracy 基线代理标注（评估诚实度，对齐 F2）

`IHomeEvalRunner.run()`：新增分支——有轨迹但全部无工具调用时，追加 note
「tool_call_accuracy 使用确定性关键词基线代理（轨迹无工具调用样本，诚实标注：
非真实轨迹工具调用度量）」。

结果：消费方明确区分「真实轨迹工具调用度量」与「基线代理」，不再误读 100% 为
生产轨迹真实表现。

### 测试与门禁

- 更新 1 用例 + 新增 3 用例（`tests/test_eval_upgrade.py`）：
  - 更新：`test_hc_compliance_score_measures_wiring`（100.0 → 90.74）、
    `test_design_safety_score_measures_hc001`（hc 断言 100.0 → 90.74）
  - 新增：HC 部分可达暴露（<100 且 HC-006 structural 声明存在）/
    无工具调用轨迹 note 标注 / 有工具调用轨迹不标注
- 回归：eval 四文件 **124 passed**（121 + 3 新增）。
- flake8（120/15）：通过；mypy（CI 阻塞门禁）：`ihome_eval.py` no issues。
- 全量 pytest：见第六节（2617 + 3 新增）。

### 诚实遗留

- **structural Agent 缺失**已由三个维度暴露（design_safety 66.67%、HC-006 逃生通道
  50%、整体 HC 合规 90.74%）；修正路径（移除 spec 引用或新增 structural Agent）
  仍属产品/交付决策，不在评估闭环范围。
- `_tool_call_score` 基线代理本身是有意的诚实降级（docstring 已标注），本轮补齐
  报告 notes 层标注；是否引入「无工具调用轨迹时 tool_call_accuracy 置 None」是
  口径取舍（会改变既有维度结构），列为候选。
- dev 库轨迹超 7 天窗口，轨迹侧指标无判定价值（同前两轮，不据此改进）。

---

## 六、质量门禁记录

- 新增测试：`tests/test_eval_upgrade.py` +3 用例（另更新 2 用例断言）
- 回归：eval 四文件 124 用例全绿
- 全量 pytest：**2620 passed + 2 skipped + 4 xfailed，0 失败**（9m29s，2617 + 3 新增）
- 基线：`scripts/test_baseline.json` 2617 → **2620**（同步 CLAUDE.md 门禁数字 collect 2623→2626）

> 注：本轮不 bump 版本（改进均在 eval 框架静态维度计算层，非对外行为变更；API 响应
> 字段结构不变，仅 hc_compliance_rate 分数语义从二值 wired 变为平均可达率）。
