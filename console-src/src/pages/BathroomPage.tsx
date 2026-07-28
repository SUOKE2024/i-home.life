/**
 * BathroomPage — 卫浴设计
 *
 * 结构：Scaffold > AppBar(卫浴设计) > [项目选择器] > layout_type 筛选 + 设计卡片列表（含通风合规校验）
 * API：GET /api/bathroom/designs/project/{projectId}（对齐 app/api/bathroom.py）
 *
 * 后端字段（app/schemas/bathroom.py:BathroomDesignResponse）：
 *   id / project_id / room_name / layout_type / room_width / room_length /
 *   ceiling_height / dry_area / wet_area / floor_drain_count /
 *   waterproof_height_mm / drain_slope_percent / status /
 *   has_natural_window / window_area_m2 / mechanical_vent_airflow / created_at / updated_at
 *
 * layout_type（app/models/bathroom.py）：dry_wet_separation | three_separation | traditional | single
 *
 * 通风合规校验镜像 app/services/bathroom_service.py:analyze_ventilation：
 *   自然通风：窗户面积 ≥ 地面面积 1/20
 *   机械通风：风量 ≥ 80 m³/h
 */

import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { BathroomDesign, Project } from '../types/domain';

type ChipTone = 'muted' | 'info' | 'success' | 'warning' | 'danger' | 'accent';

const LAYOUT_MAP: Record<string, { label: string; tone: ChipTone }> = {
  dry_wet_separation: { label: '干湿分离', tone: 'accent' },
  three_separation: { label: '三分离', tone: 'info' },
  traditional: { label: '传统', tone: 'muted' },
  single: { label: '单卫', tone: 'success' },
};

const FILTERS: Array<{ key: string; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'dry_wet_separation', label: '干湿分离' },
  { key: 'three_separation', label: '三分离' },
  { key: 'traditional', label: '传统' },
  { key: 'single', label: '单卫' },
];

const REQUIRED_AIRFLOW = 80.0; // m³/h，标准阈值（对齐 bathroom_service.py:313）

/** 计算通风合规 — 镜像 app/services/bathroom_service.py:analyze_ventilation */
function analyzeVentilation(d: BathroomDesign): {
  floorArea: number;
  requiredNaturalArea: number;
  windowArea: number;
  windowEstimated: boolean;
  naturalCompliant: boolean;
  airflow: number;
  mechanicalCompliant: boolean;
  rating: 'good' | 'mechanical_only' | 'insufficient';
  suggestion: string;
} {
  const floorArea = d.room_width * d.room_length;
  const requiredNaturalArea = floorArea / 20;
  const hasWindow = d.has_natural_window;
  let windowArea = 0;
  let windowEstimated = false;
  if (d.window_area_m2 != null) {
    windowArea = d.window_area_m2;
  } else if (hasWindow) {
    windowArea = 0.54; // 常见 0.6×0.9 估算
    windowEstimated = true;
  }
  const naturalCompliant = hasWindow && windowArea >= requiredNaturalArea;
  const airflow = d.mechanical_vent_airflow != null ? d.mechanical_vent_airflow : REQUIRED_AIRFLOW;
  const mechanicalCompliant = airflow >= REQUIRED_AIRFLOW;

  let rating: 'good' | 'mechanical_only' | 'insufficient';
  let suggestion: string;
  if (naturalCompliant && mechanicalCompliant) {
    rating = 'good';
    suggestion = '通风条件良好';
  } else if (mechanicalCompliant) {
    rating = 'mechanical_only';
    suggestion = '无自然通风，依赖机械通风';
  } else {
    rating = 'insufficient';
    suggestion = '通风不足，建议加大排风量';
  }

  return {
    floorArea: Math.round(floorArea * 100) / 100,
    requiredNaturalArea: Math.round(requiredNaturalArea * 10) / 10,
    windowArea: Math.round(windowArea * 1000) / 1000,
    windowEstimated,
    naturalCompliant,
    airflow,
    mechanicalCompliant,
    rating,
    suggestion,
  };
}

const RATING_TONE: Record<string, ChipTone> = {
  good: 'success',
  mechanical_only: 'warning',
  insufficient: 'danger',
};
const RATING_LABEL: Record<string, string> = {
  good: '通风良好',
  mechanical_only: '仅机械通风',
  insufficient: '通风不足',
};

