/**
 * TakeoffPage — 工程量计算
 *
 * 结构：Scaffold > AppBar(工程量计算) > [项目选择器] > 正向算量结果
 * API：GET /api/takeoff/project/{projectId}（对齐 app/api/takeoff.py:117）
 *
 * 后端字段（app/services/quantity_takeoff_service.py:ForwardTakeoffResult）：
 *   floorplan_name / walls[] / floors[] / ceilings[] / paints[] / summary{} / reply
 *
 * 降级：
 *   503 — forward_takeoff_enabled=False，提示走工作台手工计算
 *   404 — 项目无 active floorplan，提示先创建户型方案
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { ForwardTakeoffResult, Project } from '../types/domain';

export default function TakeoffPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  const { data: takeoff, loading, error, reload } = useAsync<ForwardTakeoffResult | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.getProjectTakeoff<ForwardTakeoffResult>(selectedProjectId);
      if (!r.isSuccess || !r.data) {
        // 503/404 降级：抛出带状态码的错误，便于区分展示
        const code = r.status ?? 0;
        if (code === 503) throw new Error('FORWARD_TAKEOFF_DISABLED');
        if (code === 404) throw new Error('NO_FLOORPLAN');
        throw new Error(r.error ?? '加载失败');
      }
      return r.data;
    },
    [selectedProjectId],
  );

  const isDisabled = error === 'FORWARD_TAKEOFF_DISABLED';
  const isNoFloorplan = error === 'NO_FLOORPLAN';

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-takeoff-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">🧮 工程量计算</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-project-picker">
            <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)} aria-label="选择项目" data-testid="wb-takeoff-project-select">
              <option value="">选择项目…</option>
              {projects?.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </div>

          {!selectedProjectId && (
            <div className="wb-state" data-testid="wb-takeoff-no-project">
              <div className="wb-state__icon">📋</div><div>请先选择项目</div>
            </div>
          )}
          {selectedProjectId && loading && (
            <div className="wb-state" data-testid="wb-takeoff-loading">
              <div className="wb-state__icon">⏳</div><div>正向算量中…</div>
            </div>
          )}
          {selectedProjectId && isNoFloorplan && !loading && (
            <div className="wb-state" data-testid="wb-takeoff-no-floorplan">
              <div className="wb-state__icon">📐</div>
              <div>该项目尚无户型方案，无法正向算量</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={() => navigate('/floorplans')}>去创建户型</button>
            </div>
          )}
          {selectedProjectId && isDisabled && !loading && (
            <div className="wb-state" data-testid="wb-takeoff-disabled">
              <div className="wb-state__icon">⚙</div>
              <div>正向算量未启用</div>
              <div style={{ fontSize: 'var(--font-size-sm)' }}>可在工作台与算量 Agent 对话进行手工计算</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={() => navigate('/')}>返回工作台</button>
            </div>
          )}
          {selectedProjectId && error && !loading && !isDisabled && !isNoFloorplan && (
            <div className="wb-state wb-state--error" data-testid="wb-takeoff-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>重试</button>
            </div>
          )}

          {selectedProjectId && !loading && !error && takeoff && (
            <div data-testid="wb-takeoff-content">
              {/* 自然语言汇总 */}
              <div className="wb-takeoff-reply" data-testid="wb-takeoff-reply">
                <div className="wb-takeoff-reply__label">基于户型「{takeoff.floorplan_name}」几何算量</div>
                <div className="wb-takeoff-reply__text">{takeoff.reply}</div>
              </div>

              {/* summary 统计网格 */}
              <div className="wb-section-label">工程量汇总</div>
              <div className="wb-takeoff-grid" data-testid="wb-takeoff-summary">
                <div className="wb-takeoff-stat">
                  <div className="wb-takeoff-stat__value">{takeoff.summary.total_wall_length_m}<span>m</span></div>
                  <div className="wb-takeoff-stat__label">墙体总长</div>
                </div>
                <div className="wb-takeoff-stat">
                  <div className="wb-takeoff-stat__value">{takeoff.summary.total_brick_count.toLocaleString()}<span>块</span></div>
                  <div className="wb-takeoff-stat__label">砖用量</div>
                </div>
                <div className="wb-takeoff-stat">
                  <div className="wb-takeoff-stat__value">{takeoff.summary.total_mortar_m3}<span>m³</span></div>
                  <div className="wb-takeoff-stat__label">砂浆</div>
                </div>
                <div className="wb-takeoff-stat">
                  <div className="wb-takeoff-stat__value">{takeoff.summary.total_tile_count.toLocaleString()}<span>块</span></div>
                  <div className="wb-takeoff-stat__label">瓷砖</div>
                </div>
                <div className="wb-takeoff-stat">
                  <div className="wb-takeoff-stat__value">{takeoff.summary.total_paint_area_m2}<span>m²</span></div>
                  <div className="wb-takeoff-stat__label">涂料面积</div>
                </div>
                <div className="wb-takeoff-stat">
                  <div className="wb-takeoff-stat__value">{takeoff.summary.total_ceiling_area_m2}<span>m²</span></div>
                  <div className="wb-takeoff-stat__label">吊顶面积</div>
                </div>
                <div className="wb-takeoff-stat">
                  <div className="wb-takeoff-stat__value">{takeoff.summary.total_floor_area_m2}<span>m²</span></div>
                  <div className="wb-takeoff-stat__label">地面面积</div>
                </div>
                <div className="wb-takeoff-stat">
                  <div className="wb-takeoff-stat__value">{takeoff.summary.door_count}<span>樘</span></div>
                  <div className="wb-takeoff-stat__label">门</div>
                </div>
              </div>

              {/* 墙体明细 */}
              {takeoff.walls.length > 0 && (
                <>
                  <div className="wb-section-label">墙体明细（{takeoff.walls.length}）</div>
                  {takeoff.walls.map((w, i) => (
                    <div key={i} className="wb-project-card" data-testid={`wb-takeoff-wall--${i}`}>
                      <div className="wb-project-card__title">{w.name}</div>
                      <div className="wb-project-card__meta">
                        <span className="wb-project-card__meta-item">📏 {w.length}m × {w.height}m</span>
                        <span className="wb-project-card__meta-item">📐 厚 {w.thickness}m</span>
                        <span className="wb-project-card__meta-item">🧱 {w.brick_count.toLocaleString()} 块</span>
                        <span className="wb-project-card__meta-item">🪣 砂浆 {w.mortar_volume} m³</span>
                      </div>
                    </div>
                  ))}
                </>
              )}

              {/* 地面明细 */}
              {takeoff.floors.length > 0 && (
                <>
                  <div className="wb-section-label">地面明细（{takeoff.floors.length}）</div>
                  {takeoff.floors.map((f, i) => (
                    <div key={i} className="wb-project-card" data-testid={`wb-takeoff-floor--${i}`}>
                      <div className="wb-project-card__title">{f.name}</div>
                      <div className="wb-project-card__meta">
                        <span className="wb-project-card__meta-item">📏 {f.area}㎡</span>
                        <span className="wb-project-card__meta-item">🔲 {f.tile_size}</span>
                        <span className="wb-project-card__meta-item">🧱 {f.tile_count} 块</span>
                      </div>
                    </div>
                  ))}
                </>
              )}

              {/* 涂料明细 */}
              {takeoff.paints.length > 0 && (
                <>
                  <div className="wb-section-label">涂料明细（{takeoff.paints.length}）</div>
                  {takeoff.paints.map((p, i) => (
                    <div key={i} className="wb-project-card" data-testid={`wb-takeoff-paint--${i}`}>
                      <div className="wb-project-card__title">{p.name}</div>
                      <div className="wb-project-card__meta">
                        <span className="wb-project-card__meta-item">📏 {p.area}㎡</span>
                        <span className="wb-project-card__meta-item">🎨 底漆 {p.primer_count} 桶</span>
                        <span className="wb-project-card__meta-item">🖌 面漆 {p.finish_count} 桶</span>
                        <span className="wb-project-card__meta-item">🛢 {p.total_paint_liters} L</span>
                      </div>
                    </div>
                  ))}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
