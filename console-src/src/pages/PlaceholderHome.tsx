import { useEffect, useState } from 'react';
import { tokens } from '../tokens/tokens';
import { apiClient } from '../services/api-client';

/**
 * 批次 1 验证页 — 渲染令牌色板 + feature flag 读取
 * 批次 2 替换为真实 WorkbenchPage（对齐 AIChatPage）
 *
 * 验证点：
 *   1. textMuted 色块为 #6B6978
 *   2. radius-md 演示块圆角 12px
 *   3. console_v2_enabled flag 值正确读取（需后端运行 + 已登录）
 */
export default function PlaceholderHome() {
  const [flags, setFlags] = useState<Record<string, unknown> | null>(null);
  const [flagError, setFlagError] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .getFeatureFlags()
      .then((f) => {
        if (f) setFlags(f);
        else setFlagError('flag unavailable（未登录或后端未运行）');
      })
      .catch((e) => setFlagError(e instanceof Error ? e.message : String(e)));
  }, []);

  const swatches: Array<{ name: string; value: string }> = [
    { name: 'bgDeep', value: tokens.bgDeep },
    { name: 'surface1', value: tokens.surface1 },
    { name: 'surface2', value: tokens.surface2 },
    { name: 'accent', value: tokens.accent },
    { name: 'textPrimary', value: tokens.textPrimary },
    { name: 'textSecondary', value: tokens.textSecondary },
    { name: 'textMuted', value: tokens.textMuted },
  ];

  return (
    <div style={{ padding: '24px', maxWidth: '800px', margin: '0 auto' }}>
      <h1 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '8px' }}>
        索克家居 Web 控制台 v2
      </h1>
      <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginBottom: '24px' }}>
        批次 1 基建验证页 · UI/UX 对齐移动端
      </p>

      {/* 令牌色板 */}
      <section style={{ marginBottom: '32px' }}>
        <h2 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '12px', color: 'var(--accent)' }}>
          设计令牌色板
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '8px' }}>
          {swatches.map((s) => (
            <div
              key={s.name}
              data-testid={`token-swatch--${s.name}`}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px',
                background: 'var(--surface1)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border)',
              }}
            >
              <span
                style={{
                  width: '24px',
                  height: '24px',
                  borderRadius: '4px',
                  background: s.value,
                  border: '1px solid var(--border-active)',
                  flexShrink: 0,
                }}
              />
              <span style={{ fontSize: '12px', color: 'var(--text-primary)' }}>{s.name}</span>
              <span style={{ fontSize: '10px', color: 'var(--text-muted)', marginLeft: 'auto' }}>{s.value}</span>
            </div>
          ))}
        </div>
      </section>

      {/* 圆角演示 */}
      <section style={{ marginBottom: '32px' }}>
        <h2 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '12px', color: 'var(--accent)' }}>
          圆角令牌（radius-md=12px 对齐 Flutter radius=12.0）
        </h2>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <div
            data-testid="radius-demo--md"
            style={{
              width: '64px',
              height: '64px',
              background: 'var(--accent)',
              borderRadius: 'var(--radius-md)',
            }}
          />
          <div
            style={{
              width: '64px',
              height: '64px',
              background: 'var(--info)',
              borderRadius: 'var(--radius)',
            }}
          />
          <div
            style={{
              width: '64px',
              height: '64px',
              background: 'var(--success)',
              borderRadius: 'var(--radius-lg)',
            }}
          />
        </div>
      </section>

      {/* Feature flag */}
      <section>
        <h2 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '12px', color: 'var(--accent)' }}>
          Feature Flag
        </h2>
        <div
          style={{
            padding: '12px',
            background: 'var(--surface1)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border)',
          }}
        >
          {flags ? (
            <div data-testid="flag-loaded">
              <div style={{ fontSize: '13px', marginBottom: '4px' }}>
                <strong style={{ color: 'var(--text-primary)' }}>console_v2_enabled:</strong>{' '}
                <span style={{ color: flags.console_v2_enabled ? 'var(--success)' : 'var(--warning)' }}>
                  {String(flags.console_v2_enabled)}
                </span>
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                共 {Object.keys(flags).length} 个 flag 已加载
              </div>
            </div>
          ) : flagError ? (
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }} data-testid="flag-error">
              {flagError}
            </div>
          ) : (
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>加载中…</div>
          )}
        </div>
      </section>
    </div>
  );
}
