/**
 * ProjectDetailPage — 项目详情页（/projects/:id）
 *
 * 数据来源：
 *   GET /api/projects/{id}        项目信息
 *   GET /api/materials/bom/{id}   BOM 物料清单
 *   GET /api/budgets/project/{id} 预算
 */

import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { SuokeCard, SuokeButton } from '../components';
import { apiClient } from '../services/api-client';
import { useAsync } from '../hooks/useAsync';
import type { Project, BomItem, Budget } from '../types/domain';

const PROJECT_TYPE_LABELS: Record<string, string> = {
  full_renovation: '整装',
  hard_decoration: '硬装',
  soft_furnishing: '软装',
  curtain: '窗帘定制',
  kitchen: '厨房改造',
  bathroom: '卫浴改造',
  electrical: '电路改造',
  carpentry: '木工制作',
  painting: '油漆涂刷',
  plumbing: '水管改造',
  masonry: '泥瓦铺贴',
  installation: '设备安装',
};

const STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  active: '施工中',
  completed: '已完成',
  cancelled: '已取消',
};

const BOM_STATUS_LABELS: Record<string, string> = {
  pending: '待采购',
  ordered: '已下单',
  delivered: '已到货',
  installed: '已安装',
};

function formatDate(iso?: string): string {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString('zh-CN');
  } catch {
    return '';
  }
}

function formatMoney(n: number | null | undefined): string {
  if (n == null) return '-';
  return `¥${n.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`;
}

