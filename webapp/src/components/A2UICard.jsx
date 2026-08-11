import React from 'react'
import {
  LayoutTemplate, Wallet, HardHat, ShoppingCart, ShieldCheck,
  FileCheck, Box, BellRing,
} from 'lucide-react'

/**
 * A2UICard — 首页 feed 的 A2UI 8 类卡片渲染（web 端）
 *
 * 协议对齐 app/services/a2ui_schema.py：
 *  - design_plan / budget_breakdown / construction_progress
 *  - procurement_order / qa_report / settlement_summary
 *  - material_card / alert_card
 *
 * 诚实标注：卡片数据来自项目现有业务表，仅作导航参考。
 */
const TONE = { critical: 'red', high: 'amber', medium: 'amber', low: 'green', info: 'sky' }

const fmtMoney = (v) => {
  const n = Number(v ?? 0)
  return `¥${n.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`
}
const fmtPct = (v) => `${Math.round((Number(v ?? 0) || 0) * 100)}%`

function CardShell({ icon, title, subtitle, tone, children }) {
  const t = tone || 'sky'
  return (
    <div className="feed-card" style={{ display: 'block' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span className="feed-icon" style={{ background: `var(--${t}-dim)` }}>
          {icon}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>{title}</div>
          {subtitle && <div className="mono" style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 1 }}>{subtitle}</div>}
        </div>
      </div>
      <div style={{ marginTop: 10 }}>{children}</div>
    </div>
  )
}

function DesignPlan({ data }) {
  const rooms = Array.isArray(data.rooms) ? data.rooms : []
  const statusTone = { completed: 'green', in_progress: 'amber', attention: 'red', not_started: 'sky' }
  return (
    <CardShell icon={<LayoutTemplate size={15} style={{ color: 'var(--accent)' }} />}
      title={data.floor_layout || '设计方案'}
      subtitle={`${data.project_name || ''}${data.total_area ? ` · ${data.total_area} ㎡` : ''}`}>
      {rooms.length === 0 ? (
        <div style={{ fontSize: 11.5, color: 'var(--text-sub)' }}>{data.notes || '暂无房间明细'}</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(96px, 1fr))', gap: 6 }}>
          {rooms.slice(0, 9).map((r, i) => (
            <div key={`${r.name}-${i}`} style={{
              padding: '6px 8px', borderRadius: 9, fontSize: 11,
              border: `1px solid var(--border-strong)`, background: 'var(--bg)',
            }}>
              <div style={{ fontWeight: 700, color: 'var(--text)' }}>{r.name || '房间'}</div>
              <div style={{ color: 'var(--text-sub)', fontSize: 10, marginTop: 1 }}>
                {r.area != null ? `${r.area} ㎡` : ''}
                {r.status && <span style={{ color: `var(--${statusTone[r.status] || 'sky'})` }}> · {r.status}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </CardShell>
  )
}

function BudgetBreakdown({ data }) {
  const items = Array.isArray(data.items) ? data.items : []
  return (
    <CardShell icon={<Wallet size={15} style={{ color: 'var(--amber)' }} />}
      title={data.project_name || '预算明细'}
      subtitle={`合计 ${fmtMoney(data.total)}`}>
      {items.length === 0 ? (
        <div style={{ fontSize: 11.5, color: 'var(--text-sub)' }}>暂无预算分项</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
          {items.slice(0, 4).map((it, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, fontSize: 11.5 }}>
              <span style={{ color: 'var(--text-dim)', flex: 'none' }}>{it.category || '—'}</span>
              <b style={{ flex: 1, fontWeight: 600, color: 'var(--text)', minWidth: 0 }}>{it.name}</b>
              <span className="mono" style={{ color: 'var(--text-sub)' }}>{fmtMoney(it.amount)}</span>
            </div>
          ))}
          <div style={{ display: 'flex', gap: 8, fontSize: 11, borderTop: '1px solid var(--border)', paddingTop: 5, marginTop: 2 }}>
            <span style={{ color: 'var(--text-dim)' }}>预估</span>
            <b style={{ flex: 1, fontWeight: 700, color: 'var(--accent-text)' }}>{fmtMoney(data.subtotal)}</b>
            <span className="mono" style={{ color: 'var(--text-sub)' }}>已用 {fmtMoney(data.total)}</span>
          </div>
        </div>
      )}
    </CardShell>
  )
}

function ConstructionProgress({ data }) {
  const overall = Math.round((Number(data.overall_progress ?? 0) || 0) * 100)
  const phases = Array.isArray(data.phases) ? data.phases : []
  const st = { completed: 'green', in_progress: 'amber', delayed: 'red' }
  return (
    <CardShell icon={<HardHat size={15} style={{ color: 'var(--amber)' }} />}
      title={data.project_name || '施工进度'}
      subtitle={`总体进度 ${overall}%`}>
      <div style={{ height: 6, borderRadius: 3, background: 'var(--border)', overflow: 'hidden' }}>
        <div style={{ width: `${overall}%`, height: '100%', background: 'var(--accent)', transition: 'width .4s' }} />
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 8 }}>
        {phases.slice(0, 4).map((p, i) => (
          <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 11.5 }}>
            <span className="escrow-st" style={{ color: `var(--${st[p.status] || 'sky'})`, borderColor: `var(--${st[p.status] || 'sky'})` }}>
              {p.status === 'completed' ? '✓' : '…'}
            </span>
            <span style={{ flex: 1, color: 'var(--text)' }}>{p.name}</span>
            <span className="mono" style={{ color: 'var(--text-dim)' }}>{fmtPct(p.progress)}</span>
          </div>
        ))}
      </div>
    </CardShell>
  )
}

