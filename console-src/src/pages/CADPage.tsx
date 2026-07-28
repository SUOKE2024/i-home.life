/**
 * CADPage — CAD 导入（DXF/DWG 解析）
 *
 * 结构：Scaffold > AppBar(CAD 导入) > [文件选择] > [上传解析] > 解析结果
 * API：POST /api/cad-import/dxf（multipart upload，对齐 app/api/cad_import.py:185）
 *
 * 后端字段（app/api/cad_import.py:CADImportResult）：
 *   file_type / entity_count / lines[] / polylines[] / circles[] / arcs[] / texts[] / bounds / converted_from_dwg
 *
 * 降级：
 *   501 — 服务端未安装 ezdxf 库（cad_import.py:52）
 *   400 — DXF 解析失败 / 空文件
 */

import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { apiClient } from '../services/api-client';
import type { CADImportResult } from '../types/domain';

const ENTITY_LABELS: Array<{ key: keyof CADImportResult; label: string; emoji: string }> = [
  { key: 'lines', label: '线段', emoji: '📏' },
  { key: 'polylines', label: '多段线', emoji: '〰' },
  { key: 'circles', label: '圆形', emoji: '⭕' },
  { key: 'arcs', label: '弧线', emoji: '🌈' },
  { key: 'texts', label: '文本', emoji: '📝' },
];

export default function CADPage() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<CADImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null;
    setSelectedFile(f);
    setResult(null);
    setError(null);
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    setError(null);
    setResult(null);
    const r = await apiClient.importCadDxf<CADImportResult>(selectedFile);
    setUploading(false);
    if (r.isSuccess && r.data) {
      setResult(r.data);
    } else {
      // 501 ezdxf 未装 / 400 解析失败
      const code = r.status;
      if (code === 501) setError('服务端未安装 ezdxf 库，CAD 解析不可用。请联系管理员安装 ezdxf>=0.7.0。');
      else if (code === 400) setError(`文件解析失败：${r.error ?? 'DXF 格式错误或文件为空'}`);
      else setError(r.error ?? `上传失败（HTTP ${code}）`);
    }
  };

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-cad-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">📐 CAD 导入</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {/* 文件选择区 */}
          <div className="wb-upload-zone" data-testid="wb-cad-upload-zone">
            <input
              ref={fileInputRef}
              type="file"
              accept=".dxf,.dwg"
              onChange={handleFileChange}
              style={{ display: 'none' }}
              data-testid="wb-cad-file-input"
            />
            <button
              type="button"
              className="wb-upload-zone__pick"
              onClick={() => fileInputRef.current?.click()}
              data-testid="wb-cad-pick-btn"
            >
              📂 选择 CAD 文件
            </button>
            <div className="wb-upload-zone__hint" data-testid="wb-cad-file-name">
              {selectedFile ? `已选择：${selectedFile.name}（${(selectedFile.size / 1024).toFixed(1)} KB）` : '支持 .dxf / .dwg 格式'}
            </div>
          </div>

          {/* 上传按钮 */}
          {selectedFile && !result && (
            <button
              type="button"
              className="wb-theme-option wb-theme-option--active wb-upload-action"
              onClick={handleUpload}
              disabled={uploading}
              data-testid="wb-cad-upload-btn"
            >
              {uploading ? '⏳ 解析中…' : '🚀 开始解析'}
            </button>
          )}

          {/* 加载态 */}
          {uploading && (
            <div className="wb-state" data-testid="wb-cad-loading">
              <div className="wb-state__icon">⏳</div><div>正在解析 CAD 文件…</div>
            </div>
          )}

          {/* 错误态 */}
          {error && !uploading && (
            <div className="wb-state wb-state--error" data-testid="wb-cad-error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={() => setError(null)}>关闭</button>
            </div>
          )}

          {/* 结果展示 */}
          {result && !uploading && (
            <div data-testid="wb-cad-result">
              {/* 顶部统计卡 */}
              <div className="wb-section-label">解析结果</div>
              <div className="wb-cad-summary">
                <div className="wb-cad-summary__item" data-testid="wb-cad-file-type">
                  <span className="wb-cad-summary__label">文件类型</span>
                  <span className="wb-cad-summary__value">{result.file_type.toUpperCase()}</span>
                </div>
                <div className="wb-cad-summary__item" data-testid="wb-cad-entity-count">
                  <span className="wb-cad-summary__label">实体总数</span>
                  <span className="wb-cad-summary__value">{result.entity_count}</span>
                </div>
                <div className="wb-cad-summary__item" data-testid="wb-cad-converted">
                  <span className="wb-cad-summary__label">DWG 转换</span>
                  <span className="wb-cad-summary__value">{result.converted_from_dwg ? '✅ 是' : '❌ 否'}</span>
                </div>
              </div>

              {/* 实体明细网格 */}
              <div className="wb-section-label">实体明细</div>
              <div className="wb-takeoff-grid" data-testid="wb-cad-entities">
                {ENTITY_LABELS.map(({ key, label, emoji }) => {
                  const arr = result[key] as unknown[] | undefined;
                  return (
                    <div key={key} className="wb-takeoff-stat" data-testid={`wb-cad-entity--${key}`}>
                      <div className="wb-takeoff-stat__value">{arr?.length ?? 0}</div>
                      <div className="wb-takeoff-stat__label">{emoji} {label}</div>
                    </div>
                  );
                })}
              </div>

              {/* 边界范围 */}
              {result.bounds && (
                <>
                  <div className="wb-section-label">边界范围</div>
                  <div className="wb-project-card" data-testid="wb-cad-bounds">
                    <div className="wb-project-card__meta">
                      <span className="wb-project-card__meta-item"> minX: {result.bounds.min_x.toFixed(2)}</span>
                      <span className="wb-project-card__meta-item"> minY: {result.bounds.min_y.toFixed(2)}</span>
                      <span className="wb-project-card__meta-item"> maxX: {result.bounds.max_x.toFixed(2)}</span>
                      <span className="wb-project-card__meta-item"> maxY: {result.bounds.max_y.toFixed(2)}</span>
                      {typeof result.bounds.width === 'number' && (
                        <span className="wb-project-card__meta-item"> ↔ 宽: {result.bounds.width.toFixed(2)}</span>
                      )}
                      {typeof result.bounds.height === 'number' && (
                        <span className="wb-project-card__meta-item"> ↕ 高: {result.bounds.height.toFixed(2)}</span>
                      )}
                    </div>
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
