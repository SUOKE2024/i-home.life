/**
 * SuokeButton — 对齐 Flutter ElevatedButton/OutlinedButton/TextButton
 *
 * primary / outline / text 三变体，对齐 Material 按钮规范
 */

import type { ReactNode } from 'react';

export type ButtonVariant = 'primary' | 'outline' | 'text' | 'danger';

export interface SuokeButtonProps {
  children: ReactNode;
  variant?: ButtonVariant;
  onClick?: () => void;
  disabled?: boolean;
  fullWidth?: boolean;
  size?: 'sm' | 'md' | 'lg';
  type?: 'button' | 'submit' | 'reset';
  testId?: string;
}

const SIZE_HEIGHT: Record<string, number> = { sm: 32, md: 40, lg: 48 };
const SIZE_FONT: Record<string, string> = { sm: 'var(--font-size-sm)', md: 'var(--font-size-md)', lg: 'var(--font-size-lg)' };

export default function SuokeButton({
  children,
  variant = 'primary',
  onClick,
  disabled,
  fullWidth,
  size = 'md',
  type = 'button',
  testId,
}: SuokeButtonProps) {
  const base: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    height: SIZE_HEIGHT[size],
    padding: '0 20px',
    borderRadius: 'var(--radius-input)',
    fontFamily: 'inherit',
    fontSize: SIZE_FONT[size],
    fontWeight: 600,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.4 : 1,
    transition: 'opacity 0.15s, background 0.15s, border-color 0.15s',
    width: fullWidth ? '100%' : undefined,
    border: 'none',
  };

  const styles: Record<ButtonVariant, React.CSSProperties> = {
    primary: { background: 'var(--accent)', color: 'var(--on-accent)' },
    outline: { background: 'transparent', color: 'var(--text-primary)', border: '1px solid var(--border-active)' },
    text: { background: 'transparent', color: 'var(--accent)', padding: '0 8px' },
    danger: { background: 'var(--danger)', color: '#fff' },
  };

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      data-testid={testId}
      style={{ ...base, ...styles[variant] }}
    >
      {children}
    </button>
  );
}
