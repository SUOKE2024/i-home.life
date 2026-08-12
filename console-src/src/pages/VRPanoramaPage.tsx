/**
 * VRPanoramaPage — VR 全景图管理
 *
 * 结构：Scaffold > AppBar(VR 全景) > [项目选择器] > 全景图卡片列表
 * API：GET /api/vr/panoramas/project/{projectId}
 *      （对齐 app/api/vr_panorama.py:49）
 *
 * 后端字段（app/schemas/vr_panorama.py:VRPanoramaListItem）：
 *   room_name / panorama_type / image_url / thumbnail_url / resolution /
 *   hotspots[] / status / created_at
 *
 * 状态：pending/rendering/completed/failed
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { Project, VRPanoramaListItem } from '../types/domain';

const STATUS_LABELS: Record<string, { label: string; cls: string }> = {
  queued: { label: '排队中', cls: 'pending' },
  rendering: { label: '渲染中', cls: 'active' },
  completed: { label: '已完成', cls: 'completed' },
  failed: { label: '失败', cls: 'error' },
  // 兼容历史数据
  pending: { label: '待渲染', cls: 'pending' },
};

const PANORAMA_TYPE_LABELS: Record<string, string> = {
  equirectangular: '球面全景',
  cubemap: '立方体全景',
  stereo: '立体全景',
};

function formatDate(iso?: string | null): string {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  } catch {
    return iso;
  }
}

export default function VRPanoramaPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  const { data: panoramas, loading, error, reload } = useAsync<VRPanoramaListItem[] | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.getVRPanoramas<VRPanoramaListItem[]>(selectedProjectId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [selectedProjectId],
  );

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-vrpanorama-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">🌐 VR 全景</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-project-picker">
            <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)} aria-label="选择项目" data-testid="wb-vrpanorama-project-select">
              <option value="">选择项目…</option>
              {projects?.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </div>

          {!selectedProjectId && (
            <div className="wb-state" data-testid="wb-vrpanorama-no-project">
              <div className="wb-state__icon">📋</div><div>请先选择项目</div>
            </div>
          )}
          {selectedProjectId && loading && (
            <div className="wb-state" data-testid="wb-vrpanorama-loading">
              <div className="wb-state__icon">⏳</div><div>加载全景图中…</div>
            </div>
          )}
          {selectedProjectId && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-vrpanorama-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>重试</button>
            </div>
          )}
          {selectedProjectId && !loading && !error && (panoramas?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-vrpanorama-empty">
              <div className="wb-state__icon">🌐</div>
              <div>暂无全景图</div>
              <div style={{ fontSize: 'var(--font-size-sm)' }}>可通过工作台与设计 Agent 对话生成</div>
            </div>
          )}

          {selectedProjectId && !loading && !error && (panoramas?.length ?? 0) > 0 && (
            <div data-testid="wb-vrpanorama-content">
              <div className="wb-section-label">全景图（{panoramas!.length}）</div>
              {panoramas!.map((p, i) => {
                const st = STATUS_LABELS[p.status] ?? { label: p.status, cls: 'pending' };
                return (
                  <div key={p.id} className="wb-project-card" data-testid={`wb-vrpanorama-item--${i}`}>
                    <div className="wb-project-card__title">
                      {p.room_name}
                      <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginLeft: 8 }}>
                        {PANORAMA_TYPE_LABELS[p.panorama_type] ?? p.panorama_type}
                      </span>
                    </div>
                    {p.thumbnail_url && (
                      <img
                        src={p.thumbnail_url}
                        alt={p.room_name}
                        style={{ width: '100%', borderRadius: 'var(--radius-sm)', marginTop: 8, maxHeight: 120, objectFit: 'cover' }}
                        onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
                      />
                    )}
                    <div className="wb-project-card__meta">
                      <span className="wb-project-card__meta-item">📐 {p.resolution}</span>
                      <span className="wb-project-card__meta-item">🔴 {p.hotspots?.length ?? 0} 热点</span>
                      <span className="wb-project-card__meta-item">📅 {formatDate(p.created_at)}</span>
                      <span className={`wb-status-badge wb-status--${st.cls}`} data-testid={`wb-vrpanorama-status--${i}`}>
                        {st.label}
                      </span>
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
