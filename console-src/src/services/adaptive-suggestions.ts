/**
 * adaptive-suggestions — Workbench 上下文自适应建议（GenUI-lite）
 *
 * 2026 前沿：界面按上下文（时段）动态重排，而非静态常量。
 * 受 workbench_adaptive_suggestions_enabled flag 灰度；关闭则回退静态 SUGGESTIONS。
 *
 * 上下文信号（v1 简化版，仅时段）：
 *   - 早晨 05–11 优先：今日任务 / 设计方案
 *   - 下午 12–17 优先：施工进度 / 采购
 *   - 傍晚 18–22 优先：预算 / 厨房卫浴咨询
 *   - 深夜 23–04 优先：静心查看方案与预算（弱运营打扰）
 *
 * 后续可扩展：角色（业主/工长）、项目阶段、历史交互权重。
 */

export interface SuggestionSeed {
  emoji: string;
  text: string;
  agent: string;
}

export interface AdaptiveSuggestion extends SuggestionSeed {
  /** 选中理由（可选用作 a11y / tooltip） */
  reason?: string;
}

type Daypart = 'morning' | 'afternoon' | 'evening' | 'night';

export function daypartFor(date: Date = new Date()): Daypart {
  const h = date.getHours();
  if (h >= 5 && h < 12) return 'morning';
  if (h >= 12 && h < 18) return 'afternoon';
  if (h >= 18 && h < 23) return 'evening';
  return 'night';
}

const DAYPART_LABEL: Record<Daypart, string> = {
  morning: '早上好',
  afternoon: '下午好',
  evening: '晚上好',
  night: '夜深了',
};

/** 时段 → 建议文案优先级（匹配 seed.text 前缀，命中者前置） */
const DAYPART_PRIORITY: Record<Daypart, string[]> = {
  morning: ['查看', '我的设计', '今日'],
  afternoon: ['施工进度', '需要采购', '查看预算'],
  evening: ['查看预算', '厨房布局', '卫浴设计'],
  night: ['我的设计', '查看预算'],
};

/** 时段问候语（用于空状态副标题） */
export function greetingFor(date: Date = new Date()): string {
  return DAYPART_LABEL[daypartFor(date)];
}

/**
 * 按时段重排建议：命中期优先级关键词者前置，其余按原序追加。
 * 保持建议总数与去重，避免过滤气泡（2026 反模式：隐藏功能致采用率下降）。
 */
export function reorderSuggestions(
  seeds: SuggestionSeed[],
  date: Date = new Date(),
): AdaptiveSuggestion[] {
  const dp = daypartFor(date);
  const priority = DAYPART_PRIORITY[dp];
  const reason = `${DAYPART_LABEL[dp]}时段推荐`;

  const scored = seeds.map((s, idx) => {
    const hitIdx = priority.findIndex((kw) => s.text.includes(kw));
    return { seed: s, score: hitIdx === -1 ? 999 : hitIdx, idx };
  });

  scored.sort((a, b) => a.score - b.score || a.idx - b.idx);

  // 仅给前 2 条加 reason（避免噪音）
  return scored.map((s, i) =>
    i < 2 ? { ...s.seed, reason } : { ...s.seed },
  );
}
