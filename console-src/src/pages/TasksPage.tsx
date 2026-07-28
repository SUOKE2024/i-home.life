/**
 * TasksPage — 对齐 flutter_app/lib/pages/tasks_page.dart
 *
 * 结构：Scaffold > AppBar(任务协调) > [范围切换: 项目任务/我的任务] > [项目选择器] >
 *      状态筛选 + 优先级筛选 + 任务卡片列表
 * API：
 *   GET /api/tasks/project/{projectId}（对齐 app/api/tasks.py:project tasks）
 *   GET /api/tasks/mine（对齐 app/api/tasks.py:mine）
 *
 * 后端任务字段（app/schemas/task.py:TaskResponse）：
 *   id / project_id / task_type / title / description / assigned_agent /
 *   assigned_user_id / assigned_user_name / priority / status / parent_task_id /
 *   dependencies / claimable / claim_deadline / claim_role / result /
 *   created_by / created_at / started_at / completed_at
 *
 * 后端 TaskListResponse 字段为 { tasks, total }（非 items）
 *
 * 优先级映射对齐 tasks_page.dart:88-97：后端 priority 1-10
 *   >=8 → 高 / >=4 → 中 / else → 低
 * 状态映射对齐 tasks_page.dart:116-128：
 *   pending → 待办 / claimed → 已申领 / in_progress → 进行中 / completed → 已完成
 */

import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { TaskItem, Project } from '../types/domain';

type ChipTone = 'muted' | 'info' | 'success' | 'warning' | 'danger' | 'accent';
type PriorityLevel = 'high' | 'medium' | 'low';
type Scope = 'project' | 'mine';

// ── 状态 → 文案/颜色（对齐 tasks_page.dart:116-143）──
const STATUS_MAP: Record<string, { label: string; tone: ChipTone }> = {
  pending: { label: '待办', tone: 'muted' },
  claimed: { label: '已申领', tone: 'info' },
  in_progress: { label: '进行中', tone: 'info' },
  completed: { label: '已完成', tone: 'success' },
};

// ── 优先级映射（对齐 tasks_page.dart:88-97：priority 1-10）──
function priorityLevel(p: number): PriorityLevel {
  if (p >= 8) return 'high';
  if (p >= 4) return 'medium';
  return 'low';
}

function priorityLabel(p: number): string {
  const lvl = priorityLevel(p);
  return lvl === 'high' ? '高' : lvl === 'medium' ? '中' : '低';
}

const PRIORITY_TONE: Record<PriorityLevel, ChipTone> = {
  high: 'danger',
  medium: 'warning',
  low: 'success',
};

const STATUS_FILTERS: Array<{ key: string; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'pending', label: '待办' },
  { key: 'claimed', label: '已申领' },
  { key: 'in_progress', label: '进行中' },
  { key: 'completed', label: '已完成' },
];

const PRIORITY_FILTERS: Array<{ key: PriorityLevel | 'all'; label: string }> = [
  { key: 'all', label: '全部优先级' },
  { key: 'high', label: '高' },
  { key: 'medium', label: '中' },
  { key: 'low', label: '低' },
];

/** 截止日期格式化（对齐 tasks_page.dart:147-160 _formatDeadline）*/
function formatDeadline(iso?: string | null): string {
  if (!iso) return '无截止日期';
  try {
    const dt = new Date(iso);
    if (Number.isNaN(dt.getTime())) return '无截止日期';
    const now = new Date();
    const diff = dt.getTime() - now.getTime();
    const dateStr = `${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`;
    if (diff < 0) return `已逾期 · ${dateStr}`;
    if (diff < 24 * 3600 * 1000) return `今日截止 · ${dateStr}`;
    const days = Math.floor(diff / (24 * 3600 * 1000));
    if (days < 3) return `${days}天后截止 · ${dateStr}`;
    return `截止 ${dateStr}`;
  } catch {
    return '无截止日期';
  }
}

