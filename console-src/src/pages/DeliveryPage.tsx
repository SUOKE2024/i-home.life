/**
 * DeliveryPage — B2B 装企交付工作台（v1.4.x，借鉴"卖结果不卖功能"交付式产品）
 *
 * 面向装企/工作室：一次创建拿到「设计方案 + 报价 + 施工计划」整包交付，
 * 并支持交付单列表、详情查看与状态流转
 * （draft → quoted → accepted → in_construction → completed / cancelled）。
 *
 * API（对齐 app/api/b2b_delivery.py）：
 *   POST /api/b2b/delivery              创建交付单（落库）
 *   GET  /api/b2b/delivery              我的交付单列表
 *   GET  /api/b2b/delivery/{id}         交付单详情（整包快照）
 *   PUT  /api/b2b/delivery/{id}/status  状态流转
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type {
  B2BDeliveryStatus,
  DeliveryListItem,
  DeliveryOrderDetail,
  Project,
} from '../types/domain';

// 状态展示映射（中文标签 + 样式语义）
const STATUS_META: Record<B2BDeliveryStatus, { label: string; emoji: string }> = {
  generating: { label: '生成中', emoji: '⏳' },
  draft: { label: '草稿', emoji: '📝' },
  quoted: { label: '已报价', emoji: '💬' },
  accepted: { label: '已签约', emoji: '🤝' },
  in_construction: { label: '施工中', emoji: '🔨' },
  completed: { label: '已完成', emoji: '✅' },
  cancelled: { label: '已取消', emoji: '🚫' },
};

// 状态流转操作（对齐后端 _ALLOWED_TRANSITIONS）
const NEXT_ACTIONS: Record<B2BDeliveryStatus, { to: B2BDeliveryStatus; label: string }[]> = {
  generating: [],
  draft: [
    { to: 'quoted', label: '确认报价' },
    { to: 'cancelled', label: '取消' },
  ],
  quoted: [
    { to: 'accepted', label: '签约' },
    { to: 'cancelled', label: '取消' },
  ],
  accepted: [{ to: 'in_construction', label: '开工' }],
  in_construction: [{ to: 'completed', label: '完工' }],
  completed: [],
  cancelled: [],
};

const STYLES = ['modern', 'nordic', 'japanese', 'luxury', 'chinese'];
const STYLE_LABELS: Record<string, string> = {
  modern: '现代简约', nordic: '北欧', japanese: '日式侘寂',
  luxury: '轻奢', chinese: '新中式',
};

export default function DeliveryPage() {
  const navigate = useNavigate();

  // 创建表单状态
  const [form, setForm] = useState({
    name: '整装交付',
    area: '100',
    style: 'modern',
    budget: '200000',
    requirements: '',
    rooms: '客厅,卧室,厨房,卫生间',
    projectId: '',       // 关联真实项目（报价走项目真实预算）
    asyncMode: false,    // 异步生成：立即返回，后台填充
  });
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // 项目列表（供关联真实项目）
  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  // 我的交付单列表
  const { data: deliveries, loading, error, reload } = useAsync<DeliveryListItem[]>(async () => {
    const r = await apiClient.listDeliveries<DeliveryListItem[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  // 展开的交付单详情
  const { data: detail, loading: detailLoading, reload: reloadDetail } = useAsync<DeliveryOrderDetail | null>(
    async () => {
      if (!expandedId) return null;
      const r = await apiClient.getDelivery<DeliveryOrderDetail>(expandedId);
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载详情失败');
      return r.data;
    },
    [expandedId],
  );

  // 异步生成时轮询详情直至非 generating
  async function pollUntilReady(
    fetchDetail: () => Promise<DeliveryOrderDetail | null>,
  ) {
    for (let i = 0; i < 30; i += 1) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      const d = await fetchDetail();
      if (d && d.status !== 'generating') return d;
    }
    return null;
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      const area = parseFloat(form.area);
      if (!area || area <= 0) throw new Error('请填写有效面积');
      const budget = parseFloat(form.budget) || 0;
      const r = await apiClient.createDelivery({
        name: form.name,
        area,
        style: form.style,
        budget,
        requirements: form.requirements,
        rooms: form.rooms,
        projectId: form.projectId || null,
        asyncMode: form.asyncMode,
      });
      if (!r.isSuccess || !r.data) throw new Error(r.error ?? '创建失败');
      // 创建成功后刷新列表并展开新单；异步模式轮询至生成完成
      const created = r.data;
      await reload();
      setExpandedId(created.delivery_order_id);
      if (form.asyncMode) {
        await pollUntilReady(async () => {
          const g = await apiClient.getDelivery<DeliveryOrderDetail>(created.delivery_order_id);
          return g.isSuccess && g.data ? g.data : null;
        });
        await reloadDetail();
      }
      setForm({ ...form, requirements: '' });
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleTransition(orderId: string, status: B2BDeliveryStatus) {
    const r = await apiClient.updateDeliveryStatus(orderId, status);
    if (!r.isSuccess) {
      setFormError(r.error ?? '状态流转失败');
      return;
    }
    await reload();
    if (expandedId === orderId) await reloadDetail();
  }

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-delivery-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">📦 B2B 装企交付</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {/* 创建交付单 */}
          <div className="wb-delivery-form" data-testid="wb-delivery-create">
            <div className="wb-delivery-form__title">生成整包交付（设计方案 + 报价 + 施工计划）</div>
            <form onSubmit={handleCreate}>
              <label className="wb-delivery-form__field">
                <span>交付名称</span>
                <input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  maxLength={200}
                />
              </label>
              <div className="wb-delivery-form__row">
                <label className="wb-delivery-form__field">
                  <span>面积（㎡）</span>
                  <input
                    type="number"
                    min={1}
                    value={form.area}
                    onChange={(e) => setForm({ ...form, area: e.target.value })}
                    data-testid="wb-delivery-area"
                  />
                </label>
                <label className="wb-delivery-form__field">
                  <span>风格</span>
                  <select
                    value={form.style}
                    onChange={(e) => setForm({ ...form, style: e.target.value })}
                  >
                    {STYLES.map((s) => (
                      <option key={s} value={s}>{STYLE_LABELS[s]}</option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="wb-delivery-form__field">
                <span>业主预算（元，0 为不限定）</span>
                <input
                  type="number"
                  min={0}
                  value={form.budget}
                  onChange={(e) => setForm({ ...form, budget: e.target.value })}
                />
              </label>
              <label className="wb-delivery-form__field">
                <span>房间（逗号分隔）</span>
                <input
                  value={form.rooms}
                  onChange={(e) => setForm({ ...form, rooms: e.target.value })}
                />
              </label>
              <label className="wb-delivery-form__field">
                <span>关联项目（可选，报价走项目真实预算）</span>
                <select
                  value={form.projectId}
                  onChange={(e) => setForm({ ...form, projectId: e.target.value })}
                >
                  <option value="">不关联（独立快照）</option>
                  {projects?.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </label>
              <label className="wb-delivery-form__field">
                <span>设计需求补充</span>
                <textarea
                  rows={3}
                  value={form.requirements}
                  onChange={(e) => setForm({ ...form, requirements: e.target.value })}
                  maxLength={2000}
                  placeholder="如：主卧带衣帽间、儿童房用环保板材"
                />
              </label>
              <label className="wb-delivery-form__field" style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <input
                  type="checkbox"
                  checked={form.asyncMode}
                  onChange={(e) => setForm({ ...form, asyncMode: e.target.checked })}
                  style={{ width: 'auto' }}
                />
                <span style={{ margin: 0 }}>异步生成（立即返回，后台填充整包）</span>
              </label>
              {formError && (
                <div className="wb-state wb-state--error" data-testid="wb-delivery-form-error">
                  <div className="wb-state__icon">⚠</div>
                  <div>{formError}</div>
                </div>
              )}
              <button
                className="wb-theme-option wb-theme-option--active"
                type="submit"
                disabled={submitting}
                data-testid="wb-delivery-submit"
                style={{ width: '100%', marginTop: 8 }}
              >
                {submitting ? '生成中…' : '🚀 生成交付包'}
              </button>
            </form>
          </div>

          {/* 我的交付单列表 */}
          <div style={{ fontSize: 'var(--font-size-sm)', color: 'var(--text-muted)', margin: '20px 0 10px' }}>
            我的交付单（{deliveries?.length ?? 0}）
          </div>

          {loading && (
            <div className="wb-state" data-testid="wb-delivery-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载交付单…</div>
            </div>
          )}

          {error && !loading && (
            <div className="wb-state wb-state--error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>
                重试
              </button>
            </div>
          )}

          {!loading && !error && (!deliveries || deliveries.length === 0) && (
            <div className="wb-state" data-testid="wb-delivery-empty">
              <div className="wb-state__icon">📦</div>
              <div>暂无交付单，先在上方生成一单</div>
            </div>
          )}

          {!loading && !error && deliveries && deliveries.length > 0 && (
            <div data-testid="wb-delivery-list">
              {deliveries.map((item) => {
                const meta = STATUS_META[item.status] ?? STATUS_META.draft;
                const isOpen = expandedId === item.delivery_order_id;
                return (
                  <div className="wb-delivery-card" key={item.delivery_order_id}>
                    <button
                      className="wb-delivery-card__head"
                      type="button"
                      onClick={() => setExpandedId(isOpen ? null : item.delivery_order_id)}
                      data-testid={`wb-delivery-item-${item.delivery_order_id}`}
                    >
                      <div>
                        <div className="wb-delivery-card__name">{item.name}</div>
                        <div className="wb-delivery-card__meta">
                          {item.area}㎡ · {STYLE_LABELS[item.style] ?? item.style} ·{' '}
                          {new Date(item.created_at).toLocaleString('zh-CN')}
                        </div>
                      </div>
                      <div className="wb-delivery-card__right">
                        <span className="wb-badge">{meta.emoji} {meta.label}</span>
                        <span className="wb-delivery-card__chevron">{isOpen ? '▾' : '▸'}</span>
                      </div>
                    </button>

                    {isOpen && (
                      <div className="wb-delivery-card__body" data-testid="wb-delivery-detail">
                        {detailLoading && <div className="wb-state"><div className="wb-state__icon">⏳</div><div>加载整包…</div></div>}
                        {!detailLoading && detail && (
                          <>
                            <div className="wb-delivery-summary">{detail.summary}</div>

                            {/* 报价：db=项目真实预算 / estimated=分档估算 */}
                            {detail.budget_estimate && (
                              <div className="wb-delivery-section">
                                <div className="wb-delivery-section__title">
                                  💰 报价（{detail.budget_estimate.source === 'db' ? '项目真实预算' : '分档估算'}）
                                </div>
                                {detail.budget_estimate.source === 'db' ? (
                                  <>
                                    <div className="wb-delivery-tier">
                                      总预算：<b>¥{detail.budget_estimate.total_estimated?.toLocaleString()}</b>
                                      （{detail.budget_estimate.line_count} 项明细）
                                    </div>
                                    {detail.budget_estimate.breakdown_by_category && (
                                      <div className="wb-delivery-tiers">
                                        {Object.entries(detail.budget_estimate.breakdown_by_category).map(([k, v]) => (
                                          <div className="wb-delivery-tier" key={k}>
                                            {k}：¥{v.toLocaleString()}
                                          </div>
                                        ))}
                                      </div>
                                    )}
                                  </>
                                ) : (
                                  <>
                                    {detail.budget_estimate.tiers && detail.budget_estimate.recommended_tier && (
                                      <div className="wb-delivery-tier">
                                        推荐：<b>{detail.budget_estimate.tiers[detail.budget_estimate.recommended_tier].label}</b> ¥
                                        {detail.budget_estimate.tiers[detail.budget_estimate.recommended_tier].total_estimate.toLocaleString()}（
                                        {detail.budget_estimate.tiers[detail.budget_estimate.recommended_tier].price_per_sqm}）
                                      </div>
                                    )}
                                    <div className="wb-delivery-tiers">
                                      {Object.entries(detail.budget_estimate.tiers ?? {}).map(([key, t]) => (
                                        <div
                                          key={key}
                                          className={key === detail.budget_estimate!.recommended_tier
                                            ? 'wb-delivery-tier wb-delivery-tier--rec'
                                            : 'wb-delivery-tier'}
                                        >
                                          {t.label}：¥{t.total_estimate.toLocaleString()}
                                        </div>
                                      ))}
                                    </div>
                                  </>
                                )}
                              </div>
                            )}

                            {/* 施工计划 */}
                            {detail.construction_plan && (
                              <div className="wb-delivery-section">
                                <div className="wb-delivery-section__title">
                                  🔨 施工计划（{detail.construction_plan.source}）
                                </div>
                                <div className="wb-delivery-tier">
                                  总工期 <b>{detail.construction_plan.total_days} 天</b>
                                  （含 {detail.construction_plan.buffer_days} 天缓冲，≥10%）
                                </div>
                                <div className="wb-delivery-phases">
                                  {detail.construction_plan.phases.map((p) => (
                                    <div className="wb-delivery-phase" key={p.phase_code}>
                                      <span>{p.name}</span>
                                      <span>{p.days} 天</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* 设计方案 */}
                            {detail.proposals && detail.proposals.length > 0 && (
                              <div className="wb-delivery-section">
                                <div className="wb-delivery-section__title">📐 设计备选（{detail.proposals.length} 套）</div>
                                {detail.proposals.map((p) => (
                                  <div className="wb-delivery-proposal" key={p.proposal_id}>
                                    <div className="wb-delivery-proposal__head">
                                      <b>方案{p.proposal_id}</b> · {p.title} · ¥{p.budget_cny.toLocaleString()}
                                    </div>
                                    {p.highlights.length > 0 && (
                                      <div className="wb-delivery-proposal__hl">{p.highlights.join(' · ')}</div>
                                    )}
                                  </div>
                                ))}
                              </div>
                            )}

                            {/* 状态流转 */}
                            {NEXT_ACTIONS[detail.status]?.length > 0 && (
                              <div className="wb-delivery-actions">
                                {NEXT_ACTIONS[detail.status].map((a) => (
                                  <button
                                    key={a.to}
                                    className="wb-theme-option wb-theme-option--active"
                                    type="button"
                                    onClick={() => handleTransition(detail.delivery_order_id, a.to)}
                                    data-testid={`wb-delivery-action-${a.to}`}
                                  >
                                    {a.label}
                                  </button>
                                ))}
                              </div>
                            )}
                          </>
                        )}
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
