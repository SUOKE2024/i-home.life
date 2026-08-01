/**
 * Sketch3DPage — 草图转 3D
 *
 * 结构：Scaffold > AppBar(草图转 3D) > [文件+描述] > [tab: 分析/生成3D] > 结果
 * API：
 *   POST /api/sketch-to-3d/analyze（multipart: file + description）→ SketchAnalysisResult
 *   POST /api/sketch-to-3d/generate-3d（multipart: file + description + style）→ Sketch3DResponse
 *   GET  /api/sketch-to-3d/supported-formats → string[]
 *
 * 后端字段（app/api/sketch_to_3d.py:25-42）：
 *   SketchAnalysisResult: sketch_id / detected_walls / detected_doors / detected_windows
 *                         / estimated_area / room_count / confidence / raw_layout
 *   Sketch3DResponse: sketch_id / analysis / layout_3d / suggestions
 *
 * 降级：
 *   501 — 服务端无视觉模型且未配置 fallback（feature_disabled）
 *   503 — vision model 调用失败
 */

import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { SketchAnalysisResult, Sketch3DResponse, SketchSupportedFormats } from '../types/domain';

type Mode = 'analyze' | 'generate';

const STYLES = ['modern', 'minimal', 'chinese', 'european', 'industrial'] as const;

// 后端降级模式 → 前端诚实提示（对齐 sketch_to_3d.py raw_layout.mode）
const SKETCH_DEGRADE_MSG: Record<string, string> = {
  feature_disabled: '服务端视觉识别未开启，草图分析暂不可用（已返回占位结果）',
  no_vision_model: '服务端未配置视觉模型，草图分析暂不可用',
  vision_call_failed: '视觉模型调用失败，草图分析暂不可用',
  parse_error: '视觉模型响应解析失败，草图分析暂不可用',
};

const EMPTY_FORMATS: SketchSupportedFormats = {
  image_formats: [],
  max_file_size_mb: 10,
  recommended_resolution: '',
  tips: [],
};

/** 识别后端降级占位结果（200 + confidence=0 + raw_layout.mode 非 vision_analyzed） */
function degradeModeOf(rawLayout: Record<string, unknown> | undefined): string | null {
  const mode = (rawLayout as { mode?: string } | undefined)?.mode;
  return mode && mode !== 'vision_analyzed' ? mode : null;
}

