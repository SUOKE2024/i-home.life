# v1.10.2 Release Notes — 自进化管线边界测试补全

> 面向开发团队的发布说明
> 发布日期：2026-08-08 · 分支：main · 前置版本：v1.10.1

---

## 一、版本摘要

v1.10.2 聚焦 **Agent 自进化管线（P0 Case 提取 + P1 Skill 蒸馏/进化）的防御性路径测试补全**。
基于 v1.10.1 覆盖率报告（89%）定位的缺口，新增 22 个边界测试，将核心服务覆盖率提升至 **99%**，
并修复验证过程中发现的 2 个边界问题。

| 指标 | v1.10.1 | v1.10.2 | 变化 |
|------|---------|---------|------|
| 单元测试数（test_agent_case.py） | 37 | 59 | **+22** |
| 总覆盖率 | 89% | **99%** | **+10pp** |
| agent_case_service 覆盖率 | 91% | 99% | +8pp |
| agent_skill_evolution_service 覆盖率 | 85% | **100%** | +15pp |
| 端到端验证项 | — | 66 项全通过 | 新增验证脚本 |
| 边界问题 | — | 修复 2 个 | search_cases / compress_trajectory |

---

## 二、重点：覆盖率提升

### 2.1 覆盖率总览

```
app/models/agent_case.py                    26 stmts   0 miss   100%
app/services/agent_case_service.py         148 stmts   1 miss    99%
app/services/agent_skill_evolution_service.py  171 stmts  0 miss  100%
TOTAL                                      345 stmts   1 miss    99%
```

### 2.2 补全的防御性路径（22 个测试）

**LLM 异常返回**（覆盖率提升主力）：
- `_parse_case_json` / `_parse_skill_json` 的 json.loads 失败 → 子串提取成功/失败双路径
- `_llm_distill_skill` LLM 调用异常 → best-effort 返回 None
- markdown 代码块包裹的 LLM 输出解析
- approach 非法 JSON 时蒸馏降级仍成功

**空值输入**：
- 空/纯空格 task_intent 检索 → 返回空列表
- 空 name 跳过 Skill 查重
- 不存在的 skill_id → record/evaluate 安全无操作
- 零使用记录 Skill（total=0）三维质控边界
- sample_size=0 / before_success_rate=1.0 显著性检验边界

---

## 三、重点：死代码优化点

### 3.1 发现并守护的防御性死代码

`_compress_trajectory` L93 的 `"...[已截断]"` 分支（[agent_case_service.py](app/services/agent_case_service.py)）：

```
各段截断上限：user_msg[:500] + 工具调用[:10] + response[:800] ≈ 1450 字符
_COMPRESS_THRESHOLD = 2000
→ 上限之和恒 < 阈值，L93 分支当前参数下不可达
```

**处置方式（不强行凑测试）**：新增 `test_compress_trajectory_bounded_length`，
以**有界性不变式**（`len(compressed) <= 2000`）守护该行为——当未来某段截断逻辑变更
（如 response 不再截断）导致输出可能越界时，此测试立即失败告警。

> 设计原则：防御阈值应高于实际内容上限，防止未来字段增长时越界。
> 该分支保留为未来安全网，不删除、不假覆盖。

### 3.2 修复的边界问题（验证中发现）

| 问题 | 严重度 | 根因 | 修复 |
|------|--------|------|------|
| `search_cases` 空 task_intent 返回全量 Case | Medium | `keywords=[]` 跳过关键词过滤，查询退化为返回用户所有未蒸馏 Case | `agent_case_service.py` 增加空值提前返回守卫 |
| `_compress_trajectory` tool_calls 非列表致 AttributeError | Low | `tc.get("name")` 在 tool_calls 为字符串时崩溃 | `isinstance(tool_calls, list)` + `isinstance(tc, dict)` 防御 |

---

## 四、变更内容

### 4.1 功能变更

- **无新增 feature flag**：复用 v1.10.1 三个 flag（`agent_case_extraction_enabled` /
  `agent_skill_distillation_enabled` / `agent_skill_evolution_enabled`），默认全 False
- **行为变更**：`search_cases` 空 task_intent 现在返回空列表（此前返回全量 Case，潜在数据泄漏面）

### 4.2 文件变更

| 类别 | 文件 |
|------|------|
| 服务代码 | `app/services/agent_case_service.py`（2 处边界修复） |
| 测试 | `tests/test_agent_case.py`（37→59，+22） |
| 验证脚本 | `scripts/verify_self_evolution.py`（66 项端到端） |
| 文档 | `assets/guide/ai-self-evolution-guide.md`（附录 A） |
| 版本同步 | 全链路 16 处（见 `assets/releases/v1.10.2/changes.md`） |

### 4.3 无破坏性变更

- 所有 API 契约不变，无 schema 变更，无数据库迁移
- `_parse_case_json` / `_parse_skill_json` / `search_cases` 返回语义向后兼容
- 三个 feature flag 默认值保持 False，关闭时管线零行为变化

---

## 五、验证结论

| 门禁 | 结果 |
|------|------|
| `tests/test_agent_case.py` | **59 passed**（覆盖率 99%） |
| 版本断言 + 相关测试（5 文件） | **154 passed** |
| `scripts/verify_self_evolution.py` | **66 项端到端全通过** |
| flake8（max-line-length=120, max-complexity=15） | 0 issues |
| mypy | 0 issues |
| `bash -n scripts/rollback.sh` | 通过 |
| webapp `npm run build` | 成功（dist/version.json = 1.10.2+38） |
| pytest 基线 | 2021 passed 不回退 |

---

## 六、回滚方案

```bash
# 一键关闭自进化管线三个 flag（v1.10.2 无新 flag，复用 v1.10.1 清单）
bash scripts/rollback.sh v1.10.2
```

---

## 七、开发团队行动项

- [ ] 审查 `tests/test_agent_case.py` 新增的 22 个边界测试命名与断言
- [ ] 确认 `search_cases` 空 task_intent 守卫符合业务预期（影响面：flag 开启后的检索行为）
- [ ] 后续若修改 `_compress_trajectory` 截断逻辑，运行 `test_compress_trajectory_bounded_length` 验证有界性
- [ ] 发布前执行 `bash scripts/rollback.sh v1.10.2 --dry-run` 验证回滚脚本

---

*详细归档见 `assets/releases/v1.10.2/` 目录（validation-report.md / test-case-list.md / changes.md）*
