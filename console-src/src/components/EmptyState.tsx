/**
 * EmptyState — 对齐 ai_chat_page.dart:1752-1844 空状态
 *
 * 欢迎图标 + 标题 + 副标题 + hint + 快捷输入按钮 + 分割线
 */

import type { ReactNode } from 'react';

export interface EmptyStateSuggestion {
  emoji: string;
  text: string;
  onClick?: () => void;
}

export interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  subtitle?: string;
  hints?: string[];
  suggestions?: EmptyStateSuggestion[];
  footer?: ReactNode;
  testId?: string;
}

export default function EmptyState({
  icon = '🏠',
  title,
  subtitle,
  hints = [],
  suggestions = [],
  footer,
  testId,
}: EmptyStateProps) {
  return (
    <div className="wb-empty" data-testid={testId ?? 'wb-empty'}>
      <div className="wb-empty__inner">
        <div className="wb-empty__icon">{icon}</div>
        <div className="wb-empty__title">{title}</div>
        {subtitle && <div className="wb-empty__subtitle">{subtitle}</div>}
        {hints.map((h, i) => (
          <div key={i} className="wb-empty__hint">{h}</div>
        ))}
        {suggestions.length > 0 && (
          <div style={{ marginTop: 24 }}>
            {suggestions.map((s, i) => (
              <button
                key={i}
                type="button"
                className="wb-empty__suggestion"
                onClick={s.onClick}
                data-testid={`wb-empty-suggestion--${i}`}
              >
                {s.emoji}  {s.text}
              </button>
            ))}
          </div>
        )}
        {footer && <div className="wb-empty__divider">{footer}</div>}
      </div>
    </div>
  );
}
