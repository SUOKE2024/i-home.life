/**
 * A2UICard — Agent-to-UI 协议卡片渲染（对齐 app/services/a2ui_schema.py + web/assets/js/a2ui-renderer.js）
 *
 * 后端 /chat/stream 的 done 事件携带 a2ui_cards（8 类），Flutter 有 a2ui_renderer.dart，
 * 本组件补齐 Web 控制台渲染缺口（v1.2.3 A2UI 协议，此前解析后丢弃）。
 *
 * 卡片 JSON 结构（a2ui_schema.py make_card）：
 *   { type, version, id, timestamp, data }
 * type ∈ design_plan | budget_breakdown | construction_progress | procurement_order |
 *        qa_report | settlement_summary | material_card | alert_card
 */

interface A2UICardProps {
  card: {
    type?: string;
    data?: Record<string, any>;
  };
  onAction?: (action: string, payload?: unknown) => void;
}

const fmtMoney = (v: unknown): string =>
  `¥${(Number(v) || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const fmtPct = (v: unknown): string => `${(Number(v) || 0) * 100}%`;

const fmtIntPct = (v: unknown): string => `${Math.round((Number(v) || 0) * 100)}%`;

const safeList = (v: unknown): any[] => (Array.isArray(v) ? v : []);

const badgeFor = (status: unknown): string => {
  switch (String(status ?? '').toLowerCase()) {
    case 'paid': case 'completed': case 'pass': case 'delivered': case 'in_stock':
    case 'not_started': return '✅ ';
    case 'in_progress': case 'shipped': case 'ordered': case 'low_stock': case 'delayed':
    case 'pending': return '⏳ ';
    case 'overdue': case 'fail': case 'cancelled': case 'disputed': case 'out_of_stock':
    case 'failed': return '⚠ ';
    default: return '· ';
  }
};

export default function A2UICard({ card, onAction }: A2UICardProps) {
  const type = card?.type ?? 'unknown';
  const data = (card?.data ?? {}) as Record<string, any>;

  return (
    <div className="a2ui-card" role="article" data-testid={`a2ui-card--${type}`}>
      {renderBody(type, data, onAction)}
    </div>
  );
}

function renderBody(
  type: string,
  data: Record<string, any>,
  onAction?: (action: string, payload?: unknown) => void,
) {
  switch (type) {
    case 'design_plan':
      return <DesignPlanCard data={data} onAction={onAction} />;
    case 'budget_breakdown':
      return <BudgetBreakdownCard data={data} onAction={onAction} />;
    case 'construction_progress':
      return <ConstructionProgressCard data={data} onAction={onAction} />;
    case 'procurement_order':
      return <ProcurementOrderCard data={data} onAction={onAction} />;
    case 'qa_report':
      return <QAReportCard data={data} onAction={onAction} />;
    case 'settlement_summary':
      return <SettlementSummaryCard data={data} onAction={onAction} />;
    case 'material_card':
      return <MaterialCard data={data} onAction={onAction} />;
    case 'alert_card':
      return <AlertCard data={data} />;
    default:
      return (
        <div className="a2ui-unknown">
          <div className="a2ui-card-title">未知卡片类型</div>
          <pre className="a2ui-unknown-json">{JSON.stringify(data, null, 2)}</pre>
        </div>
      );
  }
}

function CardShell({
  title,
  subtitle,
  accentClass,
  children,
  actions,
  onAction,
  payload,
}: {
  title: string;
  subtitle?: string | null;
  accentClass: string;
  children: React.ReactNode;
  actions?: Array<{ label: string; action: string }>;
  onAction?: (action: string, payload?: unknown) => void;
  payload?: unknown;
}) {
  return (
    <div className={`a2ui-card-inner ${accentClass}`}>
      <div className="a2ui-card-header">
        <div className="a2ui-accent-bar" />
        <div className="a2ui-card-header-text">
          <div className="a2ui-card-title">{title}</div>
          {subtitle && <div className="a2ui-card-subtitle">{subtitle}</div>}
        </div>
      </div>
      <div className="a2ui-card-body">{children}</div>
      {actions && actions.length > 0 && onAction && (
        <div className="a2ui-card-actions">
          {actions.map((a) => (
            <button
              key={a.action}
              type="button"
              className="a2ui-btn a2ui-btn-primary"
              onClick={() => onAction(a.action, payload)}
            >
              {a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function TagChip({ label, cls }: { label: string; cls: string }) {
  return <span className={`a2ui-tag ${cls}`}>{label}</span>;
}

function DesignPlanCard({ data, onAction }: { data: Record<string, any>; onAction?: A2UICardProps['onAction'] }) {
  const rooms = safeList(data.rooms);
  return (
    <CardShell
      title={data.project_name ?? '设计方案'}
      subtitle={`${data.floor_layout ?? ''} · ${(Number(data.total_area) || 0).toFixed(1)}㎡`}
      accentClass="a2ui-accent-design"
      actions={data.preview_3d_url ? [{ label: '查看3D', action: 'view_3d' }] : undefined}
      onAction={onAction}
      payload={{ preview_3d_url: data.preview_3d_url }}
    >
      {(data.style || data.estimated_timeline) && (
        <div className="a2ui-tags-row">
          {data.style && <TagChip label={data.style} cls="a2ui-tag-design" />}
          {data.estimated_timeline && <TagChip label={`工期 ${data.estimated_timeline}`} cls="a2ui-tag-design" />}
        </div>
      )}
      {rooms.length > 0 && (
        <>
          <div className="a2ui-section-title">房间分布</div>
          <div className="a2ui-room-grid">
            {rooms.map((r: any, i: number) => (
              <div className="a2ui-room-tile" key={i}>
                <div className="a2ui-room-name">{r.name}</div>
                <div className="a2ui-room-area">{(Number(r.area) || 0).toFixed(1)}㎡</div>
                {r.orientation && <div className="a2ui-room-orientation">{r.orientation}</div>}
              </div>
            ))}
          </div>
        </>
      )}
    </CardShell>
  );
}

function BudgetBreakdownCard({ data, onAction }: { data: Record<string, any>; onAction?: A2UICardProps['onAction'] }) {
  const items = safeList(data.items);
  const paymentStages = safeList(data.payment_stages);
  const subtotal = Number(data.subtotal) || 0;
  const taxAmount = Number(data.tax_amount) || 0;
  const total = Number(data.total) || 0;
  return (
    <CardShell
      title={data.project_name ?? '预算明细'}
      subtitle={`合计 ${fmtMoney(total)}`}
      accentClass="a2ui-accent-budget"
      actions={[{ label: '查看详情', action: 'view_budget_detail' }]}
      onAction={onAction}
      payload={data}
    >
      <div className="a2ui-summary-line">
        <span className="a2ui-summary-label">小计</span>
        <span className="a2ui-summary-value">{fmtMoney(subtotal)}</span>
      </div>
      {taxAmount > 0 && (
        <div className="a2ui-summary-line">
          <span className="a2ui-summary-label">{`税费（${((taxAmount / Math.max(1, subtotal)) * 100).toFixed(1)}%）`}</span>
          <span className="a2ui-summary-value">{fmtMoney(taxAmount)}</span>
        </div>
      )}
      <hr className="a2ui-divider" />
      <div className="a2ui-summary-line a2ui-summary-total">
        <span className="a2ui-summary-label">合计</span>
        <span className="a2ui-summary-value">{fmtMoney(total)}</span>
      </div>
      {items.length > 0 && (
        <>
          <div className="a2ui-section-title">费用明细</div>
          <div className="a2ui-budget-table">
            {items.slice(0, 5).map((item: any, i: number) => (
              <div className="a2ui-budget-row" key={i}>
                <div className="a2ui-budget-name">
                  {item.category && <TagChip label={item.category} cls="a2ui-tag-category" />}
                  <span className="a2ui-budget-item-name">{item.name}</span>
                </div>
                <span className="a2ui-budget-qty">
                  {Number(item.quantity) > 0 ? `${Number(item.quantity).toFixed(0)}${item.unit ?? ''}` : ''}
                </span>
                <span className="a2ui-budget-amount">{fmtMoney(item.amount)}</span>
              </div>
            ))}
          </div>
          {items.length > 5 && <div className="a2ui-more-hint">… 共 {items.length} 项</div>}
        </>
      )}
      {paymentStages.length > 0 && (
        <>
          <div className="a2ui-section-title">付款计划</div>
          {paymentStages.map((st: any, i: number) => (
            <div className="a2ui-payment-stage-row" key={i}>
              <span className={`a2ui-stage-dot ${String(st.status ?? '').toLowerCase() === 'paid' ? 'a2ui-stage-dot-paid' : ''}`} />
              <span className="a2ui-stage-name">{st.stage}</span>
              <span className="a2ui-stage-ratio">{Math.round((Number(st.ratio) || 0) * 100)}%</span>
              <span className="a2ui-stage-amount">{fmtMoney(st.amount)}</span>
              <span className="a2ui-stage-status">{badgeFor(st.status)}{st.status}</span>
            </div>
          ))}
        </>
      )}
      {Number(data.warranty_months) > 0 && (
        <div className="a2ui-warranty-info">
          🛡️ 质保 {data.warranty_months} 个月{data.warranty_scope ? ` · ${data.warranty_scope}` : ''}
        </div>
      )}
    </CardShell>
  );
}

function ConstructionProgressCard({ data, onAction }: { data: Record<string, any>; onAction?: A2UICardProps['onAction'] }) {
  const phases = safeList(data.phases);
  const crewInfo = (data.crew_info ?? {}) as Record<string, any>;
  const nextMs = (data.next_milestone ?? {}) as Record<string, any>;
  const overall = Number(data.overall_progress) || 0;
  return (
    <CardShell
      title={data.project_name ?? '施工进度'}
      subtitle={`总体进度 ${fmtPct(overall)}`}
      accentClass="a2ui-accent-construction"
      actions={[{ label: '查看详情', action: 'view_progress_detail' }]}
      onAction={onAction}
      payload={data}
    >
      <div className="a2ui-progress-section">
        <div className="a2ui-progress-header">
          <span className="a2ui-progress-label">总体进度</span>
          <span className="a2ui-progress-pct">{fmtPct(overall)}</span>
        </div>
        <div className="a2ui-progress-bar" role="progressbar" aria-valuenow={Math.round(overall * 100)} aria-valuemin={0} aria-valuemax={100}>
          <div className="a2ui-progress-fill" style={{ width: fmtPct(overall) }} />
        </div>
      </div>
      {(crewInfo.leader || crewInfo.team_size) && (
        <div className="a2ui-crew-info">
          {crewInfo.leader && <span className="a2ui-crew-leader">👷 班组长: {crewInfo.leader}</span>}
          {Number(crewInfo.team_size) > 0 && <span className="a2ui-crew-size">团队 {crewInfo.team_size} 人</span>}
          {safeList(crewInfo.specialties).length > 0 && (
            <div className="a2ui-tags-row">
              {safeList(crewInfo.specialties).map((s: string, i: number) => (
                <TagChip key={i} label={s} cls="a2ui-tag-construction" />
              ))}
            </div>
          )}
        </div>
      )}
      {nextMs.name && (
        <div className="a2ui-milestone">
          <span className="a2ui-milestone-icon">🚩</span> 下一里程碑: <strong>{nextMs.name}</strong>
          {nextMs.date && <div className="a2ui-milestone-date">{nextMs.date}</div>}
        </div>
      )}
      {phases.length > 0 && (
        <>
          <div className="a2ui-section-title">阶段进度</div>
          {phases.map((phase: any, i: number) => {
            const prog = Number(phase.progress) || 0;
            const icon = prog >= 1 ? '✅' : prog > 0 ? '⏳' : '○';
            return (
              <div className="a2ui-phase-row" key={i}>
                <span className="a2ui-phase-icon">{icon}</span>
                <span className="a2ui-phase-name">{phase.name}</span>
                <span className="a2ui-phase-pct">{fmtIntPct(prog)}</span>
                <span className="a2ui-phase-status">{badgeFor(phase.status)}{phase.status}</span>
              </div>
            );
          })}
        </>
      )}
    </CardShell>
  );
}

function ProcurementOrderCard({ data, onAction }: { data: Record<string, any>; onAction?: A2UICardProps['onAction'] }) {
  const items = safeList(data.items);
  const supplier = (data.supplier ?? {}) as Record<string, any>;
  return (
    <CardShell
      title="采购订单"
      subtitle={data.order_id ? `#${data.order_id}` : null}
      accentClass="a2ui-accent-procurement"
      actions={[{ label: '查看详情', action: 'view_order_detail' }]}
      onAction={onAction}
      payload={data}
    >
      {supplier.name && (
        <div className="a2ui-supplier-row">
          <span className="a2ui-supplier-name">🏪 {supplier.name}</span>
          <span className="a2ui-supplier-status">{badgeFor(data.status)}{data.status}</span>
        </div>
      )}
      {items.length > 0 && (
        <>
          {items.map((item: any, i: number) => (
            <div className="a2ui-order-item-row" key={i}>
              <div className="a2ui-order-item-info">
                <div className="a2ui-order-item-name">{item.name}</div>
                {item.specs && <div className="a2ui-order-item-specs">{item.specs}</div>}
              </div>
              <span className="a2ui-order-item-qty">×{Number(item.quantity).toFixed(0)} {item.unit ?? ''}</span>
            </div>
          ))}
        </>
      )}
      <hr className="a2ui-divider" />
      <div className="a2ui-order-bottom">
        <div className="a2ui-order-total">
          <div className="a2ui-order-total-label">订单总额</div>
          <div className="a2ui-order-total-amount">{fmtMoney(data.total_amount)}</div>
        </div>
        {data.delivery_date && (
          <div className="a2ui-order-date">
            <div className="a2ui-order-date-label">预计交货</div>
            <div className="a2ui-order-date-value">{data.delivery_date}</div>
          </div>
        )}
      </div>
    </CardShell>
  );
}

