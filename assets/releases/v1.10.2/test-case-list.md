# v1.10.2 测试用例清单

> 归档：assets/releases/v1.10.2/ · 文件：tests/test_agent_case.py（37 → 59 用例）

## 一、新增边界测试（22 个）

### agent_case_service 覆盖（11 个）

| 测试名 | 覆盖路径 | 类别 |
|--------|---------|------|
| `test_is_goal_directed_chitchat_over_8_chars` | 闲聊词命中（≥8 字符） | 空值/异常输入 |
| `test_compress_trajectory_bounded_length` | 超长输入有界性不变式（L93 死代码守护） | 死代码守护 |
| `test_extract_case_trace_with_to_dict` | trace 对象 to_dict() 分支 | 类型分支 |
| `test_extract_case_unsupported_trace_type` | trace 类型不支持（int）→ None | 异常输入 |
| `test_parse_case_json_substring_extraction` | json.loads 失败 → 子串提取成功 | LLM 异常返回 |
| `test_parse_case_json_substring_extraction_fails` | 子串仍非法 / 无花括号 → None | LLM 异常返回 |
| `test_parse_case_json_quality_non_numeric` | quality_score 非数字 → 0.0 | 异常输入 |
| `test_build_case_context_malformed_approach` | approach 非 JSON → "(步骤解析失败)" | 异常输入 |
| `test_search_cases_empty_task_intent_returns_empty` | 空 task_intent → [] | 空值输入 |

### agent_skill_evolution_service 覆盖（11 个）

| 测试名 | 覆盖路径 | 类别 |
|--------|---------|------|
| `test_distill_skill_flag_off_returns_none` | distill flag 关闭 | 门控路径 |
| `test_distill_skill_llm_invalid_json` | LLM 返回非法 JSON → None | LLM 异常返回 |
| `test_distill_skill_llm_error` | LLM 调用异常 → None | LLM 异常返回 |
| `test_distill_skill_malformed_approach` | approach 非法 JSON 蒸馏仍成功 | 异常输入 |
| `test_parse_skill_json_markdown_wrapped` | markdown 代码块包裹解析 | LLM 异常返回 |
| `test_parse_skill_json_no_braces` | 无花括号 → None | LLM 异常返回 |
| `test_parse_skill_json_substring_extraction_fails` | 子串仍非法 → None | LLM 异常返回 |
| `test_find_similar_skill_empty_name` | name 为空跳过查重 | 空值输入 |
| `test_record_skill_outcome_not_found` | skill 不存在安全无操作 | 空值输入 |
| `test_evaluate_skill_quality_flag_off` / `_not_found` | flag 关闭 / skill 不存在 | 门控/空值 |
| `test_diagnose_credit_sample_size_zero` / `_before_rate_max` | 显著性检验边界（z=0） | 边界守卫 |

## 二、测试覆盖的防御性路径映射

| 源函数 | 覆盖的防御路径 |
|--------|--------------|
| `_is_goal_directed` | <8 字符 / 闲聊词命中 / 正常目标导向 |
| `_compress_trajectory` | 空 dict / tool_calls 非列表 / 超长有界性 |
| `extract_case_from_trace` | flag 关闭 / trace 类型（dict/to_dict/不支持）/ 非目标导向 / LLM 失败 / LLM 成功 |
| `_parse_case_json` | 合法 / markdown / 子串成功 / 子串失败 / clamp / 非数字 / outcome 非法 |
| `_parse_skill_json` | 合法 / 子串成功 / 子串失败 / markdown / 缺 system_prompt |
| `search_cases` | scope 隔离 / flag 关闭 / 空 task_intent |
| `build_case_context` | 空列表 / 正常格式化 / malformed approach |
| `distill_skill_from_cases` | flag 关闭 / 不足阈值 / LLM 非法 JSON / LLM 异常 / malformed approach / 合并相似 / 创建成功 |
| `record_skill_outcome` | flag 关闭 / 计数递增 / skill 不存在 |
| `evaluate_skill_quality` | flag 关闭 / skill 不存在 / 零使用 / 高质晋升 / 低质淘汰 |
| `diagnose_credit_skill_patch` | flag 关闭 / 显著 / 不显著 / sample_size=0 / before=1.0 |
| `get_skill_for_injection` | ACTIVE 检索 / flag 关闭 / 用户隔离 |
| `_find_similar_skill` | name 为空跳过 / 查重命中 |

## 三、原有测试（37 个，未改动）

覆盖管线主路径：Case 提取主流程、检索主流程、Skill 蒸馏主流程、三维质控、诊断归因、
Harness 集成、BaseAgent 注入等。

## 四、测试运行命令

```bash
source .venv/bin/activate
python -m pytest tests/test_agent_case.py -q --timeout=60 \
  --cov=app.services.agent_case_service \
  --cov=app.services.agent_skill_evolution_service \
  --cov=app.models.agent_case \
  --cov-report=term-missing
```
