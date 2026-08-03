/**
 * EscrowPage — 资金托管（F43, v1.5.0）
 *
 * 结构：Scaffold > AppBar(资金托管) > [项目选择器] > 创建表单 + 存管账户卡片列表
 * API（对齐 app/api/escrow_trustee.py）：
 *   GET  /api/escrow/project/{projectId}/trustee-accounts  项目存管账户列表
 *   POST /api/escrow/trustee-accounts                      开通存管账户
 *   POST /api/escrow/trustee-accounts/{id}/acceptance      节点验收双向确认（role=owner|contractor）
 *   POST /api/escrow/trustee-accounts/{id}/release         放款
 *   GET  /api/escrow/trustee-accounts/{id}/interest        托管资金利息信息
 *
 * trustee_type: bank / third_party
 * status: active / release_requested / released
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type {
  EscrowInterestInfo,
  EscrowTrusteeAccount,
  Project,
} from '../types/domain';

type ChipTone = 'muted' | 'info' | 'success' | 'warning' | 'danger' | 'accent';

const TRUSTEE_TYPES: Record<string, { label: string; tone: ChipTone }> = {
  bank: { label: '银行存管', tone: 'info' },
  third_party: { label: '第三方监管', tone: 'accent' },
};

const STATUS_META: Record<string, { label: string; tone: ChipTone }> = {
  active: { label: '存管中', tone: 'info' },
  release_requested: { label: '待放款', tone: 'warning' },
  released: { label: '已放款', tone: 'success' },
};

export default function EscrowPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [escrowPaymentId, setEscrowPaymentId] = useState('');
  const [trusteeType, setTrusteeType] = useState('bank');
  const [accountNoMasked, setAccountNoMasked] = useState('');
  const [interestToOwner, setInterestToOwner] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [interestMap, setInterestMap] = useState<Record<string, EscrowInterestInfo>>({});

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  const { data: accounts, loading, error, reload } = useAsync<EscrowTrusteeAccount[] | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.listEscrowTrusteeAccounts<EscrowTrusteeAccount[]>(selectedProjectId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [selectedProjectId],
  );

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!escrowPaymentId.trim() || !accountNoMasked.trim()) {
      setFormError('请填写担保支付 ID 与脱敏账号');
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      const r = await apiClient.createEscrowTrusteeAccount({
        escrow_payment_id: escrowPaymentId.trim(),
        trustee_type: trusteeType,
        account_no_masked: accountNoMasked.trim(),
        interest_to_owner: interestToOwner,
      });
      if (!r.isSuccess) throw new Error(r.error ?? '创建失败');
      setEscrowPaymentId('');
      setAccountNoMasked('');
      setTrusteeType('bank');
      setInterestToOwner(true);
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleAcceptance(accountId: string, role: 'owner' | 'contractor') {
    setActionId(accountId);
    setFormError(null);
    try {
      const r = await apiClient.confirmEscrowAcceptance(accountId, role);
      if (!r.isSuccess) throw new Error(r.error ?? '确认失败');
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionId(null);
    }
  }

  async function handleRelease(accountId: string) {
    setActionId(accountId);
    setFormError(null);
    try {
      const r = await apiClient.releaseEscrowFunds(accountId);
      if (!r.isSuccess) throw new Error(r.error ?? '放款失败');
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionId(null);
    }
  }

  async function handleInterest(accountId: string) {
    setActionId(accountId);
    setFormError(null);
    try {
      const r = await apiClient.getEscrowInterest<EscrowInterestInfo>(accountId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '获取利息信息失败');
      setInterestMap((prev) => ({ ...prev, [accountId]: r.data! }));
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionId(null);
    }
  }

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-escrow-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">🛡 资金托管</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-project-picker">
            <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)} aria-label="选择项目" data-testid="wb-escrow-project-select">
              <option value="">选择项目…</option>
              {projects?.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </div>

          {!selectedProjectId && (
            <div className="wb-state" data-testid="wb-escrow-no-project">
              <div className="wb-state__icon">📋</div><div>请先选择项目</div>
            </div>
          )}
          {selectedProjectId && loading && (
            <div className="wb-state" data-testid="wb-escrow-loading">
              <div className="wb-state__icon">⏳</div><div>加载存管账户中…</div>
            </div>
          )}
          {selectedProjectId && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-escrow-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>重试</button>
            </div>
          )}

          {selectedProjectId && !loading && !error && (
            <div data-testid="wb-escrow-content">
              {/* 创建表单 */}
              <div className="wb-create-form" data-testid="wb-escrow-create">
                <div className="wb-create-form__head">
                  <div className="wb-create-form__badge">🛡</div>
                  <div>
                    <div className="wb-create-form__title">开通存管账户</div>
                    <div className="wb-create-form__subtitle">为担保支付开通银行存管 / 第三方监管账户（同一担保支付仅一个）</div>
                  </div>
                </div>
                <form onSubmit={handleCreate}>
                  <div className="wb-create-form__body">
                    <div className="wb-create-form__field">
                      <label className="wb-create-form__label" htmlFor="wb-escrow-payment-id">担保支付 ID <span className="wb-create-form__required">*</span></label>
                      <input
                        id="wb-escrow-payment-id"
                        className="wb-input"
                        value={escrowPaymentId}
                        onChange={(e) => setEscrowPaymentId(e.target.value)}
                        placeholder="如：EP-20260803-0001"
                        data-testid="wb-escrow-payment-id-input"
                      />
                    </div>
                    <div className="wb-create-form__field">
                      <label className="wb-create-form__label" htmlFor="wb-escrow-trustee-type">托管类型</label>
                      <select
                        id="wb-escrow-trustee-type"
                        className="wb-input"
                        value={trusteeType}
                        onChange={(e) => setTrusteeType(e.target.value)}
                        data-testid="wb-escrow-trustee-type-select"
                      >
                        {Object.entries(TRUSTEE_TYPES).map(([key, info]) => (
                          <option key={key} value={key}>{info.label}</option>
                        ))}
                      </select>
                    </div>
                    <div className="wb-create-form__field">
                      <label className="wb-create-form__label" htmlFor="wb-escrow-account-no">脱敏账号 <span className="wb-create-form__required">*</span></label>
                      <input
                        id="wb-escrow-account-no"
                        className="wb-input"
                        value={accountNoMasked}
                        onChange={(e) => setAccountNoMasked(e.target.value)}
                        placeholder="如：6222 **** **** 8888"
                        data-testid="wb-escrow-account-no-input"
                      />
                    </div>
                    <div className="wb-create-form__field">
                      <label className="wb-create-form__label" style={{ flexDirection: 'row', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={interestToOwner}
                          onChange={(e) => setInterestToOwner(e.target.checked)}
                          style={{ width: 'auto' }}
                          data-testid="wb-escrow-interest-to-owner-toggle"
                        />
                        托管资金利息归属业主
                      </label>
                    </div>
                    {formError && (
                      <div className="wb-create-form__error" data-testid="wb-escrow-form-error">
                        ⚠ {formError}
                      </div>
                    )}
                    <div className="wb-create-form__actions">
                      <button className="wb-theme-option wb-theme-option--active" type="submit" disabled={submitting} data-testid="wb-escrow-submit" style={{ width: '100%' }}>
                        {submitting ? '开通中…' : '＋ 开通存管账户'}
                      </button>
                    </div>
                  </div>
                </form>
              </div>

              {/* 账户列表 */}
              <div className="wb-section-label">存管账户（{accounts?.length ?? 0}）</div>
              {!loading && !error && (accounts?.length ?? 0) === 0 && (
                <div className="wb-state" data-testid="wb-escrow-empty">
                  <div className="wb-state__icon">🛡</div><div>暂无存管账户</div>
                  <div style={{ fontSize: 'var(--font-size-sm)' }}>在上方为担保支付开通首个存管账户</div>
                </div>
              )}
              {(accounts ?? []).map((acc, i) => {
                const trusteeInfo = TRUSTEE_TYPES[acc.trustee_type] ?? { label: acc.trustee_type, tone: 'muted' as ChipTone };
                const statusInfo = STATUS_META[acc.status] ?? { label: acc.status, tone: 'muted' as ChipTone };
                const interest = interestMap[acc.id];
                const released = acc.status === 'released';
                return (
                  <div key={acc.id} className="wb-smart-card" data-testid={`wb-escrow-account--${i}`}>
                    <div className="wb-smart-card__head">
                      <div className="wb-smart-card__room">{acc.account_no_masked}</div>
                      <span className={`wb-status-chip wb-status-chip--${trusteeInfo.tone}`}>{trusteeInfo.label}</span>
                      <span className={`wb-status-chip wb-status-chip--${statusInfo.tone}`}>{statusInfo.label}</span>
                    </div>
                    <div className="wb-smart-card__meta">
                      <span>📄 {acc.escrow_payment_id}</span>
                      <span>👤 业主确认 {acc.owner_confirmed ? '✅' : '⭕'}</span>
                      <span>🔨 承包方确认 {acc.contractor_confirmed ? '✅' : '⭕'}</span>
                      <span>📐 规则 {acc.release_rule}</span>
                    </div>
                    {interest && (
                      <div className="wb-smart-card__meta" style={{ marginTop: 8 }} data-testid={`wb-escrow-interest-info--${i}`}>
                        <span>💹 利息归属 {interest.interest_to_owner ? '业主' : '平台'}</span>
                        <span>{interest.note}</span>
                      </div>
                    )}
                    <div className="wb-smart-card__meta" style={{ marginTop: 10, flexWrap: 'wrap' }}>
                      <button
                        className="wb-theme-option wb-theme-option--active"
                        type="button"
                        onClick={() => handleAcceptance(acc.id, 'owner')}
                        disabled={acc.owner_confirmed || released || actionId === acc.id}
                        data-testid={`wb-escrow-owner-confirm--${i}`}
                      >
                        业主确认
                      </button>
                      <button
                        className="wb-theme-option wb-theme-option--active"
                        type="button"
                        onClick={() => handleAcceptance(acc.id, 'contractor')}
                        disabled={acc.contractor_confirmed || released || actionId === acc.id}
                        data-testid={`wb-escrow-contractor-confirm--${i}`}
                      >
                        承包方确认
                      </button>
                      <button
                        className="wb-theme-option wb-theme-option--active"
                        type="button"
                        onClick={() => handleRelease(acc.id)}
                        disabled={released || actionId === acc.id}
                        data-testid={`wb-escrow-release--${i}`}
                      >
                        放款
                      </button>
                      <button
                        className="wb-theme-option"
                        type="button"
                        onClick={() => handleInterest(acc.id)}
                        disabled={actionId === acc.id}
                        data-testid={`wb-escrow-interest--${i}`}
                      >
                        利息
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
