/**
 * EcosystemPage — 生态桥接优先级 + 项目级生态凭据通道（F46, v1.5.0；2026-09-23 全链路修复）
 *
 * 结构：Scaffold > AppBar(生态桥接) > [项目选择器] > 只读状态报告（含项目级真实凭据就绪度）
 *       + 优先级策略 + 项目生态对接列表（凭据录入/删除）
 * API（对齐 app/api/ecosystem.py + app/api/scene_automation.py）：
 *   GET    /api/ecosystem/status?project_id={id}      状态报告（带项目时含真实凭据就绪度）
 *   GET    /api/ecosystem/bridges                     生态桥接优先级列表
 *   GET    /api/scene-automation/ecosystems/project/{projectId}   项目生态对接（config 已脱敏）
 *   POST   /api/scene-automation/ecosystems                      写入生态凭据（AES-256-GCM 加密落库）
 *   DELETE /api/scene-automation/ecosystems/{id}                 删除生态对接
 *
 * 诚实降级：
 *   - env 口径 `configured` 仅为历史检测（除 ecosystem_bridge_status 外无代码读取这些 env），
 *     真机就绪度以 has_credentials / project_configured 为准，UI 不得混同两者；
 *   - 凭据录入只在**该生态桥已接真机**（implemented）时才能真正生效，stub 生态保存后仍不可用，
 *     页面必须显式标注，不得让用户误以为「填了就能联动」；
 *   - 接口只回露凭据字段名，绝不再回显凭据值（含表单回显）。
 */

import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type {
  EcosystemBridgeStatus,
  EcosystemBridges,
  EcosystemIntegration,
  Project,
} from '../types/domain';

type ChipTone = 'muted' | 'info' | 'success' | 'warning' | 'danger' | 'accent';

/** 各生态的凭据字段（键名须与桥 connect() 读取的键一致，否则桥会诚实抛「需要凭据」） */
const CREDENTIAL_FIELDS: Record<
  string,
  Array<{ key: string; label: string; secret?: boolean; placeholder?: string }>
> = {
  mijia: [
    { key: 'username', label: '米家账号 *', placeholder: '手机号 / 小米 ID' },
    { key: 'password', label: '米家密码 *', secret: true },
  ],
  harmonyos: [
    { key: 'client_id', label: 'Client ID *' },
    { key: 'client_secret', label: 'Client Secret *', secret: true },
  ],
  homekit: [{ key: 'pairing_code', label: '配对码 *', placeholder: '如 123-45-678' }],
  tuya: [
    { key: 'access_id', label: 'Access ID *' },
    { key: 'access_secret', label: 'Access Secret *', secret: true },
  ],
};

const ECOSYSTEM_LABEL: Record<string, string> = {
  mijia: '米家',
  harmonyos: '华为鸿蒙',
  homekit: 'Apple HomeKit',
  tuya: '涂鸦',
  matter: 'Matter',
};

