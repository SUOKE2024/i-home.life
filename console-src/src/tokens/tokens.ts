/**
 * 索克家居统一设计令牌契约 — Web 控制台 v2
 *
 * 与 flutter_app/lib/theme/suoke_theme.dart 的 SuokeDesignTokens 一一对应。
 * 令牌变更必须同步：本文件 + tokens.css + workbench.css :root + suoke_theme.dart
 * 由 CI 校验脚本 scripts/check-token-sync.ts 保证一致（批次 6 引入）。
 *
 * 圆角命名映射裁决（批次 2 固化，不再变动）：
 *   本表 radiusMd=12  ↔ Flutter SuokeDesignTokens.radius=12.0 (suoke_theme.dart:84)  — 卡片主圆角，高频值
 *   本表 radius=16    ↔ Flutter SuokeDesignTokens.radiusLg=16.0 (suoke_theme.dart:86) — 大卡片/对话框
 *   Flutter 的 radiusMd=14.0 (suoke_theme.dart:85) 在本表无对应（命名错位，历史遗留，勿对齐）
 *   本表 radiusPill=20 ↔ Flutter radiusPill=20.0 — 胶囊圆角
 */
export const tokens = {
  // ── Surface hierarchy (4 levels，对齐 suoke_theme.dart:13-21) ──
  bgDeep: '#08080F',
  surface0: '#08080F',
  surface1: '#12121D',
  surface2: '#1A1A2A',
  surface3: '#222238',
  cardBg: '#12121D',
  cardBgHover: '#1A1A2A',
  border: '#1E1E32',
  borderActive: '#2A2A45',

  // ── Text（对齐 suoke_theme.dart:37-43，textMuted 已 WCAG AA 升级）──
  textPrimary: '#E8E6E1',
  textSecondary: '#8A8894',
  textMuted: '#6B6978',

  // ── Brand（对齐 suoke_theme.dart:46-52）──
  accent: '#C9973B',
  accentBright: '#E0AA4A',
  accentGlow: 'rgba(201, 151, 59, 0.15)',

  // ── Status（对齐 suoke_theme.dart:55-70）──
  success: '#4A9E6E',
  warning: '#C97A3B',
  danger: '#C94A4A',
  info: '#5A7EC9',
  purple: '#9B6AC9',
  teal: '#4AC9A3',

  // ── 气泡/输入（对齐 suoke_theme.dart:73-79）──
  bubbleUser: '#2A2218',
  bubbleAgent: '#1A1A2A',
  inputBg: '#0D0D18',

  // ── 圆角（对齐 suoke_theme.dart:83-89）──
  // 裁决（批次 2 固化）：radiusMd=12 对齐 Flutter radius=12.0(line84，卡片主圆角)
  //                    radius=16 对齐 Flutter radiusLg=16.0(line86，大卡片/对话框)
  // Flutter radiusMd=14.0(line85) 历史遗留命名错位，本表不对应
  radiusSm: 10,
  radiusMd: 12,
  radius: 16,
  radiusLg: 24,
  radiusPill: 20,
  radiusInput: 8,

  // ── 间距（对齐 suoke_theme.dart:93-97）──
  spacingXs: 4,
  spacingSm: 8,
  spacingMd: 12,
  spacingLg: 16,
  spacingXl: 24,

  // ── WCAG 2.2 触摸目标（对齐 suoke_theme.dart:101-104）──
  touchTargetMin: 48,
  touchTargetAa: 44,

  // ── 字体大小（对齐 suoke_theme.dart:108-111）──
  fontSizeXs: 10,
  fontSizeSm: 12,
  fontSizeMd: 13,
  fontSizeLg: 16,

  // ── Agent 颜色（对齐 suoke_theme.dart:115-122）──
  agentMaster: '#C9973B',
  agentDesign: '#5A7EC9',
  agentBudget: '#4A9E6E',
  agentProcurement: '#C97A3B',
  agentConstruction: '#C94A4A',
  agentQuality: '#4AC9A3',
  agentSettlement: '#9B6AC9',
  agentSupport: '#6A9BC9',
} as const;

export type Tokens = typeof tokens;

/** 根据 agent key 获取颜色（对齐 suoke_theme.dart:125-137） */
export function agentColor(key: string): string {
  const map: Record<string, string> = {
    master: tokens.agentMaster,
    design: tokens.agentDesign,
    budget: tokens.agentBudget,
    procurement: tokens.agentProcurement,
    construction: tokens.agentConstruction,
    quality: tokens.agentQuality,
    settlement: tokens.agentSettlement,
    support: tokens.agentSupport,
  };
  return map[key] ?? tokens.agentMaster;
}
