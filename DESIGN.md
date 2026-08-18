---
version: "alpha"
name: Suoke
description: "索克家居（Suoke Home）AI 智能装修平台统一视觉身份 —— 深色工程台美学、单一暗金强调色，跨 WebApp / 管理控制台 / Flutter 多端（iOS/Android/HarmonyOS）"
colors:
  primary: "#C9973B"
  accent-bright: "#E0AA4A"
  on-accent: "#08080F"
  accent-text: "#8A6415" # 浅色底金色文字/链接/星标加深变体（AA 4.99:1，浅色主题专用）
  bg-deep: "#08080F"
  surface1: "#12121D"
  surface2: "#1A1A2A"
  surface3: "#222238"
  text-primary: "#E8E6E1"
  text-secondary: "#8A8894"
  text-muted: "#807E8D"
  success: "#4A9E6E"
  warning: "#C97A3B"
  danger: "#C94A4A"
  info: "#5A7EC9"
  bubble-user: "#2A2218"
  bubble-agent: "#1A1A2A"
  input-bg: "#0D0D18"
  agent-master: "#C9973B"
  agent-design: "#5A7EC9"
  agent-budget: "#4A9E6E"
  agent-procurement: "#C97A3B"
  agent-construction: "#C94A4A"
  agent-quality: "#4AC9A3"
  agent-settlement: "#9B6AC9"
  agent-support: "#6A9BC9"
  # ── C 端业主体验浅色暖底（Consumer，取自 tokens.css [data-theme='light'] / Flutter SuokeTheme.light()）──
  canvas-warm: "#F8F7F4"
  surface-warm: "#FFFFFF"
  surface-warm-2: "#F0EEE8"
  ink-warm: "#1A1814"
  ink-sub-warm: "#6B6760"
  ink-muted-warm: "#706C66"
  feature-peach: "#F5EFE0"
typography:
  h1:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif"
    fontSize: 24px
    fontWeight: 700
  h2:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif"
    fontSize: 18px
    fontWeight: 700
  body-lg:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif"
    fontSize: 16px
    fontWeight: 400
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif"
    fontSize: 13px
    fontWeight: 400
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif"
    fontSize: 12px
    fontWeight: 600
  caption:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif"
    fontSize: 10px
    fontWeight: 400
  stat-value:
    fontFamily: "'SF Mono', 'JetBrains Mono', Menlo, Consolas, monospace"
    fontSize: 22px
    fontWeight: 700
  mono:
    fontFamily: "'SF Mono', 'JetBrains Mono', Menlo, Consolas, monospace"
    fontSize: 12px
    fontWeight: 400
rounded:
  input: 8px
  sm: 10px
  md: 12px
  lg: 16px
  pill: 20px
  xl: 24px
spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-accent}"
    rounded: "{rounded.input}"
    height: 40px
    typography: "{typography.label}"
  button-primary-hover:
    backgroundColor: "{colors.accent-bright}"
    textColor: "{colors.on-accent}"
  button-outline:
    textColor: "{colors.text-primary}"
    rounded: "{rounded.input}"
    height: 40px
  button-text:
    textColor: "{colors.primary}"
  button-danger:
    backgroundColor: "{colors.danger}"
    textColor: "#FFFFFF"
    rounded: "{rounded.input}"
    height: 40px
  card:
    backgroundColor: "{colors.surface1}"
    rounded: "{rounded.md}"
  card-hover:
    backgroundColor: "{colors.surface2}"
  modal:
    backgroundColor: "{colors.surface3}"
    rounded: "{rounded.lg}"
  input:
    backgroundColor: "{colors.input-bg}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.input}"
  chip:
    backgroundColor: "{colors.bg-deep}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.pill}"
  badge-neutral:
    backgroundColor: "{colors.surface2}"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.pill}"
  badge-success:
    textColor: "{colors.success}"
  badge-warning:
    textColor: "{colors.warning}"
  badge-danger:
    textColor: "{colors.danger}"
  badge-info:
    textColor: "{colors.info}"
  muted-text:
    textColor: "{colors.text-muted}"
  accent-text:
    textColor: "{colors.accent-text}"
    typography: "{typography.label}"
  bubble-user:
    backgroundColor: "{colors.bubble-user}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.md}"
  bubble-agent:
    backgroundColor: "{colors.bubble-agent}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.md}"
  stat-value:
    typography: "{typography.stat-value}"
    textColor: "{colors.text-primary}"
  agent-avatar-master:
    backgroundColor: "{colors.agent-master}"
  agent-avatar-design:
    backgroundColor: "{colors.agent-design}"
  agent-avatar-budget:
    backgroundColor: "{colors.agent-budget}"
  agent-avatar-procurement:
    backgroundColor: "{colors.agent-procurement}"
  agent-avatar-construction:
    backgroundColor: "{colors.agent-construction}"
  agent-avatar-quality:
    backgroundColor: "{colors.agent-quality}"
  agent-avatar-settlement:
    backgroundColor: "{colors.agent-settlement}"
  agent-avatar-support:
    backgroundColor: "{colors.agent-support}"
  # ── C 端业主体验（Consumer）：浅色暖底消费风，值取自 tokens.css [data-theme='light'] 与 Flutter SuokeTheme.light() ──
  consumer-hero:
    backgroundColor: "{colors.canvas-warm}"
    textColor: "{colors.ink-warm}"
    rounded: "{rounded.lg}"
  consumer-card:
    backgroundColor: "{colors.surface-warm}"
    textColor: "{colors.ink-warm}"
    rounded: "{rounded.lg}"
  consumer-card-hover:
    backgroundColor: "{colors.surface-warm-2}"
  consumer-feature-card:
    backgroundColor: "{colors.feature-peach}"
    textColor: "{colors.ink-warm}"
    rounded: "{rounded.lg}"
  consumer-button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-accent}"
    rounded: "{rounded.input}"
    height: 48px
    typography: "{typography.label}"
  consumer-search-pill:
    backgroundColor: "{colors.surface-warm}"
    textColor: "{colors.ink-warm}"
    rounded: "{rounded.pill}"
    height: 48px
  consumer-badge:
    backgroundColor: "{colors.surface-warm-2}"
    textColor: "{colors.ink-sub-warm}"
    rounded: "{rounded.pill}"
  consumer-muted-text:
    textColor: "{colors.ink-muted-warm}"
---

## 概览

索克家居（Suoke Home）是 AI 智能装修平台，采用**双端双身份**视觉体系：

- **B 端（工长/设计师/控制台）= 深色工程台（dark engineering workbench）**：深墨画布、单一暗金强调色、高对比中性文字。整体传达专业、克制、工具感 —— 像高端家装施工现场的数字化工程仪表，而不是消费级娱乐产品。
- **C 端（业主 WebApp / 业主移动端）= 暖色家居消费体验（warm consumer）**：米白暖底画布 + 品牌暗金单强调 + 效果图/实景摄影驱动 + 柔和圆润形状。借鉴 Airbnb「单强调色纪律 + 摄影驱动」与 Notion「pastel 特性卡片 + 8px 按钮/12px 卡片几何」，**只借模式不借色板**——主色永远是索克暗金 `colors.primary`（#C9973B）。

共性规则：**金色是唯一的交互驱动色**，`colors.primary` 只出现在可点击/聚焦/选中态，绝不铺成大面积背景；Token 即规范（YAML front matter 是唯一规范值来源），所有端（Flutter `suoke_theme.dart` / 控制台 `tokens.ts`+`tokens.css` / WebApp `tokens.css`）必须对齐。

## 配色

### 品牌（暗金，唯一交互色）

