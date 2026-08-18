# 三端 UI/UX 布局合理性审计与修复报告（2026-08-18）

> 版本：v1.15.3 · 类型：设计系统规范审计 + 外科手术式修复 · 范围：webapp（19 路由）/
> console-src（72 页）/ flutter_app（57 页）· 基线：根目录 `DESIGN.md` token + WCAG 2.2 +
> 通用 UX 启发式。三端并行只读审计，P0 论断由主代理二次复验后修复；全程未改后端业务代码。

## 1. 审计结论摘要

- **总体**：设计系统根基扎实（DESIGN.md 双端双身份 / 8pt 基线 / WCAG AA 门槛 / 三端 token
  主色对齐），但「规范→token→组件→页面」四级链路在页面层大面积断裂。三端健康度：
  console（中上）> webapp（一般偏中下）> flutter（差，51% 页面为孤儿死代码）。
- **规律性缺陷**（三端同现）：
  1. **引用未定义 token + 硬回退**：webapp `--success/--danger/--primary`、console
     `--accent-contrast/--primary` 均未定义，实际渲染回退到白字或 Tailwind 默认色板
     （含 indigo #2563eb），触犯「禁止 Tailwind 色板」硬约束；
  2. **触摸目标 <44px** 三端全违反（webapp 32×32 图标按钮、console 约 8 族控件、
     flutter 30–36px）；
  3. **硬编码色值/字号泛滥**（webapp 249 处内联字号、console 38 处、flutter 222 处
     `Color(0x)` + 806 处直接字号）。
- **最严重单点**：Flutter `main.dart` 无路由表，57 页中 29 页（51%）零引用，项目/预算/
  施工/结算/CAD/MEP/VR/智能家居整条业务链不可达。

## 2. 修复清单（P0）

| # | 端 | 问题 | 修复 |
|---|----|------|------|
| 1 | Flutter | 导航骨架塌陷（无 routes/底部导航，29 孤儿页） | `main.dart` 新增 `onGenerateAppRoute` 注册 58 页；`home_page` 64px NavigationBar（首页/项目/AI 管家/我的）；ProjectDetail → 预算/施工/结算 `pushNamed` 打通 |
| 2 | WebApp | `--success/--danger/--primary` 未定义回退 Tailwind 色板 | `tokens.css` 补 4 token（success #4A9E6E / danger #C94A4A / primary=accent / card 双主题），全库危险回退 hex 清零 |
| 3 | WebApp | 金色徽章用黄非暗金（#b45309 / rgba(251,191,36)） | Showroom/VirtualTour/ARScan 全部 → `var(--accent-text)` 深金 #8A6415；DESIGN.md YAML 补 `accent-text` token 三端同步 |
| 4 | WebApp | DeviceCommandPanel：`var(--card)` 透明、`btn btn-primary` 错类名、`ghost` 死类 | `--card` 定义 + `btn--primary` + `btn--ghost` 修正 |
| 5 | Console | `.wb-btn` 金底白字（`--accent-contrast` 未定义回退 #fff，8+ 页） | `tokens.css` 补 `--accent-contrast: #08080f` + 按钮高度 32→40px |
| 6 | Console | `var(--primary)` 未定义致上传按钮透明（CAD/Sketch3D/IFC） | 补 `--primary: var(--accent)` + 前景改深墨字 |
| 7 | Flutter | `light()` 缺深金 #8A6415 / surface-warm-2 / 组件主题 → M3 紫回退；C 端卡片 12px | 补 5 常量 + textButton/chip/snackBar/divider/progress/errorBorder/textTheme 主题 + 卡片 16px + **双主题 ColorScheme 的 secondary/tertiary/onPrimary 系列收进金色系（此前 secondary/tertiary 为 M3 默认紫/青，light 缺 onPrimary）** |
| 8 | Flutter | 金底白字 FAB | `design_deepening_page` 图标 → `onAccent` |
| 9 | Flutter | 15 处 C 端页引用暗色 token | home_page 等 C 端页 → `surfaceWarm2` 等浅色 token |
| 10 | WebApp | `.icon-btn` 32×32 方角、`.btn` ≈36px | 44×44 圆形 + min-height 44/48px |

## 3. 修复清单（P1/P2 摘要）

- **WebApp**：8 张裸表格（7 页）加 `table-wrap`；`.kpi-row` 小屏单列断点；误导性
  `nav-caret` 元素与 CSS 移除；图标按钮补 `aria-label`；死类名 `ghost` ×7 → `btn--ghost`。
- **Console**：侧栏 220→232px；选中态 Agent 语义色 → 品牌金；**<1025px 窄屏新增汉堡
  顶栏（60px）+ 抽屉导航**（此前无导航替代）；`#6B6978` 遗留值清零；escrow 重复导航项
  删除；`SuokeCard` 内联 `:hover` 死代码删除；`SuokeButton` 胶囊 → 8px + 主按钮硬编码
  `#000` → `var(--on-accent)`；统计值类补 `tabular-nums`。
- **Flutter**：废弃旧色 `0xFF5A5866` ×12 → `textMuted`；Material 默认蓝/indigo ×8 →
  `info`；`statTextStyle`（tabular-nums）示范落地；触摸目标 34/30/36 → ≥44 热区。

## 4. 质量门禁结果

| 门禁 | 结果 |
|------|------|
| pytest 全量 | 2499 passed + 2 skipped + 4 xfailed（不回归） |
| pre-commit | 全绿（trailing/EOF/yaml/merge-conflict/private-key 等） |
| mypy | 374 文件 0 issue |
| `npx @google/design.md lint DESIGN.md` | 0 errors / 0 warnings |
| vite build（webapp + console tsc） | 通过 |
| flutter analyze | 0 issues（58 路由 + NavigationBar 验证） |

## 5. 遗留（有意不改，留待专项治理）

- webapp 内联字号 37 处非档位（10.5/11.5/12.5/13.5/15/17/26/32px）、圆角 20 处非 8/16/20；
- console 内容区 720px 双重限宽（900px constrained + 720px narrow）、侧栏 13 组无折叠；
- flutter 硬编码 `fontSize:` 928 处、`Color(0x)` 214 处（超出本次外科手术范围）；
- 角色驱动导航（前端按 role 过滤菜单，对齐 `DEFAULT_ROLE_PERMISSIONS`）未实施——当前为
  「登录后全量展示 + 后端 API 403 兜底」模式，属独立增强项。

## 6. 附：角色触达现状（审计附项）

主角色 5 种（homeowner/designer/contractor/supplier/admin）+ 子角色（8 工种 / curtain_designer）。
前端三端均为登录门控（AuthGate 只查 token），导航静态全量展示；后端 `app/rbac.py`
`require_admin`（23 端点/8 模块）+ `RolePermission` 权限码兜底。后端无按角色返回菜单的
接口，前端不消费 `DEFAULT_ROLE_PERMISSIONS`。
