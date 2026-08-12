/**
 * EvalPage — i-home.life 评估框架（借鉴索克生活 Suoke-Eval1）
 *
 * 结构：Scaffold > AppBar(评估) > 评估维度 > 最近评估报告 > 触发运行（admin）
 * API（对齐 app/api/eval.py，前缀 /eval）：
 *   GET  /api/eval/dimensions   评估维度列表（id/name/benchmark 参照）
 *   GET  /api/eval/report       最近评估报告（从最近 harness 轨迹计算维度分数）
 *   POST /api/eval/run          触发一次评估运行（admin；baseline + output_path）
 *
 * flag: eval_enabled 关闭时 report/run 返回 run_id="disabled" 报告（notes 标注），
 * 页面诚实展示「评估框架已关闭」而非伪造数据。
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type {
  EvalDimensionsResponse,
  EvalDriftResponse,
  EvalReport,
} from '../types/domain';

/** 404/503 多为灰度 flag 未启用，追加诚实提示（保留后端真实 error 文案） */
function flagGuardMessage(status: number, error?: string): string {
  if (status === 404 || status === 503) {
    return `功能未启用（灰度 flag 默认关闭）：${error ?? `HTTP ${status}`}`;
  }
  return error ?? `HTTP ${status}`;
}

const BASELINES = ['base_llm', 'keyword', 'full_system', 'mock'];

/** v1.13.5 反馈满意度状态 → 徽章 tone（对齐后端 DRIFT_STATUS_*） */
const FB_TONE: Record<string, 'success' | 'warning' | 'danger' | 'muted'> = {
  ok: 'success',
  warn: 'warning',
  critical: 'danger',
  insufficient_samples: 'muted',
};

