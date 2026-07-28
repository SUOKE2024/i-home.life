/**
 * Badge — 对齐 Flutter ChipTheme（radiusPill 20）
 *
 * 状态徽章，支持 variant 预设色 + 自定义 color
 */

import type { ReactNode } from 'react';

export type BadgeVariant = 'default' | 'accent' | 'success' | 'warning' | 'danger' | 'info';

const VARIANT_COLOR: Record<BadgeVariant, string> = {
  default: 'var(--text-muted)',
  accent: 'var(--accent)',
  success: 'var(--success)',
  warning: 'var(--warning)',
  danger: 'var(--danger)',
  info: 'var(--info)',
};

export interface BadgeProps {
  children: ReactNode;
  variant?: BadgeVariant;
  color?: string;
  testId?: string;
}

export default function Badge({ children, variant = 'default', color, testId }: BadgeProps) {
  const c = color ?? VARIANT_COLOR[variant];
  return (
    <span
      data-testid={testId}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '2px 10px',
        borderRadius: 'var(--radius-pill)',
        border: `1px solid ${c}`,
        color: c,
        fontSize: 'var(--font-size-xs)',
        lineHeight: 1.6,
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </span>
  );
}
