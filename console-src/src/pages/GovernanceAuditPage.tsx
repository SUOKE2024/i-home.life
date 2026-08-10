/**
 * GovernanceAuditPage — Agent 运行时治理安全审计（v1.12.x）
 *
 * 对齐 2026 OWASP Agentic Skills Top 10：将 AG1-AG10 风险类别逐项映射到
 * 平台既有控制（posture/审批/Model Spec/PII 掩码/会话加密/工具防投毒/SSRF 等），
 * 输出确定性 pass/warn/fail + 证据 + 整改建议（只读，无副作用）。
 *
 * API（对齐 app/api/admin.py）：
 *   GET /api/admin/agent-governance-audit  平台管理员可调，非管理员 403 诚实展示
 */

import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { GovernanceAuditResponse } from '../types/domain';

const STATUS_TONE: Record<string, string> = {
  pass: 'wb-status-chip--success',
  warn: 'wb-status-chip--warning',
  fail: 'wb-status-chip--danger',
};

export default function GovernanceAuditPage() {
  const navigate = useNavigate();

  const {
    data: audit,
    loading,
    error,
    reload,
  } = useAsync<GovernanceAuditResponse | null>(async () => {
    const r = await apiClient.getGovernanceAudit<GovernanceAuditResponse>();
    if (!r.isSuccess || !r.data) {
      const msg =
        r.status === 403
          ? '需要平台管理员权限（403）：仅 admin 可查看治理安全审计'
          : (r.error ?? `HTTP ${r.status}`);
      throw new Error(msg);
    }
    return r.data;
  }, []);

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-governance-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">🛡 治理安全审计</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {/* 概览 */}
          <div className="wb-section-label">OWASP Agentic Skills Top 10 对照（2026）</div>
          {loading && (
            <div className="wb-state" data-testid="wb-governance-loading">
              <div className="wb-state__icon">⏳</div>
              <div>运行治理安全审计…</div>
            </div>
          )}
          {error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-governance-error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
              <button
                className="wb-theme-option wb-theme-option--active"
                onClick={reload}
                type="button"
              >
                重试
              </button>
            </div>
          )}

          {audit && !loading && (
            <>
              <div className="wb-smart-card" data-testid="wb-governance-summary">
                <div className="wb-smart-card__head">
                  <div className="wb-smart-card__room">审计得分 {audit.summary.score}</div>
                  <span className="wb-status-chip wb-status-chip--success">
                    pass {audit.summary.pass}
                  </span>
                  <span className="wb-status-chip wb-status-chip--warning">
                    warn {audit.summary.warn}
                  </span>
                  <span className="wb-status-chip wb-status-chip--danger">
                    fail {audit.summary.fail}
                  </span>
                </div>
                {audit.generated_at && (
                  <div className="wb-smart-card__meta" style={{ marginTop: 6 }}>
                    生成时间：{audit.generated_at}
                  </div>
                )}
              </div>

              {/* AG 逐项审计结果 */}
              {audit.findings.map((f, i) => (
                <div key={f.id} className="wb-smart-card" style={{ marginTop: 8 }} data-testid={`wb-governance-finding--${i}`}>
                  <div className="wb-smart-card__head">
                    <div className="wb-smart-card__room">
                      {f.id} · {f.name}
                    </div>
                    <span className={`wb-status-chip ${STATUS_TONE[f.status] ?? 'wb-status-chip--muted'}`}>
                      {f.status}
                    </span>
                  </div>
                  <div
                    style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 4 }}
                  >
                    {f.desc}
                  </div>
                  <div className="wb-smart-card__meta" style={{ marginTop: 6 }}>
                    <span className="wb-status-chip wb-status-chip--info">控制</span> {f.control}
                  </div>
                  <div className="wb-smart-card__meta" style={{ marginTop: 4 }}>
                    <span className="wb-status-chip wb-status-chip--muted">证据</span> {f.evidence}
                  </div>
                  {f.recommendation && (
                    <div className="wb-smart-card__meta" style={{ marginTop: 4 }}>
                      <span className="wb-status-chip wb-status-chip--warning">建议</span> {f.recommendation}
                    </div>
                  )}
                </div>
              ))}

              {/* 整改建议汇总 */}
              {audit.recommendations.length > 0 && (
                <div className="wb-smart-card" style={{ marginTop: 8 }} data-testid="wb-governance-recommendations">
                  <div className="wb-smart-card__head">
                    <div className="wb-smart-card__room">整改建议（{audit.recommendations.length}）</div>
                  </div>
                  {audit.recommendations.map((rec, i) => (
                    <div key={i} className="wb-smart-card__meta" style={{ marginTop: 4 }}>
                      {i + 1}. {rec}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
