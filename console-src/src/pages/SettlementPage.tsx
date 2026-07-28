/**
 * SettlementPage — 对齐 flutter_app/lib/pages/settlement_page.dart
 *
 * 结构：Scaffold > AppBar(结算) > [项目选择器] > 概览统计 + 异常预警 + 分项明细列表
 * API：GET /api/settlements/project/{projectId}（对齐 app/api/settlements.py）
 *
 * 后端结算字段（app/schemas/settlement.py:SettlementResponse）：
 *   id / project_id / milestone / contract_amount / actual_amount / payable_amount /
 *   status / anomaly_count / critical_anomaly_count / suggested_deduction /
 *   review_required / review_reason / lines[] / settled_at / created_at / updated_at
 *
 * SettlementLine 字段：
 *   id / category / name / contract_amount / change_amount / actual_amount /
 *   status / note / is_anomaly / anomaly_type / anomaly_severity / anomaly_detail
 *
 * 状态映射对齐 settlement_page.dart:420-425：
 *   draft → 草稿 / confirmed → 已确认 / paid → 已支付 / completed → 已完成
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { Settlement, Project } from '../types/domain';

type ChipTone = 'muted' | 'info' | 'success' | 'warning' | 'danger' | 'accent';

// ── 结算状态 → 文案/颜色（对齐 settlement_page.dart:420-425）──
const STATUS_MAP: Record<string, { label: string; tone: ChipTone }> = {
  draft: { label: '草稿', tone: 'muted' },
  confirmed: { label: '已确认', tone: 'info' },
  paid: { label: '已支付', tone: 'success' },
  completed: { label: '已完成', tone: 'success' },
};

// ── 异常严重度 → 文案/颜色 ──
const SEVERITY_MAP: Record<string, { label: string; tone: ChipTone }> = {
  critical: { label: '严重', tone: 'danger' },
  high: { label: '高', tone: 'danger' },
  medium: { label: '中', tone: 'warning' },
  low: { label: '低', tone: 'warning' },
};

function formatCurrency(n: number): string {
  return `¥${(n ?? 0).toLocaleString()}`;
}

export default function SettlementPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');

  // 加载项目列表
  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  // 加载结算单
  const { data: settlement, loading, error, reload } = useAsync<Settlement | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.getSettlement<Settlement>(selectedProjectId);
      if (r.status === 404) return null; // 无结算单
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [selectedProjectId],
  );

  const statusInfo = settlement
    ? STATUS_MAP[settlement.status] ?? { label: settlement.status, tone: 'muted' as ChipTone }
    : null;

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-settlement-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">🏁 结算管理</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-project-picker">
            <select
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              aria-label="选择项目"
              data-testid="wb-settlement-project-select"
            >
              <option value="">选择项目…</option>
              {projects?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {!selectedProjectId && (
            <div className="wb-state" data-testid="wb-settlement-no-project">
              <div className="wb-state__icon">📋</div>
              <div>请先选择项目</div>
            </div>
          )}

          {selectedProjectId && loading && (
            <div className="wb-state" data-testid="wb-settlement-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载结算单中…</div>
            </div>
          )}

          {selectedProjectId && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-settlement-error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>
                重试
              </button>
            </div>
          )}

          {selectedProjectId && !loading && !error && !settlement && (
            <div className="wb-state" data-testid="wb-settlement-empty">
              <div className="wb-state__icon">📝</div>
              <div>该项目暂无结算单</div>
              <div style={{ fontSize: 'var(--font-size-sm)' }}>
                可通过工作台与结算 Agent 对话生成结算单
              </div>
            </div>
          )}

          {selectedProjectId && !loading && !error && settlement && statusInfo && (
            <div data-testid="wb-settlement-content">
              {/* 概览统计 */}
              <div className="wb-settlement-summary">
                <div className="wb-budget-stat">
                  <div className="wb-budget-stat__label">里程碑</div>
                  <div
                    className="wb-budget-stat__value"
                    style={{ fontSize: 'var(--font-size-md)' }}
                  >
                    {settlement.milestone}
                  </div>
                </div>
                <div className="wb-budget-stat">
                  <div className="wb-budget-stat__label">合同金额</div>
                  <div className="wb-budget-stat__value">
                    {formatCurrency(settlement.contract_amount)}
                  </div>
                </div>
                <div className="wb-budget-stat wb-budget-stat--spent">
                  <div className="wb-budget-stat__label">实际金额</div>
                  <div className="wb-budget-stat__value">
                    {formatCurrency(settlement.actual_amount)}
                  </div>
                </div>
                <div className="wb-budget-stat wb-budget-stat--remaining">
                  <div className="wb-budget-stat__label">应付金额</div>
                  <div className="wb-budget-stat__value">
                    {formatCurrency(settlement.payable_amount)}
                  </div>
                </div>
              </div>

              {/* 状态条 */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  marginBottom: 16,
                }}
              >
                <span>状态：</span>
                <span
                  className={`wb-status-chip wb-status-chip--${statusInfo.tone}`}
                  data-testid="wb-settlement-status"
                >
                  {statusInfo.label}
                </span>
                {settlement.settled_at && (
                  <span style={{ fontSize: 'var(--font-size-sm)', color: 'var(--text-muted)' }}>
                    结算于 {new Date(settlement.settled_at).toLocaleDateString()}
                  </span>
                )}
              </div>

              {/* 异常预警（对齐 settlement_page.dart 异常检测 tab）*/}
              {settlement.anomaly_count > 0 && (
                <div
                  className="wb-settlement-alert"
                  data-testid="wb-settlement-anomaly-alert"
                >
                  ⚠ 检测到 {settlement.anomaly_count} 项异常
                  {settlement.critical_anomaly_count > 0 &&
                    `（其中 ${settlement.critical_anomaly_count} 项严重）`}
                  {settlement.suggested_deduction > 0 &&
                    `，建议扣减 ${formatCurrency(settlement.suggested_deduction)}`}
                </div>
              )}

              {/* 需复核提示 */}
              {settlement.review_required && (
                <div
                  className="wb-settlement-alert wb-settlement-alert--review"
                  data-testid="wb-settlement-review-alert"
                >
                  🔍 需人工复核
                  {settlement.review_reason && `：${settlement.review_reason}`}
                </div>
              )}

              {/* 分项明细 */}
              <div className="wb-section-label">
                分项明细（{settlement.lines?.length ?? 0} 项）
              </div>
              {settlement.lines && settlement.lines.length > 0 ? (
                settlement.lines.map((line, i) => {
                  const sevInfo = line.anomaly_severity
                    ? SEVERITY_MAP[line.anomaly_severity] ?? {
                        label: line.anomaly_severity,
                        tone: 'warning' as ChipTone,
                      }
                    : null;
                  return (
                    <div
                      key={line.id}
                      className={`wb-sline ${line.is_anomaly ? 'wb-sline--anomaly' : ''}`}
                      data-testid={`wb-settlement-line--${i}`}
                    >
                      <div>
                        <div className="wb-sline__name">{line.name}</div>
                        <div className="wb-sline__cat">{line.category}</div>
                        {line.is_anomaly && (
                          <div className="wb-sline__anomaly">
                            ⚠ 异常
                            {line.anomaly_type && ` · ${line.anomaly_type}`}
                            {sevInfo && ` · ${sevInfo.label}`}
                            {line.anomaly_detail && ` · ${line.anomaly_detail}`}
                          </div>
                        )}
                        {line.note && !line.is_anomaly && (
                          <div
                            style={{
                              fontSize: 'var(--font-size-xs)',
                              color: 'var(--text-muted)',
                              marginTop: 4,
                            }}
                          >
                            {line.note}
                          </div>
                        )}
                      </div>
                      <div className="wb-sline__amounts">
                        <div className="wb-sline__actual">
                          {formatCurrency(line.actual_amount)}
                        </div>
                        <div className="wb-sline__contract">
                          合同 {formatCurrency(line.contract_amount)}
                        </div>
                        {line.change_amount !== 0 && (
                          <div
                            className="wb-sline__contract"
                            style={{
                              color:
                                line.change_amount > 0
                                  ? 'var(--warning)'
                                  : 'var(--success)',
                            }}
                          >
                            变更 {line.change_amount > 0 ? '+' : ''}
                            {formatCurrency(line.change_amount)}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="wb-state">
                  <div>暂无分项明细</div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
