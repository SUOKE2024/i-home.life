/**
 * DoorWindowPage — 门窗规格 + 防水方案（双视图）
 *
 * 结构：Scaffold > AppBar(门窗防水) > [项目选择器] > 视图切换（门窗规格 / 防水方案）
 * API：
 *   GET /api/door-window-waterproof/door-windows/project/{projectId}（对齐 app/api/door_window_waterproof.py）
 *   GET /api/door-window-waterproof/waterproof/project/{projectId}
 *
 * 后端字段：
 *   DoorWindowSpecResponse：id / project_id / room_name / location / spec_type / material /
 *     width / height / thickness / opening_direction / glass_type / brand / model / price /
 *     has_screen / has_lock / notes / created_at / updated_at
 *   WaterproofPlanResponse：id / project_id / room_name / room_type / wall_height_mm /
 *     floor_area / wall_area / waterproof_material / coating_layers / thickness_mm /
 *     closure_test_hours / material_quantity / unit_price / total_price / status / notes /
 *     created_at / updated_at
 *
 * spec_type：entry_door | interior_door | window | sliding_door | french_window
 * material：solid_wood | wood_composite | aluminum | pvc | steel
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { DoorWindowSpec, WaterproofPlan, Project } from '../types/domain';

type ChipTone = 'muted' | 'info' | 'success' | 'warning' | 'danger' | 'accent';

const SPEC_TYPE_MAP: Record<string, { label: string; tone: ChipTone }> = {
  entry_door: { label: '入户门', tone: 'accent' },
  interior_door: { label: '室内门', tone: 'info' },
  window: { label: '窗户', tone: 'success' },
  sliding_door: { label: '推拉门', tone: 'warning' },
  french_window: { label: '法式窗', tone: 'info' },
};

const MATERIAL_MAP: Record<string, string> = {
  solid_wood: '实木',
  wood_composite: '复合木',
  aluminum: '铝合金',
  pvc: 'PVC',
  steel: '钢制',
};

export default function DoorWindowPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [view, setView] = useState<'doorwindow' | 'waterproof'>('doorwindow');

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  // 门窗规格
  const {
    data: specs, loading: specsLoading, error: specsError, reload: specsReload,
  } = useAsync<DoorWindowSpec[] | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.getDoorWindowSpecs<DoorWindowSpec[]>(selectedProjectId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [selectedProjectId],
  );

  // 防水方案
  const {
    data: plans, loading: plansLoading, error: plansError, reload: plansReload,
  } = useAsync<WaterproofPlan[] | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.getWaterproofPlans<WaterproofPlan[]>(selectedProjectId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [selectedProjectId],
  );

  const loading = view === 'doorwindow' ? specsLoading : plansLoading;
  const error = view === 'doorwindow' ? specsError : plansError;
  const reload = view === 'doorwindow' ? specsReload : plansReload;
  const list = view === 'doorwindow' ? specs : plans;

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-doorwindow-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">🚪 门窗防水</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-project-picker">
            <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)} aria-label="选择项目" data-testid="wb-doorwindow-project-select">
              <option value="">选择项目…</option>
              {projects?.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </div>

          {/* 视图切换 */}
          <div className="wb-task-filter" role="tablist" aria-label="视图切换">
            <button type="button" role="tab" aria-selected={view === 'doorwindow'}
              className={`wb-task-filter__chip ${view === 'doorwindow' ? 'wb-task-filter__chip--active' : ''}`}
              onClick={() => setView('doorwindow')} data-testid="wb-doorwindow-view--doorwindow">
              门窗规格
            </button>
            <button type="button" role="tab" aria-selected={view === 'waterproof'}
              className={`wb-task-filter__chip ${view === 'waterproof' ? 'wb-task-filter__chip--active' : ''}`}
              onClick={() => setView('waterproof')} data-testid="wb-doorwindow-view--waterproof">
              防水方案
            </button>
          </div>

          {!selectedProjectId && (
            <div className="wb-state" data-testid="wb-doorwindow-no-project">
              <div className="wb-state__icon">📋</div><div>请先选择项目</div>
            </div>
          )}
          {selectedProjectId && loading && (
            <div className="wb-state" data-testid="wb-doorwindow-loading">
              <div className="wb-state__icon">⏳</div><div>加载中…</div>
            </div>
          )}
          {selectedProjectId && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-doorwindow-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>重试</button>
            </div>
          )}
          {selectedProjectId && !loading && !error && (list?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-doorwindow-empty">
              <div className="wb-state__icon">{view === 'doorwindow' ? '🚪' : '🛡'}</div>
              <div>暂无{view === 'doorwindow' ? '门窗规格' : '防水方案'}</div>
            </div>
          )}

          {/* 门窗规格视图 */}
          {view === 'doorwindow' && selectedProjectId && !loading && !error && (specs?.length ?? 0) > 0 && (
            <div data-testid="wb-doorwindow-content">
              <div className="wb-section-label">门窗规格（{specs!.length}）</div>
              {specs!.map((s, i) => {
                const typeInfo = SPEC_TYPE_MAP[s.spec_type] ?? { label: s.spec_type, tone: 'muted' as ChipTone };
                const materialLabel = MATERIAL_MAP[s.material] ?? s.material;
                return (
                  <div key={s.id} className="wb-smart-card" data-testid={`wb-doorwindow-item--${i}`}>
                    <div className="wb-smart-card__head">
                      <div className="wb-smart-card__room">
                        {s.room_name}{s.location ? ` · ${s.location}` : ''}
                      </div>
                      <span className={`wb-status-chip wb-status-chip--${typeInfo.tone}`}>{typeInfo.label}</span>
                    </div>
                    <div className="wb-smart-card__meta">
                      <span>📦 {materialLabel}</span>
                      <span>📐 {s.width}×{s.height}cm</span>
                      {s.thickness != null && <span>📏 厚 {s.thickness}cm</span>}
                      <span>🔄 {s.opening_direction}</span>
                      {s.glass_type && <span>🪟 {s.glass_type}</span>}
                    </div>
                    <div className="wb-smart-card__meta">
                      {s.brand && <span>🏷 {s.brand}{s.model ? ` ${s.model}` : ''}</span>}
                      <span className="wb-smart-card__price">¥{s.price.toLocaleString()}</span>
                      <span>{s.has_screen ? '🛡 含纱窗' : '无纱窗'}</span>
                      <span>{s.has_lock ? '🔒 含锁' : '无锁'}</span>
                    </div>
                    {s.notes && (
                      <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 6 }}>{s.notes}</div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* 防水方案视图 */}
          {view === 'waterproof' && selectedProjectId && !loading && !error && (plans?.length ?? 0) > 0 && (
            <div data-testid="wb-waterproof-content">
              <div className="wb-section-label">防水方案（{plans!.length}）</div>
              {plans!.map((p, i) => (
                <div key={p.id} className="wb-smart-card" data-testid={`wb-waterproof-item--${i}`}>
                  <div className="wb-smart-card__head">
                    <div className="wb-smart-card__room">{p.room_name}</div>
                    <span className="wb-status-chip wb-status-chip--info">{p.room_type}</span>
                  </div>
                  <div className="wb-smart-card__meta">
                    <span>🛡 {p.waterproof_material}</span>
                    <span>📐 厚 {p.thickness_mm}mm</span>
                    <span>🎨 {p.coating_layers} 遍</span>
                    <span>📏 墙高 {p.wall_height_mm}mm</span>
                  </div>
                  <div className="wb-smart-card__meta">
                    <span>🌫 地面 {p.floor_area}㎡</span>
                    <span>🧱 墙面 {p.wall_area}㎡</span>
                    <span>💧 闭水 {p.closure_test_hours}h</span>
                    <span className="wb-smart-card__price">¥{p.total_price.toLocaleString()}</span>
                  </div>
                  {p.notes && (
                    <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 6 }}>{p.notes}</div>
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
