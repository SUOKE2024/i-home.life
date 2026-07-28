/**
 * ProcurementPage — 对齐 flutter_app/lib/pages/procurement_enhanced_page.dart
 *
 * 结构：Scaffold > AppBar(采购管理) > [项目选择器] > 订单卡片列表（含明细 + 物流状态）
 * API：GET /api/procurement/orders/{projectId}（对齐 app/api/procurement.py）
 *
 * 后端订单字段（app/schemas/procurement.py:OrderResponse）：
 *   id / project_id / supplier_id / total_amount / status / expected_delivery /
 *   note / lines[] / delivery_status / tracking_number / carrier /
 *   estimated_delivery_date / actual_delivery_date / delivery_address /
 *   assembly_required / assembly_difficulty / delivery_notes / created_at / updated_at
 *
 * 后端订单状态：draft | pending | confirmed | shipped | delivered | cancelled
 * 后端物流状态 delivery_status：pending | shipping | in_transit | delivered | delayed | cancelled
 *
 * OrderLine 字段：material_id / quantity / unit_price / total_price / note
 * （注意：后端 OrderLineResponse 无 product_name/unit，仅 material_id 引用物料）
 *
 * Flutter 端有 4 tabs（比价/托管/物流/样品），批次 5 实现"订单 + 物流"主视图。
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { ProcurementOrder, Project } from '../types/domain';

type ChipTone = 'muted' | 'info' | 'success' | 'warning' | 'danger' | 'accent';

// ── 订单状态 → 文案/颜色（对齐 procurement_enhanced_page.dart + 后端约束）──
const ORDER_STATUS_MAP: Record<string, { label: string; tone: ChipTone }> = {
  draft: { label: '草稿', tone: 'muted' },
  pending: { label: '待确认', tone: 'warning' },
  confirmed: { label: '已确认', tone: 'info' },
  shipped: { label: '已发货', tone: 'info' },
  delivered: { label: '已送达', tone: 'success' },
  cancelled: { label: '已取消', tone: 'danger' },
};

// ── 物流状态 → 文案/颜色（对齐 A5 采购交付透明度）──
const DELIVERY_STATUS_MAP: Record<string, { label: string; tone: ChipTone }> = {
  pending: { label: '待发货', tone: 'muted' },
  shipping: { label: '发货中', tone: 'info' },
  in_transit: { label: '运输中', tone: 'info' },
  delivered: { label: '已送达', tone: 'success' },
  delayed: { label: '延期', tone: 'danger' },
  cancelled: { label: '已取消', tone: 'danger' },
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

function shortId(id: string): string {
  return id.length > 8 ? id.slice(0, 8) : id;
}

export default function ProcurementPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');

  // 加载项目列表
  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  // 加载采购订单
  const { data: orders, loading, error, reload } = useAsync<ProcurementOrder[] | null>(
    async () => {
      if (!selectedProjectId) return null;
      const r = await apiClient.getProcurementOrders<ProcurementOrder[]>(selectedProjectId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载失败');
      return r.data;
    },
    [selectedProjectId],
  );

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-procurement-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">🛒 采购管理</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          <div className="wb-project-picker">
            <select
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              aria-label="选择项目"
              data-testid="wb-procurement-project-select"
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
            <div className="wb-state" data-testid="wb-procurement-no-project">
              <div className="wb-state__icon">📋</div>
              <div>请先选择项目</div>
            </div>
          )}

          {selectedProjectId && loading && (
            <div className="wb-state" data-testid="wb-procurement-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载采购订单中…</div>
            </div>
          )}

          {selectedProjectId && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-procurement-error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>
                重试
              </button>
            </div>
          )}

          {selectedProjectId && !loading && !error && (orders?.length ?? 0) === 0 && (
            <div className="wb-state" data-testid="wb-procurement-empty">
              <div className="wb-state__icon">📦</div>
              <div>暂无采购订单</div>
              <div style={{ fontSize: 'var(--font-size-sm)' }}>
                可通过工作台与采购 Agent 对话生成物料清单并下单
              </div>
            </div>
          )}

          {selectedProjectId && !loading && !error && (orders?.length ?? 0) > 0 && (
            <div data-testid="wb-procurement-content">
              <div className="wb-section-label">采购订单（{orders!.length}）</div>
              {orders!.map((order, i) => {
                const statusInfo = ORDER_STATUS_MAP[order.status] ?? {
                  label: order.status,
                  tone: 'muted' as ChipTone,
                };
                const deliveryInfo = order.delivery_status
                  ? DELIVERY_STATUS_MAP[order.delivery_status] ?? {
                      label: order.delivery_status,
                      tone: 'muted' as ChipTone,
                    }
                  : null;
                return (
                  <div
                    key={order.id}
                    className="wb-order-card"
                    data-testid={`wb-procurement-order--${i}`}
                  >
                    <div className="wb-order-card__head">
                      <div>
                        <div className="wb-order-card__id">订单 #{shortId(order.id)}</div>
                        <span
                          className={`wb-status-chip wb-status-chip--${statusInfo.tone}`}
                          style={{ marginTop: 4 }}
                          data-testid={`wb-procurement-order-status--${i}`}
                        >
                          {statusInfo.label}
                        </span>
                      </div>
                      <div className="wb-order-card__amount">
                        ¥{(order.total_amount ?? 0).toLocaleString()}
                      </div>
                    </div>

                    {/* 订单明细 */}
                    {order.lines && order.lines.length > 0 && (
                      <div className="wb-order-card__lines">
                        {order.lines.map((line, li) => (
                          <div className="wb-order-line" key={line.id ?? li}>
                            <span>
                              物料 #{shortId(line.material_id)} × {line.quantity}
                            </span>
                            <span>¥{(line.total_price ?? 0).toLocaleString()}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* 物流信息（A5 采购交付透明度）*/}
                    {(deliveryInfo || order.tracking_number || order.carrier) && (
                      <div
                        className="wb-order-card__logistics"
                        data-testid={`wb-procurement-order-logistics--${i}`}
                      >
                        {deliveryInfo && (
                          <div>
                            🚚 物流：
                            <span
                              className={`wb-status-chip wb-status-chip--${deliveryInfo.tone}`}
                              style={{ marginLeft: 4 }}
                            >
                              {deliveryInfo.label}
                            </span>
                          </div>
                        )}
                        {order.carrier && <div>承运：{order.carrier}</div>}
                        {order.tracking_number && (
                          <div>运单号：{order.tracking_number}</div>
                        )}
                        {order.estimated_delivery_date && (
                          <div>预计送达：{formatDate(order.estimated_delivery_date)}</div>
                        )}
                        {order.actual_delivery_date && (
                          <div>实际送达：{formatDate(order.actual_delivery_date)}</div>
                        )}
                        {order.delivery_address && (
                          <div>送达地址：{order.delivery_address}</div>
                        )}
                        {order.assembly_required && (
                          <div style={{ color: 'var(--warning)' }}>
                            🔧 需安装
                            {order.assembly_difficulty
                              ? `（${order.assembly_difficulty}）`
                              : ''}
                          </div>
                        )}
                      </div>
                    )}

                    {order.note && (
                      <div
                        style={{
                          fontSize: 'var(--font-size-xs)',
                          color: 'var(--text-muted)',
                          marginTop: 6,
                        }}
                      >
                        备注：{order.note}
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
