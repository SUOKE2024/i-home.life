/**
 * ListItem — 对齐 Flutter ListTile
 *
 * leading + title + subtitle + trailing 横向布局
 */

import type { ReactNode } from 'react';

export interface ListItemProps {
  leading?: ReactNode;
  title: ReactNode;
  subtitle?: ReactNode;
  trailing?: ReactNode;
  onClick?: () => void;
  dense?: boolean;
  divider?: boolean;
  testId?: string;
}

export default function ListItem({
  leading,
  title,
  subtitle,
  trailing,
  onClick,
  dense,
  divider,
  testId,
}: ListItemProps) {
  return (
    <div
      data-testid={testId}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: dense ? '8px 16px' : '14px 16px',
        borderBottom: divider ? '1px solid var(--border)' : undefined,
        cursor: onClick ? 'pointer' : 'default',
        background: 'transparent',
      }}
    >
      {leading && <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center' }}>{leading}</div>}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 'var(--font-size-md)', color: 'var(--text-primary)' }}>{title}</div>
        {subtitle && (
          <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--text-secondary)', marginTop: 2 }}>
            {subtitle}
          </div>
        )}
      </div>
      {trailing && <div style={{ flexShrink: 0, color: 'var(--text-muted)' }}>{trailing}</div>}
    </div>
  );
}
