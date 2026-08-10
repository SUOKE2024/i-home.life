/**
 * AgentMemoryPage — Agent 长期记忆管理（跨会话记忆的手动读写入口）
 *
 * 结构：Scaffold > AppBar(长期记忆) > 记忆列表（含 scope 过滤）> 手动保存表单
 * API（对齐 app/api/agent_memory.py，前缀 /agents/memory）：
 *   GET    /api/agents/memory          列出当前用户长期记忆（scope/project_id 过滤）
 *   POST   /api/agents/memory          手动保存一条记忆（upsert，同 key+scope+project_id 覆盖）
 *   DELETE /api/agents/memory/{id}     删除一条记忆
 *
 * category: preference | location | fact；scope: personal | project | team | org
 * 所有操作强制 user_id 隔离；后端 422 错误真实展示。
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { AgentMemoryItem, AgentMemoryListResponse } from '../types/domain';

/** 404/503 多为灰度 flag 未启用，追加诚实提示（保留后端真实 error 文案） */
function flagGuardMessage(status: number, error?: string): string {
  if (status === 404 || status === 503) {
    return `功能未启用（灰度 flag 默认关闭）：${error ?? `HTTP ${status}`}`;
  }
  return error ?? `HTTP ${status}`;
}

const CATEGORY_META: Record<string, { label: string; tone: string }> = {
  preference: { label: '偏好', tone: 'wb-status-chip--info' },
  location: { label: '位置', tone: 'wb-status-chip--accent' },
  fact: { label: '事实', tone: 'wb-status-chip--muted' },
};

const SCOPE_LABELS: Record<string, string> = {
  personal: '个人',
  project: '项目',
  team: '团队',
  org: '组织',
};

const SCOPE_FILTERS: Array<{ key: string; label: string }> = [
  { key: '', label: '全部' },
  { key: 'personal', label: '个人' },
  { key: 'project', label: '项目' },
  { key: 'team', label: '团队' },
  { key: 'org', label: '组织' },
];