export default function BathroomPage() {
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

  const { data: designs, loading, error, reload } = useAsync<BathroomDesign[] | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.getBathroomDesigns<BathroomDesign[]>(selectedProjectId);
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
      <div className="wb-page-shell" data-testid="wb-bathroom-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">🚿 卫浴设计</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-project-picker">
            <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)} aria-label="选择项目" data-testid="wb-bathroom-project-select">
              <option value="">选择项目…</option>
              {projects?.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </div>

          {!selectedProjectId && (
            <div className="wb-state" data-testid="wb-bathroom-no-project">
              <div className="wb-state__icon">📋</div><div>请先选择项目</div>
            </div>
          )}
          {selectedProjectId && loading && (
            <div className="wb-state" data-testid="wb-bathroom-loading">
              <div className="wb-state__icon">⏳</div><div>加载卫浴设计中…</div>
            </div>
          )}
          {selectedProjectId && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-bathroom-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>重试</button>
            </div>
          )}
          {selectedProjectId && !loading && !error && (designs?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-bathroom-empty">
              <div className="wb-state__icon">🚿</div><div>暂无卫浴设计</div>
              <div style={{ fontSize: 'var(--font-size-sm)' }}>可通过工作台与卫浴 Agent 对话生成设计</div>
            </div>
          )}

          {selectedProjectId && !loading && !error && (designs?.length ?? 0) > 0 && (
            <div data-testid="wb-bathroom-content">
              <div className="wb-task-filter" role="tablist" aria-label="布局类型筛选">
                {FILTERS.map((f) => {
                  const count = f.key === 'all' ? designs!.length : typeCounts[f.key] ?? 0;
                  return (
                    <button key={f.key} type="button" role="tab" aria-selected={filterType === f.key}
                      className={`wb-task-filter__chip ${filterType === f.key ? 'wb-task-filter__chip--active' : ''}`}
                      onClick={() => setFilterType(f.key)} data-testid={`wb-bathroom-filter--${f.key}`}>
                      {f.label}{f.key !== 'all' && count > 0 ? `(${count})` : ''}
                    </button>
                  );
                })}
              </div>

              <div className="wb-section-label">卫浴设计（{filteredDesigns.length}/{designs!.length}）</div>
              {filteredDesigns.map((d, i) => {
                const layoutInfo = LAYOUT_MAP[d.layout_type] ?? { label: d.layout_type, tone: 'muted' as ChipTone };
                const vent = analyzeVentilation(d);
                return (
                  <div key={d.id} className="wb-smart-card" data-testid={`wb-bathroom-item--${i}`}>
                    <div className="wb-smart-card__head">
                      <div className="wb-smart-card__room">{d.room_name}</div>
                      <span className={`wb-status-chip wb-status-chip--${layoutInfo.tone}`}>{layoutInfo.label}</span>
                    </div>
                    <div className="wb-smart-card__meta">
                      <span>📐 {d.room_width}×{d.room_length}m</span>
                      <span>📏 层高 {d.ceiling_height}m</span>
                      {d.dry_area != null && <span>🏜 干区 {d.dry_area}㎡</span>}
                      {d.wet_area != null && <span>💧 湿区 {d.wet_area}㎡</span>}
                    </div>
                    {/* 防水 & 排水 */}
                    <div className="wb-bath-spec">
                      <span className="wb-bath-spec__item">🛡 防水 {d.waterproof_height_mm}mm</span>
                      <span className="wb-bath-spec__item">📐 坡度 {d.drain_slope_percent}%</span>
                      <span className="wb-bath-spec__item">🕳 地漏 ×{d.floor_drain_count}</span>
                    </div>
                    {/* 通风合规校验 */}
                    <div className="wb-vent-box" data-testid={`wb-bathroom-vent--${i}`}>
                      <div className="wb-vent-box__head">
                        <span className="wb-vent-box__title">🌬 通风校验</span>
                        <span className={`wb-status-chip wb-status-chip--${RATING_TONE[vent.rating]}`}
                          data-testid={`wb-bathroom-vent-rating--${i}`}>
                          {RATING_LABEL[vent.rating]}
                        </span>
                      </div>
                      <div className="wb-vent-box__row">
                        <span>自然通风：{vent.naturalCompliant ? '✓ 合规' : '✗ 不达标'}</span>
                        <span>窗面积 {vent.windowArea}㎡{vent.windowEstimated ? '（估算）' : ''} / 需 ≥{vent.requiredNaturalArea}㎡</span>
                      </div>
                      <div className="wb-vent-box__row">
                        <span>机械通风：{vent.mechanicalCompliant ? '✓ 合规' : '✗ 不达标'}</span>
                        <span>风量 {vent.airflow}m³/h / 需 ≥{REQUIRED_AIRFLOW}m³/h</span>
                      </div>
                      <div className="wb-vent-box__hint">{vent.suggestion}</div>
                    </div>
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
