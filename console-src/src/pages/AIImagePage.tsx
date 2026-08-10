/**
 * AIImagePage — AI 图生图（视觉表现层渲染任务）
 *
 * 结构：Scaffold > AppBar(AI 图生图) > 创建任务 + 批量渲染 + 预设模板（套用）
 *   + 项目任务列表（详情/状态/处理/删除）
 * API（对齐 app/api/ai_image.py，前缀 /api/ai-image）：
 *   POST   /api/ai-image/jobs                   创建图生图任务
 *   GET    /api/ai-image/jobs/project/{projectId}  项目任务列表
 *   GET    /api/ai-image/jobs/{jobId}           任务详情
 *   POST   /api/ai-image/jobs/{jobId}/process   触发任务处理（queued/failed）
 *   GET    /api/ai-image/jobs/{jobId}/status    任务状态（含成本）
 *   DELETE /api/ai-image/jobs/{jobId}           删除任务
 *   GET    /api/ai-image/presets                预设模板列表
 *   POST   /api/ai-image/jobs/apply-preset      应用预设创建任务
 *   POST   /api/ai-image/jobs/batch             批量渲染
 *
 * 诚实降级：render_backend=mock 时后端标注占位渲染；isSuccess=false 展示真实 error。
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type {
  AIImageJob,
  AIImageJobCreateInput,
  AIImageJobListItem,
  AIImageJobStatus,
  AIImagePreset,
  Project,
} from '../types/domain';

function fmtTime(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

const JOB_TYPE_OPTIONS = [
  { value: 'style_transfer', label: '风格迁移' },
  { value: 'restoration', label: '修复翻新' },
  { value: 'furniture_swap', label: '家具替换' },
];

const MODEL_OPTIONS = ['stable-diffusion-xl', 'stable-diffusion-1.5', 'sd-turbo'];

export default function AIImagePage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [createError, setCreateError] = useState<string | null>(null);
  const [createMsg, setCreateMsg] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [batchError, setBatchError] = useState<string | null>(null);
  const [batchMsg, setBatchMsg] = useState<string | null>(null);
  const [batching, setBatching] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  // 创建任务表单
  const [form, setForm] = useState<{
    project_id: string;
    job_type: string;
    model_name: string;
    input_image_url: string;
    prompt: string;
    negative_prompt: string;
    controlnet_strength: string;
    guidance_scale: string;
    num_inference_steps: string;
    seed: string;
  }>({
    project_id: '',
    job_type: 'style_transfer',
    model_name: 'stable-diffusion-xl',
    input_image_url: '',
    prompt: '',
    negative_prompt: '',
    controlnet_strength: '0.5',
    guidance_scale: '7.5',
    num_inference_steps: '30',
    seed: '',
  });

  // 批量渲染表单
  const [batch, setBatch] = useState<{ project_id: string; input_image_url: string; preset_ids: string[] }>({
    project_id: '',
    input_image_url: '',
    preset_ids: [],
  });

  // 套用预设表单
  const [apply, setApply] = useState<{ preset_id: string; project_id: string; input_image_url: string }>({
    preset_id: '',
    project_id: '',
    input_image_url: '',
  });
  const [applyError, setApplyError] = useState<string | null>(null);
  const [applyMsg, setApplyMsg] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    const pid = selectedProjectId || projects?.[0]?.id || '';
    setSelectedProjectId(pid);
    if (pid) {
      setForm((f) => (f.project_id ? f : { ...f, project_id: pid }));
      setBatch((b) => (b.project_id ? b : { ...b, project_id: pid }));
      setApply((a) => (a.project_id ? a : { ...a, project_id: pid }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projects]);

  const { data: jobs, loading: jobsLoading, error: jobsError, reload: reloadJobs } =
    useAsync<AIImageJobListItem[] | null>(async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.listAIImageJobs<AIImageJobListItem[]>(selectedProjectId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载任务列表失败');
      return r.data;
    }, [selectedProjectId]);

  const { data: presets, loading: presetsLoading, error: presetsError, reload: reloadPresets } =
    useAsync<AIImagePreset[] | null>(async () => {
      const r = await apiClient.listAIImagePresets<AIImagePreset[]>();
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载预设模板失败');
      return r.data;
    }, []);

  const { data: jobDetail, loading: detailLoading, error: detailError } =
    useAsync<AIImageJob | null>(async () => {
      if (!selectedJobId) return null;
      const r = await apiClient.getAIImageJob<AIImageJob>(selectedJobId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载任务详情失败');
      return r.data;
    }, [selectedJobId]);

  const { data: jobStatus, loading: statusLoading, error: statusError } =
    useAsync<AIImageJobStatus | null>(async () => {
      if (!selectedJobId) return null;
      const r = await apiClient.getAIImageJobStatus<AIImageJobStatus>(selectedJobId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '查询任务状态失败');
      return r.data;
    }, [selectedJobId]);

  function updateForm<K extends keyof typeof form>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreateError(null);
    setCreateMsg(null);
    setCreating(true);
    try {
      if (!form.project_id) throw new Error('请选择项目');
      const payload: AIImageJobCreateInput = {
        project_id: form.project_id,
        job_type: form.job_type,
        model_name: form.model_name,
        input_image_url: form.input_image_url.trim() || null,
        prompt: form.prompt.trim() || null,
        negative_prompt: form.negative_prompt.trim() || null,
        controlnet_strength: parseFloat(form.controlnet_strength) || 0.5,
        guidance_scale: parseFloat(form.guidance_scale) || 7.5,
        num_inference_steps: parseInt(form.num_inference_steps, 10) || 30,
        seed: form.seed.trim() ? parseInt(form.seed.trim(), 10) : null,
      };
      const r = await apiClient.createAIImageJob<AIImageJob>(payload);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '创建任务失败');
      setCreateMsg(`任务已创建（${r.data.id.slice(0, 8)}…，状态 ${r.data.status}）`);
      reloadJobs();
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : String(err));
    } finally {
      setCreating(false);
    }
  }

  function togglePreset(presetId: string) {
    setBatch((b) => ({
      ...b,
      preset_ids: b.preset_ids.includes(presetId)
        ? b.preset_ids.filter((id) => id !== presetId)
        : [...b.preset_ids, presetId],
    }));
  }

  async function handleBatch(e: React.FormEvent) {
    e.preventDefault();
    setBatchError(null);
    setBatchMsg(null);
    setBatching(true);
    try {
      if (!batch.project_id) throw new Error('请选择项目');
      if (batch.preset_ids.length === 0) throw new Error('请至少选择一个预设模板');
      const r = await apiClient.batchAIImageRender<AIImageJob[]>({
        project_id: batch.project_id,
        preset_ids: batch.preset_ids,
        input_image_url: batch.input_image_url.trim() || null,
      });
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '批量渲染失败');
      setBatchMsg(`已批量创建 ${r.data.length} 个渲染任务`);
      reloadJobs();
    } catch (err) {
      setBatchError(err instanceof Error ? err.message : String(err));
    } finally {
      setBatching(false);
    }
  }

  async function handleApply(e: React.FormEvent) {
    e.preventDefault();
    setApplyError(null);
    setApplyMsg(null);
    setApplying(true);
    try {
      if (!apply.preset_id) throw new Error('请选择预设模板');
      if (!apply.project_id) throw new Error('请选择项目');
      if (!apply.input_image_url.trim()) throw new Error('请输入输入图片 URL（必填）');
      const r = await apiClient.applyAIImagePreset<AIImageJob>({
        preset_id: apply.preset_id,
        project_id: apply.project_id,
        input_image_url: apply.input_image_url.trim(),
      });
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '套用预设失败');
      setApplyMsg(`已按预设「${presets?.find((p) => p.id === apply.preset_id)?.name ?? ''}」创建任务`);
      reloadJobs();
    } catch (err) {
      setApplyError(err instanceof Error ? err.message : String(err));
    } finally {
      setApplying(false);
    }
  }

  async function handleProcess(jobId: string) {
    setActionError(null);
    try {
      const r = await apiClient.processAIImageJob<AIImageJob>(jobId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '处理失败');
      reloadJobs();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleDelete(jobId: string) {
    setActionError(null);
    try {
      const r = await apiClient.deleteAIImageJob(jobId);
      if (!r.isSuccess) throw new Error(r.error ?? '删除失败');
      if (selectedJobId === jobId) setSelectedJobId(null);
      reloadJobs();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-ai-image-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">🎨 AI 图生图</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {/* 项目选择器 */}
          <div className="wb-project-picker">
            <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)} aria-label="选择项目" data-testid="wb-ai-image-project-select">
              <option value="">选择项目…</option>
              {projects?.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </div>

          {/* 创建任务 */}
          <div className="wb-create-form" data-testid="wb-ai-image-create">
            <div className="wb-create-form__head">
              <div className="wb-create-form__badge">🎨</div>
              <div>
                <div className="wb-create-form__title">创建图生图任务</div>
                <div className="wb-create-form__subtitle">提交 Stable Diffusion / ControlNet 渲染任务（后端 render_backend 诚实标注真实渲染引擎）</div>
              </div>
            </div>
            <form onSubmit={handleCreate}>
              <div className="wb-create-form__body">
                <div className="wb-create-form__row">
                  <div className="wb-create-form__field wb-create-form__field--grow">
                    <label className="wb-create-form__label" htmlFor="wb-ai-image-create-project">项目 <span className="wb-create-form__required">*</span></label>
                    <select id="wb-ai-image-create-project" className="wb-input" value={form.project_id} onChange={(e) => updateForm('project_id', e.target.value)} data-testid="wb-ai-image-create-project">
                      <option value="">选择项目…</option>
                      {projects?.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
                    </select>
                  </div>
                  <div className="wb-create-form__field">
                    <label className="wb-create-form__label" htmlFor="wb-ai-image-create-type">任务类型</label>
                    <select id="wb-ai-image-create-type" className="wb-input" value={form.job_type} onChange={(e) => updateForm('job_type', e.target.value)} data-testid="wb-ai-image-create-type">
                      {JOB_TYPE_OPTIONS.map((o) => (<option key={o.value} value={o.value}>{o.label}</option>))}
                    </select>
                  </div>
                  <div className="wb-create-form__field">
                    <label className="wb-create-form__label" htmlFor="wb-ai-image-create-model">模型</label>
                    <select id="wb-ai-image-create-model" className="wb-input" value={form.model_name} onChange={(e) => updateForm('model_name', e.target.value)} data-testid="wb-ai-image-create-model">
                      {MODEL_OPTIONS.map((m) => (<option key={m} value={m}>{m}</option>))}
                    </select>
                  </div>
                </div>
                <div className="wb-create-form__field">
                  <label className="wb-create-form__label" htmlFor="wb-ai-image-create-input-url">输入图片 URL</label>
                  <input id="wb-ai-image-create-input-url" className="wb-input" value={form.input_image_url} onChange={(e) => updateForm('input_image_url', e.target.value)} placeholder="https://…（可留空，仅提示词渲染）" data-testid="wb-ai-image-create-input-url" />
                </div>
                <div className="wb-create-form__field wb-create-form__field--area">
                  <label className="wb-create-form__label" htmlFor="wb-ai-image-create-prompt">提示词</label>
                  <textarea id="wb-ai-image-create-prompt" className="wb-textarea" rows={3} value={form.prompt} onChange={(e) => updateForm('prompt', e.target.value)} placeholder="描述期望的渲染效果…" data-testid="wb-ai-image-create-prompt" />
                </div>
                <div className="wb-create-form__field">
                  <label className="wb-create-form__label" htmlFor="wb-ai-image-create-neg">负面提示词</label>
                  <input id="wb-ai-image-create-neg" className="wb-input" value={form.negative_prompt} onChange={(e) => updateForm('negative_prompt', e.target.value)} placeholder="不希望出现的内容…" data-testid="wb-ai-image-create-neg" />
                </div>
                <div className="wb-create-form__row">
                  <div className="wb-create-form__field">
                    <label className="wb-create-form__label" htmlFor="wb-ai-image-create-strength">ControlNet 强度</label>
                    <input id="wb-ai-image-create-strength" className="wb-input wb-input--num" type="number" min={0} max={1} step={0.1} value={form.controlnet_strength} onChange={(e) => updateForm('controlnet_strength', e.target.value)} data-testid="wb-ai-image-create-strength" />
                  </div>
                  <div className="wb-create-form__field">
                    <label className="wb-create-form__label" htmlFor="wb-ai-image-create-guidance">引导系数</label>
                    <input id="wb-ai-image-create-guidance" className="wb-input wb-input--num" type="number" min={1} max={30} step={0.5} value={form.guidance_scale} onChange={(e) => updateForm('guidance_scale', e.target.value)} data-testid="wb-ai-image-create-guidance" />
                  </div>
                  <div className="wb-create-form__field">
                    <label className="wb-create-form__label" htmlFor="wb-ai-image-create-steps">采样步数</label>
                    <input id="wb-ai-image-create-steps" className="wb-input wb-input--num" type="number" min={1} max={200} value={form.num_inference_steps} onChange={(e) => updateForm('num_inference_steps', e.target.value)} data-testid="wb-ai-image-create-steps" />
                  </div>
                  <div className="wb-create-form__field">
                    <label className="wb-create-form__label" htmlFor="wb-ai-image-create-seed">随机种子</label>
                    <input id="wb-ai-image-create-seed" className="wb-input wb-input--num" type="number" value={form.seed} onChange={(e) => updateForm('seed', e.target.value)} placeholder="留空随机" data-testid="wb-ai-image-create-seed" />
                  </div>
                </div>
                {createError && (
                  <div className="wb-create-form__error" data-testid="wb-ai-image-create-error">⚠ {createError}</div>
                )}
                {createMsg && (
                  <div className="wb-smart-card" data-testid="wb-ai-image-create-msg">✅ {createMsg}</div>
                )}
                <div className="wb-create-form__actions">
                  <button className="wb-theme-option wb-theme-option--active" type="submit" disabled={creating} data-testid="wb-ai-image-create-submit">
                    {creating ? '提交中…' : '🚀 创建任务'}
                  </button>
                </div>
              </div>
            </form>
          </div>

          {/* 批量渲染 */}
          <div className="wb-create-form" style={{ marginTop: 16 }} data-testid="wb-ai-image-batch">
            <div className="wb-create-form__head">
              <div className="wb-create-form__badge">⚡</div>
              <div>
                <div className="wb-create-form__title">批量渲染</div>
                <div className="wb-create-form__subtitle">选择多个预设模板，一次为项目批量创建渲染任务</div>
              </div>
            </div>
            <form onSubmit={handleBatch}>
              <div className="wb-create-form__body">
                <div className="wb-create-form__row">
                  <div className="wb-create-form__field wb-create-form__field--grow">
                    <label className="wb-create-form__label" htmlFor="wb-ai-image-batch-project">项目 <span className="wb-create-form__required">*</span></label>
                    <select id="wb-ai-image-batch-project" className="wb-input" value={batch.project_id} onChange={(e) => setBatch((b) => ({ ...b, project_id: e.target.value }))} data-testid="wb-ai-image-batch-project">
                      <option value="">选择项目…</option>
                      {projects?.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
                    </select>
                  </div>
                  <div className="wb-create-form__field wb-create-form__field--grow">
                    <label className="wb-create-form__label" htmlFor="wb-ai-image-batch-url">输入图片 URL（可选）</label>
                    <input id="wb-ai-image-batch-url" className="wb-input" value={batch.input_image_url} onChange={(e) => setBatch((b) => ({ ...b, input_image_url: e.target.value }))} placeholder="https://…" data-testid="wb-ai-image-batch-url" />
                  </div>
                </div>
                <div className="wb-create-form__field">
                  <label className="wb-create-form__label">预设模板（已选 {batch.preset_ids.length} 个）</label>
                  <div className="wb-task-filter" role="list" aria-label="选择预设模板">
                    {(presets ?? []).map((p) => (
                      <span
                        key={p.id}
                        role="button"
                        tabIndex={0}
                        className={`wb-task-filter__chip ${batch.preset_ids.includes(p.id) ? 'wb-task-filter__chip--active' : ''}`}
                        onClick={() => togglePreset(p.id)}
                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') togglePreset(p.id); }}
                        data-testid={`wb-ai-image-batch-preset--${p.id}`}
                      >
                        {p.name}
                      </span>
                    ))}
                  </div>
                  {presetsError && <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--danger)', marginTop: 6 }}>{presetsError}</div>}
                </div>
                {batchError && (
                  <div className="wb-create-form__error" data-testid="wb-ai-image-batch-error">⚠ {batchError}</div>
                )}
                {batchMsg && (
                  <div className="wb-smart-card" data-testid="wb-ai-image-batch-msg">✅ {batchMsg}</div>
                )}
                <div className="wb-create-form__actions">
                  <button className="wb-theme-option wb-theme-option--active" type="submit" disabled={batching} data-testid="wb-ai-image-batch-submit">
                    {batching ? '提交中…' : '⚡ 批量渲染'}
                  </button>
                </div>
              </div>
            </form>
          </div>

          {/* 预设模板 */}
          <div className="wb-section-label" style={{ marginTop: 16 }}>预设模板（{presets?.length ?? 0}）</div>
          {presetsLoading && (
            <div className="wb-state" data-testid="wb-ai-image-presets-loading">
              <div className="wb-state__icon">⏳</div><div>加载预设模板…</div>
            </div>
          )}
          {presetsError && !presetsLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-ai-image-presets-error">
              <div className="wb-state__icon">⚠</div><div>{presetsError}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={() => reloadPresets()} type="button">重试</button>
            </div>
          )}
          {!presetsLoading && !presetsError && (presets?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-ai-image-presets-empty">
              <div className="wb-state__icon">🗂</div><div>暂无预设模板</div>
            </div>
          )}
          {(presets ?? []).map((p, i) => (
            <div key={p.id} className="wb-smart-card" data-testid={`wb-ai-image-preset--${i}`}>
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">{p.name}</div>
                <span className="wb-status-chip wb-status-chip--muted">{p.category} · 使用 {p.usage_count} 次</span>
              </div>
              <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 4, whiteSpace: 'pre-wrap' }}>
                {p.prompt_template}
              </div>
              <div style={{ marginTop: 10 }}>
                <button
                  type="button"
                  className="wb-theme-option"
                  onClick={() => { setApply((a) => ({ ...a, preset_id: p.id })); setApplyError(null); setApplyMsg(null); }}
                  data-testid={`wb-ai-image-preset-apply--${i}`}
                >
                  套用此预设
                </button>
              </div>
            </div>
          ))}

          {/* 套用预设 */}
          <div className="wb-create-form" style={{ marginTop: 16 }} data-testid="wb-ai-image-apply">
            <div className="wb-create-form__head">
              <div className="wb-create-form__badge">🔗</div>
              <div>
                <div className="wb-create-form__title">套用预设创建任务</div>
                <div className="wb-create-form__subtitle">按预设模板 + 输入图片生成一个渲染任务</div>
              </div>
            </div>
            <form onSubmit={handleApply}>
              <div className="wb-create-form__body">
                <div className="wb-create-form__row">
                  <div className="wb-create-form__field wb-create-form__field--grow">
                    <label className="wb-create-form__label" htmlFor="wb-ai-image-apply-preset">预设模板 <span className="wb-create-form__required">*</span></label>
                    <select id="wb-ai-image-apply-preset" className="wb-input" value={apply.preset_id} onChange={(e) => setApply((a) => ({ ...a, preset_id: e.target.value }))} data-testid="wb-ai-image-apply-preset">
                      <option value="">选择预设…</option>
                      {(presets ?? []).map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
                    </select>
                  </div>
                  <div className="wb-create-form__field wb-create-form__field--grow">
                    <label className="wb-create-form__label" htmlFor="wb-ai-image-apply-project">项目 <span className="wb-create-form__required">*</span></label>
                    <select id="wb-ai-image-apply-project" className="wb-input" value={apply.project_id} onChange={(e) => setApply((a) => ({ ...a, project_id: e.target.value }))} data-testid="wb-ai-image-apply-project">
                      <option value="">选择项目…</option>
                      {projects?.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
                    </select>
                  </div>
                </div>
                <div className="wb-create-form__field">
                  <label className="wb-create-form__label" htmlFor="wb-ai-image-apply-url">输入图片 URL <span className="wb-create-form__required">*</span></label>
                  <input id="wb-ai-image-apply-url" className="wb-input" value={apply.input_image_url} onChange={(e) => setApply((a) => ({ ...a, input_image_url: e.target.value }))} placeholder="https://…（后端必填）" data-testid="wb-ai-image-apply-url" />
                </div>
                {applyError && (
                  <div className="wb-create-form__error" data-testid="wb-ai-image-apply-error">⚠ {applyError}</div>
                )}
                {applyMsg && (
                  <div className="wb-smart-card" data-testid="wb-ai-image-apply-msg">✅ {applyMsg}</div>
                )}
                <div className="wb-create-form__actions">
                  <button className="wb-theme-option wb-theme-option--active" type="submit" disabled={applying} data-testid="wb-ai-image-apply-submit">
                    {applying ? '提交中…' : '🔗 套用预设'}
                  </button>
                </div>
              </div>
            </form>
          </div>

          {/* 项目任务列表 */}
          <div className="wb-section-label" style={{ marginTop: 16 }}>项目渲染任务（{jobs?.length ?? 0}）</div>
          {!selectedProjectId && (
            <div className="wb-state" data-testid="wb-ai-image-no-project">
              <div className="wb-state__icon">📋</div><div>请先选择项目</div>
            </div>
          )}
          {selectedProjectId && jobsLoading && (
            <div className="wb-state" data-testid="wb-ai-image-jobs-loading">
              <div className="wb-state__icon">⏳</div><div>加载任务列表…</div>
            </div>
          )}
          {selectedProjectId && jobsError && !jobsLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-ai-image-jobs-error">
              <div className="wb-state__icon">⚠</div><div>{jobsError}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={() => reloadJobs()} type="button">重试</button>
            </div>
          )}
          {selectedProjectId && !jobsLoading && !jobsError && (jobs?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-ai-image-jobs-empty">
              <div className="wb-state__icon">🖼</div><div>该项目暂无渲染任务</div>
            </div>
          )}
          {actionError && (
            <div className="wb-create-form__error" data-testid="wb-ai-image-action-error">⚠ {actionError}</div>
          )}
          {(jobs ?? []).map((job, i) => (
            <div key={job.id} className="wb-smart-card" data-testid={`wb-ai-image-job--${i}`}>
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">{job.job_type} · {job.model_name}</div>
                <span className={`wb-status-chip ${job.status === 'completed' ? 'wb-status-chip--success' : job.status === 'failed' ? 'wb-status-chip--danger' : job.status === 'processing' ? 'wb-status-chip--info' : 'wb-status-chip--muted'}`}>
                  {job.status}
                </span>
              </div>
              <div className="wb-smart-card__meta">
                <span>{fmtTime(job.created_at)}</span>
                <span>进度 {job.progress_percent}%</span>
              </div>
              {job.output_image_url && (
                <div style={{ marginTop: 8 }}>
                  <a href={job.output_image_url} target="_blank" rel="noreferrer" style={{ fontSize: 'var(--font-size-xs)', color: 'var(--accent-bright)' }}>查看输出图 →</a>
                </div>
              )}
              <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button type="button" className="wb-theme-option" onClick={() => { setSelectedJobId(job.id); setActionError(null); }} data-testid={`wb-ai-image-job-detail--${i}`}>详情</button>
                {(job.status === 'queued' || job.status === 'failed') && (
                  <button type="button" className="wb-theme-option wb-theme-option--active" onClick={() => handleProcess(job.id)} data-testid={`wb-ai-image-job-process--${i}`}>处理</button>
                )}
                <button type="button" className="wb-theme-option" onClick={() => handleDelete(job.id)} data-testid={`wb-ai-image-job-delete--${i}`}>删除</button>
              </div>
            </div>
          ))}

          {/* 任务详情 / 状态 */}
          {selectedJobId && detailLoading && (
            <div className="wb-state" data-testid="wb-ai-image-detail-loading">
              <div className="wb-state__icon">⏳</div><div>加载任务详情…</div>
            </div>
          )}
          {selectedJobId && detailError && !detailLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-ai-image-detail-error">
              <div className="wb-state__icon">⚠</div><div>{detailError}</div>
            </div>
          )}
          {jobDetail && !detailLoading && !detailError && (
            <div className="wb-smart-card" data-testid="wb-ai-image-detail">
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">任务详情 {jobDetail.id.slice(0, 8)}…</div>
                <span className={`wb-status-chip ${jobDetail.render_backend === 'mock' ? 'wb-status-chip--warning' : 'wb-status-chip--success'}`}>
                  {jobDetail.render_backend === 'mock' ? '占位渲染' : '真实渲染'}
                </span>
              </div>
              <div className="wb-smart-card__meta">
                <span>状态 {jobDetail.status}</span>
                <span>进度 {jobDetail.progress_percent}%</span>
                <span>耗时 {jobDetail.render_duration_sec}s</span>
              </div>
              {jobDetail.prompt && <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 6 }}>提示词：{jobDetail.prompt}</div>}
              {jobDetail.negative_prompt && <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 4 }}>负面：{jobDetail.negative_prompt}</div>}
              {jobDetail.error_message && <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--danger)', marginTop: 4 }}>错误：{jobDetail.error_message}</div>}
              {jobDetail.input_image_url && (
                <div style={{ marginTop: 8 }}>
                  <a href={jobDetail.input_image_url} target="_blank" rel="noreferrer" style={{ fontSize: 'var(--font-size-xs)', color: 'var(--accent-bright)' }}>输入图 →</a>
                </div>
              )}
              {jobDetail.output_image_url && (
                <div style={{ marginTop: 4 }}>
                  <a href={jobDetail.output_image_url} target="_blank" rel="noreferrer" style={{ fontSize: 'var(--font-size-xs)', color: 'var(--accent-bright)' }}>输出图 →</a>
                </div>
              )}
            </div>
          )}
          {selectedJobId && statusLoading && (
            <div className="wb-state" data-testid="wb-ai-image-status-loading">
              <div className="wb-state__icon">⏳</div><div>查询任务状态…</div>
            </div>
          )}
          {selectedJobId && statusError && !statusLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-ai-image-status-error">
              <div className="wb-state__icon">⚠</div><div>{statusError}</div>
            </div>
          )}
          {jobStatus && !statusLoading && !statusError && (
            <div className="wb-smart-card" data-testid="wb-ai-image-status">
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">实时状态</div>
                <span className="wb-status-chip wb-status-chip--info">{jobStatus.status}</span>
              </div>
              <div className="wb-smart-card__meta">
                <span>进度 {jobStatus.progress_percent}%</span>
                <span>预计成本 ¥{jobStatus.cost_yuan.toFixed(2)}</span>
                <span>引擎 {jobStatus.render_backend === 'mock' ? '占位' : '真实'}</span>
              </div>
              {jobStatus.error_message && <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--danger)', marginTop: 4 }}>错误：{jobStatus.error_message}</div>}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
