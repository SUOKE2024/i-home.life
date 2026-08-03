/**
 * EcoMaterialsPage — 环保材料标签（F44, v1.5.0）
 *
 * 结构：Scaffold > AppBar(环保材料) > 等级筛选 chips + 材料列表 + 认证分配表单 + 合规校验
 * API（对齐 app/api/eco_materials.py）：
 *   GET  /api/eco-materials/grades            环保等级数量统计（ENF/E0/E1）
 *   GET  /api/eco-materials/materials?grade=  按环保等级筛选材料（缺省返回全部）
 *   POST /api/eco-materials/certs             分配环保认证标签（已存在则更新）
 *   POST /api/eco-materials/validate          环保合规校验报告（对标 HC-003）
 *
 * eco_grade: ENF / E0 / E1（ENF > E0 > E1，GB/T 39600-2021）
 */

import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type {
  EcoComplianceReport,
  EcoGradeCounts,
  MaterialEcoCertItem,
} from '../types/domain';

type ChipTone = 'muted' | 'info' | 'success' | 'warning' | 'danger' | 'accent';

const GRADE_ORDER = ['ENF', 'E0', 'E1'];
const GRADE_TONES: Record<string, ChipTone> = { ENF: 'success', E0: 'info', E1: 'warning' };

const SOURCES = [
  { value: 'third_party', label: '第三方认证' },
  { value: 'factory', label: '厂家声明' },
  { value: 'platform', label: '平台抽检' },
];

