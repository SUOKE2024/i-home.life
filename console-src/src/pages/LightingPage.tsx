/**
 * LightingPage — 灯光设计
 *
 * 结构：Scaffold > AppBar(灯光设计) > [项目选择器] > scheme_type 筛选 + 方案卡片列表
 * API：GET /api/lighting/schemes/project/{projectId}（对齐 app/api/lighting.py）
 *
 * 后端字段（app/schemas/lighting.py:LightingSchemeResponse）：
 *   id / project_id / room_name / scheme_type / room_area / ceiling_height /
 *   total_lumens / total_power_w / color_temp_k / cri / ugpr / status / notes /
 *   created_at / updated_at
 *
 * scheme_type（app/models/lighting.py）：main_light | none_main | mixed | scene
 */

import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { LightingScheme, Project } from '../types/domain';

type ChipTone = 'muted' | 'info' | 'success' | 'warning' | 'danger' | 'accent';

const SCHEME_TYPE_MAP: Record<string, { label: string; tone: ChipTone }> = {
  main_light: { label: '主灯', tone: 'accent' },
  none_main: { label: '无主灯', tone: 'info' },
  mixed: { label: '混合', tone: 'warning' },
  scene: { label: '场景', tone: 'success' },
};

const FILTERS: Array<{ key: string; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'main_light', label: '主灯' },
  { key: 'none_main', label: '无主灯' },
  { key: 'mixed', label: '混合' },
  { key: 'scene', label: '场景' },
];

export default function LightingPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [filterType, setFilterType] = useState<string>('all');

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  const { data: schemes, loading, error, reload } = useAsync<LightingScheme[] | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.getLightingSchemes<LightingScheme[]>(selectedProjectId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [selectedProjectId],
  );

  const filteredSchemes = useMemo(() => {
    if (!schemes) return [];
    if (filterType === 'all') return schemes;
    return schemes.filter((s) => s.scheme_type === filterType);
  }, [schemes, filterType]);

  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    (schemes ?? []).forEach((s) => { counts[s.scheme_type] = (counts[s.scheme_type] ?? 0) + 1; });
    return counts;
  }, [schemes]);

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-lighting-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">💡 灯光设计</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-project-picker">
            <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)} aria-label="选择项目" data-testid="wb-lighting-project-select">
              <option value="">选择项目…</option>
              {projects?.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </div>

          {!selectedProjectId && (
            <div className="wb-state" data-testid="wb-lighting-no-project">
              <div className="wb-state__icon">📋</div><div>请先选择项目</div>
            </div>
          )}
          {selectedProjectId && loading && (
            <div className="wb-state" data-testid="wb-lighting-loading">
              <div className="wb-state__icon">⏳</div><div>加载灯光方案中…</div>
            </div>
          )}
          {selectedProjectId && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-lighting-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>重试</button>
            </div>
          )}
          {selectedProjectId && !loading && !error && (schemes?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-lighting-empty">
              <div className="wb-state__icon">💡</div><div>暂无灯光方案</div>
              <div style={{ fontSize: 'var(--font-size-sm)' }}>可通过工作台与灯光 Agent 对话生成方案</div>
            </div>
          )}

          {selectedProjectId && !loading && !error && (schemes?.length ?? 0) > 0 && (
            <div data-testid="wb-lighting-content">
              <div className="wb-task-filter" role="tablist" aria-label="方案类型筛选">
                {FILTERS.map((f) => {
                  const count = f.key === 'all' ? schemes!.length : typeCounts[f.key] ?? 0;
                  return (
                    <button key={f.key} type="button" role="tab" aria-selected={filterType === f.key}
                      className={`wb-task-filter__chip ${filterType === f.key ? 'wb-task-filter__chip--active' : ''}`}
                      onClick={() => setFilterType(f.key)} data-testid={`wb-lighting-filter--${f.key}`}>
                      {f.label}({count})
                    </button>
                  );
                })}
              </div>

              <div className="wb-section-label">灯光方案（{filteredSchemes.length}/{schemes!.length}）</div>
              {filteredSchemes.map((s, i) => {
                const typeInfo = SCHEME_TYPE_MAP[s.scheme_type] ?? { label: s.scheme_type, tone: 'muted' as ChipTone };
                return (
                  <div key={s.id} className="wb-smart-card" data-testid={`wb-lighting-item--${i}`}>
                    <div className="wb-smart-card__head">
                      <div className="wb-smart-card__room">{s.room_name}</div>
                      <span className={`wb-status-chip wb-status-chip--${typeInfo.tone}`}>{typeInfo.label}</span>
                    </div>
                    <div className="wb-smart-card__meta">
                      <span>📐 {s.room_area}㎡</span>
                      <span>📏 层高 {s.ceiling_height}m</span>
                      {s.total_lumens != null && <span>💡 {s.total_lumens}lm</span>}
                      {s.total_power_w != null && <span>⚡ {s.total_power_w}W</span>}
                      {s.color_temp_k != null && <span>🌡 {s.color_temp_k}K</span>}
                      {s.cri != null && <span>🎨 CRI {s.cri}</span>}
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