function QAReportCard({ data, onAction }: { data: Record<string, any>; onAction?: A2UICardProps['onAction'] }) {
  const checkpoints = safeList(data.checkpoints);
  const isPassed = String(data.overall_result ?? '').toLowerCase() === 'pass';
  const passedCount = Number(data.passed_count) || 0;
  const failedCount = Number(data.failed_count) || 0;
  const totalCount = passedCount + failedCount;
  const passRate = totalCount > 0 ? Math.round((passedCount / totalCount) * 100) : 0;
  return (
    <CardShell
      title={data.project_name ?? '质检报告'}
      subtitle={`${data.inspector ?? ''}${data.inspector && data.inspection_date ? ' · ' : ''}${data.inspection_date ?? ''}`}
      accentClass="a2ui-accent-quality"
      actions={[{ label: '查看详情', action: 'view_qa_detail' }]}
      onAction={onAction}
      payload={data}
    >
      <div className={`a2ui-qa-result ${isPassed ? 'a2ui-qa-passed' : 'a2ui-qa-failed'}`}>
        <span className="a2ui-qa-result-icon">{isPassed ? '✅' : '❌'}</span>
        <div className="a2ui-qa-result-text">
          <div className="a2ui-qa-result-title">{isPassed ? '验收通过' : '需整改'}</div>
          <div className="a2ui-qa-result-stats">通过 {passedCount} / 不通过 {failedCount}</div>
        </div>
        <span className="a2ui-qa-pct">{passRate}%</span>
      </div>
      {!isPassed && data.fix_deadline && (
        <div className="a2ui-qa-deadline">⏰ 整改截止: <strong>{data.fix_deadline}</strong></div>
      )}
      {checkpoints.length > 0 && (
        <>
          <div className="a2ui-section-title">检查点</div>
          {checkpoints.map((cp: any, i: number) => {
            const result = String(cp.result ?? '').toLowerCase();
            const icon = result === 'pass' ? '✅' : result === 'fail' ? '❌' : '❓';
            return (
              <div className="a2ui-checkpoint-row" key={i}>
                <span className="a2ui-checkpoint-icon">{icon}</span>
                <div className="a2ui-checkpoint-info">
                  <div className="a2ui-checkpoint-name">{cp.name}</div>
                  {(cp.standard || cp.actual) && (
                    <div className="a2ui-checkpoint-detail">
                      标准: {cp.standard ?? ''}{cp.actual ? ` · 实测: ${cp.actual}` : ''}
                    </div>
                  )}
                </div>
                <span className="a2ui-checkpoint-status">{badgeFor(cp.result)}{cp.result}</span>
              </div>
            );
          })}
        </>
      )}
    </CardShell>
  );
}

