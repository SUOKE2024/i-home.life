# 前端 P1 修复 QA — 自动化测试用例草稿（v1.11.0 → 下一轮）

> 生成日期：2026-08-09 · 对象：console-src 12 新页 + flutter_app 3 新页（共 15 页）
> 依据：`docs/reports/frontend-fix-iteration-tasks-20260809.md` 阶段 P1
> 说明：用户口径「19 页」= 15 个新页面 + 4 个基础设施修改文件（App.tsx / SideNav.tsx / api-client.ts / domain.ts / api.dart / project_detail_page.dart）
> 技术栈：console → Playwright（`console-src/tests/visual/`，`test:visual`）；Flutter → flutter_test + `MockHttpOverrides` + `setupTestEnv()` + `createTestApp()`（`flutter_app/test/pages/` 惯例）

---

## 一、测试范围

### 1.1 console-src 新页（12 页，Playwright）

| 页面 | 文件 | 关键后端端点 | 门控 flag |
|------|------|-------------|----------|
| AgentIdentity | AgentIdentityPage.tsx | /api/agents/identity | agent_identity_enabled |
| AgentApprovals | AgentApprovalsPage.tsx | /api/agents/approvals | agent_approval_enabled |
| AgentSkills | AgentSkillsPage.tsx | /api/agents/skills | agent_skills_enabled |
| AgentMemory | AgentMemoryPage.tsx | /api/agents/memory | agent_memory_enabled |
| A2A | A2APage.tsx | /api/a2a | a2a_enabled |
| MCP | MCPPage.tsx | /api/mcp | mcp_enabled |
| Harness | HarnessPage.tsx | /api/harness | harness_enabled |
| Eval | EvalPage.tsx | /api/eval | eval_enabled |
| Points | PointsPage.tsx | /api/points | — |
| AIImage | AIImagePage.tsx | /api/ai-image | ai_image_enabled |
| Identity | IdentityPage.tsx | /api/identity | — |
| Surveys | SurveysPage.tsx | /api/surveys + /api/ar-scan | — |

### 1.2 Flutter 新页（3 页，flutter_test）

| 页面 | 文件 | 后端端点 | 门控 |
|------|------|---------|------|
| 装企交付 | b2b_delivery_page.dart | /api/b2b/delivery | — |
| 草图转 3D | sketch_to_3d_page.dart | /api/sketch-to-3d | ai_image_enabled |
| IFC 导出 | ifc_export_page.dart | /api/ifc/export | ifc_enabled |

> 门控列表以 `console-src/src/services/api-client.ts` / `flutter_app/lib/services/api.dart` 实际实现为准（提交前复核）。

---

## 二、测试策略（5 类 QA）

| 类别 | 断言要点 | 工具 |
|------|---------|------|
| T1 页面三态 | 加载态（loading）→ 成功态（数据渲染）→ 空态/错误态（诚实提示） | 双端 |
| T2 flag 门控降级 | flag 关闭时页面显示「功能未启用」降级，不报错、不伪装数据 | 双端 |
| T3 越权 403 | 无权限访问时提示「无权限」，不泄漏数据 | 双端 |
| T4 时区展示 | 时间字段统一 `+08:00`（对齐后端 `_BJ_TZ` 约定） | 双端 |
| T5 API 契约 | 页面调用端点与后端 schema 字段一致（api-client/domain 类型对齐） | console 类型测试 |

---

## 三、console Playwright 用例草稿

### 3.1 通用 fixture（草稿）

```typescript
// console-src/tests/visual/p1-qa.spec.ts
import { test, expect } from '@playwright/test';

// 通过 query 或路由参数控制 flag 门控（按各页实际实现）
const PAGES = [
  { path: '/agents/identity', name: 'AgentIdentity' },
  { path: '/agents/approvals', name: 'AgentApprovals' },
  { path: '/agents/skills', name: 'AgentSkills' },
  { path: '/agents/memory', name: 'AgentMemory' },
  { path: '/a2a', name: 'A2A' },
  { path: '/mcp', name: 'MCP' },
  { path: '/harness', name: 'Harness' },
  { path: '/eval', name: 'Eval' },
  { path: '/points', name: 'Points' },
  { path: '/ai-image', name: 'AIImage' },
  { path: '/identity', name: 'Identity' },
  { path: '/surveys', name: 'Surveys' },
];
```

### 3.2 用例矩阵（12 页 × 5 类 = 60 条骨架）

