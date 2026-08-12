/**
 * FilesPage — 文件管理（v1.13.x 前端缺口补齐 B3）
 *
 * 结构：Scaffold > AppBar(文件管理) > 项目选择器 > 上传表单 + 附件列表（下载/删除）
 * API（对齐 app/api/files.py，前缀 /api/files）：
 *   GET    /api/files/project/{projectId}      附件列表
 *   POST   /api/files/upload                   上传（multipart，≤20MB）
 *   GET    /api/files/download/{attachmentId}  下载
 *   DELETE /api/files/{attachmentId}           删除
 *
 * 诚实降级：后端错误文案真实展示（不支持的文件类型 400、越权 403 等）。
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { Project, ProjectFileItem } from '../types/domain';

const CATEGORY_OPTIONS = ['other', 'design', 'contract', 'photo', 'inspection', 'material'];

function fmtSize(bytes: number | null | undefined): string {
  const b = bytes ?? 0;
  if (b >= 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`;
  if (b >= 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${b} B`;
}

function fmtDate(v: string | null | undefined): string {
  if (!v) return '—';
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('zh-CN', { hour12: false });
}

export default function FilesPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [category, setCategory] = useState('other');
  const [file, setFile] = useState<File | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  const { data: files, loading, error, reload } = useAsync<ProjectFileItem[] | null>(async () => {
    if (!selectedProjectId) return null;
    const r = await apiClient.listProjectFiles<ProjectFileItem[]>(selectedProjectId);
    if (!r.isSuccess || !r.data) throw new Error(r.error ?? `HTTP ${r.status}`);
    return r.data;
  }, [selectedProjectId]);

  async function handleUpload() {
    setFormError(null);
    if (!selectedProjectId) {
      setFormError('请先选择项目');
      return;
    }
    if (!file) {
      setFormError('请选择要上传的文件');
      return;
    }
    setUploading(true);
    try {
      const r = await apiClient.uploadProjectFile(selectedProjectId, file, category);
      if (!r.isSuccess) throw new Error(r.error ?? '上传失败');
      setFile(null);
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setUploading(false);
    }
  }

  async function handleDownload(f: ProjectFileItem) {
    setActionId(f.id);
    try {
      const r = await apiClient.downloadProjectFile(f.id);
      if (!r.isSuccess || !r.blob) throw new Error(r.error ?? '下载失败');
      const url = URL.createObjectURL(r.blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = r.filename ?? f.filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionId(null);
    }
  }

  async function handleDelete(f: ProjectFileItem) {
    setActionId(f.id);
    try {
      const r = await apiClient.deleteProjectFile(f.id);
      if (!r.isSuccess) throw new Error(r.error ?? '删除失败');
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setActionId(null);
    }
  }

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-files-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">📁 文件管理</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-project-picker">
            <select
              value={selectedProjectId}
              onChange={(e) => { setSelectedProjectId(e.target.value); setFormError(null); }}
              aria-label="选择项目"
              data-testid="wb-files-project-select"
            >
              <option value="">选择项目…</option>
              {projects?.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </div>

          {formError && (
            <div className="wb-alert" data-testid="wb-files-form-error">⚠ {formError}</div>
          )}

          {/* 上传表单 */}
          {selectedProjectId && (
            <div className="wb-card" data-testid="wb-files-upload">
              <div className="wb-card__title">上传附件（≤20MB）</div>
              <div className="wb-actions">
                <select
                  className="wb-input wb-input--sm"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  aria-label="分类"
                >
                  {CATEGORY_OPTIONS.map((c) => (<option key={c} value={c}>{c}</option>))}
                </select>
                <input
                  className="wb-input wb-input--sm"
                  style={{ flex: 1, width: 'auto', minWidth: 180 }}
                  type="file"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  aria-label="选择文件"
                />
                <button
                  className="wb-btn wb-btn--sm"
                  disabled={uploading}
                  onClick={handleUpload}
                  type="button"
                >{uploading ? '上传中…' : '上传'}</button>
              </div>
            </div>
          )}

          {/* 附件列表 */}
          <div className="wb-card" data-testid="wb-files-list">
            <div className="wb-card__title">项目附件（{files?.length ?? 0}）</div>
            {!selectedProjectId && (
              <div className="wb-state"><div className="wb-state__icon">📋</div><div>请先选择项目</div></div>
            )}
            {selectedProjectId && loading && (
              <div className="wb-state"><div className="wb-state__icon">⏳</div><div>加载附件中…</div></div>
            )}
            {selectedProjectId && error && !loading && (
              <div className="wb-state wb-state--error" data-testid="wb-files-error">
                <div className="wb-state__icon">⚠</div><div>{error}</div>
                <button className="wb-btn wb-btn--sm" onClick={() => reload()} type="button">重试</button>
              </div>
            )}
            {selectedProjectId && !loading && !error && files && files.length === 0 && (
              <div className="wb-state"><div className="wb-state__icon">📄</div><div>暂无附件（上传后显示）</div></div>
            )}
            {selectedProjectId && !loading && !error && files && files.length > 0 && (
              <table className="wb-table">
                <thead>
                  <tr><th>文件名</th><th>分类</th><th>大小</th><th>上传时间</th><th>操作</th></tr>
                </thead>
                <tbody>
                  {files.map((f) => (
                    <tr key={f.id}>
                      <td title={f.filename}>{(f.filename ?? '').slice(0, 32)}{(f.filename ?? '').length > 32 ? '…' : ''}</td>
                      <td><span className="wb-status-chip wb-status-chip--info">{f.category}</span></td>
                      <td>{fmtSize(f.file_size)}</td>
                      <td>{fmtDate(f.created_at)}</td>
                      <td>
                        <div className="wb-actions">
                          <button
                            className="wb-btn wb-btn--sm"
                            disabled={actionId === f.id}
                            onClick={() => handleDownload(f)}
                            type="button"
                          >{actionId === f.id ? '处理中…' : '下载'}</button>
                          <button
                            className="wb-btn wb-btn--sm wb-btn--ghost"
                            disabled={actionId === f.id}
                            onClick={() => handleDelete(f)}
                            type="button"
                          >删除</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </SuokeLayout>
  );
}
