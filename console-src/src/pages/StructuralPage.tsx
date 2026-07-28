/**
 * StructuralPage — 土建结构
 *
 * 结构：Scaffold > AppBar(土建结构) > [项目选择器] > [构件 tab: 墙/梁/柱/板] > 构件卡片列表
 * API：GET /api/structural/projects/{projectId}/{walls|beams|columns|slabs}
 *      （对齐 app/api/structural.py，4 类构件 CRUD 的列表端点）
 *
 * 后端字段（app/schemas/structural.py）：
 *   LoadBearingWall / Beam / StructuralColumn / FloorSlab
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type {
  Project,
  LoadBearingWall,
  Beam,
  StructuralColumn,
  FloorSlab,
} from '../types/domain';

type Kind = 'walls' | 'beams' | 'columns' | 'slabs';

const TABS: Array<{ key: Kind; label: string; emoji: string }> = [
  { key: 'walls', label: '承重墙', emoji: '🧱' },
  { key: 'beams', label: '梁', emoji: '📏' },
  { key: 'columns', label: '柱', emoji: '🏛' },
  { key: 'slabs', label: '楼板', emoji: '📐' },
];

export default function StructuralPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [activeKind, setActiveKind] = useState<Kind>('walls');

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  const { data: items, loading, error, reload } = useAsync<unknown[] | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.getStructuralItems<unknown[]>(selectedProjectId, activeKind);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [selectedProjectId, activeKind],
  );

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-structural-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">🏗 土建结构</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-project-picker">
            <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)} aria-label="选择项目" data-testid="wb-structural-project-select">
              <option value="">选择项目…</option>
              {projects?.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </div>

          {!selectedProjectId && (
            <div className="wb-state" data-testid="wb-structural-no-project">
              <div className="wb-state__icon">📋</div><div>请先选择项目</div>
            </div>
          )}

          {selectedProjectId && (
            <>
              {/* 构件 tab */}
              <div className="wb-task-filter" role="tablist" aria-label="构件类型" data-testid="wb-structural-tabs">
                {TABS.map((t) => (
                  <button
                    key={t.key}
                    type="button"
                    role="tab"
                    aria-selected={activeKind === t.key}
                    className={`wb-task-filter__chip ${activeKind === t.key ? 'wb-task-filter__chip--active' : ''}`}
                    onClick={() => setActiveKind(t.key)}
                    data-testid={`wb-structural-tab--${t.key}`}
                  >
                    {t.emoji} {t.label}
                  </button>
                ))}
              </div>

              {loading && (
                <div className="wb-state" data-testid="wb-structural-loading">
                  <div className="wb-state__icon">⏳</div><div>加载{TABS.find((t) => t.key === activeKind)?.label}中…</div>
                </div>
              )}
              {error && !loading && (
                <div className="wb-state wb-state--error" data-testid="wb-structural-error">
                  <div className="wb-state__icon">⚠</div><div>{error}</div>
                  <button className="wb-theme-option wb-theme-option--active" onClick={reload}>重试</button>
                </div>
              )}
              {!loading && !error && (items?.length ?? 0) === 0 && (
                <div className="wb-state" data-testid="wb-structural-empty">
                  <div className="wb-state__icon">🏗</div>
                  <div>暂无{TABS.find((t) => t.key === activeKind)?.label}数据</div>
                </div>
              )}

              {!loading && !error && (items?.length ?? 0) > 0 && (
                <div data-testid="wb-structural-content">
                  <div className="wb-section-label">{TABS.find((t) => t.key === activeKind)?.label}（{items!.length}）</div>
                  {activeKind === 'walls' && (items as LoadBearingWall[]).map((w, i) => (
                    <div key={w.id} className="wb-project-card" data-testid={`wb-structural-item--${i}`}>
                      <div className="wb-project-card__title">{w.wall_name}</div>
                      <div className="wb-project-card__meta">
                        <span className="wb-project-card__meta-item">{w.is_load_bearing ? '🔒 承重' : '🔓 非承重'}</span>
                        <span className="wb-project-card__meta-item">📏 {w.length_m}m × {w.height_m}m</span>
                        <span className="wb-project-card__meta-item">📐 厚 {w.thickness_mm}mm</span>
                        {w.material && <span className="wb-project-card__meta-item">🧱 {w.material}</span>}
                      </div>
                    </div>
                  ))}
                  {activeKind === 'beams' && (items as Beam[]).map((b, i) => (
                    <div key={b.id} className="wb-project-card" data-testid={`wb-structural-item--${i}`}>
                      <div className="wb-project-card__title">{b.beam_name}</div>
                      <div className="wb-project-card__meta">
                        <span className="wb-project-card__meta-item">📐 {b.beam_type}</span>
                        <span className="wb-project-card__meta-item">📏 {b.width_mm}×{b.height_mm}mm</span>
                        <span className="wb-project-card__meta-item">↔ {b.length_m}m</span>
                        {b.concrete_grade && <span className="wb-project-card__meta-item">🏗 {b.concrete_grade}</span>}
                      </div>
                    </div>
                  ))}
                  {activeKind === 'columns' && (items as StructuralColumn[]).map((c, i) => (
                    <div key={c.id} className="wb-project-card" data-testid={`wb-structural-item--${i}`}>
                      <div className="wb-project-card__title">{c.column_name}</div>
                      <div className="wb-project-card__meta">
                        <span className="wb-project-card__meta-item">📐 {c.column_type}</span>
                        <span className="wb-project-card__meta-item">📏 {c.width_mm}×{c.depth_mm}mm</span>
                        <span className="wb-project-card__meta-item">↕ {c.height_m}m</span>
                        {c.concrete_grade && <span className="wb-project-card__meta-item">🏗 {c.concrete_grade}</span>}
                      </div>
                    </div>
                  ))}
                  {activeKind === 'slabs' && (items as FloorSlab[]).map((s, i) => (
                    <div key={s.id} className="wb-project-card" data-testid={`wb-structural-item--${i}`}>
                      <div className="wb-project-card__title">{s.slab_name}</div>
                      <div className="wb-project-card__meta">
                        <span className="wb-project-card__meta-item">📐 {s.slab_type}</span>
                        <span className="wb-project-card__meta-item">📏 厚 {s.thickness_mm}mm</span>
                        <span className="wb-project-card__meta-item">🔲 {s.area_m2}㎡</span>
                        {s.rebar_diameter_mm && <span className="wb-project-card__meta-item">⚙ {s.rebar_diameter_mm}mm@{s.rebar_spacing_mm}</span>}
                      </div>
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