function ProcurementOrder({ data }) {
  const stTone = { delivered: 'green', shipped: 'sky', shipping: 'sky', ordered: 'amber', pending: 'amber', delayed: 'red', cancelled: 'red' }
  return (
    <CardShell icon={<ShoppingCart size={15} style={{ color: 'var(--sky)' }} />}
      title="采购订单"
      subtitle={`订单 ${String(data.order_id || '').slice(0, 8)}`}>
      <div style={{ display: 'flex', gap: 10, fontSize: 11.5 }}>
        <span className="badge" style={{ background: `var(--${stTone[data.status] || 'sky'}-dim)`, color: `var(--${stTone[data.status] || 'sky'})` }}>
          {data.status || 'ordered'}
        </span>
        <span style={{ color: 'var(--text-sub)' }}>金额 {fmtMoney(data.total_amount)}</span>
        {data.delivery_date && <span className="mono" style={{ color: 'var(--text-dim)' }}>预计 {data.delivery_date}</span>}
      </div>
    </CardShell>
  )
}

function QAReport({ data }) {
  const checkpoints = Array.isArray(data.checkpoints) ? data.checkpoints : []
  return (
    <CardShell icon={<ShieldCheck size={15} style={{ color: 'var(--green)' }} />}
      title="质检报告"
      subtitle={`通过 ${data.passed_count ?? 0} / 未通过 ${data.failed_count ?? 0}`}>
      {checkpoints.length === 0 ? (
        <div style={{ fontSize: 11.5, color: 'var(--text-sub)' }}>暂无质检记录</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
          {checkpoints.slice(0, 4).map((c, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, fontSize: 11.5, alignItems: 'center' }}>
              <span className="escrow-st" style={{ color: c.result === 'fail' ? 'var(--red)' : 'var(--green)', borderColor: c.result === 'fail' ? 'var(--red)' : 'var(--green)' }}>
                {c.result === 'fail' ? '✕' : c.result === 'pass' ? '✓' : '…'}
              </span>
              <span style={{ flex: 1, color: 'var(--text)' }}>{c.name}</span>
              {c.actual && <span className="mono" style={{ color: 'var(--text-dim)' }}>{c.actual}</span>}
            </div>
          ))}
        </div>
      )}
    </CardShell>
  )
}

function SettlementSummary({ data }) {
  return (
    <CardShell icon={<FileCheck size={15} style={{ color: 'var(--green)' }} />}
      title="结算汇总"
      subtitle={`状态 ${data.settlement_status || 'in_progress'}`}>
      <div className="kpi-row" style={{ gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
        <div>
          <div className="lab">合同额</div>
          <div className="val" style={{ fontSize: 13 }}>{fmtMoney(data.total_amount)}</div>
        </div>
        <div>
          <div className="lab">已付</div>
          <div className="val" style={{ fontSize: 13 }}>{fmtMoney(data.paid_amount)}</div>
        </div>
        <div>
          <div className="lab">待付</div>
          <div className="val" style={{ fontSize: 13, color: 'var(--accent-text)' }}>{fmtMoney(data.balance_amount)}</div>
        </div>
      </div>
    </CardShell>
  )
}

function MaterialCard({ data }) {
  return (
    <CardShell icon={<Box size={15} style={{ color: 'var(--sky)' }} />}
      title={data.name || '材料'}
      subtitle={`${data.category || ''}${data.specs ? ` · ${data.specs}` : ''}`}>
      <div style={{ display: 'flex', gap: 10, fontSize: 11.5, alignItems: 'center' }}>
        <span className="mono" style={{ color: 'var(--accent-text)', fontWeight: 700 }}>
          {fmtMoney(data.unit_price)}{data.unit ? `/${data.unit}` : ''}
        </span>
        {data.supplier && <span style={{ color: 'var(--text-sub)' }}>供应商 {data.supplier}</span>}
        {data.eco_level && <span className="badge badge--green">{data.eco_level}</span>}
      </div>
      {data.description && (
        <div style={{ fontSize: 11, color: 'var(--text-sub)', marginTop: 6, lineHeight: 1.5 }}>{data.description}</div>
      )}
    </CardShell>
  )
}

function AlertCard({ data, onAction }) {
  const tone = TONE[data.severity] || 'amber'
  const label = { critical: '严重', high: '高', low: '低', info: '提示' }[data.severity] || '中'
  return (
    <CardShell icon={<BellRing size={15} style={{ color: `var(--${tone})` }} />}
      title={data.title || '系统告警'} subtitle={data.source_agent ? `来源 ${data.source_agent}` : undefined}>
      <div style={{ fontSize: 12.5, lineHeight: 1.5, color: 'var(--text)' }}>{data.message}</div>
      <div className="feed-meta">
        <span>告警 · {label}</span>
        {(Array.isArray(data.actions) ? data.actions : []).map((a, i) => (
          <button key={i} className="btn btn--ghost" style={{ padding: '4px 10px', fontSize: 11.5 }}
            onClick={() => onAction && onAction(a.action, { title: data.title, message: data.message })}>
            {a.label || '处理'}
          </button>
        ))}
      </div>
    </CardShell>
  )
}

export default function A2UICard({ card, onAction }) {
  const type = card?.type
  const data = card?.data || {}
  switch (type) {
    case 'design_plan': return <DesignPlan data={data} />
    case 'budget_breakdown': return <BudgetBreakdown data={data} />
    case 'construction_progress': return <ConstructionProgress data={data} />
    case 'procurement_order': return <ProcurementOrder data={data} />
    case 'qa_report': return <QAReport data={data} />
    case 'settlement_summary': return <SettlementSummary data={data} />
    case 'material_card': return <MaterialCard data={data} />
    case 'alert_card': return <AlertCard data={data} onAction={onAction} />
    default: return null
  }
}
