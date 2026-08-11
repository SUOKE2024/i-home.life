/**
 * EnergyPage — 能耗监测（v1.13.x 前端缺口补齐）
 *
 * 结构：Scaffold > AppBar(能耗监测) > 项目选择器 > 报告摘要 + 能耗记录 + 设备排行 + 节能建议
 * API（对齐 app/api/energy.py，前缀 /api/energy）：
 *   GET  /api/energy/records/project/{projectId}   项目能耗记录
 *   GET  /api/energy/report/{schemeId}             方案能耗报告（趋势/设备排行/节能建议）
 *   GET  /api/energy/tips/{schemeId}               节能建议
 *   PATCH /api/energy/tips/{tipId}/apply           采纳节能建议
 *
 * 诚实降级：flag 未启用（energy_monitor_enabled=False）时后端 503/404，页面展示灰度提示。
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type {
  EnergyMonitorItem,
  EnergyReport,
  EnergySavingTip,
  Project,
} from '../types/domain';

type ChipTone = 'muted' | 'info' | 'success' | 'warning' | 'danger' | 'accent';

const PRIORITY_META: Record<string, { label: string; tone: ChipTone }> = {
  high: { label: '高', tone: 'danger' },
  medium: { label: '中', tone: 'warning' },
  low: { label: '低', tone: 'muted' },
};

const PERIOD_LABELS: Record<string, string> = {
  daily: '日',
  weekly: '周',
  monthly: '月',
};

function flagGuardMessage(status: number, error?: string): string {
  if (status === 404 || status === 503) {
    return `功能未启用（灰度 flag 默认关闭）：${error ?? `HTTP ${status}`}`;
  }
  return error ?? `HTTP ${status}`;
}

function fmtMoney(v: number | null | undefined): string {
  return `¥${(v ?? 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`;
}

function fmtKwh(v: number | null | undefined): string {
  return `${(v ?? 0).toLocaleString('zh-CN', { maximumFractionDigits: 1 })} kWh`;
}

export default function EnergyPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [schemeId, setSchemeId] = useState<string>('');
  const [actionId, setActionId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  const { data: records, loading, error, reload } = useAsync<EnergyMonitorItem[] | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.listEnergyRecords<EnergyMonitorItem[]>(selectedProjectId);
      if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
      return r.data;
    },
    [selectedProjectId],
  );

  // 默认取最新记录的 scheme_id 拉报告；空记录时展示空态
  useEffect(() => {
    if (!schemeId && records && records.length > 0) {
      setSchemeId(records[0].scheme_id);
    }
  }, [records, schemeId]);

  const { data: report } = useAsync<EnergyReport | null>(
    async () => {
      if (!schemeId) return null;
      const r = await apiClient.getEnergyReport<EnergyReport>(schemeId);
      if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
      return r.data;
    },
    [schemeId],
  );

  const { data: tips } = useAsync<EnergySavingTip[] | null>(
    async () => {
      if (!schemeId) return null;
      const r = await apiClient.listEnergyTips<EnergySavingTip[]>(schemeId);
      if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
      return r.data;
    },
    [schemeId],
  );

  async function handleApplyTip(tipId: string) {
    setActionId(tipId);
    setActionError(null);
    try {
      const r = await apiClient.applyEnergyTip(tipId);
      if (!r.isSuccess) throw new Error(r.error ?? '采纳失败');
      await reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionId(null);
    }
  }

  const visibleTips = report?.tips?.length ? report.tips : (tips ?? []);
  const pendingTips = visibleTips.filter((t) => t.status === 'pending');

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-energy-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">⚡ 能耗监测</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-project-picker">
            <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)} aria-label="选择项目" data-testid="wb-energy-project-select">
              <option value="">选择项目…</option>
              {projects?.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </div>

          {!selectedProjectId && (
            <div className="wb-state" data-testid="wb-energy-no-project">
              <div className="wb-state__icon">📋</div><div>请先选择项目</div>
            </div>
          )}
          {selectedProjectId && loading && (
            <div className="wb-state" data-testid="wb-energy-loading">
              <div className="wb-state__icon">⏳</div><div>加载能耗数据中…</div>
            </div>
          )}
          {selectedProjectId && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-energy-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>重试</button>
            </div>
          )}

          {selectedProjectId && !loading && !error && (!records || records.length === 0) && (
            <div className="wb-state" data-testid="wb-energy-empty">
              <div className="wb-state__icon">⚡</div><div>暂无能耗记录（项目尚未上报能耗数据）</div>
            </div>
          )}

          {selectedProjectId && !loading && !error && records && records.length > 0 && (
            <div data-testid="wb-energy-content">
              {actionError && (
                <div className="wb-alert" data-testid="wb-energy-action-error">⚠ {actionError}</div>
              )}

              {/* 报告摘要 */}
              {report && (
                <div className="wb-grid wb-grid--2" data-testid="wb-energy-report">
                  <div className="wb-stat-card">
                    <div className="wb-stat-card__label">总能耗（{PERIOD_LABELS[report.period] ?? report.period}）</div>
                    <div className="wb-stat-card__value">{fmtKwh(report.total_consumption_kwh)}</div>
                  </div>
                  <div className="wb-stat-card">
                    <div className="wb-stat-card__label">预估电费</div>
                    <div className="wb-stat-card__value">{fmtMoney(report.estimated_cost)}</div>
                  </div>
                  <div className="wb-stat-card">
                    <div className="wb-stat-card__label">碳排放</div>
                    <div className="wb-stat-card__value">{report.carbon_footprint_kg?.toFixed(1)} kgCO₂</div>
                  </div>
                  <div className="wb-stat-card">
                    <div className="wb-stat-card__label">待机能耗占比</div>
                    <div className="wb-stat-card__value">{report.standby_ratio?.toFixed(1)}%</div>
                  </div>
                </div>
              )}

              {/* 设备能耗排行 */}
              {report && report.device_ranking && report.device_ranking.length > 0 && (
                <div className="wb-card" data-testid="wb-energy-ranking">
                  <div className="wb-card__title">设备能耗排行</div>
                  {report.device_ranking.map((d, idx) => (
                    <div className="wb-list-row" key={`${d.device_name}-${idx}`}>
                      <span className="wb-list-row__main">{d.device_name}</span>
                      <span className="wb-list-row__sub">{d.percentage?.toFixed(1)}%</span>
                      <span className="wb-status-chip wb-status-chip--info">{fmtKwh(d.consumption_kwh)}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* 节能建议 */}
              {visibleTips.length > 0 && (
                <div className="wb-card" data-testid="wb-energy-tips">
                  <div className="wb-card__title">节能建议</div>
                  {visibleTips.map((tip) => (
                    <div className="wb-list-row" key={tip.id}>
                      <span className="wb-list-row__main">{tip.suggestion}</span>
                      {tip.potential_saving_pct != null && (
                        <span className="wb-status-chip wb-status-chip--success">省 {tip.potential_saving_pct}%</span>
                      )}
                      {(() => { const m = PRIORITY_META[tip.priority]; return m ? (<span className={`wb-status-chip wb-status-chip--${m.tone}`}>{m.label}</span>) : null; })()}
                      {tip.status === 'pending' && (
                        <button
                          className="wb-btn wb-btn--sm"
                          disabled={actionId === tip.id}
                          onClick={() => handleApplyTip(tip.id)}
                          type="button"
                        >{actionId === tip.id ? '处理中…' : '采纳'}</button>
                      )}
                      {tip.status !== 'pending' && (
                        <span className="wb-status-chip wb-status-chip--success">已采纳</span>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* 能耗记录列表 */}
              <div className="wb-card" data-testid="wb-energy-records">
                <div className="wb-card__title">能耗记录（{records.length}）</div>
                <table className="wb-table">
                  <thead>
                    <tr>
                      <th>周期</th><th>总能耗</th><th>峰值功率</th><th>平均功率</th><th>待机能耗</th><th>电费</th><th>时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    {records.map((r) => (
                      <tr key={r.id}>
                        <td>{PERIOD_LABELS[r.period] ?? r.period}</td>
                        <td>{fmtKwh(r.total_consumption_kwh)}</td>
                        <td>{r.peak_power_w} W</td>
                        <td>{r.avg_power_w} W</td>
                        <td>{fmtKwh(r.standby_consumption_kwh)}</td>
                        <td>{fmtMoney(r.estimated_cost)}</td>
                        <td>{new Date(r.recorded_at).toLocaleString('zh-CN')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {pendingTips.length > 0 && (
                <div className="wb-state" data-testid="wb-energy-pending-note">
                  <div className="wb-state__icon">💡</div>
                  <div>{pendingTips.length} 条节能建议待采纳，预计可降低待机能耗</div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
