/**
 * QualityPage — 质检
 *
 * 结构：Scaffold > AppBar(质检) > [项目选择器] > 阶段 tab + 双视图（质检清单 / 质量问题）
 * API：
 *   GET /api/construction/quality-checklist/{phase}                          — 阶段质检清单
 *   GET /api/construction/quality-issues/{projectId}?phase=&status=&severity= — 项目质量问题列表
 *
 * 后端字段（app/schemas/quality.py:QualityIssueResponse）：
 *   phase / category / description / severity / status / location / standard /
 *   resolution / detected_by / resolved_by / verified_by
 *
 * 注意：quality 端点位于 app/api/construction.py（无独立 quality.py 路由文件）。
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { Project, QualityIssue, QualityChecklist } from '../types/domain';

const PHASES: Array<{ key: string; label: string; emoji: string }> = [
  { key: 'water_electricity', label: '水电', emoji: '⚡' },
  { key: 'waterproof', label: '防水', emoji: '💧' },
  { key: 'masonry', label: '泥瓦', emoji: '🧱' },
  { key: 'painting', label: '油漆', emoji: '🎨' },
  { key: 'acceptance', label: '竣工', emoji: '✓' },
  { key: 'completion', label: '完工', emoji: '🏠' },
];

const SEVERITY_LABELS: Record<string, { label: string; cls: string }> = {
  low: { label: '轻微', cls: 'pending' },
  medium: { label: '中等', cls: 'active' },
  high: { label: '严重', cls: 'error' },
  critical: { label: '致命', cls: 'error' },
};

const ISSUE_STATUS_LABELS: Record<string, { label: string; cls: string }> = {
  open: { label: '待处理', cls: 'pending' },
  in_progress: { label: '整改中', cls: 'active' },
  resolved: { label: '已整改', cls: 'completed' },
  verified: { label: '已验收', cls: 'completed' },
  closed: { label: '已关闭', cls: 'completed' },
};

type View = 'checklist' | 'issues';

export default function QualityPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [activePhase, setActivePhase] = useState<string>('water_electricity');
  const [view, setView] = useState<View>('checklist');

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  // 质检清单（阶段维度，与项目无关）
  const {
    data: checklist,
    loading: clLoading,
    error: clError,
    reload: clReload,
  } = useAsync<QualityChecklist | null>(
    async () => {
      const r = await apiClient.getQualityChecklist<QualityChecklist>(activePhase);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [activePhase],
  );

  // 质量问题列表（项目 + 阶段筛选）
  const {
    data: issues,
    loading: issLoading,
    error: issError,
    reload: issReload,
  } = useAsync<QualityIssue[] | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.getQualityIssues<QualityIssue[]>(selectedProjectId, {
        phase: activePhase,
      });
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [selectedProjectId, activePhase],
  );

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-quality-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">✅ 质检</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-project-picker">
            <select
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              aria-label="选择项目"
              data-testid="wb-quality-project-select"
            >
              <option value="">选择项目…</option>
              {projects?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {/* 阶段 tab */}
          <div
            className="wb-task-filter"
            role="tablist"
            aria-label="施工阶段"
            data-testid="wb-quality-phases"
            style={{ marginBottom: 8 }}
          >
            {PHASES.map((p) => (
              <button
                key={p.key}
                type="button"
                role="tab"
                aria-selected={activePhase === p.key}
                className={`wb-task-filter__chip ${activePhase === p.key ? 'wb-task-filter__chip--active' : ''}`}
                onClick={() => setActivePhase(p.key)}
                data-testid={`wb-quality-phase--${p.key}`}
              >
                {p.emoji} {p.label}
              </button>
            ))}
          </div>

          {/* 视图切换 */}
          <div
            className="wb-task-filter"
            role="tablist"
            aria-label="视图切换"
            data-testid="wb-quality-views"
            style={{ marginBottom: 12 }}
          >
            <button
              type="button"
              role="tab"
              aria-selected={view === 'checklist'}
              className={`wb-task-filter__chip ${view === 'checklist' ? 'wb-task-filter__chip--active' : ''}`}
              onClick={() => setView('checklist')}
              data-testid="wb-quality-view--checklist"
            >
              📋 质检清单
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={view === 'issues'}
              className={`wb-task-filter__chip ${view === 'issues' ? 'wb-task-filter__chip--active' : ''}`}
              onClick={() => setView('issues')}
              data-testid="wb-quality-view--issues"
            >
              ⚠ 质量问题
            </button>
          </div>

          {/* 质检清单视图 */}
          {view === 'checklist' && (
            <div data-testid="wb-quality-checklist-view">
              {clLoading && (
                <div className="wb-state" data-testid="wb-quality-checklist-loading">
                  <div className="wb-state__icon">⏳</div>
                  <div>加载质检清单…</div>
                </div>
              )}
              {clError && !clLoading && (
                <div className="wb-state wb-state--error" data-testid="wb-quality-checklist-error">
                  <div className="wb-state__icon">⚠</div>
                  <div>{clError}</div>
                  <button className="wb-theme-option wb-theme-option--active" onClick={clReload}>
                    重试
                  </button>
                </div>
              )}
              {checklist && !clLoading && !clError && (
                <div data-testid="wb-quality-checklist-content">
                  <div className="wb-section-label">
                    {PHASES.find((p) => p.key === checklist.phase)?.label ?? checklist.phase}阶段质检清单（{checklist.total_items}）
                  </div>
                  {checklist.checklist.length === 0 ? (
                    <div className="wb-state" data-testid="wb-quality-checklist-empty">
                      <div className="wb-state__icon">📋</div>
                      <div>该阶段暂无预设质检清单</div>
                    </div>
                  ) : (
                    checklist.checklist.map((item, i) => (
                      <div
                        key={i}
                        className="wb-project-card"
                        data-testid={`wb-quality-checklist-item--${i}`}
                      >
                        <div className="wb-project-card__title">{item.item}</div>
                        <div className="wb-project-card__meta">
                          <span className="wb-project-card__meta-item">标准: {item.standard}</span>
                        </div>
                        <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 4 }}>
                          🔍 检验方法: {item.method}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          )}

          {/* 质量问题视图 */}
          {view === 'issues' && (
            <div data-testid="wb-quality-issues-view">
              {!selectedProjectId && (
                <div className="wb-state" data-testid="wb-quality-issues-no-project">
                  <div className="wb-state__icon">📋</div>
                  <div>请先选择项目</div>
                </div>
              )}
              {selectedProjectId && issLoading && (
                <div className="wb-state" data-testid="wb-quality-issues-loading">
                  <div className="wb-state__icon">⏳</div>
                  <div>加载质量问题…</div>
                </div>
              )}
              {selectedProjectId && issError && !issLoading && (
                <div className="wb-state wb-state--error" data-testid="wb-quality-issues-error">
                  <div className="wb-state__icon">⚠</div>
                  <div>{issError}</div>
                  <button className="wb-theme-option wb-theme-option--active" onClick={issReload}>
                    重试
                  </button>
                </div>
              )}
              {selectedProjectId && !issLoading && !issError && (issues?.length ?? 0) === 0 && (
                <div className="wb-state" data-testid="wb-quality-issues-empty">
                  <div className="wb-state__icon">✅</div>
                  <div>该阶段暂无质量问题</div>
                </div>
              )}
              {selectedProjectId && !issLoading && !issError && (issues?.length ?? 0) > 0 && (
                <div data-testid="wb-quality-issues-content">
                  <div className="wb-section-label">质量问题（{issues!.length}）</div>
                  {issues!.map((iss, i) => {
                    const sev = SEVERITY_LABELS[iss.severity] ?? { label: iss.severity, cls: 'pending' };
                    const st = ISSUE_STATUS_LABELS[iss.status] ?? { label: iss.status, cls: 'pending' };
                    return (
                      <div
                        key={iss.id}
                        className="wb-project-card"
                        data-testid={`wb-quality-issue--${i}`}
                      >
                        <div className="wb-project-card__title">
                          {iss.category}
                          <span
                            style={{
                              fontSize: 'var(--font-size-xs)',
                              color: 'var(--text-muted)',
                              marginLeft: 8,
                            }}
                          >
                            {iss.location ? `· ${iss.location}` : ''}
                          </span>
                        </div>
                        <div style={{ fontSize: 'var(--font-size-sm)', marginTop: 4 }}>
                          {iss.description}
                        </div>
                        {iss.standard && (
                          <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 4 }}>
                            📏 标准: {iss.standard}
                          </div>
                        )}
                        <div className="wb-project-card__meta" style={{ marginTop: 8 }}>
                          <span
                            className={`wb-status-badge wb-status--${sev.cls}`}
                            data-testid={`wb-quality-issue-severity--${i}`}
                          >
                            {sev.label}
                          </span>
                          <span
                            className={`wb-status-badge wb-status--${st.cls}`}
                            data-testid={`wb-quality-issue-status--${i}`}
                          >
                            {st.label}
                          </span>
                          <span
                            style={{
                              fontSize: 'var(--font-size-xs)',
                              color: 'var(--text-muted)',
                              marginLeft: 'auto',
                            }}
                          >
                            {iss.detected_by === 'manual' ? '👤 人工' : '🤖 AI'}
                          </span>
                        </div>
                        {iss.resolution && (
                          <div
                            style={{
                              fontSize: 'var(--font-size-xs)',
                              color: 'var(--text-muted)',
                              marginTop: 8,
                              padding: 8,
                              background: 'var(--surface2)',
                              borderRadius: 'var(--radius-md)',
                            }}
                          >
                            ✓ 整改: {iss.resolution}
                            {iss.resolved_by && `（${iss.resolved_by}）`}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
