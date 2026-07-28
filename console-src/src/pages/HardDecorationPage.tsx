/**
 * HardDecorationPage — 硬装设计
 *
 * 结构：Scaffold > AppBar(硬装设计) > [项目选择器] > 方案类型筛选 + 方案卡片列表
 * API：GET /api/hard-decoration/schemes/project/{projectId}
 *      （对齐 app/api/hard_decoration.py:46）
 *
 * 后端字段（app/schemas/hard_decoration.py:HardDecorationSchemeResponse）：
 *   room_name / scheme_type(floor/wall/ceiling) / floor_area / wall_area /
 *   ceiling_area / total_budget / status / notes
 */

import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { Project, HardDecorationScheme } from '../types/domain';

const SCHEME_TYPES: Array<{ key: string; label: string; emoji: string }> = [
  { key: 'all', label: '全部', emoji: '📋' },
  { key: 'floor', label: '地面', emoji: '🔲' },
  { key: 'wall', label: '墙面', emoji: '🧱' },
  { key: 'ceiling', label: '吊顶', emoji: '⬆' },
];

const STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  active: '进行中',
  completed: '已完成',
  approved: '已确认',
};

export default function HardDecorationPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [selectedType, setSelectedType] = useState<string>('all');

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  const { data: schemes, loading, error, reload } = useAsync<HardDecorationScheme[] | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.getHardDecorationSchemes<HardDecorationScheme[]>(selectedProjectId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [selectedProjectId],
  );

  const filtered = useMemo(() => {
    if (!schemes) return [];
    if (selectedType === 'all') return schemes;
    return schemes.filter((s) => s.scheme_type === selectedType);
  }, [schemes, selectedType]);

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-harddecoration-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">🎨 硬装设计</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-project-picker">
            <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)} aria-label="选择项目" data-testid="wb-harddecoration-project-select">
              <option value="">选择项目…</option>
              {projects?.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </div>

          {!selectedProjectId && (
            <div className="wb-state" data-testid="wb-harddecoration-no-project">
              <div className="wb-state__icon">📋</div><div>请先选择项目</div>
            </div>
          )}

          {selectedProjectId && loading && (
            <div className="wb-state" data-testid="wb-harddecoration-loading">
              <div className="wb-state__icon">⏳</div><div>加载硬装方案中…</div>
            </div>
          )}
          {selectedProjectId && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-harddecoration-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>重试</button>
            </div>
          )}
          {selectedProjectId && !loading && !error && (schemes?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-harddecoration-empty">
              <div className="wb-state__icon">🎨</div>
              <div>暂无硬装方案</div>
              <div style={{ fontSize: 'var(--font-size-sm)' }}>可通过工作台与设计 Agent 对话生成</div>
            </div>
          )}

          {selectedProjectId && !loading && !error && (schemes?.length ?? 0) > 0 && (
            <div data-testid="wb-harddecoration-content">
              <div className="wb-task-filter" role="tablist" aria-label="方案类型筛选" data-testid="wb-harddecoration-filters">
                {SCHEME_TYPES.map((t) => (
                  <button
                    key={t.key}
                    type="button"
                    role="tab"
                    aria-selected={selectedType === t.key}
                    className={`wb-task-filter__chip ${selectedType === t.key ? 'wb-task-filter__chip--active' : ''}`}
                    onClick={() => setSelectedType(t.key)}
                    data-testid={`wb-harddecoration-filter--${t.key}`}
                  >
                    {t.emoji} {t.label}
                  </button>
                ))}
              </div>

              <div className="wb-section-label">硬装方案（{filtered.length}）</div>

              {filtered.map((s, i) => (
                <div key={s.id} className="wb-project-card" data-testid={`wb-harddecoration-item--${i}`}>
                  <div className="wb-project-card__title">
                    {s.room_name}
                    <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginLeft: 8 }}>
                      {SCHEME_TYPES.find((t) => t.key === s.scheme_type)?.label ?? s.scheme_type}
                    </span>
                  </div>
                  <div className="wb-project-card__meta">
                    {s.floor_area > 0 && <span className="wb-project-card__meta-item">🔲 地面 {s.floor_area}㎡</span>}
                    {s.wall_area > 0 && <span className="wb-project-card__meta-item">🧱 墙面 {s.wall_area}㎡</span>}
                    {s.ceiling_area > 0 && <span className="wb-project-card__meta-item">⬆ 吊顶 {s.ceiling_area}㎡</span>}
                    {s.total_budget > 0 && <span className="wb-project-card__meta-item">💰 ¥{s.total_budget.toLocaleString()}</span>}
                  </div>
                  <div className="wb-project-card__meta">
                    <span className={`wb-status-badge wb-status--${s.status}`} data-testid={`wb-harddecoration-status--${i}`}>
                      {STATUS_LABELS[s.status] ?? s.status}
                    </span>
                  </div>
                  {s.notes && (
                    <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 4 }}>
                      📝 {s.notes}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
