/**
 * ChangeOrdersPage — 变更管理
 *
 * 结构：Scaffold > AppBar(变更管理) > [项目选择器] > 状态筛选 + 变更单卡片列表
 * API：GET /api/change-orders/project/{projectId}（对齐 app/api/change_orders.py）
 *
 * 后端字段（app/schemas/change_order.py:ChangeOrderResponse）：
 *   id / project_id / title / description / change_type / feasibility /
 *   feasibility_note / cost_impact / schedule_impact_days / design_impact /
 *   status / submitted_by / reviewed_by / approved_by / submitted_at /
 *   reviewed_at / approved_at / items[] / created_at / updated_at
 *
 * 后端状态（app/models/change_order.py）：pending | reviewing | approved | rejected | cancelled | completed
 * 可行性：feasible | infeasible | partial
 */

import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { ChangeOrder, Project } from '../types/domain';

type ChipTone = 'muted' | 'info' | 'success' | 'warning' | 'danger' | 'accent';

const STATUS_MAP: Record<string, { label: string; tone: ChipTone }> = {
  pending: { label: '待审核', tone: 'muted' },
  reviewing: { label: '审核中', tone: 'info' },
  approved: { label: '已批准', tone: 'success' },
  rejected: { label: '已驳回', tone: 'danger' },
  cancelled: { label: '已取消', tone: 'muted' },
  completed: { label: '已完成', tone: 'success' },
};

const FEASIBILITY_MAP: Record<string, { label: string; tone: ChipTone }> = {
  feasible: { label: '可行', tone: 'success' },
  infeasible: { label: '不可行', tone: 'danger' },
  partial: { label: '部分可行', tone: 'warning' },
};

const ACTION_MAP: Record<string, string> = {
  add: '新增',
  modify: '修改',
  remove: '删除',
};

const FILTERS: Array<{ key: string; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'pending', label: '待审核' },
  { key: 'reviewing', label: '审核中' },
  { key: 'approved', label: '已批准' },
  { key: 'rejected', label: '已驳回' },
  { key: 'completed', label: '已完成' },
];

function formatDate(iso?: string | null): string {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return `${d.getMonth() + 1}/${d.getDate()}`;
  } catch {
    return iso;
  }
}

export default function ChangeOrdersPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [filterStatus, setFilterStatus] = useState<string>('all');

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  const { data: orders, loading, error, reload } = useAsync<ChangeOrder[] | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.getChangeOrders<ChangeOrder[]>(selectedProjectId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [selectedProjectId],
  );

  const filteredOrders = useMemo(() => {
    if (!orders) return [];
    if (filterStatus === 'all') return orders;
    return orders.filter((o) => o.status === filterStatus);
  }, [orders, filterStatus]);

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    (orders ?? []).forEach((o) => {
      counts[o.status] = (counts[o.status] ?? 0) + 1;
    });
    return counts;
  }, [orders]);

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-changeorders-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">📝 变更管理</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-project-picker">
            <select
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              aria-label="选择项目"
              data-testid="wb-changeorders-project-select"
            >
              <option value="">选择项目…</option>
              {projects?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {!selectedProjectId && (
            <div className="wb-state" data-testid="wb-changeorders-no-project">
              <div className="wb-state__icon">📋</div>
              <div>请先选择项目</div>
            </div>
          )}

          {selectedProjectId && loading && (
            <div className="wb-state" data-testid="wb-changeorders-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载变更单中…</div>
            </div>
          )}

          {selectedProjectId && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-changeorders-error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>
                重试
              </button>
            </div>
          )}

          {selectedProjectId && !loading && !error && (orders?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-changeorders-empty">
              <div className="wb-state__icon">📝</div>
              <div>暂无变更单</div>
            </div>
          )}

          {selectedProjectId && !loading && !error && (orders?.length ?? 0) > 0 && (
            <div data-testid="wb-changeorders-content">
              <div className="wb-task-filter" role="tablist" aria-label="状态筛选">
                {FILTERS.map((f) => {
                  const count = f.key === 'all' ? orders!.length : statusCounts[f.key] ?? 0;
                  return (
                    <button
                      key={f.key}
                      type="button"
                      role="tab"
                      aria-selected={filterStatus === f.key}
                      className={`wb-task-filter__chip ${
                        filterStatus === f.key ? 'wb-task-filter__chip--active' : ''
                      }`}
                      onClick={() => setFilterStatus(f.key)}
                      data-testid={`wb-changeorders-filter--${f.key}`}
                    >
                      {f.label}({count})
                    </button>
                  );
                })}
              </div>

              <div className="wb-section-label">
                变更单（{filteredOrders.length}/{orders!.length}）
              </div>

              {filteredOrders.map((order, i) => {
                const statusInfo = STATUS_MAP[order.status] ?? {
                  label: order.status,
                  tone: 'muted' as ChipTone,
                };
                const feasInfo = order.feasibility
                  ? FEASIBILITY_MAP[order.feasibility] ?? {
                      label: order.feasibility,
                      tone: 'muted' as ChipTone,
                    }
                  : null;
                return (
                  <div
                    key={order.id}
                    className={`wb-co-card wb-co-card--${order.status}`}
                    data-testid={`wb-changeorders-item--${i}`}
                  >
                    <div className="wb-co-card__head">
                      <div className="wb-co-card__title">{order.title}</div>
                      <span
                        className={`wb-status-chip wb-status-chip--${statusInfo.tone}`}
                        data-testid={`wb-changeorders-status--${i}`}
                      >
                        {statusInfo.label}
                      </span>
                    </div>
                    <div className="wb-co-card__desc">{order.description}</div>

                    {/* 影响评估 */}
                    <div className="wb-co-card__impact">
                      {order.cost_impact !== 0 && (
                        <span className="wb-co-card__impact--cost">
                          💰 费用影响 ¥{order.cost_impact.toLocaleString()}
                        </span>
                      )}
                      {order.schedule_impact_days !== 0 && (
                        <span className="wb-co-card__impact--schedule">
                          📅 工期影响 {order.schedule_impact_days} 天
                        </span>
                      )}
                      {feasInfo && (
                        <span
                          className={`wb-status-chip wb-status-chip--${feasInfo.tone}`}
                        >
                          {feasInfo.label}
                        </span>
                      )}
                      {order.submitted_at && (
                        <span>提交于 {formatDate(order.submitted_at)}</span>
                      )}
                    </div>

                    {order.feasibility_note && (
                      <div
                        style={{
                          fontSize: 'var(--font-size-xs)',
                          color: 'var(--text-secondary)',
                          marginTop: 6,
                        }}
                      >
                        审核意见：{order.feasibility_note}
                      </div>
                    )}

                    {/* 变更项明细 */}
                    {order.items && order.items.length > 0 && (
                      <div className="wb-co-items">
                        {order.items.map((item, li) => (
                          <div className="wb-co-item" key={item.id ?? li}>
                            <span>
                              [{ACTION_MAP[item.action] ?? item.action}] {item.name}
                              {item.quantity > 0 && ` × ${item.quantity}`}
                            </span>
                            {item.amount > 0 && (
                              <span>¥{item.amount.toLocaleString()}</span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
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