export default function AgentMemoryPage() {
  const navigate = useNavigate();
  const [scopeFilter, setScopeFilter] = useState('');

  // 手动保存表单
  const [category, setCategory] = useState('fact');
  const [key, setKey] = useState('');
  const [value, setValue] = useState('');
  const [importance, setImportance] = useState('1');
  const [scope, setScope] = useState('personal');
  const [projectId, setProjectId] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const {
    data: list,
    loading,
    error,
    reload,
  } = useAsync<AgentMemoryListResponse | null>(async () => {
    const r = await apiClient.listAgentMemories<AgentMemoryListResponse>(
      scopeFilter ? { scope: scopeFilter } : {},
    );
    if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
    return r.data;
  }, [scopeFilter]);

  const items = list?.items ?? [];

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!key.trim() || !value.trim()) {
      setFormError('key 与 value 必填');
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      const r = await apiClient.createAgentMemory<AgentMemoryItem>({
        category,
        key: key.trim(),
        value: value.trim(),
        importance: Number(importance),
        scope,
        project_id: scope === 'project' ? (projectId.trim() || null) : null,
      });
      if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
      setKey('');
      setValue('');
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(memoryId: string) {
    setDeletingId(memoryId);
    setFormError(null);
    try {
      const r = await apiClient.deleteAgentMemory(memoryId);
      if (!r.isSuccess) throw new Error(flagGuardMessage(r.status, r.error));
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-agent-memory-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">🧠 Agent 长期记忆</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {formError && (
            <div
              className="wb-create-form__error"
              style={{ marginBottom: 12 }}
              data-testid="wb-agent-memory-error"
            >
              ⚠ {formError}
            </div>
          )}

          {/* 手动保存表单 */}
          <div className="wb-create-form" data-testid="wb-agent-memory-create">
            <div className="wb-create-form__head">
              <div className="wb-create-form__badge">📝</div>
              <div>
                <div className="wb-create-form__title">手动保存一条记忆</div>
                <div className="wb-create-form__subtitle">
                  同 key + scope + project_id 重复保存将覆盖更新（upsert）
                </div>
              </div>
            </div>
            <form onSubmit={handleSave}>
              <div className="wb-create-form__body">
                <div className="wb-create-form__row">
                  <div className="wb-create-form__field wb-create-form__field--grow">
                    <label className="wb-create-form__label" htmlFor="wb-agent-memory-key">
                      key <span className="wb-create-form__required">*</span>
                    </label>
                    <input
                      id="wb-agent-memory-key"
                      className="wb-input"
                      value={key}
                      onChange={(e) => setKey(e.target.value)}
                      placeholder="如 user_style"
                      data-testid="wb-agent-memory-key-input"
                    />
                  </div>
                  <div className="wb-create-form__field">
                    <label className="wb-create-form__label" htmlFor="wb-agent-memory-category">
                      类目
                    </label>
                    <select
                      id="wb-agent-memory-category"
                      className="wb-input"
                      value={category}
                      onChange={(e) => setCategory(e.target.value)}
                      data-testid="wb-agent-memory-category-select"
                    >
                      <option value="preference">偏好</option>
                      <option value="location">位置</option>
                      <option value="fact">事实</option>
                    </select>
                  </div>
                </div>
                <div className="wb-create-form__field">
                  <label className="wb-create-form__label" htmlFor="wb-agent-memory-value">
                    value <span className="wb-create-form__required">*</span>
                  </label>
                  <input
                    id="wb-agent-memory-value"
                    className="wb-input"
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    placeholder="记忆内容（≤200 字）"
                    data-testid="wb-agent-memory-value-input"
                  />
                </div>
                <div className="wb-create-form__row">
                  <div className="wb-create-form__field">
                    <label className="wb-create-form__label" htmlFor="wb-agent-memory-importance">
                      重要度（1-5）
                    </label>
                    <select
                      id="wb-agent-memory-importance"
                      className="wb-input"
                      value={importance}
                      onChange={(e) => setImportance(e.target.value)}
                      data-testid="wb-agent-memory-importance-select"
                    >
                      {[1, 2, 3, 4, 5].map((n) => (
                        <option key={n} value={n}>
                          {n}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="wb-create-form__field">
                    <label className="wb-create-form__label" htmlFor="wb-agent-memory-scope">
                      作用域
                    </label>
                    <select
                      id="wb-agent-memory-scope"
                      className="wb-input"
                      value={scope}
                      onChange={(e) => setScope(e.target.value)}
                      data-testid="wb-agent-memory-scope-select"
                    >
                      {Object.entries(SCOPE_LABELS).map(([k, label]) => (
                        <option key={k} value={k}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                {scope === 'project' && (
                  <div className="wb-create-form__field">
                    <label className="wb-create-form__label" htmlFor="wb-agent-memory-project">
                      project_id <span className="wb-create-form__required">*</span>
                    </label>
                    <input
                      id="wb-agent-memory-project"
                      className="wb-input"
                      value={projectId}
                      onChange={(e) => setProjectId(e.target.value)}
                      placeholder="scope=project 时必填"
                      data-testid="wb-agent-memory-project-input"
                    />
                  </div>
                )}
                <div className="wb-create-form__actions">
                  <button
                    className="wb-theme-option wb-theme-option--active"
                    type="submit"
                    disabled={saving}
                    data-testid="wb-agent-memory-save"
                    style={{ width: '100%' }}
                  >
                    {saving ? '保存中…' : '💾 保存记忆'}
                  </button>
                </div>
              </div>
            </form>
          </div>

          {/* 列表 */}
          <div className="wb-section-label" style={{ marginTop: 20 }}>
            长期记忆（{items.length}）
          </div>
          <div className="wb-task-filter" role="tablist" aria-label="作用域筛选">
            {SCOPE_FILTERS.map((f) => (
              <button
                key={f.key}
                type="button"
                role="tab"
                aria-selected={scopeFilter === f.key}
                className={`wb-task-filter__chip ${
                  scopeFilter === f.key ? 'wb-task-filter__chip--active' : ''
                }`}
                onClick={() => setScopeFilter(f.key)}
                data-testid={`wb-agent-memory-scope-filter--${f.key || 'all'}`}
              >
                {f.label}
              </button>
            ))}
          </div>

          {loading && (
            <div className="wb-state" data-testid="wb-agent-memory-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载记忆中…</div>
            </div>
          )}

          {error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-agent-memory-load-error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
              <button
                className="wb-theme-option wb-theme-option--active"
                onClick={reload}
                type="button"
              >
                重试
              </button>
            </div>
          )}

          {!loading && !error && items.length === 0 && (
            <div className="wb-state" data-testid="wb-agent-memory-empty">
              <div className="wb-state__icon">🗂️</div>
              <div>暂无长期记忆</div>
            </div>
          )}

          {!loading && !error && items.length > 0 && (
            <div data-testid="wb-agent-memory-content">
              {items.map((mem, i) => {
                const meta = CATEGORY_META[mem.category] ?? {
                  label: mem.category,
                  tone: 'wb-status-chip--muted',
                };
                return (
                  <div key={mem.id} className="wb-smart-card" data-testid={`wb-agent-memory-item--${i}`}>
                    <div className="wb-smart-card__head">
                      <div className="wb-smart-card__room">{mem.key}</div>
                      <span className={`wb-status-chip ${meta.tone}`}>{meta.label}</span>
                      <span className="wb-status-chip wb-status-chip--muted">
                        {SCOPE_LABELS[mem.scope] ?? mem.scope}
                      </span>
                      <span className="wb-status-chip wb-status-chip--accent">
                        ★{mem.importance}
                      </span>
                    </div>
                    <div
                      style={{
                        fontSize: 'var(--font-size-sm)',
                        marginTop: 6,
                      }}
                    >
                      {mem.value}
                    </div>
                    <div className="wb-smart-card__meta" style={{ marginTop: 6 }}>
                      <span>来源 {mem.source ?? '-'}</span>
                      {mem.project_id && <span>📁 {mem.project_id}</span>}
                      <span>🕒 {mem.updated_at ?? mem.created_at ?? '-'}</span>
                    </div>
                    <div className="wb-create-form__actions" style={{ marginTop: 8 }}>
                      <button
                        className="wb-theme-option"
                        type="button"
                        disabled={deletingId === mem.id}
                        onClick={() => handleDelete(mem.id)}
                        data-testid={`wb-agent-memory-delete--${i}`}
                      >
                        {deletingId === mem.id ? '删除中…' : '🗑 删除'}
                      </button>
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
