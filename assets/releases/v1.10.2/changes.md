# v1.10.2 版本变更详情

> 归档：assets/releases/v1.10.2/ · 变更基线：v1.10.1 → v1.10.2

## 一、语义变更

| 类型 | 说明 |
|------|------|
| 新增 | 22 个边界测试（tests/test_agent_case.py 37→59） |
| 修复 | `search_cases` 空 task_intent 返回全量 Case（新增空值守卫） |
| 修复 | `_compress_trajectory` tool_calls 非列表致 AttributeError（isinstance 防御） |
| 文档 | assets/guide 附录 A + 第十一章覆盖率更新 |
| 无变更 | 无新 feature flag、无 schema/迁移、无 API 契约变更 |

## 二、代码变更清单

| 文件 | 变更 | 类型 |
|------|------|------|
| `app/services/agent_case_service.py` | search_cases 空值守卫 + compress tool_calls 类型防御 | 修复 |
| `tests/test_agent_case.py` | 新增 22 个边界测试 + import `_find_similar_skill` | 测试 |
| `scripts/verify_self_evolution.py` | 版本断言 1.10.1→1.10.2 | 验证脚本 |
| `assets/guide/ai-self-evolution-guide.md` | 头部版本 + 第十一章 + 附录 A | 文档 |
| `assets/releases/v1.10.2/` | 本目录 5 个归档文件 | 新增 |

## 三、版本号全链路同步清单（16 处）

### 后端（6 处）
| 文件 | 变更 |
|------|------|
| `app/config.py` | `app_version: str = "1.10.2"` |
| `app/mcp/server.py` | `SERVER_VERSION = "1.10.2"` |
| `.env` | `APP_VERSION=1.10.2` |
| `.env.example` | `APP_VERSION=1.10.2` |
| `.env.production` | `APP_VERSION=1.10.2` |
| `.env.production.example` | `APP_VERSION=1.10.2` |

### Flutter（3 处）
| 文件 | 变更 |
|------|------|
| `flutter_app/pubspec.yaml` | `version: 1.10.2+38`（build 号 37→38） |
| `flutter_app/lib/config.dart` | `appVersion = '1.10.2'` |
| `flutter_app/lib/pages/settings_page.dart` | 版本展示 `'1.10.2'` |

### Web / 控制台（3 处）
| 文件 | 变更 |
|------|------|
| `webapp/package.json` | `"version": "1.10.2"` |
| `webapp/public/version.json` | `"version":"1.10.2","build_number":"38"` |
| `console-src/package.json` | `"version": "1.10.2.0"` |

### CI / 部署 / 回滚（4 处）
| 文件 | 变更 |
|------|------|
| `.github/workflows/ci.yml` | `APP_VERSION: "1.10.2"`（3 处） |
| `.github/workflows/schema-compare.yml` | `APP_VERSION: "1.10.2"` |
| `scripts/deploy-production.sh` | `APP_VERSION=1.10.2` |
| `scripts/rollback.sh` | 新增 v1.10.2 条目（复用 3 flag 清单） |

### 测试断言（3 文件）
| 文件 | 变更 |
|------|------|
| `tests/test_v1_3_0_compliance.py` | 断言 + 函数名（test_app_version_is_1_10_2） |
| `tests/test_v1128_suoke_borrowed.py` | 断言 1.10.2 |
| `tests/test_mcp_2026_07_28.py` | 断言 SERVER_VERSION 1.10.2 |

### 文档（3 处）
| 文件 | 变更 |
|------|------|
| `README.md` | 头部 v1.10.2 + 最近更新条目 |
| `CLAUDE.md` | 「Agent 自进化管线」小节 v1.10.2 |
| `CHANGELOG.md` | 新增 [1.10.2] 条目 |

## 四、feature flag 状态

| Flag | 默认值 | v1.10.2 变更 |
|------|--------|-------------|
| `agent_case_extraction_enabled` | False | 无（保持） |
| `agent_skill_distillation_enabled` | False | 无（保持） |
| `agent_skill_evolution_enabled` | False | 无（保持） |

> 三个 flag 默认全 False，关闭时 Agent 维持无记忆无进化静态行为。

## 五、回滚

```bash
bash scripts/rollback.sh v1.10.2 [.env] [--dry-run]
# 等价于 v1.10.1 清单：关闭 AGENT_CASE_EXTRACTION / AGENT_SKILL_DISTILLATION / AGENT_SKILL_EVOLUTION
```
