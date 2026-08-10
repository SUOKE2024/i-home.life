/**
 * AgentSkillsPage — Agent Skill 资产（scope-owned 可授权共享的 Agent 能力）
 *
 * 结构：Scaffold > AppBar(Skill 资产) > 列表（scope 过滤）> 创建/导入表单 > 选中 Skill 详情与操作
 * API（对齐 app/api/agent_skills.py，前缀 /agents/skills；创建/导入受 agent_skill_enabled flag 控制）：
 *   GET    /api/agents/skills                列表（scope / include_archived 过滤）
 *   POST   /api/agents/skills                创建（status=draft；flag 关闭返回 503）
 *   GET    /api/agents/skills/{id}           详情
 *   DELETE /api/agents/skills/{id}           软删除（仅 owner）
 *   POST   /api/agents/skills/{id}/share     授权共享（grant_to + share_scope）
 *   POST   /api/agents/skills/{id}/promote   提升 org 级（仅 admin，403 否则）
 *   POST   /api/agents/skills/{id}/rollback  回退指定 version（仅 owner）
 *   POST   /api/agents/skills/import         从 git URL 导入（flag 关闭返回 503）
 *   POST   /api/agents/skills/{id}/instantiate 实例化执行测试消息
 *
 * 后端 403/409/422 错误真实展示，不伪造。
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type {
  AgentSkillInstantiateResponse,
  AgentSkillItem,
  AgentSkillListResponse,
} from '../types/domain';

/** 404/503 多为灰度 flag 未启用，追加诚实提示（保留后端真实 error 文案） */
function flagGuardMessage(status: number, error?: string): string {
  if (status === 404 || status === 503) {
    return `功能未启用（灰度 flag 默认关闭）：${error ?? `HTTP ${status}`}`;
  }
  return error ?? `HTTP ${status}`;
}

const SCOPE_LABELS: Record<string, string> = {
  personal: '个人',
  project: '项目',
  team: '团队',
  org: '组织',
};

const STATUS_META: Record<string, { label: string; tone: string }> = {
  draft: { label: '草稿', tone: 'wb-status-chip--muted' },
  active: { label: '生效', tone: 'wb-status-chip--success' },
  archived: { label: '已归档', tone: 'wb-status-chip--danger' },
};

const SCOPE_FILTERS: Array<{ key: string; label: string }> = [
  { key: '', label: '全部' },
  { key: 'personal', label: '个人' },
  { key: 'project', label: '项目' },
  { key: 'team', label: '团队' },
  { key: 'org', label: '组织' },
];

