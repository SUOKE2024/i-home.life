/**
 * ConstructionPage — 对齐 flutter_app/lib/pages/construction_page.dart
 *
 * 结构：Scaffold > AppBar(施工管理) > [项目选择器] > 状态筛选 chips + 施工任务卡片列表
 * API：GET /api/construction/tasks/{projectId}（对齐 app/api/construction.py:list_tasks）
 *
 * 后端任务字段（app/schemas/construction.py:TaskResponse）：
 *   id / project_id / name / phase / assigned_to / status / priority /
 *   start_date / end_date / description / created_at / updated_at
 *
 * 后端状态约束（app/models/construction.py:chk_construction_task_status）：
 *   pending | in_progress | ready | paused | completed | cancelled
 *
 * Flutter 端有 3 tabs（任务/排期/质检），批次 5 实现"任务"主 tab；
 * 排期 Gantt 与质检留后续批次。
 */

import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { ConstructionTask, Project } from '../types/domain';

// ── 状态 → 文案/颜色映射（对齐 construction_page.dart:147-152 + 后端约束）──
type ChipTone = 'muted' | 'info' | 'success' | 'warning' | 'danger';

const STATUS_MAP: Record<string, { label: string; tone: ChipTone }> = {
  pending: { label: '待开始', tone: 'muted' },
  in_progress: { label: '进行中', tone: 'info' },
  ready: { label: '待验收', tone: 'warning' },
  paused: { label: '已暂停', tone: 'warning' },
  completed: { label: '已完成', tone: 'success' },
  cancelled: { label: '已取消', tone: 'danger' },
};

// ── 阶段 → 中文（对齐后端 phase 约束）──
const PHASE_MAP: Record<string, string> = {
  preparation: '准备阶段',
  demolition: '拆除',
  water_electricity: '水电',
  electrical: '电气',
  waterproof: '防水',
  masonry: '泥瓦',
  mep: '机电',
  carpentry: '木工',
  painting: '油漆',
  installation: '安装',
  completion: '竣工',
  inspection: '验收',
};

const FILTERS: Array<{ key: string; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'pending', label: '待开始' },
  { key: 'in_progress', label: '进行中' },
  { key: 'ready', label: '待验收' },
  { key: 'paused', label: '已暂停' },
  { key: 'completed', label: '已完成' },
  { key: 'cancelled', label: '已取消' },
];

function formatDate(iso?: string | null): string {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return `${d.getMonth() + 1}/${d.getDate()}`;
  } catch {
    return iso;
  }
}

export default function ConstructionPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [filterStatus, setFilterStatus] = useState<string>('all');

  // 加载项目列表（供选择器）
  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  // 默认选第一个项目
  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  // 加载施工任务（依赖选中项目）
  const { data: tasks, loading, error, reload } = useAsync<ConstructionTask[] | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.getConstructionTasks<ConstructionTask[]>(selectedProjectId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [selectedProjectId],
  );

  // 按状态筛选
  const filteredTasks = useMemo(() => {
    if (!tasks) return [];
    if (filterStatus === 'all') return tasks;
    return tasks.filter((t) => t.status === filterStatus);
  }, [tasks, filterStatus]);

  // 统计各状态数量
  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    (tasks ?? []).forEach((t) => {
      counts[t.status] = (counts[t.status] ?? 0) + 1;
    });
    return counts;
  }, [tasks]);

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-construction-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">🔨 施工管理</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {/* 项目选择器 */}
          <div className="wb-project-picker">
            <select
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              aria-label="选择项目"
              data-testid="wb-construction-project-select"
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
            <div className="wb-state" data-testid="wb-construction-no-project">
              <div className="wb-state__icon">📋</div>
              <div>请先选择项目</div>
            </div>
          )}

          {selectedProjectId && loading && (
            <div className="wb-state" data-testid="wb-construction-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载施工任务中…</div>
            </div>
          )}

          {selectedProjectId && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-construction-error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>
                重试
              </button>
            </div>
          )}

          {selectedProjectId && !loading && !error && (tasks?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-construction-empty">
              <div className="wb-state__icon">🏗️</div>
              <div>暂无施工任务</div>
              <div style={{ fontSize: 'var(--font-size-sm)' }}>
                可通过工作台与施工 Agent 对话生成施工计划
              </div>
            </div>
          )}

          {selectedProjectId && !loading && !error && (tasks?.length ?? 0) > 0 && (
            <div data-testid="wb-construction-content">
              {/* 状态筛选 */}
              <div className="wb-task-filter" role="tablist" aria-label="任务状态筛选">
                {FILTERS.map((f) => {
                  const count = f.key === 'all' ? tasks!.length : statusCounts[f.key] ?? 0;
                  return (
                    <button
                      key={f.key}
                      type="button"
                      role="tab"
                      aria-selected={filterStatus === f.key}
                      className={`wb-task-filter__chip ${
                        filterStatus === f.key ? 'wb-task-filter__chip--active' : ''
                      }`}
                      onClick={() => setFilterStatus(f.key)}
                      data-testid={`wb-construction-filter--${f.key}`}
                    >
                      {f.label}({count})
                    </button>
                  );
                })}
              </div>

              {/* 任务卡片列表 */}
              <div className="wb-section-label">
                施工任务（{filteredTasks.length}/{tasks!.length}）
              </div>
              {filteredTasks.length > 0 ? (
                filteredTasks.map((task, i) => {
                  const statusInfo = STATUS_MAP[task.status] ?? {
                    label: task.status,
                    tone: 'muted' as ChipTone,
                  };
                  const phaseLabel = PHASE_MAP[task.phase] ?? task.phase;
                  return (
                    <div
                      key={task.id}
                      className={`wb-ctask-card wb-ctask-card--${task.status}`}
                      data-testid={`wb-construction-task--${i}`}
                    >
                      <div className="wb-ctask-card__head">
                        <div className="wb-ctask-card__title">{task.name}</div>
                        <span
                          className={`wb-status-chip wb-status-chip--${statusInfo.tone}`}
                          data-testid={`wb-construction-task-status--${i}`}
                        >
                          {statusInfo.label}
                        </span>
                      </div>
                      <div className="wb-ctask-card__meta">
                        <span>📍 {phaseLabel}</span>
                        {task.assigned_to && <span>👤 {task.assigned_to}</span>}
                        {task.priority > 0 && <span>⭐ 优先级 {task.priority}</span>}
                        {task.start_date && <span>▶ {formatDate(task.start_date)}</span>}
                        {task.end_date && <span>⏹ {formatDate(task.end_date)}</span>}
                      </div>
                      {task.description && (
                        <div
                          style={{
                            fontSize: 'var(--font-size-sm)',
                            color: 'var(--text-secondary)',
                            marginTop: 6,
                          }}
                        >
                          {task.description}
                        </div>
                      )}
                    </div>
                  );
                })
              ) : (
                <div className="wb-state">
                  <div>该状态下暂无任务</div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