export default function EcosystemPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [ecosystem, setEcosystem] = useState<string>('mijia');
  const [credValues, setCredValues] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [removingId, setRemovingId] = useState<string | null>(null);

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  const { data: status, loading, error, reload } = useAsync<EcosystemBridgeStatus | null>(
    async () => {
      const r = await apiClient.getEcosystemStatus<EcosystemBridgeStatus>(
        selectedProjectId || undefined,
      );
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [selectedProjectId],
  );

  const { data: integrations, reload: reloadIntegrations } = useAsync<EcosystemIntegration[] | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.listEcosystemIntegrations<EcosystemIntegration[]>(selectedProjectId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '生态对接加载失败');
      return r.data;
    },
    [selectedProjectId],
  );

  const { data: bridges, error: bridgesError } = useAsync<EcosystemBridges | null>(async () => {
    const r = await apiClient.getEcosystemBridges<EcosystemBridges>();
    if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载优先级失败');
    return r.data;
  }, []);

  /** 桥是否已接真机（stub 生态保存凭据也无法真机联动，需显式标注） */
  const implementedByKey = useMemo(() => {
    const map: Record<string, boolean> = {};
    (status?.bridges ?? []).forEach((b) => { map[b.key] = b.implemented === true; });
    return map;
  }, [status]);

  const ecosystemOptions = useMemo(
    () => (status?.bridges ?? []).map((b) => b.key),
    [status],
  );

  const currentFields = CREDENTIAL_FIELDS[ecosystem] ?? [];
  const currentImplemented = implementedByKey[ecosystem] === true;

  async function submitCredentials() {
    setFormError(null);
    setNotice(null);
    if (!selectedProjectId) {
      setFormError('请先选择项目');
      return;
    }
    const config: Record<string, string> = {};
    for (const field of currentFields) {
      const value = (credValues[field.key] ?? '').trim();
      if (!value) {
        setFormError(`${field.label.replace(' *', '')}不可为空`);
        return;
      }
      config[field.key] = value;
    }
    setSubmitting(true);
    const r = await apiClient.createEcosystemIntegration({
      project_id: selectedProjectId,
      ecosystem,
      config: Object.keys(config).length > 0 ? config : null,
      notes: notes.trim() || null,
    });
    setSubmitting(false);
    if (!r.isSuccess) {
      setFormError(r.error ?? '凭据保存失败');
      return;
    }
    setNotice(
      `${ECOSYSTEM_LABEL[ecosystem] ?? ecosystem} 凭据已加密保存（AES-256-GCM；接口只回露字段名，不回显凭据值）`
      + (currentImplemented ? '' : '。注意：该生态桥仍为 stub，真机联动仍不可用'),
    );
    setCredValues({});
    setNotes('');
    await Promise.all([reloadIntegrations(), reload()]);
  }

  async function removeIntegration(id: string) {
    setFormError(null);
    setNotice(null);
    setRemovingId(id);
    const r = await apiClient.deleteEcosystemIntegration(id);
    setRemovingId(null);
    if (!r.isSuccess) {
      setFormError(r.error ?? '删除失败');
      return;
    }
    setNotice('生态对接已删除');
    await Promise.all([reloadIntegrations(), reload()]);
  }

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-ecosystem-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">🔗 生态桥接</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {/* 项目选择器（项目级真实凭据就绪度 / 生态对接均按项目维度） */}
          <div className="wb-section-label" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <label htmlFor="eco-project">项目</label>
            <select
              id="eco-project"
              className="wb-input wb-input--sm"
              value={selectedProjectId}
              onChange={(e) => { setSelectedProjectId(e.target.value); setNotice(null); setFormError(null); }}
              data-testid="wb-ecosystem-project-select"
            >
              {(!projects || projects.length === 0) && <option value="">暂无可选项目</option>}
              {(projects ?? []).map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>

          {loading && (
            <div className="wb-state" data-testid="wb-ecosystem-loading">
              <div className="wb-state__icon">⏳</div><div>加载生态桥接状态中…</div>
            </div>
          )}
          {error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-ecosystem-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>重试</button>
            </div>
          )}

          {!loading && !error && status && (
            <div data-testid="wb-ecosystem-content">
              {/* honest_note 提示条 */}
              <div className="wb-create-form" style={{ borderColor: 'rgba(201, 122, 59, 0.45)' }} data-testid="wb-ecosystem-honest-note">
                <div className="wb-create-form__head">
                  <div className="wb-create-form__badge">🤝</div>
                  <div>
                    <div className="wb-create-form__title">诚实降级说明</div>
                    <div className="wb-create-form__subtitle">{status.honest_note}</div>
                  </div>
                </div>
                {status.credential_channel_note && (
                  <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 6 }} data-testid="wb-ecosystem-credential-channel">
                    🔑 {status.credential_channel_note}
                  </div>
                )}
                <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)' }}>
                  状态更新于 {new Date(status.updated_at).toLocaleString('zh-CN')}
                  {status.project_id ? ` · 项目维度：${status.project_id}` : ' · 未选择项目（不展示项目凭据就绪度）'}
                </div>
              </div>

              {/* 生态表格 */}
              <div className="wb-section-label" style={{ marginTop: 20 }}>生态桥接状态</div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--font-size-sm)', background: 'var(--surface1)', borderRadius: 'var(--radius)', overflow: 'hidden' }} data-testid="wb-ecosystem-table">
                <thead>
                  <tr style={{ textAlign: 'left', color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}>
                    <th style={{ padding: '10px 12px' }}>优先级</th>
                    <th style={{ padding: '10px 12px' }}>生态</th>
                    <th style={{ padding: '10px 12px' }}>桥接实现</th>
                    <th style={{ padding: '10px 12px' }}>项目凭据</th>
                    <th style={{ padding: '10px 12px' }}>说明</th>
                  </tr>
                </thead>
                <tbody>
                  {status.bridges.map((bridge) => {
                    const implemented = bridge.implemented === true;
                    const projectConfigured = bridge.project_configured;
                    const credentialTone: ChipTone = projectConfigured === true
                      ? 'success'
                      : projectConfigured === false ? 'warning' : 'muted';
                    return (
                      <tr key={bridge.key} style={{ borderBottom: '1px solid var(--border)' }} data-testid={`wb-ecosystem-bridge--${bridge.key}`}>
                        <td style={{ padding: '10px 12px' }}>P{bridge.priority}</td>
                        <td style={{ padding: '10px 12px', fontWeight: 600 }}>{bridge.name}</td>
                        <td style={{ padding: '10px 12px' }}>
                          <span className={`wb-status-chip wb-status-chip--${implemented ? 'info' : 'muted'}`}>
                            {implemented ? '真机桥' : 'stub（未接真机）'}
                          </span>
                        </td>
                        <td style={{ padding: '10px 12px' }}>
                          <span
                            className={`wb-status-chip wb-status-chip--${credentialTone}`}
                            data-testid={`wb-ecosystem-credential--${bridge.key}`}
                          >
                            {projectConfigured === null || projectConfigured === undefined
                              ? '未查询该项目'
                              : projectConfigured
                                ? `已配置（${(bridge.credential_keys ?? []).join(' / ') || '—'}）`
                                : '项目未配置'}
                          </span>
                        </td>
                        <td style={{ padding: '10px 12px', color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>
                          {implemented
                            ? '凭据齐备即真机可下发；缺失则诚实标 pending'
                            : `桥接方法未实现（诚实降级）；env 口径需 ${bridge.required_env_keys.join(' / ') || '无'}`}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              {/* 项目生态对接（凭据通道 UI 入口） */}
              <div className="wb-section-label" style={{ marginTop: 20 }}>
                项目生态对接（真机凭据通道）
              </div>
              {notice && (
                <div className="wb-smart-card__meta" style={{ marginTop: 6 }} data-testid="wb-ecosystem-notice">
                  <span className="wb-status-chip wb-status-chip--success">{notice}</span>
                </div>
              )}
              {formError && (
                <div className="wb-smart-card__meta" style={{ marginTop: 6 }} data-testid="wb-ecosystem-form-error">
                  <span className="wb-status-chip wb-status-chip--danger">{formError}</span>
                </div>
              )}

              {integrations && integrations.length > 0 ? (
                <div className="wb-smart-card" style={{ marginTop: 8 }} data-testid="wb-ecosystem-integrations">
                  {integrations.map((eco) => (
                    <div
                      key={eco.id}
                      className="wb-smart-card__meta"
                      style={{ justifyContent: 'space-between', alignItems: 'center', gap: 8 }}
                      data-testid={`wb-ecosystem-integration--${eco.ecosystem}`}
                    >
                      <span>
                        <strong>{ECOSYSTEM_LABEL[eco.ecosystem] ?? eco.ecosystem}</strong>
                        {' '}
                        <span className="wb-status-chip wb-status-chip--muted">{eco.auth_status}</span>
                        {' '}
                        凭据字段：{(eco.config?.keys ?? []).join(' / ') || '无（未回露值）'}
                      </span>
                      <button
                        className="wb-btn wb-btn--sm wb-btn--ghost"
                        type="button"
                        disabled={removingId === eco.id}
                        onClick={() => removeIntegration(eco.id)}
                        data-testid={`wb-ecosystem-remove--${eco.ecosystem}`}
                      >
                        {removingId === eco.id ? '删除中…' : '删除'}
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="wb-smart-card" style={{ marginTop: 8 }} data-testid="wb-ecosystem-integrations-empty">
                  <div className="wb-smart-card__meta">
                    <span className="wb-status-chip wb-status-chip--muted">
                      该项目暂无生态对接 → 真机命令将兜底 matter stub，实际保持 pending（诚实标注）
                    </span>
                  </div>
                </div>
              )}

              {/* 凭据录入 */}
              <div className="wb-smart-card" style={{ marginTop: 8 }} data-testid="wb-ecosystem-credential-form">
                <div className="wb-smart-card__head">
                  <div className="wb-smart-card__room">录入生态凭据（按项目加密落库）</div>
                </div>
                <div className="wb-field">
                  <label className="wb-field__label" htmlFor="eco-ecosystem">生态</label>
                  <select
                    id="eco-ecosystem"
                    className="wb-input"
                    value={ecosystem}
                    onChange={(e) => { setEcosystem(e.target.value); setCredValues({}); setFormError(null); }}
                    data-testid="wb-ecosystem-form-ecosystem"
                  >
                    {(ecosystemOptions.length > 0 ? ecosystemOptions : Object.keys(CREDENTIAL_FIELDS)).map((key) => (
                      <option key={key} value={key}>{ECOSYSTEM_LABEL[key] ?? key}</option>
                    ))}
                  </select>
                </div>

                {!currentImplemented && (
                  <div className="wb-smart-card__meta" style={{ marginTop: 6 }} data-testid="wb-ecosystem-stub-warning">
                    <span className="wb-status-chip wb-status-chip--warning">
                      该生态桥为 stub（未接真机）：保存凭据不会带来真机联动能力，命令仍诚实标 pending
                    </span>
                  </div>
                )}

                {currentFields.map((field) => (
                  <div className="wb-field" key={field.key}>
                    <label className="wb-field__label" htmlFor={`eco-cred-${field.key}`}>{field.label}</label>
                    <input
                      id={`eco-cred-${field.key}`}
                      className="wb-input"
                      type={field.secret ? 'password' : 'text'}
                      placeholder={field.placeholder}
                      autoComplete="off"
                      value={credValues[field.key] ?? ''}
                      onChange={(e) => setCredValues({ ...credValues, [field.key]: e.target.value })}
                      data-testid={`wb-ecosystem-form-cred--${field.key}`}
                    />
                  </div>
                ))}
                {currentFields.length === 0 && (
                  <div className="wb-smart-card__meta" style={{ marginTop: 6 }}>
                    该生态无需凭据
                  </div>
                )}

                <div className="wb-field">
                  <label className="wb-field__label" htmlFor="eco-notes">备注（可选）</label>
                  <input
                    id="eco-notes"
                    className="wb-input"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="如：米家账号归属人 / 对接联系人"
                    data-testid="wb-ecosystem-form-notes"
                  />
                </div>
                <div className="wb-smart-card__meta" style={{ marginTop: 8 }}>
                  <button
                    className="wb-btn wb-btn--sm"
                    type="button"
                    disabled={submitting || !selectedProjectId}
                    onClick={submitCredentials}
                    data-testid="wb-ecosystem-form-submit"
                  >
                    {submitting ? '保存中…' : '加密保存凭据'}
                  </button>
                </div>
                <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 6 }}>
                  🔒 凭据经 AES-256-GCM 加密落库；接口仅回露字段名，不回显值（保存后表单即刻清空）
                </div>
              </div>

              {/* 优先级策略说明 */}
              {bridges && !bridgesError && (
                <div className="wb-smart-card" style={{ marginTop: 16 }} data-testid="wb-ecosystem-strategy">
                  <div className="wb-smart-card__head">
                    <div className="wb-smart-card__room">优先级策略</div>
                  </div>
                  <div className="wb-smart-card__meta">
                    <span>📌 {bridges.priority_strategy}</span>
                  </div>
                  <div className="wb-smart-card__meta" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 2, marginTop: 8 }}>
                    {bridges.bridges.map((b) => (
                      <span key={b.key}>
                        <strong>P{b.priority} {b.name}</strong>（{b.bridge}）
                        {b.implemented ? ' · 已接真机' : ' · 当前桥接为 stub'}
                        {b.required_env_keys.length > 0 ? ` · env 口径需 ${b.required_env_keys.join(' / ')}` : ''}
                      </span>
                    ))}
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