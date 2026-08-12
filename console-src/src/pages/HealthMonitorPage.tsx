/**
 * HealthMonitorPage — 智能家居健康监测（v1.13.x 前端缺口补齐 B2）
 *
 * 结构：Scaffold > AppBar(健康监测) > 项目选择器 > 健康报告（汇总 + 空气质量 + 预警 + 建议）
 * API（对齐 app/api/health.py，前缀 /api/health-monitor；flag 关闭返回 503）：
 *   GET /api/health-monitor/report/{projectId}               健康报告
 *   GET /api/health-monitor/records/project/{projectId}     健康记录
 *
 * 诚实降级：503（health_monitor_enabled=False）时错误文案真实展示，不伪造数据。
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { HealthReport, Project } from '../types/domain';

type ChipTone = 'muted' | 'info' | 'success' | 'warning' | 'danger' | 'accent';

const ALERT_TONE: Record<string, ChipTone> = {
  normal: 'success',
  warning: 'warning',
  critical: 'danger',
  high: 'danger',
  medium: 'warning',
  low: 'info',
};

function fmtDate(v: string | null | undefined): string {
  if (!v) return '—';
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('zh-CN', { hour12: false });
}

export default function HealthMonitorPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState('');

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  const { data: report, loading, error, reload } = useAsync<HealthReport | null>(async () => {
    if (!selectedProjectId) return null;
    const r = await apiClient.getHealthReport<HealthReport>(selectedProjectId);
    if (!r.isSuccess || !r.data) throw new Error(r.error ?? `HTTP ${r.status}`);
    return r.data;
  }, [selectedProjectId]);

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-health-monitor-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">🩺 健康监测</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-project-picker">
            <select
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              aria-label="选择项目"
              data-testid="wb-health-project-select"
            >
              <option value="">选择项目…</option>
              {projects?.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </div>

          {!selectedProjectId && (
            <div className="wb-state"><div className="wb-state__icon">📋</div><div>请先选择项目</div></div>
          )}
          {selectedProjectId && loading && (
            <div className="wb-state"><div className="wb-state__icon">⏳</div><div>加载健康报告中…</div></div>
          )}
          {selectedProjectId && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-health-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-btn wb-btn--sm" onClick={() => reload()} type="button">重试</button>
            </div>
          )}

          {selectedProjectId && !loading && !error && report && (
            <div data-testid="wb-health-content">
              {/* 汇总 */}
              <div className="wb-grid wb-grid--2" data-testid="wb-health-summary">
                <div className="wb-stat-card">
                  <div className="wb-stat-card__label">监测记录</div>
                  <div className="wb-stat-card__value">{report.total_records}</div>
                </div>
                <div className="wb-stat-card">
                  <div className="wb-stat-card__label">预警数</div>
                  <div className="wb-stat-card__value">{report.alert_records}</div>
                </div>
                {report.sleep_avg_score !== null && report.sleep_avg_score !== undefined && (
                  <div className="wb-stat-card">
                    <div className="wb-stat-card__label">睡眠均分</div>
                    <div className="wb-stat-card__value">{report.sleep_avg_score}</div>
                  </div>
                )}
              </div>
              {report.summary && (
                <div className="wb-card" data-testid="wb-health-summary-text">
                  <div className="wb-card__title">监测摘要</div>
                  <div style={{ fontSize: 13, lineHeight: 1.6 }}>{report.summary}</div>
                </div>
              )}

              {/* 最新空气质量 */}
              {report.latest_air_quality && (
                <div className="wb-card" data-testid="wb-health-air-quality">
                  <div className="wb-card__title">
                    最新空气质量（{report.latest_air_quality.room_name}）
                    <span className={`wb-status-chip wb-status-chip--${ALERT_TONE[report.latest_air_quality.aqi_level] ?? 'muted'}`} style={{ marginLeft: 8 }}>
                      AQI {report.latest_air_quality.aqi_index} · {report.latest_air_quality.aqi_level}
                    </span>
                  </div>
                  <div className="wb-actions" style={{ gap: 16 }}>
                    <span className="wb-list-row__sub">PM2.5：{report.latest_air_quality.pm25} μg/m³</span>
                    <span className="wb-list-row__sub">CO₂：{report.latest_air_quality.co2} ppm</span>
                    <span className="wb-list-row__sub">甲醛：{report.latest_air_quality.formaldehyde} μg/m³</span>
                    <span className="wb-list-row__sub">温度：{report.latest_air_quality.temperature}℃</span>
                    <span className="wb-list-row__sub">湿度：{report.latest_air_quality.humidity}%</span>
                  </div>
                  <div className="wb-list-row__sub" style={{ marginTop: 8 }}>
                    记录时间：{fmtDate(report.latest_air_quality.recorded_at)}
                  </div>
                </div>
              )}

              {/* 近期预警 */}
              <div className="wb-card" data-testid="wb-health-alerts">
                <div className="wb-card__title">近期预警（{report.recent_alerts.length}）</div>
                {report.recent_alerts.length === 0 ? (
                  <div className="wb-state"><div className="wb-state__icon">✅</div><div>暂无预警</div></div>
                ) : (
                  report.recent_alerts.map((a, i) => (
                    <div className="wb-list-row" key={i}>
                      <span className={`wb-status-chip wb-status-chip--${ALERT_TONE[a.alert_level] ?? 'muted'}`}>
                        {a.alert_level}
                      </span>
                      <span className="wb-list-row__main">{a.monitor_type}</span>
                      <span className="wb-list-row__sub">{a.alert_message ?? '—'}</span>
                      <span className="wb-list-row__sub">{fmtDate(a.recorded_at)}</span>
                    </div>
                  ))
                )}
              </div>

              {/* 建议 */}
              {report.recommendations.length > 0 && (
                <div className="wb-card" data-testid="wb-health-recommendations">
                  <div className="wb-card__title">健康建议</div>
                  {report.recommendations.map((r, i) => (
                    <div key={i} style={{ fontSize: 13, marginBottom: 6 }}>• {r}</div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
