/**
 * SkillEvolutionPage — Agent Skill 进化周期（2026-10-22）
 *
 * API（对齐 app/api/admin.py）：
 *   GET /api/admin/skill-evolution  平台管理员；触发式（蒸馏 Case 簇 + 三维质控），
 *                                   非只读接口，点击按钮才运行一次。
 *
 * 诚实边界：
 * - 生产由阿里云 FC 定时触发器每日 08:00 调用同一端点，本页用于手动触发与观察；
 * - 无未蒸馏 Case 簇时零 LLM 成本（确定性查询后直接返回）；
 * - 候选簇展示 shortfall（还差几条 Case 达阈值），用于诊断「定时任务恒 0」。
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { apiClient } from '../services/api-client';
import type { SkillEvolutionReport } from '../types/domain';

export default function SkillEvolutionPage() {
  const navigate = useNavigate();
  const [report, setReport] = useState<SkillEvolutionReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchReport = async (dryRun: boolean) => {
    setLoading(true);
    setError(null);
    try {
      const r = await apiClient.runSkillEvolution<SkillEvolutionReport>({ dryRun });
      if (!r.isSuccess || !r.data) {
        const msg =
          r.status === 403
            ? '需要平台管理员权限（403）：仅 admin 可运行进化周期'
            : (r.error ?? `HTTP ${r.status}`);
        throw new Error(msg);
      }
      setReport(r.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  // 首屏只读诊断（dry_run=true，不蒸馏/不评估/零 LLM 成本）；按钮才触发完整周期
  useEffect(() => {
    void fetchReport(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runCycle = () => fetchReport(false);

  const summaryRows: Array<{ label: string; value: string }> = report
    ? [
        { label: '蒸馏簇', value: String(report.clusters_found) },
        { label: '失败簇', value: String(report.failure_clusters_found) },
        ...(report.dry_run
          ? []
          : [
              { label: '新增 Skill', value: String(report.distilled_new.length) },
              { label: '合并已有', value: String(report.merged_existing.length) },
              { label: '反模式 Skill', value: String(report.anti_pattern_distilled.length) },
              { label: '质控评估', value: String(report.evaluated) },
              { label: '晋升 ACTIVE', value: String(report.promoted_draft_to_active.length) },
              { label: '低质归档', value: String(report.archived_low_quality.length) },
            ]),
      ]
    : [];

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-skill-evolution-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">🧬 Skill 进化周期</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-smart-card">
            <div className="wb-smart-card__head">
              <div className="wb-smart-card__room">自进化周期</div>
              <span className="wb-status-chip wb-status-chip--info">触发式</span>
            </div>
            <div
              style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 6 }}
            >
              生产由阿里云 FC 定时触发器每日 08:00 调用同一端点。页面加载执行只读诊断
              （dry_run，零 LLM 成本，不蒸馏不评估）；点击按钮才运行完整周期（可能调用 LLM 蒸馏）。
              阈值 {report?.thresholds.min_cases_per_cluster ?? 3} 条 Case / 簇，单周期上限{' '}
              {report?.limits.max_clusters ?? 50} 簇 / {report?.limits.max_evaluations ?? 200} 次评估。
            </div>
            <div style={{ marginTop: 10 }}>
              <button
                className="wb-theme-option wb-theme-option--active"
                onClick={runCycle}
                disabled={loading}
                type="button"
                data-testid="wb-skill-evolution-run"
              >
                {loading ? '运行中…' : '运行完整周期'}
              </button>
            </div>
          </div>

          {loading && !report && (
            <div className="wb-state" data-testid="wb-skill-evolution-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载诊断数据…</div>
            </div>
          )}

          {error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-skill-evolution-error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
              <button
                className="wb-theme-option wb-theme-option--active"
                onClick={runCycle}
                type="button"
              >
                重试
              </button>
            </div>
          )}

          {report && !loading && (
            <>
              <div className="wb-smart-card" data-testid="wb-skill-evolution-summary">
                <div className="wb-smart-card__head">
                  <div className="wb-smart-card__room">
                    {report.dry_run ? '诊断结果（只读）' : '周期结果（已执行）'}
                  </div>
                  <span
                    className={`wb-status-chip ${
                      report.dry_run ? 'wb-status-chip--info' : 'wb-status-chip--success'
                    }`}
                  >
                    {report.dry_run ? 'dry_run' : '已执行'}
                  </span>
                </div>
                <div className="wb-smart-card__meta" style={{ marginTop: 6 }}>
                  {summaryRows.map((row) => (
                    <span key={row.label}>
                      {row.label} {row.value}
                    </span>
                  ))}
                </div>
              </div>

              <div className="wb-section-label" style={{ marginTop: 20 }}>
                候选簇（未达阈值 · {report.candidate_clusters.length}）
              </div>
              {report.candidate_clusters.length === 0 ? (
                <div className="wb-state" data-testid="wb-skill-evolution-candidates-empty">
                  <div className="wb-state__icon">🧬</div>
                  <div>暂无未蒸馏 Case 簇（Case 分散或已全部蒸馏）</div>
                </div>
              ) : (
                <div data-testid="wb-skill-evolution-candidates">
                  {report.candidate_clusters.map((c, i) => (
                    <div
                      key={`${c.agent_name}-${c.owner_id ?? '-'}-${c.scope ?? '-'}-${i}`}
                      className="wb-smart-card"
                      style={{ marginTop: 8 }}
                    >
                      <div className="wb-smart-card__head">
                        <div className="wb-smart-card__room">{c.agent_name}</div>
                        <span
                          className={`wb-status-chip ${
                            c.shortfall > 0
                              ? 'wb-status-chip--warning'
                              : 'wb-status-chip--success'
                          }`}
                        >
                          {c.shortfall > 0 ? `还差 ${c.shortfall} 条` : '已达阈值'}
                        </span>
                      </div>
                      <div className="wb-smart-card__meta" style={{ marginTop: 6 }}>
                        <span>Case {c.case_count}</span>
                        <span>scope {c.scope || '-'}</span>
                        <span>owner {c.owner_id || '-'}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {report.skipped_reasons.length > 0 && (
                <div
                  className="wb-smart-card"
                  style={{ marginTop: 12 }}
                  data-testid="wb-skill-evolution-skipped"
                >
                  <div className="wb-smart-card__head">
                    <div className="wb-smart-card__room">跳过原因（诚实标注）</div>
                  </div>
                  {report.skipped_reasons.map((reason, i) => (
                    <div key={i} className="wb-smart-card__meta" style={{ marginTop: 4 }}>
                      {reason}
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