export default function TasksPage() {
  const navigate = useNavigate();
  const [scope, setScope] = useState<Scope>('project');
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterPriority, setFilterPriority] = useState<PriorityLevel | 'all'>('all');

  // 加载项目列表（仅项目模式需要）
  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  // 加载任务列表（范围切换 + 项目切换）
  const effectiveProjectId = scope === 'project' ? selectedProjectId : '';
  const { data: taskList, loading, error, reload } = useAsync<TaskItem[] | null>(
    async () => {
      if (scope === 'project') {
        if (!selectedProjectId) return null;
        const r = await apiClient.getProjectTasks<{ tasks: TaskItem[]; total: number }>(
          selectedProjectId,
        );
        if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
        return r.data.tasks ?? [];
      }
      // scope === 'mine'
      const r = await apiClient.getMyTasks<{ tasks: TaskItem[]; total: number }>();
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data.tasks ?? [];
    },
    [scope, effectiveProjectId],
  );

  // 双维度筛选（状态 + 优先级）
  const filteredTasks = useMemo(() => {
    if (!taskList) return [];
    return taskList.filter((t) => {
      if (filterStatus !== 'all' && t.status !== filterStatus) return false;
      if (filterPriority !== 'all' && priorityLevel(t.priority) !== filterPriority) return false;
      return true;
    });
  }, [taskList, filterStatus, filterPriority]);

  const total = taskList?.length ?? 0;

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-tasks-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">✅ 任务协调</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {/* 范围切换：项目任务 / 我的任务（对齐 tasks_page.dart kanban/list 双视图意图）*/}
          <div className="wb-task-filter" role="tablist" aria-label="任务范围">
            <button
              type="button"
              role="tab"
              aria-selected={scope === 'project'}
              className={`wb-task-filter__chip ${scope === 'project' ? 'wb-task-filter__chip--active' : ''}`}
              onClick={() => setScope('project')}
              data-testid="wb-tasks-scope--project"
            >
              📁 项目任务
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={scope === 'mine'}
              className={`wb-task-filter__chip ${scope === 'mine' ? 'wb-task-filter__chip--active' : ''}`}
              onClick={() => setScope('mine')}
              data-testid="wb-tasks-scope--mine"
            >
              👤 我的任务
            </button>
          </div>

          {/* 项目选择器（仅项目模式）*/}
          {scope === 'project' && (
            <div className="wb-project-picker">
              <select
                value={selectedProjectId}
                onChange={(e) => setSelectedProjectId(e.target.value)}
                aria-label="选择项目"
                data-testid="wb-tasks-project-select"
              >
                <option value="">选择项目…</option>
                {projects?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {scope === 'project' && !selectedProjectId && (
            <div className="wb-state" data-testid="wb-tasks-no-project">
              <div className="wb-state__icon">📋</div>
              <div>请先选择项目</div>
            </div>
          )}

          {(scope === 'mine' || selectedProjectId) && loading && (
            <div className="wb-state" data-testid="wb-tasks-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载任务中…</div>
            </div>
          )}

          {(scope === 'mine' || selectedProjectId) && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-tasks-error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>
                重试
              </button>
            </div>
          )}

          {(scope === 'mine' || selectedProjectId) &&
            !loading &&
            !error &&
            total === 0 && (
              <div className="wb-state" data-testid="wb-tasks-empty">
                <div className="wb-state__icon">🗂️</div>
                <div>暂无任务</div>
                <div style={{ fontSize: 'var(--font-size-sm)' }}>
                  可通过工作台与 Agent 对话创建任务
                </div>
              </div>
            )}

          {(scope === 'mine' || selectedProjectId) && !loading && !error && total > 0 && (
            <div data-testid="wb-tasks-content">
              {/* 状态筛选 */}
              <div
                className="wb-task-filter"
                role="tablist"
                aria-label="任务状态筛选"
              >
                {STATUS_FILTERS.map((f) => {
                  const count =
                    f.key === 'all'
                      ? total
                      : taskList!.filter((t) => t.status === f.key).length;
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
                      data-testid={`wb-tasks-status-filter--${f.key}`}
                    >
                      {f.label}({count})
                    </button>
                  );
                })}
              </div>

              {/* 优先级筛选 */}
              <div
                className="wb-task-filter"
                role="tablist"
                aria-label="优先级筛选"
              >
                {PRIORITY_FILTERS.map((f) => (
                  <button
                    key={f.key}
                    type="button"
                    role="tab"
                    aria-selected={filterPriority === f.key}
                    className={`wb-task-filter__chip ${
                      filterPriority === f.key ? 'wb-task-filter__chip--active' : ''
                    }`}
                    onClick={() => setFilterPriority(f.key)}
                    data-testid={`wb-tasks-priority-filter--${f.key}`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>

              <div className="wb-section-label">
                任务（{filteredTasks.length}/{total}）
              </div>

              {filteredTasks.length > 0 ? (
                filteredTasks.map((task, i) => {
                  const statusInfo = STATUS_MAP[task.status] ?? {
                    label: task.status,
                    tone: 'muted' as ChipTone,
                  };
                  const pl = priorityLevel(task.priority);
                  const overdue =
                    task.claim_deadline &&
                    new Date(task.claim_deadline).getTime() < Date.now() &&
                    task.status !== 'completed';
                  return (
                    <div
                      key={task.id}
                      className="wb-taskitem"
                      data-testid={`wb-tasks-item--${i}`}
                    >
                      <div
                        className={`wb-taskitem__priority wb-taskitem__priority--${pl}`}
                        aria-label={`优先级 ${priorityLabel(task.priority)}`}
                      />
                      <div className="wb-taskitem__body">
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: 8,
                            marginBottom: 4,
                          }}
                        >
                          <div className="wb-taskitem__title">{task.title}</div>
                          <span
                            className={`wb-status-chip wb-status-chip--${statusInfo.tone}`}
                            data-testid={`wb-tasks-item-status--${i}`}
                          >
                            {statusInfo.label}
                          </span>
                        </div>
                        {task.description && (
                          <div className="wb-taskitem__desc">{task.description}</div>
                        )}
                        <div className="wb-taskitem__meta">
                          <span>
                            <span
                              className={`wb-status-chip wb-status-chip--${PRIORITY_TONE[pl]}`}
                            >
                              {priorityLabel(task.priority)}
                            </span>
                          </span>
                          <span>🤖 {task.assigned_agent}</span>
                          {task.assigned_user_name && (
                            <span>👤 {task.assigned_user_name}</span>
                          )}
                          <span
                            style={overdue ? { color: 'var(--danger)' } : undefined}
                          >
                            ⏰ {formatDeadline(task.claim_deadline)}
                          </span>
                          {task.claimable && (
                            <span style={{ color: 'var(--accent)' }}>可申领</span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="wb-state">
                  <div>当前筛选条件下暂无任务</div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
