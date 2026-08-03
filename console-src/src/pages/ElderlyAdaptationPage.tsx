/**
 * ElderlyAdaptationPage — 适老改造（F41, v1.5.0）
 *
 * 结构：Scaffold > AppBar(适老改造) > [项目选择器] > 创建表单 + 方案卡片列表
 * API（对齐 app/api/elderly_adaptation.py）：
 *   GET  /api/elderly-adaptation/schemes/project/{projectId}
 *   POST /api/elderly-adaptation/schemes
 *   POST /api/elderly-adaptation/schemes/{id}/validate
 *
 * occupant_type: elderly_living / semi_selfcare / nursing / family
 * compliance_status: pass / warning / fail（GB 50763-2012）
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type {
  ElderlyAdaptationScheme,
  ElderlyAdaptationValidation,
  Project,
} from '../types/domain';

type ChipTone = 'muted' | 'info' | 'success' | 'warning' | 'danger' | 'accent';

const OCCUPANT_TYPES: Record<string, { label: string; tone: ChipTone }> = {
  elderly_living: { label: '老人独立生活', tone: 'info' },
  semi_selfcare: { label: '半自理', tone: 'warning' },
  nursing: { label: '失能护理', tone: 'accent' },
  family: { label: '多代同堂', tone: 'success' },
};

const COMPLIANCE_TONES: Record<string, ChipTone> = { pass: 'success', warning: 'warning', fail: 'danger' };
const COMPLIANCE_LABELS: Record<string, string> = { pass: '合规', warning: '待复核', fail: '不合规' };

export default function ElderlyAdaptationPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [name, setName] = useState('');
  const [occupantType, setOccupantType] = useState('elderly_living');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [validatingId, setValidatingId] = useState<string | null>(null);
  const [validations, setValidations] = useState<Record<string, ElderlyAdaptationValidation>>({});

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  const { data: schemes, loading, error, reload } = useAsync<ElderlyAdaptationScheme[] | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.getElderlyAdaptationSchemes<ElderlyAdaptationScheme[]>(selectedProjectId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [selectedProjectId],
  );

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedProjectId) return;
    if (!name.trim()) {
      setFormError('请填写方案名称');
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      const r = await apiClient.createElderlyAdaptationScheme({
        project_id: selectedProjectId,
        name: name.trim(),
        occupant_type: occupantType,
      });
      if (!r.isSuccess) throw new Error(r.error ?? '创建失败');
      setName('');
      setOccupantType('elderly_living');
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleValidate(schemeId: string) {
    setValidatingId(schemeId);
    setFormError(null);
    try {
      const r = await apiClient.validateElderlyAdaptationScheme<ElderlyAdaptationValidation>(schemeId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '校验失败');
      setValidations((prev) => ({ ...prev, [schemeId]: r.data! }));
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setValidatingId(null);
    }
  }

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-elderly-adaptation-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">🧓 适老改造</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-project-picker">
            <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)} aria-label="选择项目" data-testid="wb-elderly-adaptation-project-select">
              <option value="">选择项目…</option>
              {projects?.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </div>

          {!selectedProjectId && (
            <div className="wb-state" data-testid="wb-elderly-adaptation-no-project">
              <div className="wb-state__icon">📋</div><div>请先选择项目</div>
            </div>
          )}
          {selectedProjectId && loading && (
            <div className="wb-state" data-testid="wb-elderly-adaptation-loading">
              <div className="wb-state__icon">⏳</div><div>加载适老改造方案中…</div>
            </div>
          )}
          {selectedProjectId && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-elderly-adaptation-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>重试</button>
            </div>
          )}

          {selectedProjectId && !loading && !error && (
            <div data-testid="wb-elderly-adaptation-content">
              {/* 创建表单 */}
              <div className="wb-create-form" data-testid="wb-elderly-adaptation-create">
                <div className="wb-create-form__head">
                  <div className="wb-create-form__badge">🧓</div>
                  <div>
                    <div className="wb-create-form__title">创建适老改造方案</div>
                    <div className="wb-create-form__subtitle">自动生成适老条目（依据 GB 50763-2012）</div>
                  </div>
                </div>
                <form onSubmit={handleCreate}>
                  <div className="wb-create-form__body">
                    <div className="wb-create-form__field">
                      <label className="wb-create-form__label" htmlFor="wb-elderly-adaptation-name">方案名称 <span className="wb-create-form__required">*</span></label>
                      <input
                        id="wb-elderly-adaptation-name"
                        className="wb-input"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="如：长辈房适老改造"
                        data-testid="wb-elderly-adaptation-name-input"
                      />
                    </div>
                    <div className="wb-create-form__field">
                      <label className="wb-create-form__label" htmlFor="wb-elderly-adaptation-occupant">居住类型</label>
                      <select
                        id="wb-elderly-adaptation-occupant"
                        className="wb-input"
                        value={occupantType}
                        onChange={(e) => setOccupantType(e.target.value)}
                        data-testid="wb-elderly-adaptation-occupant-select"
                      >
                        {Object.entries(OCCUPANT_TYPES).map(([key, info]) => (
                          <option key={key} value={key}>{info.label}</option>
                        ))}
                      </select>
                    </div>
                    {formError && (
                      <div className="wb-create-form__error" data-testid="wb-elderly-adaptation-form-error">
                        ⚠ {formError}
                      </div>
                    )}
                    <div className="wb-create-form__actions">
                      <button className="wb-theme-option wb-theme-option--active" type="submit" disabled={submitting} data-testid="wb-elderly-adaptation-submit" style={{ width: '100%' }}>
                        {submitting ? '创建中…' : '＋ 创建方案'}
                      </button>
                    </div>
                  </div>
                </form>
              </div>

              {/* 方案列表 */}
              <div className="wb-section-label">适老改造方案（{schemes?.length ?? 0}）</div>
              {!loading && !error && (schemes?.length ?? 0) === 0 && (
                <div className="wb-state" data-testid="wb-elderly-adaptation-empty">
                  <div className="wb-state__icon">🧓</div><div>暂无适老改造方案</div>
                  <div style={{ fontSize: 'var(--font-size-sm)' }}>在上方创建首个方案，系统将按 GB 50763-2012 自动生成适老条目</div>
                </div>
              )}
              {(schemes ?? []).map((s, i) => {
                const occInfo = OCCUPANT_TYPES[s.occupant_type] ?? { label: s.occupant_type, tone: 'muted' as ChipTone };
                const compTone = COMPLIANCE_TONES[s.compliance_status] ?? 'muted';
                const validation = validations[s.id];
                return (
                  <div key={s.id} className="wb-smart-card" data-testid={`wb-elderly-adaptation-item--${i}`}>
                    <div className="wb-smart-card__head">
                      <div className="wb-smart-card__room">{s.name}</div>
                      <span className={`wb-status-chip wb-status-chip--${occInfo.tone}`}>{occInfo.label}</span>
                      <span className={`wb-status-chip wb-status-chip--${compTone}`}>{COMPLIANCE_LABELS[s.compliance_status] ?? s.compliance_status}</span>
                    </div>
                    <div className="wb-smart-card__meta">
                      <span>🧩 适老条目 {(s.items ?? []).length} 项</span>
                      {s.notes && <span>{s.notes}</span>}
                    </div>
                    {validation && (
                      <div className="wb-smart-card__meta" style={{ marginTop: 8 }} data-testid={`wb-elderly-adaptation-validate-result--${i}`}>
                        <span className={`wb-status-chip wb-status-chip--${COMPLIANCE_TONES[validation.compliance_status] ?? 'muted'}`}>
                          {COMPLIANCE_LABELS[validation.compliance_status] ?? validation.compliance_status}
                        </span>
                        {validation.score != null && <span>得分 {validation.score}</span>}
                        <span>{validation.summary}</span>
                      </div>
                    )}
                    <div style={{ marginTop: 10 }}>
                      <button
                        className="wb-theme-option wb-theme-option--active"
                        type="button"
                        onClick={() => handleValidate(s.id)}
                        disabled={validatingId === s.id}
                        data-testid={`wb-elderly-adaptation-validate--${i}`}
                      >
                        {validatingId === s.id ? '校验中…' : '✅ 合规校验'}
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
