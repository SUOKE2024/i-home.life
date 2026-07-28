/**
 * FloorplansPage — 户型管理
 *
 * 结构：Scaffold > AppBar(户型管理) > [项目选择器] > 户型方案卡片列表
 * API：GET /api/floorplans/project/{projectId}（对齐 app/api/floorplans.py）
 *
 * 后端字段（app/schemas/floorplan.py:FloorPlanListItem）：
 *   id / project_id / name / total_area / room_count / wall_height / updated_at
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { FloorPlan, Project } from '../types/domain';

function formatDate(iso?: string | null): string {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  } catch {
    return iso;
  }
}

export default function FloorplansPage() {
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

  const { data: plans, loading, error, reload } = useAsync<FloorPlan[] | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.getFloorPlans<FloorPlan[]>(selectedProjectId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [selectedProjectId],
  );

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-floorplans-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">📐 户型管理</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-project-picker">
            <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)} aria-label="选择项目" data-testid="wb-floorplans-project-select">
              <option value="">选择项目…</option>
              {projects?.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </div>

          {!selectedProjectId && (
            <div className="wb-state" data-testid="wb-floorplans-no-project">
              <div className="wb-state__icon">📋</div><div>请先选择项目</div>
            </div>
          )}
          {selectedProjectId && loading && (
            <div className="wb-state" data-testid="wb-floorplans-loading">
              <div className="wb-state__icon">⏳</div><div>加载户型方案中…</div>
            </div>
          )}
          {selectedProjectId && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-floorplans-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>重试</button>
            </div>
          )}
          {selectedProjectId && !loading && !error && (plans?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-floorplans-empty">
              <div className="wb-state__icon">📐</div><div>暂无户型方案</div>
              <div style={{ fontSize: 'var(--font-size-sm)' }}>可通过工作台与设计 Agent 对话生成户型</div>
            </div>
          )}

          {selectedProjectId && !loading && !error && (plans?.length ?? 0) > 0 && (
            <div data-testid="wb-floorplans-content">
              <div className="wb-section-label">户型方案（{plans!.length}）</div>
              {plans!.map((plan, i) => (
                <div key={plan.id} className="wb-project-card" data-testid={`wb-floorplans-item--${i}`}>
                  <div className="wb-project-card__title">{plan.name}</div>
                  <div className="wb-project-card__meta">
                    <span className="wb-project-card__meta-item">📏 {plan.total_area}㎡</span>
                    <span className="wb-project-card__meta-item">🚪 {plan.room_count} 室</span>
                    <span className="wb-project-card__meta-item">📐 层高 {plan.wall_height}m</span>
                    <span className="wb-project-card__meta-item">📅 {formatDate(plan.updated_at)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