export default function ProjectDetailPage() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [bomError, setBomError] = useState('');

  const { data: project, loading, error } = useAsync<Project>(
    async () => {
      if (!id) throw new Error('缺少项目 ID');
      const r = await apiClient.getProject<Project>(id);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [id],
  );

  const { data: bom, loading: bomLoading, reload: reloadBom } = useAsync<BomItem[]>(
    async () => {
      if (!id) return [];
      setBomError('');
      const r = await apiClient.getProjectBom<BomItem[]>(id);
      if (!r.isSuccess) {
        setBomError(r.error ?? 'BOM 加载失败');
        return [];
      }
      return r.data ?? [];
    },
    [id],
  );

  const { data: budget } = useAsync<Budget | null>(
    async () => {
      if (!id) return null;
      const r = await apiClient.getBudget<Budget>(id);
      if (!r.isSuccess) return null; // 404 = 暂无预算
      return r.data ?? null;
    },
    [id],
  );

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-project-detail-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/projects')}
            aria-label="返回项目列表"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">项目详情</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {loading && (
            <div className="wb-state" data-testid="wb-project-detail-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载项目中…</div>
            </div>
          )}

          {error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-project-detail-error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
              <SuokeButton variant="outline" size="sm" onClick={() => navigate('/projects')}>
                返回项目列表
              </SuokeButton>
            </div>
          )}

          {project && !loading && (
            <>
              {/* ── 项目信息 ── */}
              <SuokeCard style={{ marginBottom: 16 }} testId="wb-project-detail-info">
                <div className="wb-project-card__title">{project.name}</div>
                <div className="wb-project-card__meta">
                  <span className="wb-project-card__meta-item">
                    📐 {PROJECT_TYPE_LABELS[project.project_type] ?? project.project_type}
                  </span>
                  {project.total_area != null && (
                    <span className="wb-project-card__meta-item">📏 {project.total_area}㎡</span>
                  )}
                  <span className="wb-project-card__meta-item">
                    🔖 {STATUS_LABELS[project.status] ?? project.status}
                  </span>
                  <span className="wb-project-card__meta-item">📅 {formatDate(project.created_at)}</span>
                </div>
                {project.description && (
                  <div
                    style={{ fontSize: 'var(--font-size-sm)', color: 'var(--text-muted)', marginTop: 8 }}
                  >
                    {project.description}
                  </div>
                )}
                {project.house_type && (
                  <div
                    style={{ fontSize: 'var(--font-size-sm)', color: 'var(--text-muted)', marginTop: 6 }}
                  >
                    🏠 户型：{project.house_type}
                  </div>
                )}
                {project.address && (
                  <div
                    style={{ fontSize: 'var(--font-size-sm)', color: 'var(--text-muted)', marginTop: 6 }}
                  >
                    📍 {project.address}
                  </div>
                )}
                {(project.contact_name || project.contact_phone) && (
                  <div
                    style={{ fontSize: 'var(--font-size-sm)', color: 'var(--text-muted)', marginTop: 6 }}
                  >
                    👤 {project.contact_name ?? '未填写联系人'}
                    {project.contact_phone ? ` · ${project.contact_phone}` : ''}
                  </div>
                )}
              </SuokeCard>

              {/* ── 预算 ── */}
              <SuokeCard style={{ marginBottom: 16 }} testId="wb-project-detail-budget">
                <div className="wb-project-card__title">预算</div>
                {budget ? (
                  <>
                    <div className="wb-project-card__meta" style={{ marginBottom: 12 }}>
                      <span className="wb-project-card__meta-item">
                        预估 {formatMoney(budget.total_estimated)}
                      </span>
                      <span className="wb-project-card__meta-item">
                        实际 {formatMoney(budget.total_actual)}
                      </span>
                    </div>
                    {budget.lines.length > 0 ? (
                      <div style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
                      <table
                        style={{
                          width: '100%',
                          borderCollapse: 'collapse',
                          fontSize: 'var(--font-size-sm)',
                        }}
                      >
                        <thead>
                          <tr>
                            <th style={thStyle}>分类</th>
                            <th style={thStyle}>名称</th>
                            <th style={{ ...thStyle, textAlign: 'right' }}>数量</th>
                            <th style={{ ...thStyle, textAlign: 'right' }}>预估</th>
                            <th style={{ ...thStyle, textAlign: 'right' }}>实际</th>
                          </tr>
                        </thead>
                        <tbody>
                          {budget.lines.map((l) => (
                            <tr key={l.id}>
                              <td style={tdStyle}>{l.category}</td>
                              <td style={tdStyle}>{l.name}</td>
                              <td style={{ ...tdStyle, textAlign: 'right' }}>
                                {l.quantity} {l.unit}
                              </td>
                              <td style={{ ...tdStyle, textAlign: 'right' }}>
                                {formatMoney(l.estimated_amount)}
                              </td>
                              <td style={{ ...tdStyle, textAlign: 'right' }}>
                                {formatMoney(l.actual_amount)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      </div>
                    ) : (
                      <div style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-sm)' }}>
                        预算暂无明细
                      </div>
                    )}
                  </>
                ) : (
                  <div style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-sm)' }}>
                    暂未生成预算
                  </div>
                )}
              </SuokeCard>

              {/* ── BOM 清单 ── */}
              <SuokeCard testId="wb-project-detail-bom">
                <div className="wb-project-card__title">物料清单（BOM）</div>
                {bomLoading && (
                  <div style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-sm)' }}>
                    加载中…
                  </div>
                )}
                {!bomLoading && bomError && (
                  <div style={{ color: 'var(--danger, #e57373)', fontSize: 'var(--font-size-sm)' }}>
                    ⚠ {bomError}{' '}
                    <button
                      type="button"
                      className="wb-mini-btn"
                      onClick={() => reloadBom()}
                    >
                      重试
                    </button>
                  </div>
                )}
                {!bomLoading && !bomError && bom && bom.length === 0 && (
                  <div style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-sm)' }}>
                    暂无物料清单
                  </div>
                )}
                {!bomLoading && bom && bom.length > 0 && (
                  <div style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
                  <table
                    style={{
                      width: '100%',
                      borderCollapse: 'collapse',
                      fontSize: 'var(--font-size-sm)',
                    }}
                  >
                    <thead>
                      <tr>
                        <th style={thStyle}>物料</th>
                        <th style={{ ...thStyle, textAlign: 'right' }}>数量</th>
                        <th style={{ ...thStyle, textAlign: 'right' }}>单价</th>
                        <th style={{ ...thStyle, textAlign: 'right' }}>小计</th>
                        <th style={thStyle}>状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      {bom.map((b) => (
                        <tr key={b.id}>
                          <td style={tdStyle}>{b.material?.name ?? b.material_id}</td>
                          <td style={{ ...tdStyle, textAlign: 'right' }}>{b.quantity}</td>
                          <td style={{ ...tdStyle, textAlign: 'right' }}>
                            {formatMoney(b.unit_price)}
                          </td>
                          <td style={{ ...tdStyle, textAlign: 'right' }}>
                            {formatMoney(b.total_price)}
                          </td>
                          <td style={tdStyle}>{BOM_STATUS_LABELS[b.status] ?? b.status}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  </div>
                )}
              </SuokeCard>
            </>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}

const thStyle: React.CSSProperties = {
  textAlign: 'left',
  padding: '8px 6px',
  borderBottom: '1px solid var(--border)',
  color: 'var(--text-muted)',
  fontWeight: 600,
  whiteSpace: 'nowrap',
};

const tdStyle: React.CSSProperties = {
  padding: '8px 6px',
  borderBottom: '1px solid var(--border)',
  verticalAlign: 'top',
};
