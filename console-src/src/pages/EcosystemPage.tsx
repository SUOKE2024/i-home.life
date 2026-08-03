/**
 * EcosystemPage — 生态桥接优先级（F46, v1.5.0）
 *
 * 结构：Scaffold > AppBar(生态桥接) > 只读状态报告（生态表格 + 诚实降级提示条）+ 优先级策略说明
 * API（对齐 app/api/ecosystem.py）：
 *   GET /api/ecosystem/status   生态桥接状态报告（含配置检测与诚实降级标注）
 *   GET /api/ecosystem/bridges  生态桥接优先级列表
 *
 * 诚实降级：未配置真实 API key 的生态，实际设备联动端点保持 501，不伪装能力。
 */

import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { EcosystemBridgeStatus, EcosystemBridges } from '../types/domain';

type ChipTone = 'muted' | 'info' | 'success' | 'warning' | 'danger' | 'accent';

export default function EcosystemPage() {
  const navigate = useNavigate();

  const { data: status, loading, error, reload } = useAsync<EcosystemBridgeStatus | null>(
    async () => {
      const r = await apiClient.getEcosystemStatus<EcosystemBridgeStatus>();
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [],
  );

  const { data: bridges, error: bridgesError } = useAsync<EcosystemBridges | null>(
    async () => {
      const r = await apiClient.getEcosystemBridges<EcosystemBridges>();
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载优先级失败');
      return r.data;
    },
    [],
  );

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-ecosystem-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">🔗 生态桥接</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {loading && (
            <div className="wb-state" data-testid="wb-ecosystem-loading">
              <div className="wb-state__icon">⏳</div><div>加载生态桥接状态中…</div>
            </div>
          )}
          {error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-ecosystem-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>重试</button>
            </div>
          )}

          {!loading && !error && status && (
            <div data-testid="wb-ecosystem-content">
              {/* honest_note 提示条 */}
              <div className="wb-create-form" style={{ borderColor: 'rgba(201, 122, 59, 0.45)' }} data-testid="wb-ecosystem-honest-note">
                <div className="wb-create-form__head">
                  <div className="wb-create-form__badge">🤝</div>
                  <div>
                    <div className="wb-create-form__title">诚实降级说明</div>
                    <div className="wb-create-form__subtitle">{status.honest_note}</div>
                  </div>
                </div>
                <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)' }}>
                  状态更新于 {new Date(status.updated_at).toLocaleString('zh-CN')}
                </div>
              </div>

              {/* 生态表格 */}
              <div className="wb-section-label" style={{ marginTop: 20 }}>生态桥接状态</div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--font-size-sm)', background: 'var(--surface1)', borderRadius: 'var(--radius)', overflow: 'hidden' }} data-testid="wb-ecosystem-table">
                <thead>
                  <tr style={{ textAlign: 'left', color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}>
                    <th style={{ padding: '10px 12px' }}>优先级</th>
                    <th style={{ padding: '10px 12px' }}>生态</th>
                    <th style={{ padding: '10px 12px' }}>Key</th>
                    <th style={{ padding: '10px 12px' }}>状态</th>
                    <th style={{ padding: '10px 12px' }}>说明</th>
                  </tr>
                </thead>
                <tbody>
                  {status.bridges.map((bridge) => {
                    const tone: ChipTone = bridge.configured ? 'success' : 'warning';
                    return (
                      <tr key={bridge.key} style={{ borderBottom: '1px solid var(--border)' }} data-testid={`wb-ecosystem-bridge--${bridge.key}`}>
                        <td style={{ padding: '10px 12px' }}>P{bridge.priority}</td>
                        <td style={{ padding: '10px 12px', fontWeight: 600 }}>{bridge.name}</td>
                        <td style={{ padding: '10px 12px', color: 'var(--text-muted)' }}>{bridge.key}</td>
                        <td style={{ padding: '10px 12px' }}>
                          <span className={`wb-status-chip wb-status-chip--${tone}`}>
                            {bridge.configured ? '已配置' : '待配置'}
                          </span>
                        </td>
                        <td style={{ padding: '10px 12px', color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>
                          {bridge.configured ? '已就绪' : `需要 API Key（${bridge.required_env_keys.join(' / ') || 'stub'}）`}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              {/* 优先级策略说明 */}
              {bridges && !bridgesError && (
                <div className="wb-smart-card" style={{ marginTop: 16 }} data-testid="wb-ecosystem-strategy">
                  <div className="wb-smart-card__head">
                    <div className="wb-smart-card__room">优先级策略</div>
                  </div>
                  <div className="wb-smart-card__meta">
                    <span>📌 {bridges.priority_strategy}</span>
                  </div>
                  <div className="wb-smart-card__meta" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 2, marginTop: 8 }}>
                    {bridges.bridges.map((b) => (
                      <span key={b.key}>
                        <strong>P{b.priority} {b.name}</strong>（{b.bridge}）
                        {b.required_env_keys.length > 0 ? ` · 需环境变量 ${b.required_env_keys.join(' / ')}` : ' · 当前桥接为 stub'}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
