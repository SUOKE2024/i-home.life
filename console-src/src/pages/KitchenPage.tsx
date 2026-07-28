/**
 * KitchenPage — 厨房设计
 *
 * 结构：Scaffold > AppBar(厨房设计) > [项目选择器] > layout_type 筛选 + 设计卡片列表
 * API：GET /api/kitchen/designs/project/{projectId}（对齐 app/api/kitchen.py）
 *
 * 后端字段（app/schemas/kitchen.py:KitchenDesignResponse）：
 *   id / project_id / room_name / layout_type / room_width / room_length /
 *   ceiling_height / counter_height / counter_depth /
 *   water_inlet_pos / drain_pos / gas_pos / vent_pos / status / created_at / updated_at
 *
 * layout_type（app/models/kitchen.py）：L | U | I | G | double_i | island
 */

import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { KitchenDesign, Project } from '../types/domain';

type ChipTone = 'muted' | 'info' | 'success' | 'warning' | 'danger' | 'accent';

const LAYOUT_MAP: Record<string, { label: string; tone: ChipTone }> = {
  L: { label: 'L 型', tone: 'accent' },
  U: { label: 'U 型', tone: 'info' },
  I: { label: 'I 型', tone: 'success' },
  G: { label: 'G 型', tone: 'warning' },
  double_i: { label: '双 I 型', tone: 'info' },
  island: { label: '岛台型', tone: 'accent' },
};

const FILTERS: Array<{ key: string; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'L', label: 'L 型' },
  { key: 'U', label: 'U 型' },
  { key: 'I', label: 'I 型' },
  { key: 'island', label: '岛台' },
  { key: 'double_i', label: '双 I' },
  { key: 'G', label: 'G 型' },
];

export default function KitchenPage() {
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

  const { data: designs, loading, error, reload } = useAsync<KitchenDesign[] | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.getKitchenDesigns<KitchenDesign[]>(selectedProjectId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [selectedProjectId],
  );

  const filteredDesigns = useMemo(() => {
    if (!designs) return [];
    if (filterType === 'all') return designs;
    return designs.filter((d) => d.layout_type === filterType);
  }, [designs, filterType]);

  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    (designs ?? []).forEach((d) => { counts[d.layout_type] = (counts[d.layout_type] ?? 0) + 1; });
    return counts;
  }, [designs]);

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-kitchen-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">🍳 厨房设计</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-project-picker">
            <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)} aria-label="选择项目" data-testid="wb-kitchen-project-select">
              <option value="">选择项目…</option>
              {projects?.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </div>

          {!selectedProjectId && (
            <div className="wb-state" data-testid="wb-kitchen-no-project">
              <div className="wb-state__icon">📋</div><div>请先选择项目</div>
            </div>
          )}
          {selectedProjectId && loading && (
            <div className="wb-state" data-testid="wb-kitchen-loading">
              <div className="wb-state__icon">⏳</div><div>加载厨房设计中…</div>
            </div>
          )}
          {selectedProjectId && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-kitchen-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>重试</button>
            </div>
          )}
          {selectedProjectId && !loading && !error && (designs?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-kitchen-empty">
              <div className="wb-state__icon">🍳</div><div>暂无厨房设计</div>
              <div style={{ fontSize: 'var(--font-size-sm)' }}>可通过工作台与厨房 Agent 对话生成设计</div>
            </div>
          )}

          {selectedProjectId && !loading && !error && (designs?.length ?? 0) > 0 && (
            <div data-testid="wb-kitchen-content">
              <div className="wb-task-filter" role="tablist" aria-label="布局类型筛选">
                {FILTERS.map((f) => {
                  const count = f.key === 'all' ? designs!.length : typeCounts[f.key] ?? 0;
                  return (
                    <button key={f.key} type="button" role="tab" aria-selected={filterType === f.key}
                      className={`wb-task-filter__chip ${filterType === f.key ? 'wb-task-filter__chip--active' : ''}`}
                      onClick={() => setFilterType(f.key)} data-testid={`wb-kitchen-filter--${f.key}`}>
                      {f.label}{f.key !== 'all' && count > 0 ? `(${count})` : ''}
                    </button>
                  );
                })}
              </div>

              <div className="wb-section-label">厨房设计（{filteredDesigns.length}/{designs!.length}）</div>
              {filteredDesigns.map((d, i) => {
                const layoutInfo = LAYOUT_MAP[d.layout_type] ?? { label: d.layout_type, tone: 'muted' as ChipTone };
                return (
                  <div key={d.id} className="wb-smart-card" data-testid={`wb-kitchen-item--${i}`}>
                    <div className="wb-smart-card__head">
                      <div className="wb-smart-card__room">{d.room_name}</div>
                      <span className={`wb-status-chip wb-status-chip--${layoutInfo.tone}`}>{layoutInfo.label}</span>
                    </div>
                    <div className="wb-smart-card__meta">
                      <span>📐 {d.room_width}×{d.room_length}m</span>
                      <span>📏 层高 {d.ceiling_height}m</span>
                      <span>🍽 台面 {d.counter_height}×{d.counter_depth}cm</span>
                    </div>
                    {/* 关键点位（水电燃气排烟） */}
                    {(d.water_inlet_pos || d.drain_pos || d.gas_pos || d.vent_pos) && (
                      <div className="wb-kitchen-points">
                        {d.water_inlet_pos && <span className="wb-kitchen-point">🚰 进水 {d.water_inlet_pos}</span>}
                        {d.drain_pos && <span className="wb-kitchen-point">💧 排水 {d.drain_pos}</span>}
                        {d.gas_pos && <span className="wb-kitchen-point">🔥 燃气 {d.gas_pos}</span>}
                        {d.vent_pos && <span className="wb-kitchen-point">💨 排烟 {d.vent_pos}</span>}
                      </div>
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
