/**
 * SoftFurnishingPage — 软装设计
 *
 * 结构：Scaffold > AppBar(软装设计) > [项目选择器] > 风格筛选 + 方案卡片列表（含预算进度）
 * API：GET /api/soft-furnishing/schemes/project/{projectId}（对齐 app/api/soft_furnishing.py）
 *
 * 后端字段（app/schemas/soft_furnishing.py:SoftFurnishingSchemeResponse）：
 *   id / project_id / room_name / style / color_scheme / budget_total /
 *   budget_used / status / notes / created_at / updated_at
 *
 * style（app/models/soft_furnishing.py）：modern | 现代 | 北欧 | 新中式 | 美式 | 法式 | 工业 | 日式
 */

import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { SoftFurnishingScheme, Project } from '../types/domain';

const STYLE_FILTERS: Array<{ key: string; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'modern', label: '现代' },
  { key: '北欧', label: '北欧' },
  { key: '新中式', label: '新中式' },
  { key: '日式', label: '日式' },
  { key: '法式', label: '法式' },
  { key: '工业', label: '工业' },
  { key: '美式', label: '美式' },
];

export default function SoftFurnishingPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [filterStyle, setFilterStyle] = useState<string>('all');

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  const { data: schemes, loading, error, reload } = useAsync<SoftFurnishingScheme[] | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.getSoftFurnishingSchemes<SoftFurnishingScheme[]>(selectedProjectId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [selectedProjectId],
  );

  const filteredSchemes = useMemo(() => {
    if (!schemes) return [];
    if (filterStyle === 'all') return schemes;
    // style 可能是 modern 或 中文，modern 归类为"现代"
    return schemes.filter((s) => {
      if (filterStyle === 'modern') return s.style === 'modern' || s.style === '现代';
      return s.style === filterStyle;
    });
  }, [schemes, filterStyle]);

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-softfurnishing-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">🛋 软装设计</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-project-picker">
            <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)} aria-label="选择项目" data-testid="wb-softfurnishing-project-select">
              <option value="">选择项目…</option>
              {projects?.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </div>

          {!selectedProjectId && (
            <div className="wb-state" data-testid="wb-softfurnishing-no-project">
              <div className="wb-state__icon">📋</div><div>请先选择项目</div>
            </div>
          )}
          {selectedProjectId && loading && (
            <div className="wb-state" data-testid="wb-softfurnishing-loading">
              <div className="wb-state__icon">⏳</div><div>加载软装方案中…</div>
            </div>
          )}
          {selectedProjectId && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-softfurnishing-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>重试</button>
            </div>
          )}
          {selectedProjectId && !loading && !error && (schemes?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-softfurnishing-empty">
              <div className="wb-state__icon">🛋</div><div>暂无软装方案</div>
              <div style={{ fontSize: 'var(--font-size-sm)' }}>可通过工作台与软装 Agent 对话生成方案</div>
            </div>
          )}

          {selectedProjectId && !loading && !error && (schemes?.length ?? 0) > 0 && (
            <div data-testid="wb-softfurnishing-content">
              <div className="wb-task-filter" role="tablist" aria-label="风格筛选">
                {STYLE_FILTERS.map((f) => (
                  <button key={f.key} type="button" role="tab" aria-selected={filterStyle === f.key}
                    className={`wb-task-filter__chip ${filterStyle === f.key ? 'wb-task-filter__chip--active' : ''}`}
                    onClick={() => setFilterStyle(f.key)} data-testid={`wb-softfurnishing-filter--${f.key}`}>
                    {f.label}
                  </button>
                ))}
              </div>

              <div className="wb-section-label">软装方案（{filteredSchemes.length}/{schemes!.length}）</div>
              {filteredSchemes.map((s, i) => {
                const usedPercent = s.budget_total > 0 ? Math.round((s.budget_used / s.budget_total) * 100) : 0;
                return (
                  <div key={s.id} className="wb-smart-card" data-testid={`wb-softfurnishing-item--${i}`}>
                    <div className="wb-smart-card__head">
                      <div className="wb-smart-card__room">{s.room_name}</div>
                      <span className="wb-status-chip wb-status-chip--accent">{s.style === 'modern' ? '现代' : s.style}</span>
                    </div>
                    <div className="wb-smart-card__meta">
                      <span>💰 预算 ¥{s.budget_total.toLocaleString()}</span>
                      <span style={{ color: usedPercent >= 90 ? 'var(--danger)' : usedPercent >= 70 ? 'var(--warning)' : 'var(--success)' }}>
                        已用 ¥{s.budget_used.toLocaleString()} ({usedPercent}%)
                      </span>
                    </div>
                    {/* 预算进度条 */}
                    <div className="wb-progress-bar" style={{ marginTop: 8 }}>
                      <div className="wb-progress-bar__fill" style={{
                        width: `${Math.min(usedPercent, 100)}%`,
                        background: usedPercent >= 90 ? 'var(--danger)' : usedPercent >= 70 ? 'var(--warning)' : 'var(--success)',
                      }} />
                    </div>
                    {s.notes && (
                      <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 6 }}>{s.notes}</div>
                    )}
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
