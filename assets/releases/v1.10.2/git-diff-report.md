# v1.10.2 预提交差异对比报告

> 归档：assets/releases/v1.10.2/ · 生成时间：2026-08-08
> 用途：提交前核验（Pre-commit review）

---

## 一、提交元数据

| 项 | 值 |
|----|-----|
| 目标分支 | main |
| 当前 HEAD | `365d6a5` infra(i-home.life): 开通加固 — HSTS 落地 / favicon 兜底 / SEO 元数据 |
| 待提交版本 | v1.10.2（含此前会话累积的自进化管线/记忆闭环/诊断等未提交工作） |
| 暂存文件数 | **126** |
| 差异规模 | **+8877 / -687 行** |

## 二、暂存概览（按类别）

| 类别 | 文件数 | 说明 |
|------|--------|------|
| 后端 app/ | 25 | 自进化管线服务/模型、诊断、agents 记忆闭环、config、MCP |
| Flutter | 50 | 页面 UI/UX 优化、LBS 定位、网络图降级、版本号 |
| Web/console | 16 | webapp 页面/样式、console 构建 |
| CI/scripts | 11 | ci.yml、schema-compare、deploy、rollback、验证脚本 |
| 测试 tests/ | 6 | test_agent_case（+22 边界）、test_diagnostics 等 |
| 文档 | 10 | README、CLAUDE.md、CHANGELOG、assets/guide、assets/releases |

## 三、v1.10.2 核心变更（本次发布主内容）

| 文件 | 差异 | 类型 |
|------|------|------|
| `app/services/agent_case_service.py` | +329（新增文件） | 服务：Case 提取/检索/注入 + 2 处边界修复 |
| `app/services/agent_skill_evolution_service.py` | +471（新增文件） | 服务：Skill 蒸馏/进化/诊断归因 |
| `app/models/agent_case.py` | +98（新增文件） | 模型：AgentCase 表 |
| `tests/test_agent_case.py` | +880（新增文件） | 测试：59 用例（含 22 个 v1.10.2 边界测试） |
| `scripts/verify_self_evolution.py` | +881（新增文件） | 验证脚本：66 项端到端 |
| `assets/guide/ai-self-evolution-guide.md` | +258 | 文档：边界清单/覆盖率/附录 A |
| `assets/releases/v1.10.2/` | +5 文件 | 本次归档 |

### 3.1 本次会话修改的服务代码 diff（关键片段）

**`search_cases` 空值守卫**（[agent_case_service.py](app/services/agent_case_service.py)）：
```diff
     settings = get_settings()
     if not settings.agent_skill_distillation_enabled:
         return []
 
+    # 空 task_intent 不检索（避免无关键词过滤时返回全量 Case）
+    if not task_intent or not task_intent.strip():
+        return []
```

**`_compress_trajectory` 类型防御**：
```diff
     tool_calls = trace_dict.get("tool_calls", [])
-    if tool_calls:
+    if tool_calls and isinstance(tool_calls, list):
         tc_summary = []
         for tc in tool_calls[:10]:
-            name = tc.get("name", tc.get("function", {}).get("name", ""))
+            if isinstance(tc, dict):
+                name = tc.get("name", tc.get("function", {}).get("name", ""))
+            else:
+                name = str(tc)
             tc_summary.append(f"  - {name}")
```

## 四、版本号同步核验（16 处）

| 位置 | 文件 | 值 |
|------|------|-----|
| 后端 | app/config.py / app/mcp/server.py | 1.10.2 |
| 环境 | .env / .env.example / .env.production / .env.production.example | 1.10.2 |
| Flutter | pubspec.yaml（+38）/ config.dart / settings_page.dart | 1.10.2 |
| Web | webapp/package.json / version.json / console-src/package.json | 1.10.2 / 1.10.2.0 |
| CI | ci.yml ×3 / schema-compare.yml | 1.10.2 |
| 部署 | deploy-production.sh | 1.10.2 |
| 回滚 | rollback.sh（v1.10.2 条目） | 新增 |
| 测试 | test_v1_3_0_compliance / test_v1128_suoke_borrowed / test_mcp_2026_07_28 | 1.10.2 |
| 文档 | README / CLAUDE.md / CHANGELOG | 1.10.2 |

## 五、敏感文件核验

| 检查项 | 结果 |
|--------|------|
| `.env` / `.env.production` | ✅ gitignore 保护，未暂存 |
| `data/*.db` / `data/test_*.db` | ✅ gitignore 保护（data/test_*.db + *.db-journal） |
| 密钥/证书（.pem/.key） | ✅ 无 |
| 凭据文件 | ✅ 无 |

## 六、预提交检查清单

- [x] 所有 v1.10.2 修改已暂存（git add -A，126 文件）
- [x] 无敏感文件混入
- [x] 版本号 16 处全链路一致（见 `changes.md` 第三节）
- [x] 测试通过：test_agent_case 59 + 版本断言 154
- [x] flake8 / mypy / bash -n 通过
- [x] webapp build 成功（dist/version.json = 1.10.2+38）
- [x] 回滚脚本 v1.10.2 条目就绪
- [ ] **待确认**：提交信息 message（建议遵循仓库风格，如 `feat(agents): v1.10.2 自进化管线边界测试补全`）
- [ ] **待确认**：是否推送远端

## 七、提交命令参考（待用户确认后执行）

```bash
git commit -m "feat(agents): v1.10.2 自进化管线边界测试补全（覆盖率 89%→99%）"
# 推送（需用户确认）
# git push -u origin main
```