- **primary (#C9973B)**：品牌暗金。主 CTA、链接、选中态、进度指示。金色底上必须用 `on-accent`（#08080F）深墨文字（对比 7.56:1，达 WCAG AA）；**禁止白字**（仅 2.64:1，不达 AA）。
- **accent-bright (#E0AA4A)**：hover/按压的提亮端点，用于金色渐变与发光（rgba(201,151,59,0.15)）。
- **on-accent (#08080F)**：金色底上的前景文字色，跨主题恒定。

### 表面层级（4 级，暗色）

| Token | 色值 | 用途 |
|---|---|---|
| bg-deep | #08080F | 页面画布（最深） |
| surface1 | #12121D | 卡片、面板 |
| surface2 | #1A1A2A | 悬浮、升阶面板、头部 |
| surface3 | #222238 | 弹层、对话框、Popover |

边框用半透明白发丝线（rgba(255,255,255,0.08) 常规 / 0.16 强化、激活态 #2A2A45），不依赖实心边框。

### 文字层级（WCAG AA 为硬门槛）

- **text-primary (#E8E6E1)**：标题与正文核心文字。
- **text-secondary (#8A8894)**：说明、元数据、占位（surface1 上 5.42:1，达 AA）。
- **text-muted (#807E8D)**：弱文字（surface1 上 4.63:1，达 AA）。**#6B6978 是历史遗留非 AA 值，禁止用于新 UI**。

### 语义色

success #4A9E6E / warning #C97A3B / danger #C94A4A / info #5A7EC9，配 14% 透明度低饱和底（如 rgba(74,201,163,0.14)）做徽章/状态。气泡：用户 #2A2218、Agent #1A1A2A；输入框底 #0D0D18。

### C 端浅色暖底（Consumer，业主端默认）

C 端业主端默认浅色暖底（区别于 B 端默认深色），启用 tokens.css `[data-theme='light']` / Flutter `SuokeTheme.light()`：

| Token | 色值 | 用途 |
|---|---|---|
| canvas-warm | #F8F7F4 | 页面暖米画布（比纯白柔和，Airbnb 式留白） |
| surface-warm | #FFFFFF | 卡片/弹层 |
| surface-warm-2 | #F0EEE8 | 悬浮、胶囊底、徽章底 |
| ink-warm | #1A1814 | 主文字（接近墨色，非纯黑） |
| ink-sub-warm | #6B6760 | 次文字/说明 |
| ink-muted-warm | #706C66 | 弱文字（达 WCAG AA，4.79:1） |
| border-warm | #E8E5DE | 发丝边框（正文值，不入 YAML） |
| feature-peach | #F5EFE0 | 暖米特性卡底（pastel，借鉴 Notion 特性卡） |

**品牌/语义/Agent 色跨主题恒定**：C 端浅色只替换表面与文字，主色仍是暗金 `colors.primary`（#C9973B）——这正是 Airbnb「单强调色纪律」：浅色页面上金色时刻稀缺（主 CTA、链接、评分星标），其余用墨色中性层级。星级/评分用暗金而非黄色（对齐 Airbnb 用 ink 而非黄的「星级克制」哲学，但换成品牌金色）。

**浅色底的金色文字需用深金变体**：`#C9973B` 在米白底上仅 2.45:1（不达 AA，金色天生为深底设计）；浅色下的金色**文字/链接/星标**改用深金 `#8A6415`（AA 4.99:1，对齐 Airbnb 将 `primary` 加深为 `primary-active` 的同类处理）。金色**按钮底**仍用 `#C9973B` + 深墨字（7.56:1，跨主题恒定）。

### Agent 身份色

8 个执行型 Agent 各有身份色，用于头像/标识/消息强调，**不用于大面积背景**：master 金 #C9973B、design 蓝 #5A7EC9、budget 绿 #4A9E6E、procurement 橙 #C97A3B、construction 红 #C94A4A、quality 青 #4AC9A3、settlement 紫 #9B6AC9、support 蓝灰 #6A9BC9。

## 排版

- **无衬线系统栈**：`-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif` —— 中文优先（PingFang SC / 苹方），不引入 Web 字体，保证跨端（iOS/Android/HarmonyOS）一致与零加载成本。
- **等宽栈**：`'SF Mono', 'JetBrains Mono', Menlo, Consolas, monospace` —— 数字、ID、代码、金额一律等宽 + `tabular-nums`，避免滚动时跳动。
- 字号档位：**h1 24px/700**、**h2 18px/700**（对齐 Flutter `titleLarge`）、body-lg 16、**body 13px（主力正文）**、label 12px/600（按钮/标签/导航）、caption 10px（元数据）、stat-value 22px/700 等宽（仪表盘大数字）。
- 行高：正文 1.5–1.6；标题 1.2–1.3。

## 布局

- **8pt 基线**：间距档位 xs 4 / sm 8 / md 12 / lg 16 / xl 24（对齐 Flutter `SuokeDesignTokens` spacing）。
- 骨架：侧边导航 232px、顶栏 60px、卡片内边距 18px、内容最大宽度约 1200px 居中。
- **触摸目标（WCAG 2.2 硬约束）**：可交互元素 ≥44×44px，最小 48×48px；移动端图标按钮不得小于此值。
- 响应式：移动端优先垂直堆叠；窄屏收起侧边导航为底部导航（Flutter `NavigationBar` 高 64px）。

## 层级与深度

- **半透明表面**营造质感：头部/输入栏 rgba(18,18,29,0.85)、卡片 0.95 alpha、空状态建议 0.6。
- **发丝边框优先**（见配色），层级主要由表面亮度差表达，阴影仅作辅助。
- 阴影三档：sm（0 1px 2px rgba(0,0,0,0.2)）、base（0 2px 8px rgba(0,0,0,0.3) + 0 8px 24px rgba(0,0,0,0.4)）、lg（0 4px 12px rgba(0,0,0,0.4) + 0 16px 48px rgba(0,0,0,0.6)）；仅浮层使用。
- 动效语言：时长 120ms（微反馈）/ 200ms（标准）/ 320ms（强调与大位移），**均 <320ms**；缓动对齐 Material 3（standard / emphasized-decelerate / decelerated-leave）；按压反馈用 scale(0.97)。`prefers-reduced-motion` 时必须降级（见 Do's）。

## 形状

- 圆角档位：**input 8px**（输入框、主按钮）、sm 10px、**md 12px（卡片主圆角）**、lg 16px（大卡片/对话框）、xl 24px（弹层）、pill 20px（chip/徽章）。
- 风格偏**方正（工具感）**：仅 chip/badge 使用胶囊；按钮/卡片用 8–12px 小圆角。
- 注意：控制台旧版主按钮曾用胶囊 20px，属历史不一致；新 UI 一律走 `rounded.input`（对齐 Flutter `ElevatedButton` 与 WebApp `.btn`）。

### C 端柔和圆润（Consumer）

C 端业主端形状语言比 B 端**更圆润、更友好**（借鉴 Airbnb「无硬角」哲学）：卡片主圆角从 B 端 12px 提到 `rounded.lg`（16px），主 CTA/输入保持 `rounded.input`（8px），搜索/筛选条用 `rounded.pill`（20px）胶囊；图标按钮与搜索球为圆形。圆角收敛为 8 / 16 / 20 三档，避免堆砌。

## 组件

- **按钮**：`button-primary` 金色底 + 深墨字（唯一主 CTA）；hover 提亮 `accent-bright`；`button-outline` 描边 + 主文字；`button-text` 金色文字链接；`button-danger` 危险操作（白字 #FFFFFF 对比 4.47:1，接近 AA，作为已知可接受项）。高度 40px（控制台 md），文字 label 12/600，按压 scale(0.97)，禁用 opacity 0.4–0.5。
- **卡片**：surface1 + 1px 发丝边框 + 12px 圆角；hover 升 surface2。
- **弹层/对话框**：surface3 + 16–24px 圆角。
- **输入框**：input-bg + 8px 圆角 + 发丝边框，focus 金色边框。
- **chip/徽章**：胶囊圆角；中性徽章 surface2 + 次文字，语义徽章用语义色文字 + 14% 低饱和底（不透明度 0.14）。
- **对话气泡**：用户 bubble-user / Agent bubble-agent，12px 圆角。
- **统计数字**：等宽 22px/700，`tabular-nums`。
- **Agent 头像**：8 个执行型 Agent 用身份色做头像底（对齐 `agentColor()` 映射）。

### C 端组件（Consumer，业主端）

- **consumer-hero**：浅色 hero 通栏，效果图/实景大图驱动（借鉴 Airbnb 摄影驱动——视觉重量靠图，标题克制不用超大字号），圆角 `rounded.lg`，可内嵌平台工作台预览（借鉴 Notion hero mockup）。
- **consumer-card**：白卡 + 发丝边框 `border-warm` + 16px 圆角；hover 升 `surface-warm-2`。图优先：效果图/案例图裁 16px 圆角（借鉴 Airbnb property-card 图优先结构）。
- **consumer-feature-card**：暖米 pastel 底（`feature-peach`），用于服务模块展示（设计/施工/质检/结算），借鉴 Notion 特性卡。
- **consumer-button-primary**：金色底 + 深墨字，高度 48px（触摸友好，对齐 Airbnb 48px CTA）。
- **consumer-search-pill**：白色胶囊搜索条，高度 48px，圆角 `rounded.pill`（借鉴 Airbnb 全局胶囊搜索）。
- **consumer-badge**：`surface-warm-2` 底 + `ink-sub-warm` 字，胶囊徽章。
- **consumer-muted-text**：弱文字 `ink-muted-warm`（达 AA）。

## 该做的与不该做的

### Do

- 新 UI 一律引用本文件 token（组件引用 `{colors.*}` / `{typography.*}` / `{rounded.*}`），**禁止硬编码色值/字号**。
- 主 CTA 用金色 + `on-accent` 深墨字；金色上放白字视为缺陷。
- 文字层级必须达 WCAG AA（≥4.5:1）；弱文字用 `text-muted`，勿回退到历史非 AA 值 #6B6978。
- 数字/金额/ID 用等宽 + `tabular-nums`。
- 动效 ≤320ms，并实现 `prefers-reduced-motion` 降级（时长 →0.001ms）。
- 可交互元素 ≥44×44px。
- 新组件先从既有组件派生（按钮→card→input→badge 家族），保持同构。
- 改任何 token 必须**三端同步**：`flutter_app/lib/theme/suoke_theme.dart` + `console-src/src/tokens/tokens.{ts,css}` + `webapp/src/styles/tokens.css`，并用 `npx @google/design.md lint DESIGN.md` 复验。
- 浅色主题仅覆盖 surface/text/border/shadow，品牌色与语义色恒定。
- C 端业主端默认浅色暖底（`canvas-warm`），用 `consumer-*` 组件族；效果图/实景图是视觉主力，标题克制。

### Don't

- 不引入 Tailwind 默认 palette / Inter 字体 / indigo 蓝色系 —— 本系统视觉身份是深墨+暗金，不是 AI 模板味。
- 不把紫色、青色等语义色当主色使用；金色是唯一交互驱动色。
- 不在金色底上放白字（2.64:1 不达 AA）。
- 不为装饰添加 >320ms 的动画；不忽略 `prefers-reduced-motion`。
- 不新增页面移除 Dashboard 底部 ICP 备案号「滇ICP备2026015233号-2」及其 `https://beian.miit.gov.cn/` 链接（硬约束，见 CLAUDE.md）。
- 不单端改 token 造成三端漂移（曾发生控制台 textMuted 未同步 AA 升级）。
- 不把弹窗当页面、不用悬浮阴影堆层级 —— 层级靠表面亮度差。
- 不照抄 Airbnb 珊瑚红 #ff385c / Notion 紫 #5645d4 作为 C 端强调色 —— C 端唯一交互色仍是暗金 `colors.primary`。
- C 端画布不用纯白 #FFFFFF（用 `canvas-warm` 暖米）；星级/评分不用黄色（用品牌暗金，对齐 Airbnb「星级克制」哲学）。
- 不把 C 端做成深色工程台、不把 B 端做成浅色消费风 —— 双端双身份各司其职，跨端混用视为缺陷。