export default function EvalPage() {
  const navigate = useNavigate();

  // 触发运行表单
  const [baseline, setBaseline] = useState('full_system');
  const [outputPath, setOutputPath] = useState('');
  const [running, setRunning] = useState(false);
  const [opError, setOpError] = useState<string | null>(null);

  const {
    data: dims,
    loading: dimsLoading,
    error: dimsError,
    reload: reloadDims,
  } = useAsync<EvalDimensionsResponse | null>(async () => {
    const r = await apiClient.getEvalDimensions<EvalDimensionsResponse>();
    if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
    return r.data;
  }, []);

  const {
    data: report,
    loading: reportLoading,
    error: reportError,
    reload: reloadReport,
  } = useAsync<EvalReport | null>(async () => {
    const r = await apiClient.getEvalReport<EvalReport>();
    if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
    return r.data;
  }, []);

  // v1.12.x: Agent 质量漂移检测（admin 端点，403 时诚实展示权限不足）
  const {
    data: drift,
    loading: driftLoading,
    error: driftError,
    reload: reloadDrift,
  } = useAsync<EvalDriftResponse | null>(async () => {
    const r = await apiClient.getEvalDrift<EvalDriftResponse>();
    if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
    return r.data;
  }, []);

  async function handleRun() {
    setRunning(true);
    setOpError(null);
    try {
      const r = await apiClient.runEval<EvalReport>(baseline, outputPath.trim() || undefined);
      if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
      // 用运行结果刷新报告区（后端返回 run_id=disabled 时同样展示诚实 notes）
      await reloadReport();
    } catch (err) {
      setOpError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  }

  const disabled = report?.run_id === 'disabled';

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-eval-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">📐 评估框架</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {opError && (
            <div
              className="wb-create-form__error"
              style={{ marginBottom: 12 }}
              data-testid="wb-eval-op-error"
            >
              ⚠ {opError}
            </div>
          )}

          {/* 评估维度 */}
          <div className="wb-section-label">评估维度（{dims?.total ?? 0}）</div>
          {dimsLoading && (
            <div className="wb-state" data-testid="wb-eval-dims-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载评估维度…</div>
            </div>
          )}
          {dimsError && !dimsLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-eval-dims-error">
              <div className="wb-state__icon">⚠</div>
              <div>{dimsError}</div>
              <button
                className="wb-theme-option wb-theme-option--active"
                onClick={reloadDims}
                type="button"
              >
                重试
              </button>
            </div>
          )}
          {!dimsLoading && !dimsError && (dims?.dimensions.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-eval-dims-empty">
              <div className="wb-state__icon">📐</div>
              <div>暂无评估维度</div>
            </div>
          )}
          {!dimsLoading && !dimsError && dims && dims.dimensions.length > 0 && (
            <div data-testid="wb-eval-dims-content">
              {dims.dimensions.map((d, i) => (
                <div key={d.id} className="wb-smart-card" data-testid={`wb-eval-dim--${i}`}>
                  <div className="wb-smart-card__head">
                    <div className="wb-smart-card__room">{d.name}</div>
                    <span className="wb-status-chip wb-status-chip--muted">{d.id}</span>
                  </div>
                  {d.benchmark && (
                    <div
                      style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 4 }}
                    >
                      📖 {d.benchmark}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* 评估报告 */}
          <div className="wb-section-label" style={{ marginTop: 20 }}>
            最近评估报告
          </div>
          {reportLoading && (
            <div className="wb-state" data-testid="wb-eval-report-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载评估报告…</div>
            </div>
          )}
          {reportError && !reportLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-eval-report-error">
              <div className="wb-state__icon">⚠</div>
              <div>{reportError}</div>
              <button
                className="wb-theme-option wb-theme-option--active"
                onClick={reloadReport}
                type="button"
              >
                重试
              </button>
            </div>
          )}
          {report && !reportLoading && (
            <div className="wb-smart-card" data-testid="wb-eval-report">
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">报告 {report.run_id}</div>
                <span className="wb-status-chip wb-status-chip--muted">{report.baseline}</span>
                <span className="wb-status-chip wb-status-chip--info">
                  样本 {report.sample_size}
                </span>
              </div>
              {disabled && report.notes.length > 0 && (
                <div
                  className="wb-create-form__error"
                  style={{ margin: '8px 0 0' }}
                  data-testid="wb-eval-disabled-note"
                >
                  ⚠ {report.notes.join('；')}
                </div>
              )}
              {!disabled && Object.keys(report.metrics).length > 0 && (
                <>
                  <div
                    style={{
                      fontSize: 'var(--font-size-xs)',
                      color: 'var(--text-muted)',
                      marginTop: 8,
                    }}
                  >
                    运行时指标
                  </div>
                  <pre
                    style={{
                      fontSize: 'var(--font-size-xs)',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                      margin: '4px 0 0',
                    }}
                  >
                    {JSON.stringify(report.metrics, null, 2)}
                  </pre>
                </>
              )}
              {!disabled && Object.keys(report.dimension_scores).length > 0 && (
                <>
                  <div
                    style={{
                      fontSize: 'var(--font-size-xs)',
                      color: 'var(--text-muted)',
                      marginTop: 8,
                    }}
                  >
                    维度得分
                  </div>
                  <pre
                    style={{
                      fontSize: 'var(--font-size-xs)',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                      margin: '4px 0 0',
                    }}
                  >
                    {JSON.stringify(report.dimension_scores, null, 2)}
                  </pre>
                </>
              )}
              {!disabled && Object.keys(report.per_agent_scores ?? {}).length > 0 && (
                <>
                  <div
                    style={{
                      fontSize: 'var(--font-size-xs)',
                      color: 'var(--text-muted)',
                      marginTop: 8,
                    }}
                  >
                    per-agent 评分（v1.12.x）
                  </div>
                  <pre
                    data-testid="wb-eval-per-agent"
                    style={{
                      fontSize: 'var(--font-size-xs)',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                      margin: '4px 0 0',
                    }}
                  >
                    {JSON.stringify(report.per_agent_scores, null, 2)}
                  </pre>
                </>
              )}
              {/* v1.13.5: 用户反馈满意度维度（per-agent like 率 + overall） */}
              {!disabled && report.feedback_metrics && (
                <div
                  className="wb-smart-card"
                  data-testid="wb-eval-feedback-metrics"
                  style={{ marginTop: 10 }}
                >
                  <div className="wb-smart-card__head">
                    <div className="wb-smart-card__room">用户反馈满意度（近 7 天）</div>
                    {report.feedback_metrics.overall ? (
                      <span className={`wb-status-chip wb-status-chip--${FB_TONE[report.feedback_metrics.overall.status] ?? 'muted'}`}>
                        overall {report.feedback_metrics.overall.like_rate}% · {report.feedback_metrics.overall.status}
                      </span>
                    ) : (
                      <span className="wb-status-chip wb-status-chip--muted">
                        样本不足（&lt;{report.feedback_metrics.min_samples}）
                      </span>
                    )}
                  </div>
                  <div className="wb-smart-card__meta" style={{ marginTop: 6 }}>
                    目标 like 率 ≥ {Object.values(report.feedback_metrics.per_agent ?? {})[0]?.target ?? 70}% ·
                    {report.feedback_metrics.agent_count} 个 Agent 有反馈
                  </div>
                  {Object.keys(report.feedback_metrics.per_agent ?? {}).length === 0 ? (
                    <div className="wb-state" style={{ padding: '8px 0' }}>
                      <div className="wb-state__icon">💬</div>
                      <div>暂无用户反馈（L4 学习尚未沉淀样本）</div>
                    </div>
                  ) : (
                    Object.entries(report.feedback_metrics.per_agent).map(([name, m]) => (
                      <div className="wb-list-row" key={name}>
                        <span className="wb-list-row__main">{name}</span>
                        <span className="wb-list-row__sub">{m.like_rate}%（{m.samples} 条）</span>
                        <span className={`wb-status-chip wb-status-chip--${FB_TONE[m.status] ?? 'muted'}`}>
                          {m.status}
                        </span>
                      </div>
                    ))
                  )}
                </div>
              )}
              {report.notes.length > 0 && !disabled && (
                <div className="wb-smart-card__meta" style={{ marginTop: 6 }}>
                  {report.notes.map((note, i) => (
                    <span key={i}>{note}</span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* v1.12.x: Agent 质量漂移检测 */}
          <div className="wb-section-label" style={{ marginTop: 20 }}>
            Agent 质量漂移（近 7 天，admin）
          </div>
          {driftLoading && (
            <div className="wb-state" data-testid="wb-eval-drift-loading">
              <div className="wb-state__icon">⏳</div>
              <div>检测漂移…</div>
            </div>
          )}
          {driftError && !driftLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-eval-drift-error">
              <div className="wb-state__icon">⚠</div>
              <div>{driftError}</div>
              <button
                className="wb-theme-option wb-theme-option--active"
                onClick={reloadDrift}
                type="button"
              >
                重试
              </button>
            </div>
          )}
          {drift && !driftLoading && (
            <div className="wb-smart-card" data-testid="wb-eval-drift">
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">漂移摘要</div>
                <span className="wb-status-chip wb-status-chip--info">
                  critical {drift.summary.critical}
                </span>
                <span className="wb-status-chip wb-status-chip--muted">
                  warn {drift.summary.warn} / ok {drift.summary.ok}
                </span>
              </div>
              {drift.summary.critical === 0 && drift.summary.warn === 0 && (
                <div className="wb-smart-card__meta" style={{ marginTop: 6 }}>
                  ✅ 全部 Agent 满足量化基线
                </div>
              )}
              {drift.records.filter((r) => r.status !== 'ok').map((r, i) => (
                <div key={`${r.agent_name}-${r.metric}-${i}`} className="wb-smart-card__meta" style={{ marginTop: 4 }}>
                  <span className="wb-status-chip wb-status-chip--muted">{r.agent_name}</span>{' '}
                  <span className="wb-status-chip wb-status-chip--info">{r.metric}</span>{' '}
                  <span
                    className={
                      r.status === 'critical'
                        ? 'wb-status-chip wb-status-chip--danger'
                        : 'wb-status-chip wb-status-chip--warning'
                    }
                  >
                    {r.status}
                  </span>{' '}
                  当前 {r.current} / 目标 {r.target}
                </div>
              ))}
            </div>
          )}

          {/* 触发运行 */}
          <div className="wb-create-form" style={{ marginTop: 20 }} data-testid="wb-eval-run">
            <div className="wb-create-form__head">
              <div className="wb-create-form__badge">▶</div>
              <div>
                <div className="wb-create-form__title">触发一次评估运行（admin）</div>
                <div className="wb-create-form__subtitle">
                  非 admin 用户调用后端返回 403 真实错误；可选落盘路径供 CI 生成趋势图
                </div>
              </div>
            </div>
            <div className="wb-create-form__body">
              <div className="wb-create-form__row">
                <div className="wb-create-form__field wb-create-form__field--grow">
                  <label className="wb-create-form__label" htmlFor="wb-eval-baseline">
                    baseline
                  </label>
                  <select
                    id="wb-eval-baseline"
                    className="wb-input"
                    value={baseline}
                    onChange={(e) => setBaseline(e.target.value)}
                    data-testid="wb-eval-baseline-select"
                  >
                    {BASELINES.map((b) => (
                      <option key={b} value={b}>
                        {b}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="wb-create-form__field wb-create-form__field--grow">
                  <label className="wb-create-form__label" htmlFor="wb-eval-output">
                    output_path（可选）
                  </label>
                  <input
                    id="wb-eval-output"
                    className="wb-input"
                    value={outputPath}
                    onChange={(e) => setOutputPath(e.target.value)}
                    placeholder="如 reports/ihome_eval_report.json"
                    data-testid="wb-eval-output-input"
                  />
                </div>
              </div>
              <div className="wb-create-form__actions">
                <button
                  className="wb-theme-option wb-theme-option--active"
                  type="button"
                  disabled={running}
                  onClick={handleRun}
                  data-testid="wb-eval-run-btn"
                  style={{ width: '100%' }}
                >
                  {running ? '运行中…' : '▶ 运行评估'}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </SuokeLayout>
  );
}