| 用例 ID | 页面 | 类别 | 步骤要点 | 断言 |
|---------|------|------|---------|------|
| C-P1-T1 | 全部 12 页 | T1 | 打开页面 → 观察三态 | 加载后最终渲染数据或空态文案，无未捕获异常 |
| C-P1-T2 | 全部 12 页 | T2 | 以 flag 关闭状态打开 | 显示「功能未启用/降级」文案，页面 200 非 500 |
| C-P1-T3 | AgentApprovals / AgentSkills / AgentMemory | T3 | 无权限 token 访问 | 显示无权限提示，不渲染敏感数据 |
| C-P1-T4 | Points / Surveys / AgentIdentity | T4 | 断言时间字段 | 时间文本含 `+08:00` |
| C-P1-T5 | 全部 12 页 | T5 | 对比 api-client 调用参数 | 请求 URL/字段与后端 schema 一致（结合类型编译） |

### 3.3 示例用例（草稿，以 PointsPage T1/T2 为例）

```typescript
test('PointsPage 成功态渲染积分账户', async ({ page }) => {
  await page.route('**/api/points/account', route =>
    route.fulfill({ json: { balance: 1280, level: 'gold', total_earned: 5200 } }));
  await page.goto('/points');
  await expect(page.getByText('1280')).toBeVisible();
  await expect(page.getByText(/gold|金/)).toBeVisible();
});

test('PointsPage flag 关闭时诚实降级', async ({ page }) => {
  await page.route('**/api/points/account', route =>
    route.fulfill({ status: 503, json: { detail: 'points disabled' } }));
  await page.goto('/points');
  await expect(page.getByText(/未启用|降级|不可用/)).toBeVisible();
});
```

---

## 四、Flutter 测试用例草稿

### 4.1 通用骨架（3 页 × 5 类 = 15 条骨架）

```dart
// flutter_app/test/pages/b2b_delivery_page_test.dart
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:ihome_app/pages/b2b_delivery_page.dart';
import '../test_helper.dart';
import '../mock_http.dart';

void main() {
  setUp(() => setupTestEnv());
  tearDown(() => HttpOverrides.global = null);

  testWidgets('T1 成功态 - 加载交付单列表', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      '/api/b2b/delivery': {'code': 0, 'data': [{'id': 'd1', 'status': 'draft', 'created_at': '2026-08-09T08:00:00+08:00'}]},
    });
    await tester.pumpWidget(createTestApp(const B2BDeliveryPage()));
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('d1'), findsOneWidget);
  });

  testWidgets('T2 降级态 - 接口 503 诚实提示', (tester) async {
    HttpOverrides.global = MockHttpOverrides.error('/api/b2b/delivery', 503);
    await tester.pumpWidget(createTestApp(const B2BDeliveryPage()));
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.textContaining('不可用'), findsOneWidget); // 按实际降级文案调整
  });

  testWidgets('T4 时区 - 时间显示 +08:00', (tester) async {
    // 断言列表时间格式化后含 +08:00 或北京时间（按页面实现）
  });
}
```

### 4.2 各页核心用例（草稿）

| 页面 | T1 成功 | T2 降级 | T3 越权 | T4 时区 | T5 契约 |
|------|---------|---------|---------|---------|---------|
| b2b_delivery | 列表渲染 | 503 提示 | 401/403 提示 | created_at +08:00 | api.dart 参数对齐 |
| sketch_to_3d | 上传+任务列表 | flag 关闭降级 | 403 | 任务时间 +08:00 | multipart 字段对齐 |
| ifc_export | 导出任务+下载 | flag 关闭降级 | 403 | 导出时间 +08:00 | 导出端点参数对齐 |

---

## 五、执行与验收

| 项 | 说明 |
|----|------|
| console 执行 | `cd console-src && npm run test:visual`（新增 spec 到 `tests/visual/`） |
| flutter 执行 | `cd flutter_app && flutter test test/pages/{b2b_delivery,sketch_to_3d,ifc_export}_page_test.dart` |
| 全量回归 | `pytest`（后端 2046 不回退）+ console build + flutter analyze |
| 验收标准 | 15 页 × 5 类骨架全部落地；T1/T2 为必过项；T3-T5 允许标注「待后端 flag 就绪」skip |

## 六、待确认项

- [ ] 各页实际 flag 名与降级文案（提交后以 api-client.ts / api.dart 为准）
- [ ] console 路由 path（/agents/identity 等）以 SideNav.tsx/App.tsx 实际注册为准
- [ ] 「19 页」口径确认：若含 4 个基础设施文件，建议补 4 条「路由可达」用例（App.tsx/SideNav.tsx）

---

*草稿性质：给出骨架与代表用例，完整实现随 P1 阶段执行。*
