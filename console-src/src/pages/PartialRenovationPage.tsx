/**
 * PartialRenovationPage — 局部焕新（F42, v1.5.0）
 *
 * 结构：Scaffold > AppBar(局部焕新) > 模板区 + [项目选择器] > 创建表单 + 计划列表（可展开详情）
 * API（对齐 app/api/partial_renovation.py）：
 *   GET  /api/partial-renovation/templates            模板列表
 *   GET  /api/partial-renovation/plans/project/{pid}  项目计划列表
 *   POST /api/partial-renovation/plans                按模板创建计划
 *
 * scope_type: kitchen_refresh / bathroom_refresh / wall_refresh / single_room / full_renovation
 * budget_level: economic / comfort / quality
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type {
  PartialRenovationPlan,
  PartialRenovationTemplate,
  Project,
} from '../types/domain';

type ChipTone = 'muted' | 'info' | 'success' | 'warning' | 'danger' | 'accent';

const SCOPE_TONES: Record<string, ChipTone> = {
  kitchen_refresh: 'accent',
  bathroom_refresh: 'info',
  wall_refresh: 'success',
  single_room: 'warning',
  full_renovation: 'danger',
};

const BUDGET_LEVELS: Record<string, { label: string; tone: ChipTone }> = {
  economic: { label: '经济型', tone: 'muted' },
  comfort: { label: '舒适型', tone: 'info' },
  quality: { label: '品质型', tone: 'accent' },
};

const BUDGET_LEVEL_ORDER = ['economic', 'comfort', 'quality'];

export default function PartialRenovationPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [name, setName] = useState('');
  const [scopeType, setScopeType] = useState('kitchen_refresh');
  const [budgetLevel, setBudgetLevel] = useState('comfort');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  const { data: templates, loading: templatesLoading, error: templatesError } = useAsync<PartialRenovationTemplate[]>(
    async () => {
      const r = await apiClient.getPartialRenovationTemplates<PartialRenovationTemplate[]>();
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载模板失败');
      return r.data;
    },
    [],
  );

  const { data: plans, loading, error, reload } = useAsync<PartialRenovationPlan[] | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.getPartialRenovationPlans<PartialRenovationPlan[]>(selectedProjectId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [selectedProjectId],
  );

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedProjectId) return;
    if (!name.trim()) {
      setFormError('请填写计划名称');
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      const r = await apiClient.createPartialRenovationPlan({
        project_id: selectedProjectId,
        name: name.trim(),
        scope_type: scopeType,
        budget_level: budgetLevel,
      });
      if (!r.isSuccess) throw new Error(r.error ?? '创建失败');
      setName('');
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-partial-renovation-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">🔧 局部焕新</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {/* 模板区 */}
          <div className="wb-section-label">焕新模板</div>
          {templatesLoading && (
            <div className="wb-state" data-testid="wb-partial-renovation-templates-loading">
              <div className="wb-state__icon">⏳</div><div>加载模板中…</div>
            </div>
          )}
          {templatesError && !templatesLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-partial-renovation-templates-error">
              <div className="wb-state__icon">⚠</div><div>{templatesError}</div>
            </div>
          )}
          {!templatesLoading && !templatesError && (templates ?? []).length === 0 && (
            <div className="wb-state" data-testid="wb-partial-renovation-templates-empty">
              <div className="wb-state__icon">📋</div><div>暂无可用模板</div>
            </div>
          )}
          {(templates ?? []).map((t, i) => (
            <div key={t.scope_type} className="wb-smart-card" data-testid={`wb-partial-renovation-template--${i}`}>
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">{t.name}</div>
                <span className={`wb-status-chip wb-status-chip--${SCOPE_TONES[t.scope_type] ?? 'muted'}`}>{t.scope_type}</span>
              </div>
              <div className="wb-smart-card__meta">
                <span>⏱ {t.duration_days} 天</span>
                <span>📋 {t.task_count} 项任务</span>
                {BUDGET_LEVEL_ORDER.map((lv) => {
                  const range = t.budget_range?.[lv];
                  return range ? (
                    <span key={lv}>{BUDGET_LEVELS[lv]?.label ?? lv} ¥{range[0]}-{range[1]}万</span>
                  ) : null;
                })}
              </div>
            </div>
          ))}

          {/* 项目选择器 */}
          <div className="wb-project-picker" style={{ marginTop: 20 }}>
            <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)} aria-label="选择项目" data-testid="wb-partial-renovation-project-select">
              <option value="">选择项目…</option>
              {projects?.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </div>

          {!selectedProjectId && (
            <div className="wb-state" data-testid="wb-partial-renovation-no-project">
              <div className="wb-state__icon">📋</div><div>请先选择项目</div>
            </div>
          )}
          {selectedProjectId && loading && (
            <div className="wb-state" data-testid="wb-partial-renovation-loading">
              <div className="wb-state__icon">⏳</div><div>加载焕新计划中…</div>
            </div>
          )}
          {selectedProjectId && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-partial-renovation-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>重试</button>
            </div>
          )}

          {selectedProjectId && !loading && !error && (
            <div data-testid="wb-partial-renovation-content">
              {/* 创建表单 */}
              <div className="wb-create-form" data-testid="wb-partial-renovation-create">
                <div className="wb-create-form__head">
                  <div className="wb-create-form__badge">🔧</div>
                  <div>
                    <div className="wb-create-form__title">创建局部焕新计划</div>
                    <div className="wb-create-form__subtitle">按模板生成任务清单与干扰计划</div>
                  </div>
                </div>
                <form onSubmit={handleCreate}>
                  <div className="wb-create-form__body">
                    <div className="wb-create-form__field">
                      <label className="wb-create-form__label" htmlFor="wb-partial-renovation-name">计划名称 <span className="wb-create-form__required">*</span></label>
                      <input
                        id="wb-partial-renovation-name"
                        className="wb-input"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="如：厨房焕新一期"
                        data-testid="wb-partial-renovation-name-input"
                      />
                    </div>
                    <div className="wb-create-form__field">
                      <label className="wb-create-form__label" htmlFor="wb-partial-renovation-scope">焕新范围</label>
                      <select
                        id="wb-partial-renovation-scope"
                        className="wb-input"
                        value={scopeType}
                        onChange={(e) => setScopeType(e.target.value)}
                        data-testid="wb-partial-renovation-scope-select"
                      >
                        {(templates ?? []).map((t) => (
                          <option key={t.scope_type} value={t.scope_type}>{t.name}（{t.scope_type}）</option>
                        ))}
                      </select>
                    </div>
                    <div className="wb-create-form__field">
                      <label className="wb-create-form__label" htmlFor="wb-partial-renovation-budget">预算档位</label>
                      <select
                        id="wb-partial-renovation-budget"
                        className="wb-input"
                        value={budgetLevel}
                        onChange={(e) => setBudgetLevel(e.target.value)}
                        data-testid="wb-partial-renovation-budget-select"
                      >
                        {BUDGET_LEVEL_ORDER.map((lv) => (
                          <option key={lv} value={lv}>{BUDGET_LEVELS[lv]?.label ?? lv}</option>
                        ))}
                      </select>
                    </div>
                    {formError && (
                      <div className="wb-create-form__error" data-testid="wb-partial-renovation-form-error">
                        ⚠ {formError}
                      </div>
                    )}
                    <div className="wb-create-form__actions">
                      <button className="wb-theme-option wb-theme-option--active" type="submit" disabled={submitting} data-testid="wb-partial-renovation-submit" style={{ width: '100%' }}>
                        {submitting ? '创建中…' : '＋ 创建计划'}
                      </button>
                    </div>
                  </div>
                </form>
              </div>

              {/* 计划列表 */}
              <div className="wb-section-label">焕新计划（{plans?.length ?? 0}）</div>
              {!loading && !error && (plans?.length ?? 0) === 0 && (
                <div className="wb-state" data-testid="wb-partial-renovation-empty">
                  <div className="wb-state__icon">🔧</div><div>暂无焕新计划</div>
                  <div style={{ fontSize: 'var(--font-size-sm)' }}>在上方按模板创建首个计划</div>
                </div>
              )}
              {(plans ?? []).map((p, i) => {
                const scopeInfo = SCOPE_TONES[p.scope_type] ?? 'muted';
                const budgetInfo = BUDGET_LEVELS[p.budget_level] ?? { label: p.budget_level, tone: 'muted' as ChipTone };
                const isOpen = expandedId === p.id;
                const tasks = Array.isArray(p.tasks) ? (p.tasks as Array<Record<string, unknown>>) : [];
                const interference = p.interference_plan ?? {};
                return (
                  <div key={p.id} className="wb-smart-card" data-testid={`wb-partial-renovation-plan--${i}`}>
                    <button
                      className="wb-smart-card__head"
                      type="button"
                      style={{ width: '100%', background: 'none', border: 'none', padding: 0, cursor: 'pointer', textAlign: 'left', fontFamily: 'inherit' }}
                      onClick={() => setExpandedId(isOpen ? null : p.id)}
                      data-testid={`wb-partial-renovation-plan-toggle--${i}`}
                    >
                      <div className="wb-smart-card__room">{p.name}</div>
                      <span className={`wb-status-chip wb-status-chip--${scopeInfo}`}>{p.scope_type}</span>
                      <span className={`wb-status-chip wb-status-chip--${budgetInfo.tone}`}>{budgetInfo.label}</span>
                    </button>
                    <div className="wb-smart-card__meta">
                      <span>⏱ {p.duration_days} 天</span>
                      <span>💰 ¥{p.budget_lower}-{p.budget_upper}万</span>
                      <span>📋 {tasks.length} 项任务</span>
                      <span>{isOpen ? '▾ 收起详情' : '▸ 展开详情'}</span>
                    </div>
                    {isOpen && (
                      <div data-testid={`wb-partial-renovation-plan-detail--${i}`}>
                        <div className="wb-section-label" style={{ marginTop: 12 }}>任务清单</div>
                        {tasks.map((task, j) => (
                          <div key={j} className="wb-co-item" data-testid={`wb-partial-renovation-task--${i}-${j}`}>
                            <div>
                              <strong>{String(task.name ?? '')}</strong>
                              {task.detail ? <span style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}> · {String(task.detail)}</span> : null}
                            </div>
                            <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)' }}>
                              {String(task.phase ?? '')} · {String(task.duration_days ?? '')} 天
                              {task.needs_owner_confirm ? ' · 需业主确认' : ''}
                            </div>
                          </div>
                        ))}
                        {Object.keys(interference).length > 0 && (
                          <>
                            <div className="wb-section-label" style={{ marginTop: 12 }}>干扰计划</div>
                            <div className="wb-smart-card__meta" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
                              {Object.entries(interference).map(([key, value]) => (
                                <span key={key}><strong>{key}</strong>：{value}</span>
                              ))}
                            </div>
                          </>
                        )}
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
