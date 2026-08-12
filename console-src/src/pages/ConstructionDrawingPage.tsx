/**
 * ConstructionDrawingPage — 施工图生成（v1.13.x 前端缺口补齐 B2）
 *
 * 结构：Scaffold > AppBar(施工图) > 项目选择器 > 平面图 + 立面图列表 + 剖面图 + MEP 叠加
 * API（对齐 app/api/construction_drawing.py，前缀 /api/construction-drawing）：
 *   GET /api/construction-drawing/{projectId}/all   全套图纸（SVG 文本，floorplan.data 为 SSOT）
 *
 * 诚实降级：503（construction_drawing_enabled=False）或 404（无 floorplan）时
 * 错误文案真实展示；SVG 以 data URI 渲染（无 XSS 风险）。
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { ConstructionDrawingBundle, Project } from '../types/domain';

function svgDataUri(svg: string): string {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

export default function ConstructionDrawingPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState('');

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  const { data: drawings, loading, error, reload } = useAsync<ConstructionDrawingBundle | null>(async () => {
    if (!selectedProjectId) return null;
    const r = await apiClient.getConstructionDrawings<ConstructionDrawingBundle>(selectedProjectId);
    if (!r.isSuccess || !r.data) throw new Error(r.error ?? `HTTP ${r.status}`);
    return r.data;
  }, [selectedProjectId]);

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-construction-drawing-page">
        <div className="wb-page-header">
          <button className="wb-page-header__back" onClick={() => navigate('/')} aria-label="返回" type="button">‹</button>
          <div className="wb-page-header__title">📐 施工图</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-project-picker">
            <select
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              aria-label="选择项目"
              data-testid="wb-cd-project-select"
            >
              <option value="">选择项目…</option>
              {projects?.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </div>

          {!selectedProjectId && (
            <div className="wb-state"><div className="wb-state__icon">📋</div><div>请先选择项目（需已创建户型方案）</div></div>
          )}
          {selectedProjectId && loading && (
            <div className="wb-state"><div className="wb-state__icon">⏳</div><div>生成图纸中…</div></div>
          )}
          {selectedProjectId && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-cd-error">
              <div className="wb-state__icon">⚠</div><div>{error}</div>
              <button className="wb-btn wb-btn--sm" onClick={() => reload()} type="button">重试</button>
            </div>
          )}

          {selectedProjectId && !loading && !error && drawings && (
            <div data-testid="wb-cd-content">
              <div className="wb-actions" style={{ marginBottom: 8 }}>
                <span className="wb-status-chip wb-status-chip--info">{drawings.floorplan_name}</span>
                <span className="wb-list-row__sub">版本 {drawings.drawing_version} · 元素 {drawings.element_count}</span>
              </div>

              {/* 平面布置图 */}
              {drawings.floor_plan_svg && (
                <div className="wb-card" data-testid="wb-cd-floor-plan">
                  <div className="wb-card__title">平面布置图</div>
                  <img
                    src={svgDataUri(drawings.floor_plan_svg)}
                    alt="平面布置图"
                    style={{ width: '100%', borderRadius: 8, border: '1px solid var(--border)' }}
                  />
                </div>
              )}

              {/* MEP 水电叠加（flag 关闭时为空串） */}
              {drawings.mep_overlay_svg && (
                <div className="wb-card" data-testid="wb-cd-mep">
                  <div className="wb-card__title">水电管线叠加</div>
                  <img
                    src={svgDataUri(drawings.mep_overlay_svg)}
                    alt="水电管线叠加图"
                    style={{ width: '100%', borderRadius: 8, border: '1px solid var(--border)' }}
                  />
                </div>
              )}

              {/* 剖面图 */}
              {drawings.section_svg && (
                <div className="wb-card" data-testid="wb-cd-section">
                  <div className="wb-card__title">剖面图</div>
                  <img
                    src={svgDataUri(drawings.section_svg)}
                    alt="剖面图"
                    style={{ width: '100%', borderRadius: 8, border: '1px solid var(--border)' }}
                  />
                </div>
              )}

              {/* 立面图列表 */}
              {drawings.elevation_svgs && drawings.elevation_svgs.length > 0 && (
                <div className="wb-card" data-testid="wb-cd-elevations">
                  <div className="wb-card__title">立面图（{drawings.elevation_svgs.length}）</div>
                  {drawings.elevation_svgs.map((e, i) => (
                    <div key={i} style={{ marginBottom: 12 }}>
                      <div className="wb-list-row__sub" style={{ marginBottom: 4 }}>{e.wall_name || `立面 ${i + 1}`}</div>
                      {e.svg && (
                        <img
                          src={svgDataUri(e.svg)}
                          alt={e.wall_name || `立面 ${i + 1}`}
                          style={{ width: '100%', borderRadius: 8, border: '1px solid var(--border)' }}
                        />
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
