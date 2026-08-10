/**
 * AgentApprovalsPage — Agent 工具批准（strict 安全 posture 的人工批准端点）
 *
 * 结构：Scaffold > AppBar(工具批准) > 待批准请求列表（批准/拒绝 + 理由）> 单条查询区（已批准可执行工具）
 * API（对齐 app/api/agent_approvals.py，前缀 /agents/approvals）：
 *   GET  /api/agents/approvals              待批准请求列表（仅 pending）
 *   GET  /api/agents/approvals/{id}         单条批准请求
 *   POST /api/agents/approvals/{id}/approve 批准（仅本人或 admin，仅 pending）
 *   POST /api/agents/approvals/{id}/reject  拒绝
 *   POST /api/agents/approvals/{id}/execute 批准后执行工具（校验 approved + 未过期）
 *
 * 所有操作强制 user_id 隔离；后端错误真实展示（409 状态非 pending 等）。
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type {
  AgentApprovalExecuteResponse,
  AgentApprovalItem,
  AgentApprovalListResponse,
} from '../types/domain';

/** 404/503 多为灰度 flag 未启用，追加诚实提示（保留后端真实 error 文案） */
function flagGuardMessage(status: number, error?: string): string {
  if (status === 404 || status === 503) {
    return `功能未启用（灰度 flag 默认关闭）：${error ?? `HTTP ${status}`}`;
  }
  return error ?? `HTTP ${status}`;
}

const STATE_META: Record<string, { label: string; tone: string }> = {
  pending: { label: '待批准', tone: 'wb-status-chip--warning' },
  approved: { label: '已批准', tone: 'wb-status-chip--success' },
  rejected: { label: '已拒绝', tone: 'wb-status-chip--danger' },
  expired: { label: '已过期', tone: 'wb-status-chip--muted' },
};

