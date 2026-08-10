/**
 * HarnessPage — Agent Harness 管理（v1.2.0）
 *
 * 结构：Scaffold > AppBar(Harness) > 健康检查 > 运行时指标 > 离线评估 > 执行轨迹（admin）
 * API（对齐 app/api/harness_api.py，前缀 /harness）：
 *   GET /api/harness/health   健康检查（公开端点）
 *   GET /api/harness/metrics  运行时指标（登录即可）
 *   GET /api/harness/eval     离线评估（admin，最近 100 条轨迹的成功率/降级率/延迟等）
 *   GET /api/harness/traces   执行轨迹（admin，agent_name/status/limit 过滤）
 *
 * 轨迹端点仅 admin 可访问，普通用户 403 时页面展示后端真实错误。
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type {
  HarnessEvalResponse,
  HarnessHealthResponse,
  HarnessMetrics,
  HarnessTracesResponse,
} from '../types/domain';

/** 404/503 多为灰度 flag 未启用，追加诚实提示（保留后端真实 error 文案） */
function flagGuardMessage(status: number, error?: string): string {
  if (status === 404 || status === 503) {
    return `功能未启用（灰度 flag 默认关闭）：${error ?? `HTTP ${status}`}`;
  }
  return error ?? `HTTP ${status}`;
}

const STATUS_FILTERS: Array<{ key: string; label: string }> = [
  { key: '', label: '全部' },
  { key: 'success', label: '成功' },
  { key: 'failed', label: '失败' },
  { key: 'fallback', label: '降级' },
];

const TRACE_STATUS_META: Record<string, { label: string; tone: string }> = {
  success: { label: '成功', tone: 'wb-status-chip--success' },
  failed: { label: '失败', tone: 'wb-status-chip--danger' },
  fallback: { label: '降级', tone: 'wb-status-chip--warning' },
};

