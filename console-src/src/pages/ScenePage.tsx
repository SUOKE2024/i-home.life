/**
 * ScenePage — 场景自动化
 *
 * 结构：Scaffold > AppBar(场景自动化) > [项目选择器] > 类型筛选 + 场景卡片列表
 * API：GET /api/scene-automation/scenes/project/{projectId}（对齐 app/api/scene_automation.py）
 *
 * 后端字段（app/schemas/scene_automation.py:SceneAutomationResponse）：
 *   id / project_id / scheme_id / scene_name / scene_type / trigger_condition /
 *   actions[] / enabled / priority / created_at / updated_at
 *
 * 后端 scene_type（app/models/scene_automation.py）：manual | scheduled | triggered | geo
 */

import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { SceneAutomation, Project } from '../types/domain';

// scene_type → 图标/文案
const SCENE_TYPE_MAP: Record<string, { label: string; icon: string }> = {
  manual: { label: '手动', icon: '👆' },
  scheduled: { label: '定时', icon: '⏰' },
  triggered: { label: '触发', icon: '⚡' },
  geo: { label: '地理', icon: '📍' },
};

const FILTERS: Array<{ key: string; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'manual', label: '手动' },
  { key: 'scheduled', label: '定时' },
  { key: 'triggered', label: '触发' },
  { key: 'geo', label: '地理' },
];

interface SceneAction {
  device_name?: string;
  action?: string;
  [key: string]: unknown;
}

export default function ScenePage() {
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

  const { data: scenes, loading, error, reload } = useAsync<SceneAutomation[] | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.getSceneAutomations<SceneAutomation[]>(selectedProjectId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [selectedProjectId],
  );

  const filteredScenes = useMemo(() => {
    if (!scenes) return [];
    if (filterType === 'all') return scenes;
    return scenes.filter((s) => s.scene_type === filterType);
  }, [scenes, filterType]);

  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    (scenes ?? []).forEach((s) => {
      counts[s.scene_type] = (counts[s.scene_type] ?? 0) + 1;
    });
    return counts;
  }, [scenes]);

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-scene-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">🎭 场景自动化</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-project-picker">
            <select
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              aria-label="选择项目"
              data-testid="wb-scene-project-select"
            >
              <option value="">选择项目…</option>
              {projects?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {!selectedProjectId && (
            <div className="wb-state" data-testid="wb-scene-no-project">
              <div className="wb-state__icon">📋</div>
              <div>请先选择项目</div>
            </div>
          )}

          {selectedProjectId && loading && (
            <div className="wb-state" data-testid="wb-scene-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载场景中…</div>
            </div>
          )}

          {selectedProjectId && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-scene-error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>
                重试
              </button>
            </div>
          )}

          {selectedProjectId && !loading && !error && (scenes?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-scene-empty">
              <div className="wb-state__icon">🎭</div>
              <div>暂无场景自动化</div>
              <div style={{ fontSize: 'var(--font-size-sm)' }}>
                可通过工作台与场景 Agent 对话创建场景
              </div>
            </div>
          )}

          {selectedProjectId && !loading && !error && (scenes?.length ?? 0) > 0 && (
            <div data-testid="wb-scene-content">
              <div className="wb-task-filter" role="tablist" aria-label="类型筛选">
                {FILTERS.map((f) => {
                  const count = f.key === 'all' ? scenes!.length : typeCounts[f.key] ?? 0;
                  return (
                    <button
                      key={f.key}
                      type="button"
                      role="tab"
                      aria-selected={filterType === f.key}
                      className={`wb-task-filter__chip ${
                        filterType === f.key ? 'wb-task-filter__chip--active' : ''
                      }`}
                      onClick={() => setFilterType(f.key)}
                      data-testid={`wb-scene-filter--${f.key}`}
                    >
                      {f.label}({count})
                    </button>
                  );
                })}
              </div>

              <div className="wb-section-label">
                场景（{filteredScenes.length}/{scenes!.length}）
              </div>

              {filteredScenes.map((scene, i) => {
                const typeInfo = SCENE_TYPE_MAP[scene.scene_type] ?? {
                  label: scene.scene_type,
                  icon: '🎭',
                };
                const actions = (scene.actions ?? []) as SceneAction[];
                return (
                  <div
                    key={scene.id}
                    className="wb-scene-card"
                    data-testid={`wb-scene-item--${i}`}
                  >
                    <div className="wb-scene-card__icon">{typeInfo.icon}</div>
                    <div className="wb-scene-card__body">
                      <div className="wb-scene-card__head">
                        <div className="wb-scene-card__name">{scene.scene_name}</div>
                        <span
                          className={`wb-status-chip ${
                            scene.enabled
                              ? 'wb-status-chip--success'
                              : 'wb-status-chip--muted'
                          }`}
                          data-testid={`wb-scene-enabled--${i}`}
                        >
                          {scene.enabled ? '已启用' : '已禁用'}
                        </span>
                      </div>
                      <div className="wb-scene-card__trigger">
                        {typeInfo.label}
                        {scene.trigger_condition ? ` · ${scene.trigger_condition}` : ''}
                      </div>
                      {actions.length > 0 && (
                        <div className="wb-scene-card__actions">
                          动作：{actions
                            .map(
                              (a) =>
                                a.device_name ?? a.action ?? JSON.stringify(a).slice(0, 30),
                            )
                            .join('、')}
                        </div>
                      )}
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