export default function Sketch3DPage() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<Mode>('analyze');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [description, setDescription] = useState('');
  const [style, setStyle] = useState<string>('modern');
  const [submitting, setSubmitting] = useState(false);
  const [analysis, setAnalysis] = useState<SketchAnalysisResult | null>(null);
  const [generated, setGenerated] = useState<Sketch3DResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 支持格式（GET，公共端点无需 token）
  const { data: formats } = useAsync<SketchSupportedFormats>(async () => {
    const r = await apiClient.getSketchSupportedFormats<SketchSupportedFormats>();
    return r.isSuccess && r.data ? r.data : EMPTY_FORMATS;
  }, []);
  const formatNames = formats?.image_formats?.length
    ? formats.image_formats.join(' / ')
    : 'PNG / JPG';

  useEffect(() => {
    // 切换模式时清空结果，避免串显
    setAnalysis(null);
    setGenerated(null);
    setError(null);
  }, [mode]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSelectedFile(e.target.files?.[0] ?? null);
    setAnalysis(null);
    setGenerated(null);
    setError(null);
  };

  const handleSubmit = async () => {
    if (!selectedFile) return;
    setSubmitting(true);
    setError(null);
    setAnalysis(null);
    setGenerated(null);

    if (mode === 'analyze') {
      const r = await apiClient.analyzeSketch<SketchAnalysisResult>(selectedFile, description);
      setSubmitting(false);
      if (r.isSuccess && r.data) {
        // 后端可能返回 200 + 降级占位（feature_disabled/no_vision_model 等）→ 诚实提示而非空成功
        const degradeMode = degradeModeOf(r.data.raw_layout);
        if (degradeMode) {
          setError(SKETCH_DEGRADE_MSG[degradeMode] ?? `草图分析暂不可用（${degradeMode}）`);
        } else {
          setAnalysis(r.data);
        }
      } else {
        setError(r.status === 501 ? '服务端视觉模型未配置，草图分析不可用' : (r.error ?? `分析失败（HTTP ${r.status}）`));
      }
    } else {
      const r = await apiClient.generate3dFromSketch<Sketch3DResponse>(selectedFile, description, style);
      setSubmitting(false);
      if (r.isSuccess && r.data) {
        const degradeMode = degradeModeOf(r.data.analysis?.raw_layout);
        if (degradeMode) {
          setError(SKETCH_DEGRADE_MSG[degradeMode] ?? `3D 生成暂不可用（${degradeMode}）`);
        } else {
          setGenerated(r.data);
        }
      } else {
        setError(r.status === 501 ? '服务端视觉模型未配置，3D 生成不可用' : (r.error ?? `生成失败（HTTP ${r.status}）`));
      }
    }
  };

  const confidencePct = analysis ? Math.round(analysis.confidence * 100) : 0;

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-sketch-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">✏️ 草图转 3D</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {/* 模式 tab */}
          <div className="wb-task-filter" role="tablist" aria-label="模式" data-testid="wb-sketch-tabs">
            <button type="button" role="tab" aria-selected={mode === 'analyze'} className={`wb-task-filter__chip ${mode === 'analyze' ? 'wb-task-filter__chip--active' : ''}`} onClick={() => setMode('analyze')} data-testid="wb-sketch-tab--analyze">🔍 草图分析</button>
            <button type="button" role="tab" aria-selected={mode === 'generate'} className={`wb-task-filter__chip ${mode === 'generate' ? 'wb-task-filter__chip--active' : ''}`} onClick={() => setMode('generate')} data-testid="wb-sketch-tab--generate">🏗 生成 3D</button>
          </div>

          {/* 文件选择 */}
          <div className="wb-upload-zone" data-testid="wb-sketch-upload-zone">
            <input ref={fileInputRef} type="file" accept="image/png,image/jpeg,image/jpg" onChange={handleFileChange} style={{ display: 'none' }} data-testid="wb-sketch-file-input" />
            <button type="button" className="wb-upload-zone__pick" onClick={() => fileInputRef.current?.click()} data-testid="wb-sketch-pick-btn">🖼 选择草图图片</button>
            <div className="wb-upload-zone__hint" data-testid="wb-sketch-file-name">
              {selectedFile ? `已选择：${selectedFile.name}（${(selectedFile.size / 1024).toFixed(1)} KB）` : `支持 ${formatNames}`}
            </div>
          </div>

          {/* 描述输入 */}
          <input
            type="text"
            className="wb-sketch-desc"
            placeholder="草图描述（可选，如：三室两厅户型）"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            data-testid="wb-sketch-desc-input"
          />

          {/* 风格选择（仅生成模式） */}
          {mode === 'generate' && (
            <div className="wb-project-picker">
              <select value={style} onChange={(e) => setStyle(e.target.value)} aria-label="风格" data-testid="wb-sketch-style-select">
                {STYLES.map((s) => (<option key={s} value={s}>{s}</option>))}
              </select>
            </div>
          )}

          {/* 提交按钮 */}
          {selectedFile && (
            <button type="button" className="wb-theme-option wb-theme-option--active wb-upload-action" onClick={handleSubmit} disabled={submitting} data-testid="wb-sketch-submit-btn">
              {submitting ? '⏳ 处理中…' : (mode === 'analyze' ? '🔍 开始分析' : '🏗 生成 3D')}
            </button>
          )}

          {submitting && (
            <div className="wb-state" data-testid="wb-sketch-loading">
              <div className="wb-state__icon">⏳</div><div>{mode === 'analyze' ? '正在分析草图…' : '正在生成 3D 方案…'}</div>
            </div>
          )}

          {error && !submitting && (
            <div className="wb-state wb-state--error" data-testid="wb-sketch-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={() => setError(null)}>关闭</button>
            </div>
          )}

          {/* 分析结果 */}
          {mode === 'analyze' && analysis && !submitting && (
            <div data-testid="wb-sketch-analysis-result">
              <div className="wb-section-label">分析结果</div>
              <div className="wb-takeoff-grid">
                <div className="wb-takeoff-stat" data-testid="wb-sketch-walls"><div className="wb-takeoff-stat__value">{analysis.detected_walls.length}</div><div className="wb-takeoff-stat__label">🧱 墙体</div></div>
                <div className="wb-takeoff-stat" data-testid="wb-sketch-doors"><div className="wb-takeoff-stat__value">{analysis.detected_doors.length}</div><div className="wb-takeoff-stat__label">🚪 门</div></div>
                <div className="wb-takeoff-stat" data-testid="wb-sketch-windows"><div className="wb-takeoff-stat__value">{analysis.detected_windows.length}</div><div className="wb-takeoff-stat__label">🪟 窗</div></div>
                <div className="wb-takeoff-stat" data-testid="wb-sketch-rooms"><div className="wb-takeoff-stat__value">{analysis.room_count}</div><div className="wb-takeoff-stat__label">🏠 房间数</div></div>
                <div className="wb-takeoff-stat" data-testid="wb-sketch-area"><div className="wb-takeoff-stat__value">{analysis.estimated_area.toFixed(1)}</div><div className="wb-takeoff-stat__label">📐 估算面积(㎡)</div></div>
                <div className="wb-takeoff-stat" data-testid="wb-sketch-confidence"><div className="wb-takeoff-stat__value">{confidencePct}%</div><div className="wb-takeoff-stat__label">🎯 置信度</div></div>
              </div>
              <div className="wb-project-card" data-testid="wb-sketch-sketch-id">
                <div className="wb-project-card__meta"><span className="wb-project-card__meta-item">🆔 {analysis.sketch_id}</span></div>
              </div>
            </div>
          )}

          {/* 生成 3D 结果 */}
          {mode === 'generate' && generated && !submitting && (
            <div data-testid="wb-sketch-generate-result">
              <div className="wb-section-label">3D 生成结果</div>
              <div className="wb-project-card" data-testid="wb-sketch-3d-layout">
                <div className="wb-project-card__title">🏗 方案已生成</div>
                <div className="wb-project-card__meta">
                  <span className="wb-project-card__meta-item">🆔 {generated.sketch_id}</span>
                  {generated.layout_3d?.bim_compatible !== undefined && (
                    <span className="wb-project-card__meta-item">{generated.layout_3d.bim_compatible ? '✅ BIM 兼容' : '⚠ 非 BIM 兼容'}</span>
                  )}
                </div>
                {generated.layout_3d?.recommendation && (
                  <div className="wb-project-card__meta-item" data-testid="wb-sketch-3d-recommendation">💡 {generated.layout_3d.recommendation}</div>
                )}
              </div>
              {generated.suggestions.length > 0 && (
                <>
                  <div className="wb-section-label">优化建议</div>
                  <div data-testid="wb-sketch-3d-suggestions">
                    {generated.suggestions.map((s, i) => (
                      <div key={i} className="wb-project-card" data-testid={`wb-sketch-3d-suggestion--${i}`}>
                        <div className="wb-project-card__meta-item">💡 {s}</div>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
