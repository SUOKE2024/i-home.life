/**
 * IFCExportPage — BIM IFC 导出
 *
 * 结构：Scaffold > AppBar(BIM 导出) > [项目选择] > [选项] > [tab: 结构/设计] > 导出下载
 * API：
 *   POST /api/bim/export/structural/{projectId}（body: IFCExportRequest → FileResponse blob）
 *   POST /api/bim/export/design/{planId}（body: IFCExportRequest → FileResponse blob）
 *
 * 后端字段（app/schemas/ifc_export.py）：
 *   IFCExportRequest: include_furniture / lod_level（LOD200/LOD300/LOD350）
 *   注意：后端用 Depends(lambda: IFCExportRequest()) 取默认值，body 字段当前不生效；
 *        前端仍发送完整 body，待后端修复为 Body() 后自动生效。
 *
 * 降级：
 *   501 — ifcopenshell 未安装（ifc_export.py:46），提示安装
 *   404 — 项目/方案不存在或无结构数据
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { Project, FloorPlan, IFCExportRequest } from '../types/domain';

type Mode = 'structural' | 'design';

const LOD_LEVELS: Array<{ value: IFCExportRequest['lod_level']; label: string }> = [
  { value: 'LOD200', label: 'LOD200 — 概念设计' },
  { value: 'LOD300', label: 'LOD300 — 施工图设计（默认）' },
  { value: 'LOD350', label: 'LOD350 — 深化设计' },
];

/** 触发浏览器下载 blob */
function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function IFCExportPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>('structural');
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [selectedPlanId, setSelectedPlanId] = useState<string>('');
  const [includeFurniture, setIncludeFurniture] = useState(false);
  const [lodLevel, setLodLevel] = useState<IFCExportRequest['lod_level']>('LOD300');
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  // 设计模式：加载项目下的户型方案
  const { data: floorplans } = useAsync<FloorPlan[] | null>(async () => {
    if (mode !== 'design' || !selectedProjectId) return null;
    const r = await apiClient.getFloorPlans<FloorPlan[]>(selectedProjectId);
    return r.isSuccess && r.data ? r.data : [];
  }, [mode, selectedProjectId]);

  useEffect(() => {
    if (floorplans && floorplans.length > 0 && !selectedPlanId) {
      setSelectedPlanId(floorplans[0].id);
    } else if (!floorplans || floorplans.length === 0) {
      setSelectedPlanId('');
    }
  }, [floorplans, selectedPlanId]);

  const handleExport = async () => {
    if (mode === 'structural' && !selectedProjectId) return;
    if (mode === 'design' && !selectedPlanId) return;

    const options: IFCExportRequest = { include_furniture: includeFurniture, lod_level: lodLevel };
    setExporting(true);
    setError(null);
    setSuccess(null);

    const r = mode === 'structural'
      ? await apiClient.exportStructuralIfc(selectedProjectId, options)
      : await apiClient.exportDesignIfc(selectedPlanId, options);

    setExporting(false);

    if (r.isSuccess && r.blob && r.filename) {
      triggerDownload(r.blob, r.filename);
      setSuccess(`✅ 已导出：${r.filename}（${(r.blob.size / 1024).toFixed(1)} KB）`);
    } else {
      if (r.status === 501) setError('服务端未安装 ifcopenshell，IFC 导出不可用。请联系管理员安装 ifcopenshell>=0.7.0。');
      else if (r.status === 404) setError('未找到可导出的数据：项目/方案不存在或无结构数据。');
      else setError(r.error ?? `导出失败（HTTP ${r.status}）`);
    }
  };

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-ifc-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">📦 BIM 导出</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {/* 模式 tab */}
          <div className="wb-task-filter" role="tablist" aria-label="导出模式" data-testid="wb-ifc-tabs">
            <button type="button" role="tab" aria-selected={mode === 'structural'} className={`wb-task-filter__chip ${mode === 'structural' ? 'wb-task-filter__chip--active' : ''}`} onClick={() => setMode('structural')} data-testid="wb-ifc-tab--structural">🏗 结构导出</button>
            <button type="button" role="tab" aria-selected={mode === 'design'} className={`wb-task-filter__chip ${mode === 'design' ? 'wb-task-filter__chip--active' : ''}`} onClick={() => setMode('design')} data-testid="wb-ifc-tab--design">📐 设计导出</button>
          </div>

          {/* 项目选择 */}
          <div className="wb-project-picker">
            <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)} aria-label="选择项目" data-testid="wb-ifc-project-select">
              <option value="">选择项目…</option>
              {projects?.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </div>

          {/* 设计模式：方案选择 */}
          {mode === 'design' && selectedProjectId && (
            <div className="wb-project-picker">
              <select value={selectedPlanId} onChange={(e) => setSelectedPlanId(e.target.value)} aria-label="选择户型方案" data-testid="wb-ifc-plan-select">
                <option value="">选择方案…</option>
                {floorplans?.map((fp) => (<option key={fp.id} value={fp.id}>{fp.name}</option>))}
              </select>
            </div>
          )}

          {/* 导出选项 */}
          <div className="wb-ifc-options" data-testid="wb-ifc-options">
            <label className="wb-ifc-checkbox" data-testid="wb-ifc-furniture">
              <input type="checkbox" checked={includeFurniture} onChange={(e) => setIncludeFurniture(e.target.checked)} />
              <span>含家具</span>
            </label>
            <label className="wb-ifc-select">
              <span>细节等级</span>
              <select value={lodLevel} onChange={(e) => setLodLevel(e.target.value as IFCExportRequest['lod_level'])} data-testid="wb-ifc-lod">
                {LOD_LEVELS.map((l) => (<option key={l.value} value={l.value}>{l.label}</option>))}
              </select>
            </label>
          </div>

          {/* 导出按钮 */}
          <button
            type="button"
            className="wb-theme-option wb-theme-option--active wb-upload-action"
            onClick={handleExport}
            disabled={exporting || (mode === 'structural' && !selectedProjectId) || (mode === 'design' && !selectedPlanId)}
            data-testid="wb-ifc-export-btn"
          >
            {exporting ? '⏳ 导出中…' : `📦 导出 ${mode === 'structural' ? '结构' : '设计'} IFC`}
          </button>

          {exporting && (
            <div className="wb-state" data-testid="wb-ifc-loading">
              <div className="wb-state__icon">⏳</div><div>正在生成 IFC 文件…</div>
            </div>
          )}

          {error && !exporting && (
            <div className="wb-state wb-state--error" data-testid="wb-ifc-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={() => setError(null)}>关闭</button>
            </div>
          )}

          {success && !exporting && (
            <div className="wb-state" data-testid="wb-ifc-success">
              <div className="wb-state__icon">✅</div><div>{success}</div>
            </div>
          )}

          {/* 提示 */}
          <div className="wb-project-card" data-testid="wb-ifc-hint">
            <div className="wb-project-card__meta-item">💡 IFC4 格式，可在 Revit / ArchiCAD / BIMReviewer 中打开</div>
          </div>
        </div>
      </div>
    </SuokeLayout>
  );
}
