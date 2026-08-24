# 评估闭环执行记录（2026-08-25 二轮，基准-分析-验证-研究-改进）

> 执行日期：2026-08-25 · 依据：用户指令「继续」承接首轮闭环，同日第二轮
> 范围：eval 套件 + 静态检查 + 全量 pytest 回归 · 改进选题由分析结果驱动 · 全自动闭环
> 承接：`docs/eval-closed-loop-2026-08-25.md`（首轮：缺失基线 delta 诚实标注 + meets_targets 延迟判定）
> 前沿出处：Future AGI「The Definitive Guide to AI Agent Evaluation (2026-05)」（per-dimension
> scoring, aggregate hides regression）/ arXiv:2601.04170「Agent Drift」(2026-01，协调漂移) /
> vysotin「AI Agent Evaluation and Monitoring」(2026-01，多维评估组合)

---

## 一、基准测试（Benchmark）

### 1.1 全量 pytest

- 前置状态：本轮基准沿用首轮已验证的 **2614 passed**（工作区在首轮收尾后干净，
  无新增代码变更）；外部 suoke_life Flutter 测试（flutter_tester）在分析期间结束，
  改进后全量回归在 loadavg 2.15（< ncpu/2=4）干净环境下执行。
- 改进后全量：**2617 passed + 2 skipped + 4 xfailed，0 失败**（11m13s，2614 + 3 新增）。

### 1.2 eval 套件

| 项 | 结果 | 说明 |
|---|---|---|
| 工具选择准确率（全工具集） | **100%（56 用例，0 混淆）** | 确定性关键词基线，保持 |
| 工具选择准确率（Minimal 模式） | 100%（12 用例） | 保持 |
| IDOR 越权覆盖率 | **73.75%**（51 covered + 6 admin + 2 public / 80） | 保持，needs_review 21 |
| IHomeEval 静态维度 | design_safety=100% / hc_compliance=100% / material=100% | **本轮改进主因**（见分析） |

---

## 二、分析（Analyze）

**F1 — `design_safety` 维度恒等于 `hc_compliance_rate`（评估维度无区分度）**

- `_compute_dimension_scores` 两处（有/无轨迹分支）执行
  `scores[design_safety] = scores[hc_compliance_rate]` 复制赋值——两个维度永远同分。
- benchmark 描述为「承重墙/逃生通道/水电规范合规（HC-001）」，但实际度量的是
  **全部 9 条 HC 的可达率**——语义错配：设计安全维度不度量设计安全约束。
- 对比 `_material_score` 已专项度量 HC-003（v1.13.7 修复），design_safety 是遗留的
  「复制赋值」占位，聚合/复制掩盖了维度真实状态。

**F2 — HC-001/HC-006 的 applies_to 引用不存在的 `structural` Agent（spec 与实现漂移）**

- `config/ihome_model_spec.json`：HC-001（承重结构不可破坏）applies_to=
  `["designer","structural","construction"]`，HC-006（逃生通道）applies_to=
  `["designer","structural"]`。
