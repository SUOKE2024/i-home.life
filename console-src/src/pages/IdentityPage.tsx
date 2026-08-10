/**
 * IdentityPage — 身份认证（实名认证）
 *
 * 结构：Scaffold > AppBar(身份认证) > 我的认证状态 + 提交认证 + 待审核列表（管理员审核）
 * API（对齐 app/api/identity.py，前缀 /api/identity）：
 *   POST /api/identity/submit              提交实名认证
 *   GET  /api/identity/status              当前用户认证状态
 *   GET  /api/identity/pending             待审核列表（仅 admin，非 admin 返回 403 诚实提示）
 *   POST /api/identity/{id}/review         审核通过/拒绝（仅 admin）
 *
 * 诚实降级：isSuccess=false 展示后端真实 error；身份证号展示时脱敏。
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { IdentityStatus, IdentityVerification } from '../types/domain';

function fmtTime(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** 身份证脱敏：前 4 后 4，中间打码 */
function maskIdCard(card: string): string {
  if (!card) return '';
  if (card.length <= 8) return '****';
  return `${card.slice(0, 4)}${'*'.repeat(Math.max(4, card.length - 8))}${card.slice(-4)}`;
}

const STATUS_INFO: Record<string, { label: string; tone: string }> = {
  approved: { label: '已认证', tone: 'wb-status-chip--success' },
  pending: { label: '审核中', tone: 'wb-status-chip--warning' },
  rejected: { label: '已拒绝', tone: 'wb-status-chip--danger' },
  not_submitted: { label: '未提交', tone: 'wb-status-chip--muted' },
};

