/**
 * MessageCard — 对齐 message-renderers.js 的卡片 render 方法
 *
 * 按 cardType 分发到具体卡片子组件。
 * 批次 2 实现 text/settlement/quote/bom/camera-scan 5 类，其余返回 fallback 提示。
 *
 * 注意：text 类型由 MessageBubble 处理，不进入 MessageCard；
 * 此组件仅处理 cardType !== 'text' 的卡片消息。
 */

import { getAgentInfo } from '../../services/agent-router';
import type { ChatMessage } from '../../types/chat';

export interface MessageCardProps {
  message: ChatMessage;
  onAction?: (action: string, payload?: unknown) => void;
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

export default function MessageCard({ message, onAction }: MessageCardProps) {
  const agent = message.agent ?? 'master';
  const info = getAgentInfo(agent);
  const p = (message.payload ?? {}) as Record<string, any>;

  return (
    <div className="wb-msg wb-msg--agent" data-testid="wb-msg-card">
      <div className="wb-msg__meta">
        <strong className="wb-msg__meta-name" style={{ color: info.color }}>
          {info.emoji} {info.name} Agent
        </strong>
        {' · '}
        {formatTime(message.timestamp)}
      </div>
      <div className="wb-msg__card">
        {renderCardContent(message.cardType ?? 'text', p, onAction)}
      </div>
    </div>
  );
}

function renderCardContent(
  cardType: string,
  p: Record<string, any>,
  onAction?: (action: string, payload?: unknown) => void,
): React.ReactNode {
  switch (cardType) {
    case 'settlement':
      return <SettlementCard p={p} />;
    case 'quote':
      return <QuoteCard p={p} />;
    case 'bom':
      return <BOMCard p={p} onAction={onAction} />;
    case 'camera-scan':
      return <CameraScanCard p={p} />;
    case 'budget':
      return <BudgetCard p={p} />;
    case 'payment':
      return <PaymentCard p={p} />;
    default:
      return (
        <div className="wb-msg__fallback">
          该卡片类型（{cardType}）待后续批次支持
        </div>
      );
  }
}

/** 结算卡片 — 对齐 message-renderers.js renderSettlementCard */
function SettlementCard({ p }: { p: Record<string, any> }) {
  const lines: any[] = p.lines ?? [];
  const statusText: Record<string, string> = {
    draft: '草稿', confirmed: '已确认', review: '待复核', flagged: '已标记异常',
  };
  return (
    <>
      <div className="wb-msg__card-title">🧾 结算单</div>
      {lines.slice(0, 6).map((it, i) => (
        <div className="wb-msg__card-row" key={i}>
          <span>
            {i + 1}. {it.name ?? '未命名'}
            {it.is_anomaly ? <small style={{ color: 'var(--warning)', marginLeft: 4 }}>⚠ 异常</small> : null}
          </span>
          <strong>¥{(it.actual_amount ?? it.contract_amount ?? 0).toLocaleString()}</strong>
        </div>
      ))}
      {lines.length > 6 && (
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>… 共 {lines.length} 项</div>
      )}
      <div className="wb-msg__card-row">
        <span>状态</span>
        <strong>{statusText[p.status] ?? p.status ?? '草稿'}</strong>
      </div>
      {p.total_amount != null && (
        <div className="wb-msg__card-row">
          <span>合计</span>
          <strong style={{ color: 'var(--warning)' }}>¥{(p.total_amount ?? 0).toLocaleString()}</strong>
        </div>
      )}
    </>
  );
}

/** 比价卡片 — 对齐 message-renderers.js renderQuoteCard */
function QuoteCard({ p }: { p: Record<string, any> }) {
  const quotes: any[] = p.quotes ?? [];
  return (
    <>
      <div className="wb-msg__card-title">🛒 {p.product ?? '比价报告'}</div>
      {quotes.map((q, i) => (
        <div className="wb-msg__card-row" key={i}>
          <span>{q.supplier}</span>
          <strong>¥{(q.price ?? 0).toLocaleString()}{q.recommended ? ' ⭐' : ''}</strong>
        </div>
      ))}
      {p.recommendation && (
        <div className="wb-msg__card-row">
          <span>推荐</span>
          <strong style={{ color: 'var(--accent)' }}>{p.recommendation}</strong>
        </div>
      )}
    </>
  );
}

/** BOM 物料清单卡片 — 对齐 message-renderers.js renderBOMCard */
function BOMCard({ p, onAction }: { p: Record<string, any>; onAction?: (action: string, payload?: unknown) => void }) {
  const items: any[] = p.items ?? [];
  return (
    <>
      <div className="wb-msg__card-title">📦 {p.title ?? 'BOM 物料清单'}</div>
      {items.length === 0 && <div className="wb-msg__card-row"><span>暂无物料</span></div>}
      {items.slice(0, 8).map((it, i) => {
        const mat = it.material ?? {};
        const cat = mat.category ?? {};
        return (
          <div className="wb-msg__card-row" key={i}>
            <span>
              {i + 1}. {mat.name ?? mat.sku ?? '物料'}{' '}
              <small style={{ color: 'var(--text-muted)' }}>[{cat.name ?? cat.code ?? ''}]</small>
            </span>
            <strong>×{it.quantity} {mat.unit ?? ''} · ¥{(it.total_price ?? 0).toLocaleString()}</strong>
          </div>
        );
      })}
      {items.length > 8 && (
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>… 共 {items.length} 项</div>
      )}
      <div className="wb-msg__card-row">
        <span>合计</span>
        <strong style={{ color: 'var(--warning)' }}>¥{(p.total_price ?? 0).toLocaleString()}</strong>
      </div>
      {p.project_id && (
        <button
          type="button"
          className="wb-feedback-btn"
          style={{ marginTop: 6, color: 'var(--accent)', borderColor: 'var(--accent)' }}
          onClick={() => onAction?.('bom-export', { project_id: p.project_id })}
        >
          📥 导出 Excel
        </button>
      )}
    </>
  );
}

/** 产品识别卡片 — camera-scan */
function CameraScanCard({ p }: { p: Record<string, any> }) {
  const products: any[] = p.products ?? p.items ?? [];
  return (
    <>
      <div className="wb-msg__card-title">📷 产品识别</div>
      {products.length === 0 && <div className="wb-msg__card-row"><span>未识别到产品</span></div>}
      {products.map((it, i) => (
        <div className="wb-msg__card-row" key={i}>
          <span>{it.name ?? it.sku ?? '产品'}</span>
          <strong>{it.confidence != null ? `${Math.round(it.confidence * 100)}%` : ''}</strong>
        </div>
      ))}
    </>
  );
}

/** 预算卡片 — 对齐 renderBudgetCard */
function BudgetCard({ p }: { p: Record<string, any> }) {
  const percent = p.total ? Math.round(((p.spent ?? 0) / p.total) * 100) : 0;
  return (
    <>
      <div className="wb-msg__card-title">📊 预算概览</div>
      <div className="wb-msg__card-row"><span>总预算</span><strong>¥{(p.total ?? 0).toLocaleString()}</strong></div>
      <div className="wb-msg__card-row"><span>已支出</span><strong>¥{(p.spent ?? 0).toLocaleString()}（{percent}%）</strong></div>
      <div className="wb-msg__card-row"><span>剩余</span><strong style={{ color: 'var(--success)' }}>¥{(p.remaining ?? 0).toLocaleString()}</strong></div>
      <div className="wb-progress-bar"><div className="wb-progress-bar__fill" style={{ width: `${percent}%` }} /></div>
    </>
  );
}

/** 支付进度卡片 — 对齐 renderPaymentCard */
function PaymentCard({ p }: { p: Record<string, any> }) {
  const stages: any[] = p.stages ?? p.schedule ?? [];
  const totalPaid = p.total_paid ?? stages.reduce((s, st) => s + (st.paid_amount ?? 0), 0);
  const totalAmount = p.total_amount ?? stages.reduce((s, st) => s + (st.total_amount ?? 0), 0);
  const percent = totalAmount > 0 ? Math.round((totalPaid / totalAmount) * 100) : 0;
  const STAGE_LABEL: Record<string, string> = { deposit: '首付', progress: '进度款', final: '尾款', warranty: '质保金' };
  const STATUS_ICON: Record<string, string> = { paid: '✓', partial: '◐', pending: '○', overdue: '!' };

  return (
    <>
      <div className="wb-msg__card-title">💳 支付进度</div>
      <div className="wb-msg__card-row"><span>已付</span><strong style={{ color: 'var(--success)' }}>¥{(totalPaid ?? 0).toLocaleString()}</strong></div>
      <div className="wb-msg__card-row"><span>总额</span><strong>¥{(totalAmount ?? 0).toLocaleString()}</strong></div>
      <div className="wb-msg__card-row"><span>进度</span><strong>{percent}%</strong></div>
      <div className="wb-progress-bar"><div className="wb-progress-bar__fill" style={{ width: `${percent}%` }} /></div>
      {stages.map((st, i) => {
        const label = STAGE_LABEL[st.stage_code] ?? st.stage_code ?? st.milestone_code ?? '阶段';
        return (
          <div className="wb-msg__card-row" key={i}>
            <span>{STATUS_ICON[st.status] ?? '○'} {label}</span>
            <strong>¥{(st.paid_amount ?? 0).toLocaleString()} / ¥{(st.total_amount ?? 0).toLocaleString()}</strong>
          </div>
        );
      })}
    </>
  );
}