export default function AgentApprovalsPage() {
  const navigate = useNavigate();
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [actingId, setActingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // 查询区状态
  const [lookupId, setLookupId] = useState('');
  const [lookedId, setLookedId] = useState<string | null>(null);
  const [executeResult, setExecuteResult] = useState<AgentApprovalExecuteResponse | null>(null);

  const {
    data: list,
    loading,
    error,
    reload,
  } = useAsync<AgentApprovalListResponse | null>(async () => {
    const r = await apiClient.listAgentApprovals<AgentApprovalListResponse>();
    if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
    return r.data;
  }, []);

  const {
    data: detail,
    loading: detailLoading,
    error: detailError,
    reload: reloadDetail,
  } = useAsync<AgentApprovalItem | null>(async () => {
    if (!lookedId) return null;
    const r = await apiClient.getAgentApproval<AgentApprovalItem>(lookedId);
    if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
    return r.data;
  }, [lookedId]);

  const items = list?.items ?? [];

  async function runAction(
    approvalId: string,
    kind: 'approve' | 'reject' | 'execute',
  ) {
    setActingId(approvalId);
    setActionError(null);
    setExecuteResult(null);
    try {
      if (kind === 'approve') {
        const r = await apiClient.approveAgentApproval(approvalId, reasons[approvalId]);
        if (!r.isSuccess) throw new Error(flagGuardMessage(r.status, r.error));
      } else if (kind === 'reject') {
        const r = await apiClient.rejectAgentApproval(approvalId, reasons[approvalId]);
        if (!r.isSuccess) throw new Error(flagGuardMessage(r.status, r.error));
      } else {
        const r = await apiClient.executeAgentApproval<AgentApprovalExecuteResponse>(approvalId);
        if (!r.isSuccess) throw new Error(flagGuardMessage(r.status, r.error));
        if (r.data) setExecuteResult(r.data);
      }
      // 列表只含 pending：批准/拒绝后刷新；执行不影响 pending 列表
      if (kind !== 'execute') await reload();
      if (lookedId === approvalId && kind !== 'execute') await reloadDetail();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setActingId(null);
    }
  }

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-agent-approvals-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">🛡 Agent 工具批准</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {actionError && (
            <div
              className="wb-create-form__error"
              style={{ marginBottom: 12 }}
              data-testid="wb-agent-approvals-action-error"
            >
              ⚠ {actionError}
            </div>
          )}

          {loading && (
            <div className="wb-state" data-testid="wb-agent-approvals-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载批准请求…</div>
            </div>
          )}

          {error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-agent-approvals-error">
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

          {!loading && !error && items.length === 0 && (
            <div className="wb-state" data-testid="wb-agent-approvals-empty">
              <div className="wb-state__icon">✅</div>
              <div>暂无待批准的 Agent 工具请求</div>
            </div>
          )}

          {!loading && !error && items.length > 0 && (
            <div data-testid="wb-agent-approvals-content">
              <div className="wb-section-label">
                待批准请求（{items.length}）
              </div>
              {items.map((item, i) => {
                const meta = STATE_META[item.state] ?? {
                  label: item.state,
                  tone: 'wb-status-chip--muted',
                };
                return (
                  <div key={item.id} className="wb-smart-card" data-testid={`wb-agent-approvals-item--${i}`}>
                    <div className="wb-smart-card__head">
                      <div className="wb-smart-card__room">
                        {item.agent_name} · {item.tool_name}
                      </div>
                      <span className={`wb-status-chip ${meta.tone}`}>{meta.label}</span>
                    </div>
                    <div className="wb-smart-card__meta">
                      <span>🆔 {item.approval_id}</span>
                      <span>🌐 作用域 {item.scope}</span>
                      {item.project_id && <span>📁 {item.project_id}</span>}
                    </div>
                    <div
                      style={{
                        fontSize: 'var(--font-size-xs)',
                        color: 'var(--text-muted)',
                        marginTop: 6,
                      }}
                    >
                      参数
                    </div>
                    <pre
                      style={{
                        fontSize: 'var(--font-size-xs)',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-all',
                        margin: '4px 0 0',
                        maxHeight: 160,
                        overflow: 'auto',
                      }}
                    >
                      {JSON.stringify(item.arguments, null, 2)}
                    </pre>
                    <div className="wb-smart-card__meta" style={{ marginTop: 8 }}>
                      <span>⏰ 创建 {item.created_at ?? '-'}</span>
                      {item.expires_at && <span>⌛ 过期 {item.expires_at}</span>}
                    </div>
                    {item.state === 'pending' && (
                      <div style={{ marginTop: 10 }}>
                        <input
                          className="wb-input"
                          value={reasons[item.approval_id] ?? ''}
                          onChange={(e) =>
                            setReasons((prev) => ({
                              ...prev,
                              [item.approval_id]: e.target.value,
                            }))
                          }
                          placeholder="决策理由（可选，≤500 字）"
                          data-testid={`wb-agent-approvals-reason--${i}`}
                        />
                        <div className="wb-create-form__actions" style={{ marginTop: 8 }}>
                          <button
                            className="wb-theme-option wb-theme-option--active"
                            type="button"
                            disabled={actingId === item.approval_id}
                            onClick={() => runAction(item.approval_id, 'approve')}
                            data-testid={`wb-agent-approvals-approve--${i}`}
                          >
                            {actingId === item.approval_id ? '处理中…' : '✅ 批准'}
                          </button>
                          <button
                            className="wb-theme-option"
                            type="button"
                            disabled={actingId === item.approval_id}
                            onClick={() => runAction(item.approval_id, 'reject')}
                            data-testid={`wb-agent-approvals-reject--${i}`}
                          >
                            拒绝
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* 单条查询（已批准请求可执行工具） */}
          <div className="wb-create-form" style={{ marginTop: 20 }} data-testid="wb-agent-approvals-lookup">
            <div className="wb-create-form__head">
              <div className="wb-create-form__badge">🔍</div>
              <div>
                <div className="wb-create-form__title">按 approval_id 查询</div>
                <div className="wb-create-form__subtitle">
                  列表仅含 pending 请求；已批准请求需凭 approval_id 查询后可执行工具
                </div>
              </div>
            </div>
            <div className="wb-create-form__body">
              <div className="wb-create-form__field">
                <label className="wb-create-form__label" htmlFor="wb-agent-approvals-lookup-input">
                  approval_id
                </label>
                <input
                  id="wb-agent-approvals-lookup-input"
                  className="wb-input"
                  value={lookupId}
                  onChange={(e) => setLookupId(e.target.value)}
                  placeholder="输入 approval_id"
                  data-testid="wb-agent-approvals-lookup-input"
                />
              </div>
              <div className="wb-create-form__actions">
                <button
                  className="wb-theme-option wb-theme-option--active"
                  type="button"
                  disabled={!lookupId.trim() || detailLoading}
                  onClick={() => setLookedId(lookupId.trim())}
                  data-testid="wb-agent-approvals-lookup-btn"
                  style={{ width: '100%' }}
                >
                  {detailLoading ? '查询中…' : '🔍 查询'}
                </button>
              </div>
            </div>
          </div>

          {detailError && !detailLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-agent-approvals-detail-error">
              <div className="wb-state__icon">⚠</div>
              <div>{detailError}</div>
            </div>
          )}

          {detail && !detailLoading && (
            <div className="wb-smart-card" style={{ marginTop: 12 }} data-testid="wb-agent-approvals-detail">
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">
                  {detail.agent_name} · {detail.tool_name}
                </div>
                <span
                  className={`wb-status-chip ${(STATE_META[detail.state] ?? { tone: 'wb-status-chip--muted' }).tone}`}
                >
                  {(STATE_META[detail.state] ?? { label: detail.state }).label}
                </span>
              </div>
              <div className="wb-smart-card__meta">
                <span>🆔 {detail.approval_id}</span>
                <span>🌐 {detail.scope}</span>
                {detail.trace_id && <span>🧵 {detail.trace_id}</span>}
              </div>
              <pre
                style={{
                  fontSize: 'var(--font-size-xs)',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-all',
                  margin: '8px 0 0',
                  maxHeight: 160,
                  overflow: 'auto',
                }}
              >
                {JSON.stringify(detail.arguments, null, 2)}
              </pre>
              {detail.decision_reason && (
                <div className="wb-smart-card__meta" style={{ marginTop: 8 }}>
                  <span>💬 决策理由：{detail.decision_reason}</span>
                </div>
              )}
              {detail.state === 'approved' && (
                <div className="wb-create-form__actions" style={{ marginTop: 10 }}>
                  <button
                    className="wb-theme-option wb-theme-option--active"
                    type="button"
                    disabled={actingId === detail.approval_id}
                    onClick={() => runAction(detail.approval_id, 'execute')}
                    data-testid="wb-agent-approvals-execute"
                  >
                    {actingId === detail.approval_id ? '执行中…' : '⚡ 执行工具'}
                  </button>
                </div>
              )}
              {executeResult && (
                <div
                  style={{ marginTop: 10 }}
                  data-testid="wb-agent-approvals-execute-result"
                >
                  <div className="wb-smart-card__meta">
                    <span>
                      {executeResult.executed ? '✅ 执行成功' : `❌ 执行失败：${executeResult.error ?? '-'}`}
                    </span>
                  </div>
                  {executeResult.result && (
                    <pre
                      style={{
                        fontSize: 'var(--font-size-xs)',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-all',
                        margin: '6px 0 0',
                        maxHeight: 240,
                        overflow: 'auto',
                      }}
                    >
                      {JSON.stringify(executeResult.result, null, 2)}
                    </pre>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
