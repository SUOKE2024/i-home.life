/**
 * SuokeCard — 对齐 Flutter CardTheme（半透明 + border + radius 12）
 *
 * 通用卡片容器，对齐 suoke_theme.dart CardTheme: surface + border + radius=12.0
 */

import type { CSSProperties, ReactNode } from 'react';

export interface SuokeCardProps {
  children: ReactNode;
  padding?: number | string;
  onClick?: () => void;
  style?: CSSProperties;
  interactive?: boolean;
  testId?: string;
}

export default function SuokeCard({
  children,
  padding = 16,
  onClick,
  style,
  interactive,
  testId,
}: SuokeCardProps) {
  return (
    <div
      data-testid={testId}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
      style={{
        background: 'var(--surface1)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
        padding: typeof padding === 'number' ? `${padding}px` : padding,
        cursor: interactive || onClick ? 'pointer' : 'default',
        transition: 'border-color 0.15s, background 0.15s',
        ...(interactive
          ? { ':hover': { borderColor: 'var(--border-active)', background: 'var(--surface2)' } }
          : {}),
        ...style,
      }}
    >
      {children}
    </div>
  );
}
