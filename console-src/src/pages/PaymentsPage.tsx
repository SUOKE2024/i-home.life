/**
 * PaymentsPage — 支付管理（v1.13.x 前端缺口补齐）
 *
 * 结构：Scaffold > AppBar(支付管理) > 项目选择器 > 最终结算摘要 + 支付进度节点 + 支付记录（操作）
 * API（对齐 app/api/payments.py，前缀 /api/payments）：
 *   GET  /api/payments/project/{projectId}             项目支付记录
 *   GET  /api/payments/schedule/{projectId}            支付进度节点
 *   GET  /api/payments/final-settlement/{projectId}    最终结算报告
 *   POST /api/payments/{id}/confirm                    确认支付
 *   POST /api/payments/{id}/refund                     退款
 *   POST /api/payments/{id}/invoice                    开具发票
 *   POST /api/payments/{id}/fail                       标记失败
 *
 * 诚实降级：后端错误文案真实展示（PaymentStateError 等业务校验）。
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type {
  FinalSettlementReport,
  PaymentItem,
  PaymentScheduleNode,
  Project,
} from '../types/domain';

type ChipTone = 'muted' | 'info' | 'success' | 'warning' | 'danger' | 'accent';

const STATUS_META: Record<string, { label: string; tone: ChipTone }> = {
  pending: { label: '待支付', tone: 'warning' },
  paid: { label: '已支付', tone: 'success' },
  failed: { label: '失败', tone: 'danger' },
  refunded: { label: '已退款', tone: 'muted' },
  disputed: { label: '争议中', tone: 'danger' },
};

const STAGE_LABELS: Record<string, string> = {
  deposit: '定金',
  progress: '进度款',
  final: '尾款',
  warranty: '保修金',
};

function fmtMoney(v: number | null | undefined): string {
  return `¥${(v ?? 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`;
}

export default function PaymentsPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [actionId, setActionId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [refundMap, setRefundMap] = useState<Record<string, string>>({});
  const [invoiceMap, setInvoiceMap] = useState<Record<string, string>>({});

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  const {
    data: payments,
    loading,
    error,
    reload,
  } = useAsync<PaymentItem[] | null>(async () => {
    if (!selectedProjectId) return null;
    const r = await apiClient.listPayments<PaymentItem[]>(selectedProjectId);
    if (!r.isSuccess || !r.data) throw new Error(r.error ?? `HTTP ${r.status}`);
    return r.data;
  }, [selectedProjectId]);

  const { data: schedule } = useAsync<PaymentScheduleNode[] | null>(async () => {
    if (!selectedProjectId) return null;
    const r = await apiClient.getPaymentSchedule<PaymentScheduleNode[]>(selectedProjectId);
    if (!r.isSuccess || !r.data) throw new Error(r.error ?? `HTTP ${r.status}`);
    return r.data;
  }, [selectedProjectId]);

  const { data: finalSettlement } = useAsync<FinalSettlementReport | null>(async () => {
    if (!selectedProjectId) return null;
    const r = await apiClient.getFinalSettlement<FinalSettlementReport>(selectedProjectId);
    if (!r.isSuccess || !r.data) throw new Error(r.error ?? `HTTP ${r.status}`);
    return r.data;
  }, [selectedProjectId]);

  async function runAction(fn: () => Promise<unknown>) {
    setActionError(null);
    try {
      await fn();
      await reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionId(null);
    }
  }

  function handleConfirm(p: PaymentItem) {
    setActionId(p.id);
    runAction(async () => {
      const r = await apiClient.confirmPayment(p.id);
      if (!r.isSuccess) throw new Error(r.error ?? '确认失败');
    });
  }

  function handleRefund(p: PaymentItem) {
    setActionId(p.id);
    const amount = Number(refundMap[p.id]);
    if (!amount || amount <= 0) {
      setActionError('请填写有效退款金额');
      setActionId(null);
      return;
    }
    runAction(async () => {
      const r = await apiClient.refundPayment(p.id, { refund_amount: amount });
      if (!r.isSuccess) throw new Error(r.error ?? '退款失败');
    });
  }

  function handleInvoice(p: PaymentItem) {
    setActionId(p.id);
    runAction(async () => {
      const r = await apiClient.invoicePayment(p.id, { invoice_url: invoiceMap[p.id] || undefined });
      if (!r.isSuccess) throw new Error(r.error ?? '开票失败');
    });
  }

  function handleFail(p: PaymentItem) {
    setActionId(p.id);
    runAction(async () => {
      const r = await apiClient.failPayment(p.id);
      if (!r.isSuccess) throw new Error(r.error ?? '标记失败失败');
    });
  }

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-payments-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">💳 支付管理</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-project-picker">
            <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)} aria-label="选择项目" data-testid="wb-payments-project-select">
              <option value="">选择项目…</option>
              {projects?.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </div>

          {!selectedProjectId && (
            <div className="wb-state" data-testid="wb-payments-no-project">
              <div className="wb-state__icon">📋</div><div>请先选择项目</div>
            </div>
          )}
          {selectedProjectId && loading && (
            <div className="wb-state" data-testid="wb-payments-loading">
              <div className="wb-state__icon">⏳</div><div>加载支付数据中…</div>
            </div>
          )}
          {selectedProjectId && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-payments-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>重试</button>
            </div>
          )}

          {selectedProjectId && !loading && !error && (!payments || payments.length === 0) && (
            <div className="wb-state" data-testid="wb-payments-empty">
              <div className="wb-state__icon">💳</div><div>暂无支付记录（尚未发起任何支付）</div>
            </div>
          )}

          {selectedProjectId && !loading && !error && payments && payments.length > 0 && (
            <div data-testid="wb-payments-content">
              {actionError && (
                <div className="wb-alert" data-testid="wb-payments-action-error">⚠ {actionError}</div>
              )}

              {/* 最终结算摘要 */}
              {finalSettlement && (
                <div className="wb-grid wb-grid--2" data-testid="wb-payments-settlement">
                  <div className="wb-stat-card">
                    <div className="wb-stat-card__label">合同金额</div>
                    <div className="wb-stat-card__value">{fmtMoney(finalSettlement.total_contract_amount)}</div>
                  </div>
                  <div className="wb-stat-card">
                    <div className="wb-stat-card__label">已付金额</div>
                    <div className="wb-stat-card__value">{fmtMoney(finalSettlement.total_paid)}</div>
                  </div>
                  <div className="wb-stat-card">
                    <div className="wb-stat-card__label">待付金额</div>
                    <div className="wb-stat-card__value">{fmtMoney(finalSettlement.total_pending)}</div>
                  </div>
                  <div className="wb-stat-card">
                    <div className="wb-stat-card__label">已付比例</div>
                    <div className="wb-stat-card__value">{((finalSettlement.paid_ratio ?? 0) * 100).toFixed(1)}%</div>
                  </div>
                </div>
              )}

              {/* 支付进度节点 */}
              {schedule && schedule.length > 0 && (
                <div className="wb-card" data-testid="wb-payments-schedule">
                  <div className="wb-card__title">支付进度</div>
                  {schedule.map((n) => (
                    <div className="wb-list-row" key={n.stage_code}>
                      <span className="wb-list-row__main">{STAGE_LABELS[n.stage_code] ?? n.stage_code}</span>
                      <span className="wb-list-row__sub">
                        {fmtMoney(n.paid_amount)} / {fmtMoney(n.total_amount)}
                      </span>
                      <span className={`wb-status-chip wb-status-chip--${STATUS_META[n.status]?.tone ?? 'muted'}`}>
                        {STATUS_META[n.status]?.label ?? n.status}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* 支付记录 + 操作 */}
              <div className="wb-card" data-testid="wb-payments-list">
                <div className="wb-card__title">支付记录（{payments.length}）</div>
                <table className="wb-table">
                  <thead>
                    <tr>
                      <th>阶段</th><th>金额</th><th>状态</th><th>交易号</th><th>到期日</th><th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {payments.map((p) => (
                      <tr key={p.id}>
                        <td>{STAGE_LABELS[p.stage_code ?? ''] ?? p.milestone_code}</td>
                        <td>{fmtMoney(p.amount)}</td>
                        <td>
                          <span className={`wb-status-chip wb-status-chip--${STATUS_META[p.status]?.tone ?? 'muted'}`}>
                            {STATUS_META[p.status]?.label ?? p.status}
                          </span>
                        </td>
                        <td>{p.transaction_id ?? '—'}</td>
                        <td>{p.due_at ? new Date(p.due_at).toLocaleDateString('zh-CN') : '—'}</td>
                        <td>
                          <div className="wb-actions">
                            {p.status === 'pending' && (
                              <button
                                className="wb-btn wb-btn--sm"
                                disabled={actionId === p.id}
                                onClick={() => handleConfirm(p)}
                                type="button"
                              >{actionId === p.id ? '处理中…' : '确认'}</button>
                            )}
                            {p.status === 'pending' && (
                              <input
                                className="wb-input wb-input--sm"
                                type="number"
                                min="0"
                                placeholder="退款额"
                                value={refundMap[p.id] ?? ''}
                                onChange={(e) => setRefundMap((m) => ({ ...m, [p.id]: e.target.value }))}
                                aria-label="退款金额"
                              />
                            )}
                            {p.status === 'pending' && (
                              <button
                                className="wb-btn wb-btn--sm"
                                disabled={actionId === p.id}
                                onClick={() => handleRefund(p)}
                                type="button"
                              >退款</button>
                            )}
                            {p.status === 'paid' && !p.invoice_no && (
                              <>
                                <input
                                  className="wb-input wb-input--sm"
                                  type="text"
                                  placeholder="发票URL"
                                  value={invoiceMap[p.id] ?? ''}
                                  onChange={(e) => setInvoiceMap((m) => ({ ...m, [p.id]: e.target.value }))}
                                  aria-label="发票URL"
                                />
                                <button
                                  className="wb-btn wb-btn--sm"
                                  disabled={actionId === p.id}
                                  onClick={() => handleInvoice(p)}
                                  type="button"
                                >开票</button>
                              </>
                            )}
                            {p.status === 'pending' && (
                              <button
                                className="wb-btn wb-btn--sm wb-btn--ghost"
                                disabled={actionId === p.id}
                                onClick={() => handleFail(p)}
                                type="button"
                              >失败</button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
