# Web 端 UI/UX 布局对齐移动端 — 设计文档

> 日期：2026-07-28
> 状态：待审阅
> 范围：Web 控制台（`web/`）UI/UX 布局全面对齐 Flutter 移动端（`flutter_app/`），并引入 Playwright 自动化视觉回归验证

---

## 1. 背景与现状

### 1.1 移动端架构
- **单入口架构**：`main.dart` → `AuthGate` → `HomePage`，而 `HomePage`（[home_page.dart:40-48](file:///Users/netsong/Developer/i-home.life/flutter_app/lib/pages/home_page.dart#L40-L48)）直接承载 `AIChatPage`（AI 群聊工作台），**无底部 Tab、无抽屉导航**。
- 44 个业务页通过对话流中 Agent 卡片 / 路由跳转进入。
- 主题 `suoke_theme.dart` 已主动对齐 Web `workbench.css` 暗色主题（见文件头注释），令牌层 90% 一致。

### 1.2 Web 端架构
- `web/` 是**混合目录**：
  - `index.html` + `main.dart.js` + `flutter.js`：Flutter Web 应用入口（不动）。
  - 18 个 a2ui 纯静态 `.html` 控制台页（`workbench.html`/`admin.html`/`settings.html`/…），经 `main.py` 自定义路由 + 缓存中间件服务（[main.py:237-258](file:///Users/netsong/Developer/i-home.life/app/main.py#L237-L258)）。
- `workbench.html`（[行 218-445](file:///Users/netsong/Developer/i-home.life/web/workbench.html#L218-L445)）已是**移动端单列聊天布局**（`chat-header` → `message-list` → `chat-input-bar`），与 `AIChatPage` 同构。
- `settings.html` 也是移动端单列卡片式。
- `admin.html` 却是**桌面三栏布局**（侧边栏+顶栏+内容），与移动端风格不一致——典型待改造页。
- **无任何公共布局复用机制**：每个 HTML 完全独立、各自重复 HTML，无 include / JS 渲染公共布局。

### 1.3 已识别的令牌偏差
| 令牌 | Web (`workbench.css`) | Flutter (`suoke_theme.dart`) | 处置 |
|---|---|---|---|
| `textMuted` | `#5a5866` | `#6B6978`（WCAG AA 升级） | Web 升至 `#6B6978` |
| 主圆角 | `--radius: 16px` | `radius: 12.0` | 新增 `--radius-md: 12px` 对齐，`--radius: 16px` 保留为大卡片 |
| agent 色 / surface / 间距 / 字体 | — | — | 已一致，写入契约 |

### 1.4 页面映射盘点
- Web 18 页中 **13 页有 Flutter 对应**（workbench/login/settings/project-detail/materials/timeline/quality-report/crew/change-orders/vr/ar/points/structure）。
- Web 独有 5 页：`admin`/`3d-viewer`/`studio`/`our-story`/`demo`（品牌/演示/管理，保留并响应式化）。
- Flutter 独有约 **28 页** Web 暂无（见 §7 清单）——本次全量补建。

---

## 2. 目标与范围

### 2.1 目标
1. **视觉令牌对齐**：两端颜色/圆角/字体/卡片样式完全一致，单一契约源。
2. **工作台主界面对齐**：`workbench.html` ↔ `AIChatPage` 的 header/消息流/输入区/Agent 选择/语音面板布局一致。
3. **Web 窄屏移动适配**：窄屏（≤768px）呈现移动端式单列布局。
4. **全量功能页布局对齐**：13 对已有页 + 28 页补建，逐一布局对齐移动端。
5. **自动化视觉回归**：Playwright 截图对比，每个页面 ×2 断点。

### 2.2 范围
- **前端架构**：Vite + React 18 + TypeScript + React Router v6 + Zustand + CSS Modules（令牌用 CSS 变量，延续 `workbench.css :root` 模式）。
- **后端**：仅 `app/config.py` 加 `console_v2_enabled` feature flag + `app/api/config.py` 暴露到 `/config/feature-flags`；`main.py` 不改（静态服务由 Nginx）；无业务 API 变更。
- **不动**：Flutter Web（`web/index.html` + `main.dart.js`）、Flutter 移动端代码、后端 API。
- **遵循硬约束**：保持阿里云 FC 函数计算架构（不引入 K8s/Helm/Docker）；PASETO 不变。

### 2.3 非目标
- 不改 Flutter 移动端 UI（移动端是"对齐基准"）。
- 不重构后端 API。
- 不替换 Flutter Web 入口。

---

## 3. 架构设计

### 3.1 目录结构
```
i-home.life/
├── console-src/                    # 新增：Vite + React 控制台源码
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── playwright.config.ts
│   ├── index.html                  # Vite 入口（构建产物输出到 web/console/index.html）
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx                 # 路由根
│   │   ├── tokens/
│   │   │   ├── tokens.ts           # 令牌契约（与 suoke_theme.dart 一一对应）
│   │   │   └── tokens.css          # :root CSS 变量（对齐 workbench.css）
│   │   ├── components/             # 组件库（见 §5）
│   │   ├── layouts/
│   │   │   ├── SuokeLayout.tsx     # 响应式外壳（窄屏底部Tab/宽屏侧栏）
│   │   │   └── AuthGate.tsx        # 鉴权门（对齐 Flutter AuthGate）
│   │   ├── pages/                  # 40+ 页面（见 §6/§7）
│   │   ├── stores/                 # Zustand stores
│   │   ├── services/               # api-client.ts（迁移自 web/assets/js/api-client.js）
│   │   └── styles/
│   └── tests/visual/               # Playwright 视觉回归
│       ├── *.spec.ts
│       └── snapshots/
├── web/                            # FC 静态托管目录（不变）
│   ├── index.html                  # Flutter Web 入口（不动）
│   ├── main.dart.js                # Flutter Web（不动）
│   ├── console/                    # 新增：Vite 构建产物输出目录
│   │   ├── index.html
│   │   └── assets/
│   ├── workbench.html              # 现有静态页（保留，feature flag 切换）
│   └── ...                         # 其余 17 静态页保留
├── app/main.py                     # 不改（静态服务由 Nginx；flag 在 config.py）
└── flutter_app/                    # 不动
```

### 3.2 部署与路由
- Vite 构建命令 `npm run build` 输出到 `web/console/`（`vite.config.ts` 的 `build.outDir`）。
- **静态服务由 Nginx**（非 main.py）：`web/` 现有 18 静态页由 Nginx 直接服务（`scripts/nginx-ihome.conf` `root /opt/ihome/web`），`main.py` 当前无 StaticFiles mount（v1.2.3 移除后未恢复）。`/console/*` 同理由 Nginx 服务——在 nginx.conf 两个 server 块加 `location /console/ { try_files $uri $uri/ /console/index.html; }`。`main.py` 不增加任何静态路由。
- **新旧控制台共存**：`workbench.html` 等旧页保留；`console_v2_enabled` flag 控制 `/console` 入口是否暴露/重定向。
- 入口策略：flag 开启时，`/` 仍为 Flutter Web；控制台入口为 `/console`（窄屏底部 Tab 首页 = workbench）。flag 关闭时回退旧静态页。

### 3.3 技术栈选型理由
- **React + TS**：用户指定；生态成熟，类型安全。
- **React Router v6**：40+ 页面路由。
- **Zustand**：轻量状态管理（会话/项目上下文/主题），对齐 Flutter Provider 模式。
- **CSS Modules + CSS 变量**：延续 `workbench.css :root` 令牌模式，迁移成本低，不引入 Tailwind 等额外依赖。
- **Playwright**：跨浏览器视觉回归，支持多断点截图。

---

## 4. 设计令牌对齐契约

### 4.1 契约源
`console-src/src/tokens/tokens.ts` 与 `flutter_app/lib/theme/suoke_theme.dart` 的 `SuokeDesignTokens` 一一对应。令牌变更必须同步两端 + `workbench.css :root`，由 CI 校验脚本 `scripts/check-token-sync.ts` 保证一致。

### 4.2 令牌表（对齐后最终值）
```ts
// console-src/src/tokens/tokens.ts
export const tokens = {
  // Surface hierarchy (4 levels)
  bgDeep:    '#08080F',  surface0: '#08080F',
  surface1:  '#12121D',  surface2: '#1A1A2A',  surface3: '#222238',
  cardBg:    '#12121D',  cardBgHover: '#1A1A2A',
  border:    '#1E1E32',  borderActive: '#2A2A45',
  // Text
  textPrimary:   '#E8E6E1',
  textSecondary: '#8A8894',
  textMuted:     '#6B6978',   // ← Web 由 #5a5866 升级，对齐 Flutter WCAG AA
  // Brand
  accent: '#C9973B',  accentBright: '#E0AA4A',  accentGlow: 'rgba(201,151,59,0.15)',
  // Status
  success: '#4A9E6E', warning: '#C97A3B', danger: '#C94A4A', info: '#5A7EC9',
  purple: '#9B6AC9',  teal: '#4AC9A3',
  // Radii (对齐后)
  // 注意：radiusMd=12 对齐 Flutter SuokeDesignTokens.radius=12.0 (suoke_theme.dart:84)
  //       非 Flutter radiusMd=14.0 (suoke_theme.dart:85)；命名错位待批次 2 统一
  radiusSm: 10, radiusMd: 12, radius: 16, radiusLg: 24, radiusPill: 20, radiusInput: 8,
  // Spacing
  spacingXs: 4, spacingSm: 8, spacingMd: 12, spacingLg: 16, spacingXl: 24,
  // Font sizes
  fontSizeXs: 10, fontSizeSm: 12, fontSizeMd: 13, fontSizeLg: 16,
  // Touch target (WCAG 2.2)
  touchTargetMin: 48, touchTargetAa: 44,
  // Agent colors
  agentMaster: '#C9973B', agentDesign: '#5A7EC9', agentBudget: '#4A9E6E',
  agentProcurement: '#C97A3B', agentConstruction: '#C94A4A', agentQuality: '#4AC9A3',
  agentSettlement: '#9B6AC9', agentSupport: '#6A9BC9',
} as const;
```

### 4.3 改动点
- `web/assets/css/workbench.css`：`--text-muted: #5a5866` → `#6b6978`；新增 `--radius-md: 12px`。
- `flutter_app/lib/theme/suoke_theme.dart`：注释更新（无值变更，已是目标值）。
- 新建 `tokens.css`：`:root` 变量与上表一致，供旧静态页与新 React 控制台共用。

---

## 5. 组件库设计

每个组件标注对齐的移动端元素。组件位于 `console-src/src/components/`。

### 5.1 布局类
| 组件 | Props | 对齐移动端 |
|---|---|---|
| `SuokeLayout` | `children`, `navItems` | Scaffold + 响应式导航（窄屏 BottomNav / 宽屏 Drawer） |
| `AuthGate` | `children` | `AuthGate`（main.dart:107）— 401 重定向 login |
| `PageHeader` | `title`, `onBack?`, `actions?` | AppBar（半透明 + 返回 + 标题） |
| `BottomNav` | `items`, `active` | NavigationBar（suoke_theme navigationBarTheme） |
| `SideNav` | `items`, `active` | 宽屏侧边栏（桌面增强，无移动端对应） |

### 5.2 工作台类（对齐 `AIChatPage` / `workbench.html`）
| 组件 | Props | 对齐移动端 |
|---|---|---|
| `ChatHeader` | `title`, `subtitle`, `avatarSrc`, `onAvatarClick` | `chat-header`（workbench.html:228）+ AppBar |
| `MessageList` | `messages` | `message-list`（workbench.html:257）+ ListView |
| `MessageBubble` | `role`, `agent`, `content`, `time` | `msg` / `msg-bubble` |
| `MessageCard` | `cardType`, `data`, `onAction` | `msg-card`（workbench.html:2931）+ `chat_message_card.dart` |
| `ChatInputBar` | `onSend`, `onAttach`, `onVoice`, `onVoiceTasks` | `chat-input-bar`（workbench.html:433）|
| `AgentSelector` | `selected`, `onSelect` | 9 agent 色（agentColor）|
| `VoiceTaskPanel` | `tasks`, `onCancel` | `voice_task_panel.dart` |
| `TypingIndicator` | `agent` | `typing-indicator`（workbench.html:1642）|

### 5.3 通用类（对齐移动端 CardTheme / ThemeData）
| 组件 | 对齐移动端 |
|---|---|
| `SuokeCard` | CardTheme（半透明 + 边框 + radius 12） |
| `ListItem` | ListTile 等价 |
| `FormRow` | InputDecoration（inputBg + radiusInput 8） |
| `EmptyState` | 空状态占位 |
| `Badge` / `Chip` | ChipTheme（radiusPill 20） |
| `SuokeButton`（primary/outline/text） | ElevatedButton/OutlinedButton/TextButton |
| `LoadingSkeleton` | `loading_skeleton.dart` |

---

## 6. 导航架构与路由表

### 6.1 响应式导航
- **窄屏（≤768px）**：底部 Tab 4 项——`工作台`(`/workbench`)/`项目`(`/projects`)/`任务`(`/tasks`)/`我的`(`/me`)。对齐移动端 NavigationBar（`suoke_theme.dart:281`）。
- **宽屏（>1024px）**：左侧 `SideNav`，含全量页面分组（设计/预算/采购/施工/质检/结算/智能家居）。
- **769–1024px**：侧栏可折叠。
- `workbench` 为首页，对齐移动端 `HomePage = AIChatPage`。

### 6.2 路由表（40+ 路由）
**底部 Tab 主路由**：
- `/workbench` — AI 群聊工作台（对齐 AIChatPage）
- `/projects` — 项目列表 / `/projects/:id` 项目详情（对齐 projects_page / project_detail_page）
- `/tasks` — 任务（对齐 tasks_page）
- `/me` — 设置/账户（对齐 settings_page）

**设计组**：`/design/deepening`(设计深化) `/design/cad`(CAD) `/design/3d-viewer` `/design/vr`(VR全景) `/design/ar`(AR扫描/测量)

**预算/采购组**：`/budget`(预算) `/procurement`(采购) `/materials`(材料) `/takeoff`(算量) `/products`(产品)

**施工组**：`/construction`(施工) `/structural`(结构) `/mep`(水电) `/kitchen`(厨房) `/bathroom`(卫生间) `/kitchen-bath-mep`(厨卫水电) `/door-window-waterproof`(门窗防水) `/hard-decoration`(硬装) `/lighting`(照明)

**软装/家具组**：`/soft-furnishing`(软装) `/furniture-catalog`(家具目录) `/custom-furniture`(定制家具)

**质检/结算组**：`/quality-report`(质量报告) `/settlement`(结算) `/change-orders`(变更单) `/timeline`(时间线) `/points`(点位) `/crew`(人员) `/worker`(工人)

**智能家居组**：`/smart-home`(智能家居) `/appliance`(家电) `/scene-automation`(场景自动化) `/identity`(身份) `/ai-image`(AI图像)

**保留 Web 独有页**：`/admin`(管理后台，响应式化) `/studio`(工作室) `/our-story`(品牌) `/demo`(演示)

> 路由路径与 Flutter 路由名一一对应，建立映射表 `console-src/src/pages/route-map.ts` 作为契约。

---

## 7. 28 页补建清单（Flutter 独有 → Web 新建）

> 仅列 Web 暂无对应、需新建的页面。Web 已有的 13 页（workbench/login/settings/project-detail/materials/timeline/quality-report/crew/change-orders/vr/ar/points/structure）属"迁移"（§14 批次 4），不在此列。

| # | Flutter 页 | Web 路由 | 布局模式（对齐移动端） |
|---|---|---|---|
| 1 | dashboard_page | /dashboard | 卡片网格 + 指标 |
| 2 | projects_page | /projects | 列表 + 搜索 + FAB |
| 3 | budget_page | /budget | 表格 + 进度条 |
| 4 | tasks_page | /tasks | 看板/列表 + 状态流转 |
| 5 | construction_page | /construction | 时间线 + 卡片 |
| 6 | mep_page | /mep | 详情卡片组 |
| 7 | kitchen_page | /kitchen | 详情 + 清单 |
| 8 | bathroom_page | /bathroom | 详情 + 通风校验卡片 |
| 9 | kitchen_bath_mep_page | /kitchen-bath-mep | 详情卡片组 |
| 10 | door_window_waterproof_page | /door-window-waterproof | 详情 + 校验 |
| 11 | hard_decoration_page | /hard-decoration | 清单 + 卡片 |
| 12 | lighting_page | /lighting | 清单 + 卡片 |
| 13 | soft_furnishing_page | /soft-furnishing | 网格 + 卡片 |
| 14 | furniture_catalog_page | /furniture-catalog | 网格 + 详情 |
| 15 | custom_furniture_page | /custom-furniture | 表单 + 预览 |
| 16 | procurement_enhanced_page | /procurement | 表格 + 状态 |
| 17 | takeoff_page | /takeoff | 表格 + 汇总 |
| 18 | products_page | /products | 网格 + 详情 |
| 19 | settlement_page | /settlement | 表格 + 汇总 |
| 20 | worker_page | /worker | 列表 + 卡片 |
| 21 | smart_home_page | /smart-home | 设备网格 + 场景 |
| 22 | appliance_page | /appliance | 网格 + 详情 |
| 23 | scene_automation_page | /scene-automation | 场景列表 + 编辑 |
| 24 | identity_page | /identity | 表单 |
| 25 | ai_image_page | /ai-image | 生成 + 画廊 |
| 26 | design_deepening_page | /design/deepening | 详情 + 清单 |
| 27 | cad_page | /design/cad | 画布 + 工具栏 |
| 28 | chat_page | /chat | 列表 + 对话（需核验与 ai_chat 是否合并） |

> 实施时逐一 Read 对应 Flutter `_page.dart` 的 build 方法，抽取布局结构，用 §5 组件库复刻。每个页面交付时附映射核验记录（主代理亲 Read，吸取子代理误判教训）。
> 注：`vr_panorama_page`/`ar_scan_page`/`structural_page` 因 Web 已有 `vr-viewer.html`/`ar-measurement.html`/`structure.html`，归入批次 4 迁移增强，不在本补建清单。

---

## 8. 响应式策略

### 8.1 断点
| 断点 | 范围 | 布局 |
|---|---|---|
| `mobile` | ≤768px | 单列、底部 Tab、消息全宽、输入栏贴底 |
| `tablet` | 769–1024px | 可折叠侧栏、2 列卡片 |
| `desktop` | >1024px | 固定侧栏、3+ 列、工作台可双栏（消息流 + 右侧详情） |

### 8.2 实现方式
- `tokens.css` 定义断点变量：`--bp-mobile: 768px; --bp-tablet: 1024px;`。
- 组件用 CSS Modules `@media` 查询。
- `SuokeLayout` 内部按 `useMediaQuery` 切换 `BottomNav` / `SideNav`。
- 工作台窄屏单列（对齐移动端），宽屏可选双栏（消息流 + 右侧 Agent 详情/任务面板）——双栏为桌面增强，不破坏窄屏对齐。

### 8.3 触摸目标
所有可点击元素 ≥44×44px（WCAG 2.2 AA），对齐 `suoke_theme.dart:touchTargetAa`。

---

## 9. 自动化视觉回归

### 9.1 工具链
- `@playwright/test` + `playwright`。
- Vite 预览服务器：`npm run preview`（`playwright.config.ts` 的 `webServer` 启动）。
- 截图策略：`toHaveScreenshot()`，每个页面 ×2 断点（`mobile: 375x812` / `desktop: 1440x900`）。

### 9.2 测试结构
```
console-src/tests/visual/
├── workbench.spec.ts          # 工作台主界面（空状态/有消息/输入态/语音面板）
├── layout.spec.ts             # SuokeLayout 响应式（窄屏底部Tab/宽屏侧栏）
├── pages/                     # 每个页面一个 spec
│   ├── projects.spec.ts
│   ├── budget.spec.ts
│   └── ...
├── tokens.spec.ts             # 令牌渲染校验（textMuted/radius）
└── snapshots/                 # baseline 入库
```

### 9.3 执行
- 本地：`npm run test:visual`（更新 baseline：`npm run test:visual -- --update-snapshots`）。
- CI：PR 触发，对比 baseline，差异 > 阈值 fail。需 mock 登录态（复用现有 PASETO token 生成测试凭据）。
- 首次 baseline：实现完成后一次性生成，经人工确认后入库。

### 9.4 验证矩阵
| 场景 | 断点 | 基线 |
|---|---|---|
| 每个页面 | mobile + desktop | snapshot |
| 令牌渲染 | desktop | snapshot |
| 响应式切换 | 跨断点 | snapshot |
| 工作台交互态 | mobile | snapshot |

---

## 10. Feature Flag 与回滚

### 10.1 Flag
- `console_v2_enabled`（默认 `False`）：控制 `/console` 入口是否暴露、是否从旧静态页重定向。
- 加入 `project_memory.md` 的 flag 清单与 `config.py` / `.env.example`。
- 前端通过 `/api/feature-flags` 读取（复用现有 `feature_flags_service`）。

### 10.2 灰度策略
1. Flag 关：现状不变，旧 18 静态页服务。
2. Flag 开 + 内测：`/console` 可访问，旧页仍保留，逐页对比验证。
3. 全量：旧页导航重定向到 `/console/*`，旧 HTML 保留作回滚资产（不删）。

### 10.3 回滚
- 关 `console_v2_enabled` 即回退到旧静态页。
- `web/console/` 产物可独立删除/回滚版本（构建产物版本化）。
- 旧 `workbench.html` 等 18 页**保留不删**，确保回滚可用（吸取 v1.1.29 误删 web/ 的教训）。

---

## 11. 版本同步

- 所有 Web/JS/CSS 改动同步升级 `v=YYYYMMDDx` 与 `sw.js:CACHE_VERSION`（项目硬约束）。
- Vite 产物文件名带 hash（天然缓存失效），但 HTML 引用仍带 `v=` 参数控制。
- 本次基线版本：`v=20260728a`（当前 workbench.html 已用）→ 升级为 `v=20260728b`（首次改动）。
- `sw.js:CACHE_VERSION` 当前 7 → 8（sw.js 为自毁型，版本号按项目约定同步）。

---

## 12. 风险与缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| 工程量极大（Vite 项目 + 40+ 页 + 视觉回归），一次性交付风险高 | 高 | feature flag 灰度 + 旧页保留回滚 + 按 §14 顺序分批合入主干（交付可一次性，但合入有顺序） |
| React 控制台与 Flutter Web 共存于 `web/`，路由冲突 | 中 | React 控制台隔离在 `/console/*`，Flutter Web 保留 `/`；main.py 路由优先级明确 |
| 28 页补建逐一布局对齐，易遗漏移动端细节 | 中 | 每页交付附"Flutter build 方法 → React 组件"映射核验记录；主代理亲 Read 核验（吸取子代理误判教训） |
| Playwright 视觉回归在 FC 环境 CI 集成 | 中 | 视觉回归在本地/PR CI 跑，不依赖 FC 运行时；FC 只托管静态产物 |
| 令牌漂移（三处：tokens.ts / suoke_theme.dart / workbench.css） | 中 | CI 校验脚本 `check-token-sync.ts` + 单一契约源 |
| 旧 18 页与新 React 页并存期导航割裂 | 低 | flag 控制重定向；并存期旧页不受影响 |

---

## 13. 验证标准

1. **令牌对齐**：`check-token-sync.ts` 通过；`tokens.spec.ts` 截图匹配 baseline。
2. **工作台对齐**：`workbench.spec.ts` mobile 断点截图与移动端 AIChatPage 截图视觉一致（人工并排确认 + Playwright baseline）。
3. **响应式**：`layout.spec.ts` 三断点截图匹配；所有可点击元素 ≥44px。
4. **全量页**：40+ 页面均有 mobile + desktop baseline，Playwright 全绿。
5. **回滚**：关 `console_v2_enabled` 后，旧 18 静态页正常服务（回归测试）。
6. **版本同步**：`v=` 与 `sw.js:CACHE_VERSION` 已升级；`check-version-sync` 脚本通过。

---

## 14. 实施顺序（合入主干批次）

> 用户选择"一次性全改"，交付为一次切换；但为控制风险，主干合入按以下顺序分批 PR，每批可独立验证、独立回滚。

1. **批次 1 · 基建**：Vite + React 项目骨架、tokens 契约、`/console` 路由 + feature flag、Playwright 配置、令牌偏差修补（textMuted/radius）。
2. **批次 2 · 组件库 + 工作台**：§5 全组件 + `workbench` 页对齐 `AIChatPage` + 视觉回归 baseline。
3. **批次 3 · 响应式布局**：`SuokeLayout` + `BottomNav`/`SideNav` + 三断点。
4. **批次 4 · 13 对已有页迁移**：login/settings/projects/project-detail/materials/timeline/quality-report/crew/change-orders/vr/ar/points/structure。
5. **批次 5 · 28 页补建**：按 §7 清单，分设计/预算/施工/软装/质检/智能家居 6 组并行（Task subagent 并行化，主代理集成共享文件——遵循项目约定）。
6. **批次 6 · 视觉回归全量 + 灰度切换**：40+ 页 baseline 入库、CI 集成、flag 灰度开启、版本同步、回滚演练。

---

## 15. 开放问题（实施时确认）

1. React 控制台是否复用现有 `web/assets/js/api-client.js`（改写为 TS）还是重写？倾向：迁移为 TS `services/api-client.ts`，保持 PASETO 逻辑一致。
2. `admin.html` 管理后台是否纳入本次对齐（它是 Web 独有的桌面三栏页）？建议：响应式化但保留桌面主导航。
3. 28 页中 AR/VR/CAD 页（相机/全景/画布）在 Web 端的能力边界（Web 是否支持完整 AR？还是降级为查看器）？建议：AR 降级为图像识别上传，VR/CAD 保留查看/编辑能力。

---

## 附录 A · 关键文件引用
- 移动端主题：[flutter_app/lib/theme/suoke_theme.dart](file:///Users/netsong/Developer/i-home.life/flutter_app/lib/theme/suoke_theme.dart)
- 移动端入口：[flutter_app/lib/main.dart](file:///Users/netsong/Developer/i-home.life/flutter_app/lib/main.dart)
- 移动端工作台：[flutter_app/lib/pages/ai_chat_page.dart](file:///Users/netsong/Developer/i-home.life/flutter_app/lib/pages/ai_chat_page.dart)
- Web 工作台：[web/workbench.html](file:///Users/netsong/Developer/i-home.life/web/workbench.html)
- Web 令牌：[web/assets/css/workbench.css](file:///Users/netsong/Developer/i-home.life/web/assets/css/workbench.css)
- 静态服务中间件：[app/main.py:237-258](file:///Users/netsong/Developer/i-home.life/app/main.py#L237-L258)
