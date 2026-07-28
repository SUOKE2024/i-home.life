/**
 * FormRow — 对齐 Flutter InputDecoration（inputBg + radiusInput 8）
 *
 * label + input（或自定义 children）的表单行
 */

import type { ReactNode } from 'react';

export interface FormRowProps {
  label?: string;
  children: ReactNode;
  hint?: string;
  error?: string;
  testId?: string;
}

export default function FormRow({ label, children, hint, error, testId }: FormRowProps) {
  return (
    <div data-testid={testId} style={{ marginBottom: 12 }}>
      {label && (
        <label
          style={{
            display: 'block',
            fontSize: 'var(--font-size-sm)',
            color: 'var(--text-secondary)',
            marginBottom: 6,
          }}
        >
          {label}
        </label>
      )}
      {children}
      {hint && !error && (
        <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 4 }}>{hint}</div>
      )}
      {error && (
        <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--danger)', marginTop: 4 }}>{error}</div>
      )}
    </div>
  );
}

/** 受控输入框（FormRow 配套） */
export function SuokeInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  const { style, ...rest } = props;
  return (
    <input
      {...rest}
      style={{
        width: '100%',
        height: 40,
        padding: '0 12px',
        background: 'var(--input-bg)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-input)',
        color: 'var(--text-primary)',
        fontSize: 'var(--font-size-md)',
        fontFamily: 'inherit',
        outline: 'none',
        ...style,
      }}
    />
  );
}