export default function AgentSkillsPage() {
  const navigate = useNavigate();
  const [scopeFilter, setScopeFilter] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // 创建表单
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [agentName, setAgentName] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [provider, setProvider] = useState('deepseek');
  const [costTier, setCostTier] = useState('standard');
  const [ownerScope, setOwnerScope] = useState('personal');
  const [toolsJson, setToolsJson] = useState('[]');
  const [acceptJson, setAcceptJson] = useState('[]');

  // 导入表单
  const [gitUrl, setGitUrl] = useState('');

  // 操作区（选中 Skill）
  const [shareTo, setShareTo] = useState('');
  const [shareScope, setShareScope] = useState('grant');
  const [rollbackVersion, setRollbackVersion] = useState('');
  const [testMessage, setTestMessage] = useState('你好');
  const [instantiateResult, setInstantiateResult] =
    useState<AgentSkillInstantiateResponse | null>(null);

  const [busy, setBusy] = useState(false);
  const [opError, setOpError] = useState<string | null>(null);

  const {
    data: list,
    loading,
    error,
    reload,
  } = useAsync<AgentSkillListResponse | null>(async () => {
    const r = await apiClient.listAgentSkills<AgentSkillListResponse>(
      scopeFilter ? { scope: scopeFilter } : {},
    );
    if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
    return r.data;
  }, [scopeFilter]);

  const {
    data: detail,
    loading: detailLoading,
    error: detailError,
    reload: reloadDetail,
  } = useAsync<AgentSkillItem | null>(async () => {
    if (!selectedId) return null;
    const r = await apiClient.getAgentSkill<AgentSkillItem>(selectedId);
    if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
    return r.data;
  }, [selectedId]);

  const items = list?.items ?? [];

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !agentName.trim()) {
      setOpError('name 与 agent_name 必填');
      return;
    }
    let tools: unknown[];
    let acceptance: unknown[];
    try {
      tools = JSON.parse(toolsJson || '[]');
      acceptance = JSON.parse(acceptJson || '[]');
    } catch {
      setOpError('tools / acceptance_criteria 必须是合法 JSON 数组');
      return;
    }
    setBusy(true);
    setOpError(null);
    try {
      const r = await apiClient.createAgentSkill<AgentSkillItem>({
        name: name.trim(),
        description: description.trim(),
        agent_name: agentName.trim(),
        system_prompt: systemPrompt,
        provider,
        tools,
        cost_tier: costTier,
        acceptance_criteria: acceptance,
        owner_scope: ownerScope,
      });
      if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
      setName('');
      setDescription('');
      setAgentName('');
      setSystemPrompt('');
      setToolsJson('[]');
      setAcceptJson('[]');
      await reload();
    } catch (err) {
      setOpError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleImport() {
    if (gitUrl.trim().length < 10) {
      setOpError('git_url 至少 10 个字符');
      return;
    }
    setBusy(true);
    setOpError(null);
    try {
      const r = await apiClient.importAgentSkill<AgentSkillItem>({ git_url: gitUrl.trim() });
      if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
      setGitUrl('');
      await reload();
    } catch (err) {
      setOpError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function runSkillAction(kind: 'share' | 'promote' | 'rollback' | 'instantiate' | 'delete') {
    if (!selectedId) return;
    setBusy(true);
    setOpError(null);
    setInstantiateResult(null);
    try {
      if (kind === 'share') {
        const grantTo = shareTo
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean);
        if (shareScope === 'grant' && grantTo.length === 0) {
          throw new Error('share_scope=grant 时 grant_to 必填（逗号分隔的用户 id）');
        }
        const r = await apiClient.shareAgentSkill<AgentSkillItem>(selectedId, {
          grant_to: grantTo,
          share_scope: shareScope,
        });
        if (!r.isSuccess) throw new Error(flagGuardMessage(r.status, r.error));
      } else if (kind === 'promote') {
        const r = await apiClient.promoteAgentSkill<AgentSkillItem>(selectedId);
        if (!r.isSuccess) throw new Error(flagGuardMessage(r.status, r.error));
      } else if (kind === 'rollback') {
        const v = Number(rollbackVersion);
        if (!Number.isInteger(v) || v < 1) throw new Error('target_version 必须是 ≥1 的整数');
        const r = await apiClient.rollbackAgentSkill<AgentSkillItem>(selectedId, v);
        if (!r.isSuccess) throw new Error(flagGuardMessage(r.status, r.error));
      } else if (kind === 'instantiate') {
        const r = await apiClient.instantiateAgentSkill<AgentSkillInstantiateResponse>(
          selectedId,
          testMessage,
        );
        if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
        setInstantiateResult(r.data);
        return; // 不刷新详情
      } else {
        const r = await apiClient.deleteAgentSkill(selectedId);
        if (!r.isSuccess) throw new Error(flagGuardMessage(r.status, r.error));
        setSelectedId(null);
        await reload();
        return;
      }
      await reloadDetail();
      await reload();
    } catch (err) {
      setOpError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-agent-skills-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">🧩 Agent Skill 资产</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {opError && (
            <div
              className="wb-create-form__error"
              style={{ marginBottom: 12 }}
              data-testid="wb-agent-skills-op-error"
            >
              ⚠ {opError}
            </div>
          )}

          {/* 创建 Skill */}
          <div className="wb-create-form" data-testid="wb-agent-skills-create">
            <div className="wb-create-form__head">
              <div className="wb-create-form__badge">➕</div>
              <div>
                <div className="wb-create-form__title">创建 Skill（draft）</div>
                <div className="wb-create-form__subtitle">
                  受 agent_skill_enabled flag 控制，未启用时后端返回 503 诚实提示
                </div>
              </div>
            </div>
            <form onSubmit={handleCreate}>
              <div className="wb-create-form__body">
                <div className="wb-create-form__row">
                  <div className="wb-create-form__field wb-create-form__field--grow">
                    <label className="wb-create-form__label" htmlFor="wb-agent-skills-name">
                      name <span className="wb-create-form__required">*</span>
                    </label>
                    <input
                      id="wb-agent-skills-name"
                      className="wb-input"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Skill 名称（≤100 字）"
                      data-testid="wb-agent-skills-name-input"
                    />
                  </div>
                  <div className="wb-create-form__field">
                    <label className="wb-create-form__label" htmlFor="wb-agent-skills-agent">
                      agent_name <span className="wb-create-form__required">*</span>
                    </label>
                    <input
                      id="wb-agent-skills-agent"
                      className="wb-input"
                      value={agentName}
                      onChange={(e) => setAgentName(e.target.value)}
                      placeholder="如 designer"
                      data-testid="wb-agent-skills-agent-input"
                    />
                  </div>
                </div>
                <div className="wb-create-form__row">
                  <div className="wb-create-form__field wb-create-form__field--grow">
                    <label className="wb-create-form__label" htmlFor="wb-agent-skills-provider">
                      provider
                    </label>
                    <input
                      id="wb-agent-skills-provider"
                      className="wb-input"
                      value={provider}
                      onChange={(e) => setProvider(e.target.value)}
                      placeholder="deepseek"
                      data-testid="wb-agent-skills-provider-input"
                    />
                  </div>
                  <div className="wb-create-form__field">
                    <label className="wb-create-form__label" htmlFor="wb-agent-skills-cost">
                      cost_tier
                    </label>
                    <input
                      id="wb-agent-skills-cost"
                      className="wb-input"
                      value={costTier}
                      onChange={(e) => setCostTier(e.target.value)}
                      placeholder="standard"
                      data-testid="wb-agent-skills-cost-input"
                    />
                  </div>
                  <div className="wb-create-form__field">
                    <label className="wb-create-form__label" htmlFor="wb-agent-skills-owner">
                      owner_scope
                    </label>
                    <select
                      id="wb-agent-skills-owner"
                      className="wb-input"
                      value={ownerScope}
                      onChange={(e) => setOwnerScope(e.target.value)}
                      data-testid="wb-agent-skills-owner-select"
                    >
                      {Object.entries(SCOPE_LABELS).map(([k, label]) => (
                        <option key={k} value={k}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="wb-create-form__field">
                  <label className="wb-create-form__label" htmlFor="wb-agent-skills-desc">
                    description
                  </label>
                  <input
                    id="wb-agent-skills-desc"
                    className="wb-input"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Skill 描述（≤2000 字）"
                    data-testid="wb-agent-skills-desc-input"
                  />
                </div>
                <div className="wb-create-form__field wb-create-form__field--area">
                  <label className="wb-create-form__label" htmlFor="wb-agent-skills-prompt">
                    system_prompt
                  </label>
                  <textarea
                    id="wb-agent-skills-prompt"
                    className="wb-input"
                    rows={4}
                    value={systemPrompt}
                    onChange={(e) => setSystemPrompt(e.target.value)}
                    placeholder="系统提示词（≤20000 字）"
                    data-testid="wb-agent-skills-prompt-input"
                  />
                </div>
                <div className="wb-create-form__row">
                  <div className="wb-create-form__field wb-create-form__field--grow">
                    <label className="wb-create-form__label" htmlFor="wb-agent-skills-tools">
                      tools（JSON 数组）
                    </label>
                    <input
                      id="wb-agent-skills-tools"
                      className="wb-input"
                      value={toolsJson}
                      onChange={(e) => setToolsJson(e.target.value)}
                      placeholder='[]'
                      data-testid="wb-agent-skills-tools-input"
                    />
                  </div>
                  <div className="wb-create-form__field wb-create-form__field--grow">
                    <label className="wb-create-form__label" htmlFor="wb-agent-skills-accept">
                      acceptance_criteria（JSON 数组）
                    </label>
                    <input
                      id="wb-agent-skills-accept"
                      className="wb-input"
                      value={acceptJson}
                      onChange={(e) => setAcceptJson(e.target.value)}
                      placeholder='[]'
                      data-testid="wb-agent-skills-accept-input"
                    />
                  </div>
                </div>
                <div className="wb-create-form__actions">
                  <button
                    className="wb-theme-option wb-theme-option--active"
                    type="submit"
                    disabled={busy}
                    data-testid="wb-agent-skills-create-btn"
                    style={{ width: '100%' }}
                  >
                    {busy ? '提交中…' : '🚀 创建 Skill'}
                  </button>
                </div>
              </div>
            </form>
          </div>

          {/* 导入 Skill 包 */}
          <div className="wb-create-form" style={{ marginTop: 16 }} data-testid="wb-agent-skills-import">
            <div className="wb-create-form__head">
              <div className="wb-create-form__badge">📦</div>
              <div>
                <div className="wb-create-form__title">从 git URL 导入 Skill 包</div>
                <div className="wb-create-form__subtitle">
                  字段白名单解析，URL 不可达或格式错误时后端返回 422 诚实报错
                </div>
              </div>
            </div>
            <div className="wb-create-form__body">
              <div className="wb-create-form__field">
                <label className="wb-create-form__label" htmlFor="wb-agent-skills-giturl">
                  git_url <span className="wb-create-form__required">*</span>
                </label>
                <input
                  id="wb-agent-skills-giturl"
                  className="wb-input"
                  value={gitUrl}
                  onChange={(e) => setGitUrl(e.target.value)}
                  placeholder="https://raw.githubusercontent.com/.../skill.json"
                  data-testid="wb-agent-skills-giturl-input"
                />
              </div>
              <div className="wb-create-form__actions">
                <button
                  className="wb-theme-option wb-theme-option--active"
                  type="button"
                  disabled={busy}
                  onClick={handleImport}
                  data-testid="wb-agent-skills-import-btn"
                  style={{ width: '100%' }}
                >
                  {busy ? '导入中…' : '📥 导入'}
                </button>
              </div>
            </div>
          </div>

          {/* 列表 */}
          <div className="wb-section-label" style={{ marginTop: 20 }}>
            Skill 列表（{items.length}）
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
                data-testid={`wb-agent-skills-scope-filter--${f.key || 'all'}`}
              >
                {f.label}
              </button>
            ))}
          </div>

          {loading && (
            <div className="wb-state" data-testid="wb-agent-skills-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载 Skill 列表…</div>
            </div>
          )}

          {error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-agent-skills-list-error">
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
            <div className="wb-state" data-testid="wb-agent-skills-empty">
              <div className="wb-state__icon">🧩</div>
              <div>暂无 Skill 资产</div>
            </div>
          )}

          {!loading && !error && items.length > 0 && (
            <div data-testid="wb-agent-skills-content">
              {items.map((skill, i) => {
                const meta = STATUS_META[skill.status] ?? {
                  label: skill.status,
                  tone: 'wb-status-chip--muted',
                };
                return (
                  <button
                    key={skill.id}
                    type="button"
                    className="wb-smart-card"
                    style={{
                      display: 'block',
                      width: '100%',
                      textAlign: 'left',
                      cursor: 'pointer',
                      border:
                        selectedId === skill.id ? '1px solid var(--accent)' : undefined,
                    }}
                    onClick={() => setSelectedId(skill.id)}
                    data-testid={`wb-agent-skills-item--${i}`}
                  >
                    <div className="wb-smart-card__head">
                      <div className="wb-smart-card__room">{skill.name}</div>
                      <span className={`wb-status-chip ${meta.tone}`}>{meta.label}</span>
                      <span className="wb-status-chip wb-status-chip--muted">
                        v{skill.version}
                      </span>
                      <span className="wb-status-chip wb-status-chip--info">
                        {skill.agent_name}
                      </span>
                    </div>
                    {skill.description && (
                      <div className="wb-smart-card__meta" style={{ marginTop: 6 }}>
                        <span>{skill.description}</span>
                      </div>
                    )}
                    <div className="wb-smart-card__meta" style={{ marginTop: 4 }}>
                      <span>
                        {SCOPE_LABELS[skill.owner_scope] ?? skill.owner_scope} ·{' '}
                        {skill.provider} · {skill.cost_tier}
                      </span>
                      <span>🧩 工具 {skill.tools.length}</span>
                      {skill.share_scope && <span>共享 {skill.share_scope}</span>}
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          {/* 选中 Skill 详情与操作 */}
          {selectedId && (
            <div style={{ marginTop: 16 }}>
              <div className="wb-section-label">Skill 详情与操作</div>
              {detailLoading && (
                <div className="wb-state" data-testid="wb-agent-skills-detail-loading">
                  <div className="wb-state__icon">⏳</div>
                  <div>加载详情…</div>
                </div>
              )}
              {detailError && !detailLoading && (
                <div className="wb-state wb-state--error" data-testid="wb-agent-skills-detail-error">
                  <div className="wb-state__icon">⚠</div>
                  <div>{detailError}</div>
                  <button
                    className="wb-theme-option wb-theme-option--active"
                    onClick={reloadDetail}
                    type="button"
                  >
                    重试
                  </button>
                </div>
              )}
              {detail && !detailLoading && (
                <div className="wb-smart-card" data-testid="wb-agent-skills-detail">
                  <div className="wb-smart-card__head">
                    <div className="wb-smart-card__room">
                      {detail.name}（v{detail.version}）
                    </div>
                    <span
                      className={`wb-status-chip ${
                        (STATUS_META[detail.status] ?? { tone: 'wb-status-chip--muted' }).tone
                      }`}
                    >
                      {(STATUS_META[detail.status] ?? { label: detail.status }).label}
                    </span>
                  </div>
                  <div className="wb-smart-card__meta">
                    <span>🤖 {detail.agent_name}</span>
                    <span>⚙️ {detail.provider}</span>
                    <span>💰 {detail.cost_tier}</span>
                    <span>🌐 {SCOPE_LABELS[detail.owner_scope] ?? detail.owner_scope}</span>
                    <span>共享 {detail.share_scope}</span>
                  </div>
                  {detail.description && (
                    <div style={{ fontSize: 'var(--font-size-sm)', marginTop: 6 }}>
                      {detail.description}
                    </div>
                  )}
                  <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 8 }}>
                    system_prompt
                  </div>
                  <pre
                    style={{
                      fontSize: 'var(--font-size-xs)',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                      margin: '4px 0 0',
                      maxHeight: 160,
                      overflow: 'auto',
                    }}
                  >
                    {detail.system_prompt || '-'}
                  </pre>
                  <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 8 }}>
                    tools（{detail.tools.length}）
                  </div>
                  <pre
                    style={{
                      fontSize: 'var(--font-size-xs)',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                      margin: '4px 0 0',
                      maxHeight: 140,
                      overflow: 'auto',
                    }}
                  >
                    {JSON.stringify(detail.tools, null, 2)}
                  </pre>
                  {detail.share_grants.length > 0 && (
                    <>
                      <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 8 }}>
                        授权名单（{detail.share_grants.length}）
                      </div>
                      <div
                        style={{
                          display: 'flex',
                          flexWrap: 'wrap',
                          gap: 6,
                          marginTop: 6,
                        }}
                      >
                        {detail.share_grants.map((g, gi) => (
                          <span key={gi} className="wb-status-chip wb-status-chip--info">
                            {String(g)}
                          </span>
                        ))}
                      </div>
                    </>
                  )}
                  <div className="wb-smart-card__meta" style={{ marginTop: 8 }}>
                    <span>创建 {detail.created_at ?? '-'}</span>
                    <span>更新 {detail.updated_at ?? '-'}</span>
                    {detail.skill_pack_source && <span>📦 {detail.skill_pack_source}</span>}
                  </div>

                  {/* 操作区 */}
                  <div style={{ marginTop: 12, borderTop: '1px solid var(--border, rgba(107,105,120,0.2))', paddingTop: 10 }}>
                    <div className="wb-create-form__label">共享授权</div>
                    <div className="wb-create-form__row">
                      <div className="wb-create-form__field wb-create-form__field--grow">
                        <input
                          className="wb-input"
                          value={shareTo}
                          onChange={(e) => setShareTo(e.target.value)}
                          placeholder="grant_to（逗号分隔的用户 id）"
                          data-testid="wb-agent-skills-share-to"
                        />
                      </div>
                      <div className="wb-create-form__field">
                        <select
                          className="wb-input"
                          value={shareScope}
                          onChange={(e) => setShareScope(e.target.value)}
                          data-testid="wb-agent-skills-share-scope"
                        >
                          <option value="grant">grant</option>
                          <option value="org">org</option>
                          <option value="public">public</option>
                        </select>
                      </div>
                    </div>
                    <div className="wb-create-form__row" style={{ marginTop: 8 }}>
                      <div className="wb-create-form__field wb-create-form__field--grow">
                        <input
                          className="wb-input"
                          value={rollbackVersion}
                          onChange={(e) => setRollbackVersion(e.target.value)}
                          placeholder="回退目标 version（≥1）"
                          data-testid="wb-agent-skills-rollback-input"
                        />
                      </div>
                      <div className="wb-create-form__field wb-create-form__field--grow">
                        <input
                          className="wb-input"
                          value={testMessage}
                          onChange={(e) => setTestMessage(e.target.value)}
                          placeholder="实例化测试消息"
                          data-testid="wb-agent-skills-test-input"
                        />
                      </div>
                    </div>
                    <div
                      className="wb-create-form__actions"
                      style={{ marginTop: 10, flexWrap: 'wrap' }}
                    >
                      <button
                        className="wb-theme-option wb-theme-option--active"
                        type="button"
                        disabled={busy}
                        onClick={() => runSkillAction('share')}
                        data-testid="wb-agent-skills-share-btn"
                      >
                        🔗 共享
                      </button>
                      <button
                        className="wb-theme-option"
                        type="button"
                        disabled={busy}
                        onClick={() => runSkillAction('promote')}
                        data-testid="wb-agent-skills-promote-btn"
                      >
                        ⬆ 提升 org 级
                      </button>
                      <button
                        className="wb-theme-option"
                        type="button"
                        disabled={busy}
                        onClick={() => runSkillAction('rollback')}
                        data-testid="wb-agent-skills-rollback-btn"
                      >
                        ↩ 回退
                      </button>
                      <button
                        className="wb-theme-option"
                        type="button"
                        disabled={busy}
                        onClick={() => runSkillAction('instantiate')}
                        data-testid="wb-agent-skills-instantiate-btn"
                      >
                        ⚡ 实例化
                      </button>
                      <button
                        className="wb-theme-option"
                        type="button"
                        disabled={busy}
                        onClick={() => runSkillAction('delete')}
                        data-testid="wb-agent-skills-delete-btn"
                      >
                        🗑 软删除
                      </button>
                    </div>
                    {instantiateResult && (
                      <div
                        className="wb-smart-card"
                        style={{ marginTop: 10 }}
                        data-testid="wb-agent-skills-instantiate-result"
                      >
                        <div className="wb-smart-card__head">
                          <div className="wb-smart-card__room">
                            {instantiateResult.agent_name}
                          </div>
                          <span
                            className={`wb-status-chip ${
                              instantiateResult.status === 'ok'
                                ? 'wb-status-chip--success'
                                : 'wb-status-chip--warning'
                            }`}
                          >
                            {instantiateResult.status === 'ok' ? '成功' : '降级'}
                          </span>
                        </div>
                        <div style={{ whiteSpace: 'pre-wrap', fontSize: 'var(--font-size-sm)', marginTop: 6 }}>
                          {instantiateResult.reply}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
