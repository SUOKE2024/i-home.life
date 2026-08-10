# 提交前检查报告 — api-client.ts / api.dart（2026-08-09）

> 生成时间：2026-08-09 · 检查对象：console-src/src/services/api-client.ts、flutter_app/lib/services/api.dart
> 状态：**均未提交**（工作区 M），为对 HEAD 的增量修改，无冲突需手动合并，但**依赖完整功能单元整体提交**（见 §四）

---

## 一、变更摘要

| 文件 | 变更量 | 性质 |
|------|--------|------|
| `console-src/src/services/api-client.ts` | +768 行 | 新增 30+ API 端点封装（12 新页对应后端模块） |
| `flutter_app/lib/services/api.dart` | +167 行 | 新增 9 个方法 + 2 个私有辅助（_multipartPost / _exportIFC） |

## 二、api-client.ts 新增端点清单（30+，与后端路由对齐）

| 后端模块 | 新增端点 |
|---------|---------|
| Agent Identity | /api/agents/identity, /api/agents/identity/{name} |
| Agent Approvals | /api/agents/approvals, /{approvalId}/approve \| /reject \| /execute |
| Agent Skills | /api/agents/skills（CRUD）+ /import /share /promote /rollback /instantiate |
| Agent Memory | /api/agents/memory, /api/agents/memory/{memoryId} |
| A2A | /api/a2a/agents, /api/a2a/tasks/send, /api/a2a/tasks/{taskId}(/status) |
| MCP | /api/mcp/manifest, /tools, /tools/call, /mrtr |
| Harness | /api/harness/metrics, /traces, /eval, /health |
| Eval | /api/eval/dimensions, /report, /run |
| Points | /api/points/account, /transactions, /rules, /earn, /mall, /redeem, /redemptions, /ranking(/recompute) |
| AI Image | /api/ai-image/jobs（CRUD+process/status/batch/apply-preset）, /presets |
| Identity | /api/identity/submit, /status, /pending |
| Surveys | /api/surveys（CRUD+apply/device-check）, /ar/sessions, /ar/device-capability |

## 三、api.dart 新增方法清单（与后端路由对齐）

| 方法 | 端点 |
|------|------|
| b2bCreateDelivery / b2bListDeliveries / b2bGetDelivery / b2bUpdateDeliveryStatus | /api/b2b/delivery(/{id}(/status)) |
| sketchAnalyze / sketchGenerate3D / sketchSupportedFormats | /api/sketch-to-3d/{analyze,generate-3d,supported-formats} |
| exportStructuralIFCFile / exportDesignIFCFile | /api/bim/export/structural/{projectId}, /api/bim/export/design/{planId} |

## 四、未同步变更与合并判断

### 4.1 未同步变更清单（完整功能单元）

| 类别 | 文件 | 状态 |
|------|------|------|
| API 封装 | api-client.ts / api.dart | M（未提交） |
| 类型定义 | console-src/src/types/domain.ts（+843） | M |
| 路由注册 | App.tsx（+26）/ SideNav.tsx（25±） | M |
| 新页面 | console 12 页 / flutter 3 页 | untracked |
| 页面入口 | flutter project_detail_page.dart（+59） | M |

### 4.2 是否需要手动合并？

- **api-client.ts / api.dart 本身**：**无需手动合并**——工作区对 HEAD 的纯增量修改，无他人并发提交冲突（`git status` 无 conflict marker；远程 main 由本会话独占推进）
- **但禁止单独提交**：新页面文件引用 api-client/api.dart 的新方法，且 App.tsx/SideNav 引用新页面组件；若只提交 API 层，其余未提交文件将引用缺失 → 编译失败。**必须作为完整功能单元一次性提交**（15 新页 + 4 基础设施修改）

### 4.3 提交建议

```bash
# 一次性提交完整功能单元（前端缺口补齐）
git add console-src/src flutter_app/lib flutter_app/test/pages/console-src 前端相关
# 提交后验证：console npm run build + flutter analyze + 全量 pytest
```

## 五、路由/端点与后端同步性结论

- api-client.ts 30+ 端点、api.dart 9 方法，路径与 `app/api/` 实际路由逐项核对一致（含 A2A/MCP/Harness 子路径、points/ai-image CRUD 子路径、b2b/sketch/bim 路径）
- 无过期端点、无错误前缀（api.dart 相对路径经 baseUrl 拼接为 /api/*，与后端一致）
- 结论：**同步性 ✅，可直接提交（需与页面文件整体提交）**

## 六、P1 QA 本地执行结果（2026-08-09 实测）

### 6.1 Flutter 3 新页自动化测试：**6/6 全部通过** ✅

`bash scripts/run-frontend-qa.sh flutter`（--concurrency=1 串行）：

| 用例 | 结果 |
|------|------|
| b2b_delivery T1 成功态 / T2 503 降级 / T4 时区格式化 | 3/3 ✅ |
| sketch_to_3d T1 支持格式 / T2 视觉未开启降级 | 2/2 ✅ |
| ifc_export T1 页面渲染 | 1/1 ✅ |

本轮修复（b2b 测试 flaky 根因）：
- **根因**：非 mock/路由问题（T2/T4 同机制通过、请求 URL 与 mock 均正确），而是**测试视口高度不足**——创建表单占满默认 600px 视口，交付单卡片在懒加载 ListView 折叠线以下不被构建 → `find.textContaining('朝阳丽景')` 找不到
- **修复**：`useTallViewport()`（`tester.view.physicalSize = Size(800, 2000)` + `addTearDown(tester.view.reset)`）；T4 断言强化为 `findsWidgets` + `findsNothing('T08:00')`（验证 raw ISO 已格式化）
- `--concurrency=1` 串行保留（规避多 isolate 竞争）

### 6.2 Console Playwright（12 页路由 + 2 降级用例）：**环境阻塞，未执行浏览器级**

- 失败原因：Playwright chromium 浏览器二进制未安装，`npx playwright install` 需 ~700MiB 峰值空间，本地磁盘 Data 卷仅剩 167MiB（ENOSPC），用户跳过缓存清理
- **替代验证（全部通过）**：
  - `npm run build`：131 模块编译通过（tsc --noEmit + vite build）
  - `vite preview` + curl：12 个路由 `/console/{path}` 全部 HTTP 200（SPA fallback 正常）
  - bundle 内容：12 个新页面组件唯一文案（"✅ 批准" / "🚀 创建任务" / "📱 创建会话" / "🔗 套用预设" 等）全部命中
- **结论**：console 路由可达性在 HTTP 层与产物层已验证；浏览器渲染级断言（`main/#root` 可见性）需磁盘空间恢复后补跑 `bash scripts/run-frontend-qa.sh console` 或 CI 环境执行（github actions 有浏览器缓存）

## 七、结论汇总

| 检查项 | 结果 |
|--------|------|
| api-client.ts / api.dart 变更完整性 | ✅ 含全部最新修复与路由定义（30+ 端点 / 9 方法） |
| 与后端路由同步性 | ✅ 逐项核对一致 |
| 是否需手动合并 | ❌ 无需（纯增量，无冲突）；**但须与 15 新页 + App/SideNav/domain 整体提交** |
| Flutter 新页自动化测试 | ✅ 6/6 通过 |
| Console Playwright | ⚠️ 浏览器级受磁盘空间阻塞；HTTP 层 + 构建产物层验证通过 |

---

*报告基于 `git diff` 与后端路由实核，未提交文件状态以 `git status` 为准。*