- 实测 `_real_agent_names()`：**`structural` 不在任何 app/agents/*.py 的真实 agent_name
  中**（26 个真实 Agent 无 structural）。被 `_hc_compliance_score` 的「至少命中一个
  真实 Agent 即 wired」粗粒度掩盖（HC-001 因 designer/construction 命中仍计 100%）。

**F3 — `_hc_target_real_names` 别名映射方向反了**

- `BaseAgent._MODEL_SPEC_AGENT_ALIASES = {"door_window": "door_window_waterproof"}`
  方向为 **{真实 agent_name: spec applies_to 名}**（base.py L747 注释 + L764 用
  `agent_name` 查 spec 名）。
- 但 `_hc_target_real_names` 用 `aliases.get(t, t)`（正向）解析 applies_to——把 HC-008
  的 `door_window_waterproof`（spec 侧名）误判为缺失 Agent，实际真实 Agent 是
  `door_window`（`app/agents/door_window_agent.py`）。

---

## 三、验证（Verify）

主代理亲自 Read 源码核验，不采信子代理结论（项目红线）：

1. `_compute_dimension_scores` 两处复制赋值（L330/L364）——F1 根因确认。
2. `BaseAgent._MODEL_SPEC_AGENT_ALIASES`（L747-749）+ 使用处 L764
   `aliases.get(self.agent_name)`——别名方向 {真实名: spec 名} 确认，F3 根因确认。
3. `_real_agent_names()` 实测：26 个真实 Agent，无 `structural`、无
   `door_window_waterproof`（有 `door_window`）——F2/F3 事实确认。
4. `config/ihome_model_spec.json`：HC-001/HC-006 含 structural、HC-008 含
   door_window_waterproof——spec 内容确认。
5. 测试约束核验：`test_eval_upgrade.py::test_hc_compliance_score_measures_wiring`
   断言 100.0（HC-008 别名反查后仍 wired → 不变）；`test_material_score_graded_by_
   target_agents` 断言 100.0（HC-003 无别名 → 不变）；无任何测试断言 design_safety
   分数或别名方向——I1/I2 兼容。

---

## 四、研究（Research，定向前沿检索）

| 出处 | 要点 | 与本次改进的映射 |
|---|---|---|
| **Future AGI「The Definitive Guide to AI Agent Evaluation」**(2026-05) | 六维度独立评分；「Aggregate task-completion alone hides which dimension regressed. Per-dimension scoring tells you what to fix this afternoon」 | F1 改进：design_safety 脱离 hc_compliance_rate 复制赋值，独立专项度量 HC-001（每维度独立评分） |
| **arXiv:2601.04170「Agent Drift」**(2026-01) | Agent 行为退化三形态（语义/协调/行为漂移）可量化监测 | F2 佐证：structural Agent 缺失属 spec-实现协调漂移，评估应如实暴露而非被粗粒度掩盖 |
| **vysotin「AI Agent Evaluation and Monitoring」**(2026-01) | 多维评估组合、可观测性、20-30pp 评估→生产落差根因 | 佐证：静态维度独立性是评估组合可信的前提 |

**红线对齐**：不引入 K8s/微服务（阿里云 FC 架构）；PASETO 鉴权不变；诚实降级不可移除；
新测试补 `tests/`；改动可回溯本报告。

---

## 五、改进（Improve）

### I1 — design_safety 专项度量 HC-001（评估维度独立，对齐 F1/F2）

`app/eval/ihome_eval.py`：
- 新增 `_design_safety_score()`：对齐 `_material_score`（HC-003 专项）模式，专项度量
  HC-001（承重结构不可破坏）的 applies_to 中真实 Agent 占比。
- 替换 `_compute_dimension_scores` 两处 `design_safety = hc_compliance_rate` 复制赋值
  为 `self._design_safety_score()`。

结果：**design_safety 100% → 66.67%**（HC-001 目标 designer/construction 真实、
`structural` 缺失），与 hc_compliance_rate（100%）解耦有区分度；如实暴露 spec 与
实现漂移（诚实降级，不伪造 100%）。

### I2 — HC 别名反查修复（spec 名 → 真实名，对齐 F3）

`_hc_target_real_names()`：aliases 反查（`{v: k for k, v in aliases.items()}`）后再
映射 applies_to。

结果：HC-008 的 `door_window_waterproof` 正确解析为真实 Agent `door_window`，
不再被误判为缺失；hc_compliance_score 仍 100%（HC-008 由「部分可达」变「全可达」），
material_score 100% 不变（HC-003 无别名）。

### 测试与门禁

- 新增 3 用例（`tests/test_eval_upgrade.py`）：design_safety 专项度量 66.67% ≠
  hc_compliance / 报告维度解耦 / HC-008 别名反查解析。
- 回归：eval 四文件 **121 passed**（118 + 3 新增）。
- flake8（120/15）：通过；mypy（CI 阻塞门禁）：`ihome_eval.py` no issues。
- 全量 pytest：见第六节（2614 + 3 新增）。

### 诚实遗留

- **structural Agent 缺失**是 model spec 与实现漂移（HC-001/HC-006 引用不存在的
  Agent）——评估如实反映（66.67%）。修正路径（移除 structural 引用或新增
  structural Agent）属产品/交付决策，不在评估闭环范围。
- `_hc_compliance_score` 仍用「至少命中一个真实 Agent 即 wired」粗粒度（部分可达
  的 HC 计为合规）——本轮不改（避免既有 100% 断言行为变化），列为下一轮候选。
- dev 库轨迹超 7 天窗口，轨迹侧指标无判定价值（同首轮，不据此改进）。

---

## 六、质量门禁记录

- 新增测试：`tests/test_eval_upgrade.py` +3 用例
- 回归：eval 四文件 121 用例全绿
- 全量 pytest：**2617 passed + 2 skipped + 4 xfailed，0 失败**（11m13s，2614 + 3 新增）
- 基线：`scripts/test_baseline.json` 2614 → **2617**（同步 CLAUDE.md 门禁数字 collect 2620→2623）

> 注：本轮不 bump 版本（改进均在 eval 框架静态维度/解析层，非对外行为变更；API 响应
> 字段结构不变，仅 design_safety 分数语义从复制占位变为 HC-001 专项度量）。