export default function EcoMaterialsPage() {
  const navigate = useNavigate();
  const [selectedGrade, setSelectedGrade] = useState<string>('all');
  // 认证分配表单
  const [certMaterialId, setCertMaterialId] = useState('');
  const [certGrade, setCertGrade] = useState('ENF');
  const [certification, setCertification] = useState('无认证');
  const [source, setSource] = useState('third_party');
  const [certSubmitting, setCertSubmitting] = useState(false);
  const [certMsg, setCertMsg] = useState<string | null>(null);
  // 合规校验表单
  const [idsText, setIdsText] = useState('');
  const [validating, setValidating] = useState(false);
  const [report, setReport] = useState<EcoComplianceReport | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const { data: grades } = useAsync<EcoGradeCounts>(async () => {
    const r = await apiClient.getEcoGrades<EcoGradeCounts>();
    if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载等级统计失败');
    return r.data;
  }, []);

  const { data: materials, loading, error, reload } = useAsync<MaterialEcoCertItem[]>(async () => {
    const r = await apiClient.getEcoMaterials<MaterialEcoCertItem[]>(selectedGrade === 'all' ? undefined : selectedGrade);
    if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
    return r.data;
  }, [selectedGrade]);

  const totalCount = useMemo(() => {
    if (!grades) return 0;
    return GRADE_ORDER.reduce((sum, g) => sum + (grades[g] ?? 0), 0);
  }, [grades]);

  async function handleAssignCert(e: React.FormEvent) {
    e.preventDefault();
    if (!certMaterialId.trim()) {
      setFormError('请填写材料 ID');
      return;
    }
    setCertSubmitting(true);
    setFormError(null);
    setCertMsg(null);
    try {
      const r = await apiClient.assignEcoCert({
        material_id: certMaterialId.trim(),
        eco_grade: certGrade,
        certification: certification.trim() || '无认证',
        source,
      });
      if (!r.isSuccess) throw new Error(r.error ?? '分配失败');
      setCertMsg(`已为材料 ${certMaterialId.trim()} 分配 ${certGrade} 等级标签`);
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setCertSubmitting(false);
    }
  }

  async function handleValidate(e: React.FormEvent) {
    e.preventDefault();
    const ids = idsText
      .split(/[,，\s]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (ids.length === 0) {
      setFormError('请输入至少一个材料 ID（逗号分隔）');
      return;
    }
    setValidating(true);
    setFormError(null);
    setReport(null);
    try {
      const r = await apiClient.validateEcoCompliance(ids);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '校验失败');
      setReport(r.data);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setValidating(false);
    }
  }

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-eco-materials-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">🌿 环保材料</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {/* 等级筛选 chips */}
          <div className="wb-task-filter" role="tablist" aria-label="环保等级筛选">
            <button type="button" role="tab" aria-selected={selectedGrade === 'all'}
              className={`wb-task-filter__chip ${selectedGrade === 'all' ? 'wb-task-filter__chip--active' : ''}`}
              onClick={() => setSelectedGrade('all')} data-testid="wb-eco-materials-grade--all">
              全部({totalCount})
            </button>
            {GRADE_ORDER.map((g) => (
              <button key={g} type="button" role="tab" aria-selected={selectedGrade === g}
                className={`wb-task-filter__chip ${selectedGrade === g ? 'wb-task-filter__chip--active' : ''}`}
                onClick={() => setSelectedGrade(g)} data-testid={`wb-eco-materials-grade--${g.toLowerCase()}`}>
                {g}({grades?.[g] ?? 0})
              </button>
            ))}
          </div>

          {loading && (
            <div className="wb-state" data-testid="wb-eco-materials-loading">
              <div className="wb-state__icon">⏳</div><div>加载环保材料中…</div>
            </div>
          )}
          {error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-eco-materials-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>重试</button>
            </div>
          )}

          <div className="wb-section-label" style={{ marginTop: 12 }}>环保材料（{materials?.length ?? 0}）</div>
          {!loading && !error && (materials?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-eco-materials-empty">
              <div className="wb-state__icon">🌿</div><div>暂无该等级的环保材料</div>
              <div style={{ fontSize: 'var(--font-size-sm)' }}>可在下方为材料分配环保认证标签</div>
            </div>
          )}
          {(materials ?? []).map((m, i) => (
            <div key={m.material_id} className="wb-smart-card" data-testid={`wb-eco-materials-item--${i}`}>
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">{m.material_name}</div>
                <span className={`wb-status-chip wb-status-chip--${GRADE_TONES[m.eco_grade] ?? 'muted'}`}>{m.eco_grade}</span>
                <span className="wb-status-chip wb-status-chip--muted">{m.certification}</span>
              </div>
              <div className="wb-smart-card__meta">
                <span>🔖 {m.sku}</span>
                {m.brand && <span>🏷 {m.brand}</span>}
                <span>💰 ¥{m.unit_price}</span>
              </div>
            </div>
          ))}

          {/* 认证分配表单 */}
          <div className="wb-create-form" style={{ marginTop: 20 }} data-testid="wb-eco-materials-cert-form">
            <div className="wb-create-form__head">
              <div className="wb-create-form__badge">🌿</div>
              <div>
                <div className="wb-create-form__title">分配环保认证标签</div>
                <div className="wb-create-form__subtitle">为材料分配 ENF/E0/E1 环保等级与认证（已存在则更新）</div>
              </div>
            </div>
            <form onSubmit={handleAssignCert}>
              <div className="wb-create-form__body">
                <div className="wb-create-form__field">
                  <label className="wb-create-form__label" htmlFor="wb-eco-materials-cert-material-id">材料 ID <span className="wb-create-form__required">*</span></label>
                  <input
                    id="wb-eco-materials-cert-material-id"
                    className="wb-input"
                    value={certMaterialId}
                    onChange={(e) => setCertMaterialId(e.target.value)}
                    placeholder="材料 ID（如 UUID）"
                    data-testid="wb-eco-materials-material-id-input"
                  />
                </div>
                <div className="wb-create-form__field">
                  <label className="wb-create-form__label" htmlFor="wb-eco-materials-cert-grade">环保等级</label>
                  <select
                    id="wb-eco-materials-cert-grade"
                    className="wb-input"
                    value={certGrade}
                    onChange={(e) => setCertGrade(e.target.value)}
                    data-testid="wb-eco-materials-cert-grade-select"
                  >
                    {GRADE_ORDER.map((g) => (<option key={g} value={g}>{g}</option>))}
                  </select>
                </div>
                <div className="wb-create-form__field">
                  <label className="wb-create-form__label" htmlFor="wb-eco-materials-cert-name">认证名称</label>
                  <input
                    id="wb-eco-materials-cert-name"
                    className="wb-input"
                    value={certification}
                    onChange={(e) => setCertification(e.target.value)}
                    placeholder="如：中国绿色建材认证"
                    data-testid="wb-eco-materials-cert-name-input"
                  />
                </div>
                <div className="wb-create-form__field">
                  <label className="wb-create-form__label" htmlFor="wb-eco-materials-cert-source">认证来源</label>
                  <select
                    id="wb-eco-materials-cert-source"
                    className="wb-input"
                    value={source}
                    onChange={(e) => setSource(e.target.value)}
                    data-testid="wb-eco-materials-cert-source-select"
                  >
                    {SOURCES.map((s) => (<option key={s.value} value={s.value}>{s.label}</option>))}
                  </select>
                </div>
                {certMsg && (
                  <div className="wb-smart-card__meta" data-testid="wb-eco-materials-cert-msg">
                    <span>✅ {certMsg}</span>
                  </div>
                )}
                {formError && (
                  <div className="wb-create-form__error" data-testid="wb-eco-materials-form-error">
                    ⚠ {formError}
                  </div>
                )}
                <div className="wb-create-form__actions">
                  <button className="wb-theme-option wb-theme-option--active" type="submit" disabled={certSubmitting} data-testid="wb-eco-materials-cert-submit" style={{ width: '100%' }}>
                    {certSubmitting ? '分配中…' : '🏷 分配认证标签'}
                  </button>
                </div>
              </div>
            </form>
          </div>

          {/* 合规校验 */}
          <div className="wb-create-form" data-testid="wb-eco-materials-validate-form">
            <div className="wb-create-form__head">
              <div className="wb-create-form__badge">✅</div>
              <div>
                <div className="wb-create-form__title">环保合规校验</div>
                <div className="wb-create-form__subtitle">逐材料校验（对标 HC-003 环保等级硬约束）</div>
              </div>
            </div>
            <form onSubmit={handleValidate}>
              <div className="wb-create-form__body">
                <div className="wb-create-form__field">
                  <label className="wb-create-form__label" htmlFor="wb-eco-materials-ids">材料 ID 列表（逗号分隔）</label>
                  <textarea
                    id="wb-eco-materials-ids"
                    className="wb-textarea"
                    value={idsText}
                    onChange={(e) => setIdsText(e.target.value)}
                    placeholder="如：mat-001, mat-002, mat-003"
                    data-testid="wb-eco-materials-ids-input"
                  />
                </div>
                {report && (
                  <div data-testid="wb-eco-materials-report">
                    <div className="wb-smart-card__meta">
                      <span>总计 {report.total}</span>
                      <span className="wb-status-chip wb-status-chip--success">合规 {report.compliant_count}</span>
                      <span className="wb-status-chip wb-status-chip--danger">不合规 {report.non_compliant_count}</span>
                    </div>
                    {report.items.map((item, j) => (
                      <div key={item.material_id} className="wb-co-item" data-testid={`wb-eco-materials-report-item--${j}`}>
                        <div>
                          <strong>{item.material_name}</strong>
                          <span style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>
                            {' '}· {item.material_id} · {item.eco_grade} · {item.certification}
                          </span>
                        </div>
                        <div>
                          <span className={`wb-status-chip ${item.compliant ? 'wb-status-chip--success' : 'wb-status-chip--danger'}`}>
                            {item.compliant ? '合规' : '不合规'}
                          </span>
                          <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)' }}> {item.note}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {formError && !certMsg && (
                  <div className="wb-create-form__error" data-testid="wb-eco-materials-validate-error">
                    ⚠ {formError}
                  </div>
                )}
                <div className="wb-create-form__actions">
                  <button className="wb-theme-option wb-theme-option--active" type="submit" disabled={validating} data-testid="wb-eco-materials-validate-submit" style={{ width: '100%' }}>
                    {validating ? '校验中…' : '🔍 校验合规'}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      </div>
    </SuokeLayout>
  );
}