export default function IdentityPage() {
  const navigate = useNavigate();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitMsg, setSubmitMsg] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);

  const [form, setForm] = useState({
    real_name: '',
    id_card: '',
    id_card_front: '',
    id_card_back: '',
    selfie_with_id: '',
    role_attributes: '',
  });

  // 审核表单状态：verification_id -> { status, note }
  const [reviews, setReviews] = useState<Record<string, { status: 'approved' | 'rejected'; note: string }>>({});

  const { data: status, loading: statusLoading, error: statusError, reload: reloadStatus } =
    useAsync<IdentityStatus | null>(async () => {
      const r = await apiClient.getIdentityStatus<IdentityStatus>();
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载认证状态失败');
      return r.data;
    }, []);

  const { data: pending, loading: pendingLoading, error: pendingError, reload: reloadPending } =
    useAsync<IdentityVerification[] | null>(async () => {
      const r = await apiClient.listPendingIdentities<IdentityVerification[]>();
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载待审核列表失败');
      return r.data;
    }, []);

  function updateForm(key: keyof typeof form, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    setSubmitMsg(null);
    setSubmitting(true);
    try {
      if (!form.real_name.trim()) throw new Error('请输入真实姓名');
      if (!form.id_card.trim()) throw new Error('请输入身份证号');
      let roleAttributes: Record<string, unknown> | null = null;
      if (form.role_attributes.trim()) {
        try {
          roleAttributes = JSON.parse(form.role_attributes.trim());
        } catch {
          throw new Error('角色属性不是合法 JSON');
        }
      }
      const r = await apiClient.submitIdentity<IdentityVerification>({
        real_name: form.real_name.trim(),
        id_card: form.id_card.trim(),
        id_card_front: form.id_card_front.trim() || null,
        id_card_back: form.id_card_back.trim() || null,
        selfie_with_id: form.selfie_with_id.trim() || null,
        role_attributes: roleAttributes,
      });
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '提交认证失败');
      setSubmitMsg('认证申请已提交，等待管理员审核');
      reloadStatus();
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleReview(v: IdentityVerification) {
    setReviewError(null);
    setReviewingId(v.id);
    try {
      const decision = reviews[v.id] ?? { status: 'approved', note: '' };
      const r = await apiClient.reviewIdentity<IdentityVerification>(v.id, decision.status, decision.note);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '审核失败');
      reloadPending();
      reloadStatus();
    } catch (err) {
      setReviewError(err instanceof Error ? err.message : String(err));
    } finally {
      setReviewingId(null);
    }
  }

  const statusInfo = status ? STATUS_INFO[status.status] ?? STATUS_INFO.not_submitted : null;

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-identity-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">🪪 身份认证</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {/* 我的认证状态 */}
          <div className="wb-section-label">我的认证状态</div>
          {statusLoading && (
            <div className="wb-state" data-testid="wb-identity-status-loading">
              <div className="wb-state__icon">⏳</div><div>加载认证状态…</div>
            </div>
          )}
          {statusError && !statusLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-identity-status-error">
              <div className="wb-state__icon">⚠</div><div>{statusError}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={() => reloadStatus()} type="button">重试</button>
            </div>
          )}
          {status && statusInfo && !statusLoading && !statusError && (
            <div className="wb-smart-card" data-testid="wb-identity-status">
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">
                  {status.is_verified ? '✅ 已通过实名认证' : '未通过实名认证'}
                </div>
                <span className={`wb-status-chip ${statusInfo.tone}`}>{statusInfo.label}</span>
              </div>
              <div className="wb-smart-card__meta">
                {status.role && <span>角色 {status.role}</span>}
                {status.submitted_at && <span>提交于 {fmtTime(status.submitted_at)}</span>}
                {status.verified_at && <span>认证于 {fmtTime(status.verified_at)}</span>}
              </div>
              {status.review_note && (
                <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 4 }}>
                  审核说明：{status.review_note}
                </div>
              )}
            </div>
          )}

          {/* 提交认证 */}
          <div className="wb-create-form" style={{ marginTop: 16 }} data-testid="wb-identity-submit">
            <div className="wb-create-form__head">
              <div className="wb-create-form__badge">📝</div>
              <div>
                <div className="wb-create-form__title">提交实名认证</div>
                <div className="wb-create-form__subtitle">真实姓名 + 身份证号，支持上传证件照 URL 与角色属性（可选）</div>
              </div>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="wb-create-form__body">
                <div className="wb-create-form__row">
                  <div className="wb-create-form__field wb-create-form__field--grow">
                    <label className="wb-create-form__label" htmlFor="wb-identity-real-name">真实姓名 <span className="wb-create-form__required">*</span></label>
                    <input id="wb-identity-real-name" className="wb-input" value={form.real_name} onChange={(e) => updateForm('real_name', e.target.value)} placeholder="与身份证一致" data-testid="wb-identity-real-name" />
                  </div>
                  <div className="wb-create-form__field wb-create-form__field--grow">
                    <label className="wb-create-form__label" htmlFor="wb-identity-id-card">身份证号 <span className="wb-create-form__required">*</span></label>
                    <input id="wb-identity-id-card" className="wb-input" value={form.id_card} onChange={(e) => updateForm('id_card', e.target.value)} placeholder="15-18 位" data-testid="wb-identity-id-card" />
                  </div>
                </div>
                <div className="wb-create-form__field">
                  <label className="wb-create-form__label" htmlFor="wb-identity-front">身份证人像面 URL</label>
                  <input id="wb-identity-front" className="wb-input" value={form.id_card_front} onChange={(e) => updateForm('id_card_front', e.target.value)} placeholder="https://…" data-testid="wb-identity-front" />
                </div>
                <div className="wb-create-form__field">
                  <label className="wb-create-form__label" htmlFor="wb-identity-back">身份证国徽面 URL</label>
                  <input id="wb-identity-back" className="wb-input" value={form.id_card_back} onChange={(e) => updateForm('id_card_back', e.target.value)} placeholder="https://…" data-testid="wb-identity-back" />
                </div>
                <div className="wb-create-form__field">
                  <label className="wb-create-form__label" htmlFor="wb-identity-selfie">手持证件照 URL</label>
                  <input id="wb-identity-selfie" className="wb-input" value={form.selfie_with_id} onChange={(e) => updateForm('selfie_with_id', e.target.value)} placeholder="https://…" data-testid="wb-identity-selfie" />
                </div>
                <div className="wb-create-form__field wb-create-form__field--area">
                  <label className="wb-create-form__label" htmlFor="wb-identity-role-attrs">角色属性（JSON，可选）</label>
                  <textarea id="wb-identity-role-attrs" className="wb-textarea" rows={3} value={form.role_attributes} onChange={(e) => updateForm('role_attributes', e.target.value)} placeholder='{"company": "索克装饰", "license_no": "…"}' data-testid="wb-identity-role-attrs" />
                </div>
                {submitError && (
                  <div className="wb-create-form__error" data-testid="wb-identity-submit-error">⚠ {submitError}</div>
                )}
                {submitMsg && (
                  <div className="wb-smart-card" data-testid="wb-identity-submit-msg">✅ {submitMsg}</div>
                )}
                <div className="wb-create-form__actions">
                  <button className="wb-theme-option wb-theme-option--active" type="submit" disabled={submitting} data-testid="wb-identity-submit-btn">
                    {submitting ? '提交中…' : '📝 提交认证'}
                  </button>
                </div>
              </div>
            </form>
          </div>

          {/* 待审核列表（管理员） */}
          <div className="wb-section-label" style={{ marginTop: 16 }}>待审核列表（管理员 · {pending?.length ?? 0}）</div>
          {pendingLoading && (
            <div className="wb-state" data-testid="wb-identity-pending-loading">
              <div className="wb-state__icon">⏳</div><div>加载待审核列表…</div>
            </div>
          )}
          {pendingError && !pendingLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-identity-pending-error">
              <div className="wb-state__icon">⚠</div><div>{pendingError}</div>
              <div style={{ fontSize: 'var(--font-size-sm)' }}>非管理员或功能未启用时无法查看待审核列表</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={() => reloadPending()} type="button">重试</button>
            </div>
          )}
          {!pendingLoading && !pendingError && (pending?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-identity-pending-empty">
              <div className="wb-state__icon">📭</div><div>暂无待审核的认证申请</div>
            </div>
          )}
          {reviewError && (
            <div className="wb-create-form__error" data-testid="wb-identity-review-error">⚠ {reviewError}</div>
          )}
          {(pending ?? []).map((v, i) => {
            const decision = reviews[v.id] ?? { status: 'approved', note: '' };
            return (
              <div key={v.id} className="wb-smart-card" data-testid={`wb-identity-pending--${i}`}>
                <div className="wb-smart-card__head">
                  <div className="wb-smart-card__room">{v.real_name}</div>
                  <span className="wb-status-chip wb-status-chip--warning">{v.status}</span>
                </div>
                <div className="wb-smart-card__meta">
                  <span>身份证 {maskIdCard(v.id_card)}</span>
                  <span>角色 {v.role}</span>
                  <span>提交于 {fmtTime(v.created_at)}</span>
                </div>
                <div style={{ marginTop: 10, display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 'var(--font-size-sm)' }}>
                    <input
                      type="radio"
                      name={`wb-identity-review-status-${v.id}`}
                      checked={decision.status === 'approved'}
                      onChange={() => setReviews((r) => ({ ...r, [v.id]: { ...decision, status: 'approved' } }))}
                    /> 通过
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 'var(--font-size-sm)' }}>
                    <input
                      type="radio"
                      name={`wb-identity-review-status-${v.id}`}
                      checked={decision.status === 'rejected'}
                      onChange={() => setReviews((r) => ({ ...r, [v.id]: { ...decision, status: 'rejected' } }))}
                    /> 拒绝
                  </label>
                  <input
                    className="wb-input"
                    style={{ flex: '1 1 180px' }}
                    value={decision.note}
                    onChange={(e) => setReviews((r) => ({ ...r, [v.id]: { ...decision, note: e.target.value } }))}
                    placeholder="审核说明（可选）"
                    data-testid={`wb-identity-review-note--${i}`}
                  />
                  <button
                    type="button"
                    className="wb-theme-option wb-theme-option--active"
                    disabled={reviewingId === v.id}
                    onClick={() => handleReview(v)}
                    data-testid={`wb-identity-review-submit--${i}`}
                  >
                    {reviewingId === v.id ? '提交中…' : '确认审核'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </SuokeLayout>
  );
}