function SettlementSummaryCard({ data, onAction }: { data: Record<string, any>; onAction?: A2UICardProps['onAction'] }) {
  const paymentHistory = safeList(data.payment_history);
  const nextPayment = (data.next_payment ?? {}) as Record<string, any>;
  const moneyBox = (label: string, amount: unknown, cls: string) => (
    <div className={`a2ui-money-box ${cls}`}>
      <div className="a2ui-money-label">{label}</div>
      <div className="a2ui-money-value">{`¥${Math.round(Number(amount) || 0)}`}</div>
    </div>
  );
  return (
    <CardShell
      title={data.project_name ?? '结算汇总'}
      accentClass="a2ui-accent-settlement"
      actions={[{ label: '查看详情', action: 'view_settlement_detail' }]}
      onAction={onAction}
      payload={data}
    >
      <div className="a2ui-money-grid">
        {moneyBox('合同总额', data.total_amount, 'a2ui-money-total')}
        {moneyBox('已付金额', data.paid_amount, 'a2ui-money-paid')}
        {moneyBox('待付余额', data.balance_amount, 'a2ui-money-balance')}
      </div>
      {nextPayment.amount != null && (
        <div className="a2ui-next-payment">
          <span className="a2ui-next-pay-icon">💳</span>
          下一笔付款: <strong>{fmtMoney(nextPayment.amount)}</strong>
          {nextPayment.due_date && <div className="a2ui-next-pay-date">到期日: {nextPayment.due_date}</div>}
          {nextPayment.condition && <div className="a2ui-next-pay-condition">条件: {nextPayment.condition}</div>}
        </div>
      )}
      {paymentHistory.length > 0 && (
        <>
          <div className="a2ui-section-title">付款历史</div>
          {paymentHistory.slice(0, 5).map((p: any, i: number) => (
            <div className="a2ui-payment-history-row" key={i}>
              <span className="a2ui-payment-date">{p.date}</span>
              <span className="a2ui-payment-method">{p.method}</span>
              <span className="a2ui-payment-amount">{fmtMoney(p.amount)}</span>
              <span className="a2ui-payment-status">{badgeFor(p.status)}{p.status}</span>
            </div>
          ))}
        </>
      )}
    </CardShell>
  );
}

