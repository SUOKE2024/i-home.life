# v1.10.2 发布归档索引

> 自进化管线边界测试补全 · 2026-08-08
> 索引文件：本目录入口，供开发/运维快速定位归档内容

---

## Changelog 摘要（基于提交 d1790d0）

> **Tag：`v1.10.2`** · Commit：`d1790d0` · 127 files changed · +8988 / -687
> 已推送远端：`git push -u origin main`（main 已跟踪 origin/main）

**feat(agents): v1.10.2 自进化管线边界测试补全（覆盖率 89%→99%）**

- **新增 22 个边界测试**（tests/test_agent_case.py 37→59）：LLM 异常返回
  （非法 JSON 子串提取/调用异常/markdown 包裹）与空值输入（空 task_intent /
  空 name / 不存在 skill_id / 零使用记录 / 显著性检验边界）
- **修复 2 个边界问题**：`search_cases` 空 task_intent 返回全量 Case（新增空值守卫）、
  `_compress_trajectory` tool_calls 非列表致 AttributeError
- **覆盖率 99%**：`agent_case_service` 91%→99%、`agent_skill_evolution_service` 85%→100%；
  L93 "[已截断]" 分支确认为防御性死代码，以有界性不变式守护
- **新增验证脚本** `scripts/verify_self_evolution.py`（66 项端到端验证全通过）
- **版本全链路 1.10.1→1.10.2**（16 处）；`rollback.sh` 新增 v1.10.2 条目
- **固化累积工作**：自进化管线 v1.10.1、全链路记忆闭环、LBS 定位、诊断系统、
  移动端 UI/UX 优化、webapp 迁移增强等

---

## 归档文件

| 文件 | 内容 | 适用对象 |
|------|------|---------|
| [RELEASE_NOTES.md](RELEASE_NOTES.md) | 面向开发团队的发布说明（覆盖率提升 + 死代码优化点） | 开发团队 |
| [validation-report.md](validation-report.md) | 验证报告（59 测试 / 66 端到端 / 覆盖率 99% / 质量门禁） | 质量保障 |
| [test-case-list.md](test-case-list.md) | 22 个新增边界测试清单 + 防御路径映射 | 测试团队 |
| [changes.md](changes.md) | 版本变更详情（代码清单 / 16 处版本同步 / flag 状态 / 回滚） | 运维/发布 |
| [git-diff-report.md](git-diff-report.md) | 预提交差异对比报告（126 文件 / 分类统计 / 敏感核验 / 检查清单） | 提交审核 |

## 版本速览

| 项 | 值 |
|----|-----|
| 版本 | 1.10.2（Flutter build 38） |
| 前置版本 | 1.10.1 |
| 分支 | main |
| 核心变化 | 覆盖率 89%→99%，修复 2 个边界问题，死代码守护 |
| feature flag | 无新增（复用 v1.10.1 三个自进化 flag，默认 False） |
| 回滚 | `bash scripts/rollback.sh v1.10.2` |

## 相关文档链接

- 用户指南：`assets/guide/ai-self-evolution-guide.md`（第九章边界 / 第十一章覆盖率 / 附录 A）
- 隐私声明：`assets/legal/agent-memory-privacy-notice.md`
- 版本变更：`CHANGELOG.md` [1.10.2] 条目

## 历史版本归档

| 版本 | 目录 |
|------|------|
| v1.10.2 | `assets/releases/v1.10.2/`（本目录） |