export default function HarnessPage() {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState('');
  const [agentFilter, setAgentFilter] = useState('');

  const {
    data: health,
    loading: healthLoading,
    error: healthError,
    reload: reloadHealth,
  } = useAsync<HarnessHealthResponse | null>(async () => {
    const r = await apiClient.getHarnessHealth<HarnessHealthResponse>();
    if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
    return r.data;
  }, []);

  const {
    data: metrics,
    loading: metricsLoading,
    error: metricsError,
    reload: reloadMetrics,
  } = useAsync<HarnessMetrics | null>(async () => {
    const r = await apiClient.getHarnessMetrics<HarnessMetrics>();
    if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
    return r.data;
  }, []);

  const {
    data: evalResp,
    loading: evalLoading,
    error: evalError,
    reload: reloadEval,
  } = useAsync<HarnessEvalResponse | null>(async () => {
    const r = await apiClient.getHarnessEval<HarnessEvalResponse>();
    if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
    return r.data;
  }, []);

  const {
    data: tracesResp,
    loading: tracesLoading,
    error: tracesError,
    reload: reloadTraces,
  } = useAsync<HarnessTracesResponse | null>(async () => {
    const r = await apiClient.getHarnessTraces<HarnessTracesResponse>({
      status: statusFilter || undefined,
      agentName: agentFilter.trim() || undefined,
    });
    if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
    return r.data;
  }, [statusFilter, agentFilter]);

  const traces = tracesResp?.traces ?? [];

  const metricRows: Array<{ label: string; value: string }> = metrics
    ? [
        { label: '总运行次数', value: String(metrics.total_runs) },
        { label: '成功', value: String(metrics.success_runs) },
        { label: '降级', value: String(metrics.fallback_runs) },
        { label: '失败', value: String(metrics.failed_runs) },
        { label: '成功率', value: `${metrics.success_rate}%` },
        { label: '降级率', value: `${metrics.fallback_rate}%` },
        { label: '平均延迟', value: `${metrics.avg_latency_ms} ms` },
        { label: '总 Token', value: String(metrics.total_tokens) },
        { label: '轨迹数', value: String(metrics.trace_count) },
      ]
    : [];

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-harness-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">⚙️ Agent Harness</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {/* 健康检查 */}
          <div className="wb-section-label">健康检查</div>
          {healthLoading && (
            <div className="wb-state" data-testid="wb-harness-health-loading">
              <div className="wb-state__icon">⏳</div>
              <div>检查中…</div>
            </div>
          )}
          {healthError && !healthLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-harness-health-error">
              <div className="wb-state__icon">⚠</div>
              <div>{healthError}</div>
              <button
                className="wb-theme-option wb-theme-option--active"
                onClick={reloadHealth}
                type="button"
              >
                重试
              </button>
            </div>
          )}
          {health && !healthLoading && (
            <div className="wb-smart-card" data-testid="wb-harness-health">
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">Harness</div>
                <span
                  className={`wb-status-chip ${
                    health.status === 'healthy'
                      ? 'wb-status-chip--success'
                      : 'wb-status-chip--danger'
                  }`}
                >
                  {health.status}
                </span>
              </div>
              <div className="wb-smart-card__meta" style={{ marginTop: 6 }}>
                <span>🤖 注册 Agent {health.registered_agents.length}</span>
                <span>🧵 轨迹 {health.trace_count}</span>
                <span>▶ 运行 {health.total_runs}</span>
              </div>
            </div>
          )}

          {/* 运行时指标 */}
          <div className="wb-section-label" style={{ marginTop: 20 }}>
            运行时指标
          </div>
          {metricsLoading && (
            <div className="wb-state" data-testid="wb-harness-metrics-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载指标…</div>
            </div>
          )}
          {metricsError && !metricsLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-harness-metrics-error">
              <div className="wb-state__icon">⚠</div>
              <div>{metricsError}</div>
              <button
                className="wb-theme-option wb-theme-option--active"
                onClick={reloadMetrics}
                type="button"
              >
                重试
              </button>
            </div>
          )}
          {metrics && !metricsLoading && (
            <div className="wb-smart-card" data-testid="wb-harness-metrics">
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))',
                  gap: 8,
                }}
              >
                {metricRows.map((row) => (
                  <div key={row.label} style={{ padding: '8px 10px', background: 'rgba(107,105,120,0.1)', borderRadius: 8 }}>
                    <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)' }}>
                      {row.label}
                    </div>
                    <div style={{ fontSize: 'var(--font-size-md)', fontWeight: 600 }}>{row.value}</div>
                  </div>
                ))}
              </div>
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: 6,
                  marginTop: 10,
                }}
              >
                {metrics.registered_agents.map((name) => (
                  <span key={name} className="wb-status-chip wb-status-chip--info">
                    {name}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* 离线评估 */}
          <div className="wb-section-label" style={{ marginTop: 20 }}>
            离线评估（admin）
          </div>
          {evalLoading && (
            <div className="wb-state" data-testid="wb-harness-eval-loading">
              <div className="wb-state__icon">⏳</div>
              <div>运行离线评估…</div>
            </div>
          )}
          {evalError && !evalLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-harness-eval-error">
              <div className="wb-state__icon">⚠</div>
              <div>{evalError}</div>
              <button
                className="wb-theme-option wb-theme-option--active"
                onClick={reloadEval}
                type="button"
              >
                重试
              </button>
            </div>
          )}
          {evalResp && !evalLoading && (
            <div className="wb-smart-card" data-testid="wb-harness-eval">
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">评估结果</div>
                <span
                  className={`wb-status-chip ${
                    evalResp.status === 'ok'
                      ? 'wb-status-chip--success'
                      : 'wb-status-chip--warning'
                  }`}
                >
                  {evalResp.status}
                </span>
                <span className="wb-status-chip wb-status-chip--muted">
                  样本 {evalResp.sample_size}
                </span>
              </div>
              <pre
                style={{
                  fontSize: 'var(--font-size-xs)',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-all',
                  margin: '8px 0 0',
                }}
              >
                {JSON.stringify(evalResp.metrics, null, 2)}
              </pre>
            </div>
          )}

          {/* 执行轨迹 */}
          <div className="wb-section-label" style={{ marginTop: 20 }}>
            执行轨迹（admin · {traces.length}）
          </div>
          <div className="wb-task-filter" role="tablist" aria-label="轨迹状态筛选">
            {STATUS_FILTERS.map((f) => (
              <button
                key={f.key}
                type="button"
                role="tab"
                aria-selected={statusFilter === f.key}
                className={`wb-task-filter__chip ${
                  statusFilter === f.key ? 'wb-task-filter__chip--active' : ''
                }`}
                onClick={() => setStatusFilter(f.key)}
                data-testid={`wb-harness-status-filter--${f.key || 'all'}`}
              >
                {f.label}
              </button>
            ))}
          </div>
          <div className="wb-project-picker" style={{ marginBottom: 10 }}>
            <input
              className="wb-input"
              value={agentFilter}
              onChange={(e) => setAgentFilter(e.target.value)}
              placeholder="按 agent_name 过滤（如 DesignerAgent）"
              data-testid="wb-harness-agent-filter"
            />
          </div>
          {tracesLoading && (
            <div className="wb-state" data-testid="wb-harness-traces-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载轨迹…</div>
            </div>
          )}
          {tracesError && !tracesLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-harness-traces-error">
              <div className="wb-state__icon">⚠</div>
              <div>{tracesError}</div>
              <button
                className="wb-theme-option wb-theme-option--active"
                onClick={reloadTraces}
                type="button"
              >
                重试
              </button>
            </div>
          )}
          {!tracesLoading && !tracesError && traces.length === 0 && (
            <div className="wb-state" data-testid="wb-harness-traces-empty">
              <div className="wb-state__icon">🧵</div>
              <div>暂无执行轨迹</div>
            </div>
          )}
          {!tracesLoading && !tracesError && traces.length > 0 && (
            <div data-testid="wb-harness-traces-content">
              {traces.map((trace, i) => {
                const meta = TRACE_STATUS_META[trace.status] ?? {
                  label: trace.status,
                  tone: 'wb-status-chip--muted',
                };
                return (
                  <div key={trace.trace_id} className="wb-smart-card" data-testid={`wb-harness-trace--${i}`}>
                    <div className="wb-smart-card__head">
                      <div className="wb-smart-card__room">{trace.agent_name}</div>
                      <span className={`wb-status-chip ${meta.tone}`}>{meta.label}</span>
                      {trace.fallback_used && (
                        <span className="wb-status-chip wb-status-chip--warning">降级</span>
                      )}
                    </div>
                    <div className="wb-smart-card__meta" style={{ marginTop: 6 }}>
                      <span>🆔 {trace.trace_id}</span>
                      <span>⚡ {trace.latency_ms} ms</span>
                      <span>🔤 {trace.total_tokens} tokens</span>
                      <span>🧰 工具调用 {trace.tool_call_count}</span>
                    </div>
                    {trace.user_message_truncated && (
                      <div
                        style={{
                          fontSize: 'var(--font-size-xs)',
                          color: 'var(--text-muted)',
                          marginTop: 4,
                        }}
                      >
                        💬 {trace.user_message_truncated}
                      </div>
                    )}
                    {trace.error_message && (
                      <div
                        style={{
                          fontSize: 'var(--font-size-xs)',
                          color: 'var(--danger)',
                          marginTop: 4,
                        }}
                      >
                        ❌ {trace.error_message}
                      </div>
                    )}
                    <div className="wb-smart-card__meta" style={{ marginTop: 4 }}>
                      <span>🕒 {trace.started_at ?? '-'}</span>
                      <span>🌐 {trace.scope || '-'}</span>
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