function MaterialCard({ data, onAction }: { data: Record<string, any>; onAction?: A2UICardProps['onAction'] }) {
  const certifications = safeList(data.certifications);
  const infoRow = (label: string, value: unknown) => (
    <div className="a2ui-material-info-row">
      <span className="a2ui-material-info-label">{label}</span>
      <span className="a2ui-material-info-value">{String(value)}</span>
    </div>
  );
  return (
    <CardShell
      title={data.name ?? '材料详情'}
      subtitle={data.category ?? null}
      accentClass="a2ui-accent-master"
      actions={[{ label: '查看详情', action: 'view_material_detail' }]}
      onAction={onAction}
      payload={data}
    >
      <div className="a2ui-material-price-row">
        <span className="a2ui-material-price">{fmtMoney(data.unit_price)}</span>
        <span className="a2ui-material-unit">/{data.unit ?? '㎡'}</span>
        <span className="a2ui-material-stock">{badgeFor(data.stock_status)}{data.stock_status}</span>
      </div>
      {data.specs && infoRow('规格', data.specs)}
      {data.eco_level && infoRow('环保等级', data.eco_level)}
      {data.supplier && infoRow('供应商', data.supplier)}
      {certifications.length > 0 && (
        <div className="a2ui-tags-row">
          {certifications.map((c: string, i: number) => (
            <TagChip key={i} label={c} cls="a2ui-tag-cert" />
          ))}
        </div>
      )}
      {data.description && <div className="a2ui-material-desc">{data.description}</div>}
    </CardShell>
  );
}

const SEVERITY_LABEL: Record<string, string> = {
  critical: '严重', error: '错误', warning: '警告', info: '信息',
};

function AlertCard({ data }: { data: Record<string, any> }) {
  const severity = String(data.severity ?? 'info').toLowerCase();
  const actions = safeList(data.actions);
  const label = SEVERITY_LABEL[severity] ?? '信息';
  return (
    <div className={`a2ui-alert a2ui-alert-${severity}`} role="alert" data-testid={`a2ui-alert--${severity}`}>
      <div className="a2ui-alert-header">
        <span className="a2ui-alert-badge">{label}</span>
        {data.source_agent && <span className="a2ui-alert-source">{data.source_agent}</span>}
      </div>
      {data.title && <div className="a2ui-alert-title">{data.title}</div>}
      {data.message && <div className="a2ui-alert-message">{data.message}</div>}
      {actions.length > 0 && (
        <div className="a2ui-alert-actions">
          {actions.map((a: any, i: number) =>
            a.label ? (
              <button key={i} type="button" className={`a2ui-btn a2ui-btn-outline a2ui-alert-btn-${severity}`}>
                {a.label}
              </button>
            ) : null,
          )}
        </div>
      )}
    </div>
  );
}
