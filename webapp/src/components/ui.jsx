import React from 'react'
import { RefreshCw } from 'lucide-react'

/* Logo — 品牌标记 */
export function Logo({ size = 34, withText = false }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
      <span
        style={{
          width: size,
          height: size,
          minWidth: size,
          borderRadius: 10,
          background: 'linear-gradient(135deg, #c9973b, #e0aa4a)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontWeight: 800,
          fontSize: size * 0.42,
          color: '#1a1206',
          fontFamily: 'var(--font-sans)',
        }}
      >
        索
      </span>
      {withText && (
        <span style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <b style={{ fontSize: 15, letterSpacing: 0.5, color: 'var(--text)', whiteSpace: 'nowrap' }}>
            索克家居
          </b>
          <span className="mono" style={{ fontSize: 10, color: 'var(--text-dim)' }}>
            i-home.life
          </span>
        </span>
      )}
    </div>
  )
}

/* Avatar — 首字母圆形头像 */
export function Avatar({ text, size = 32 }) {
  return (
    <span
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        background: 'var(--bg-elev-2)',
        border: '1px solid var(--border-strong)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: size * 0.42,
        fontWeight: 600,
        color: 'var(--accent-text)',
        minWidth: size,
      }}
    >
      {text || '索'}
    </span>
  )
}

/* Card */
export function Card({ title, sub, icon, children, style, actions }) {
  return (
    <div className="card" style={style}>
      {(title || actions) && (
        <div className="card-title">
          {icon}
          {title && (
            <>
              <span>{title}</span>
              {sub && <span className="sub">{sub}</span>}
            </>
          )}
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>{actions}</div>
        </div>
      )}
      {children}
    </div>
  )
}

/* Badge */
export function Badge({ children, tone }) {
  return <span className={`badge${tone ? ` badge--${tone}` : ''}`}>{children}</span>
}

/* Stat — 数字统计块 */
export function Stat({ label, value, hint, tone }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className={`stat-value${tone ? ` ${tone}-text` : ''}`}>{value ?? '—'}</span>
      {hint && <span className="stat-hint">{hint}</span>}
    </div>
  )
}

/* Spinner — 加载中 */
export function Spinner({ label = '加载中…' }) {
  return (
    <div className="empty" style={{ flexDirection: 'row', gap: 10 }}>
      <span
        style={{
          width: 18,
          height: 18,
          border: '2px solid rgba(201,151,59,0.2)',
          borderTopColor: 'var(--accent)',
          borderRadius: '50%',
          animation: 'spin 0.8s linear infinite',
        }}
      />
      <span style={{ color: 'var(--text-sub)', fontSize: 13 }}>{label}</span>
    </div>
  )
}

/* Empty — 空态（对齐 Flutter EmptyStateWidget：图标 + 标题 + 描述 + 可选 CTA） */
export function Empty({ message = '暂无数据', description, actionLabel, onAction, icon = '🗂' }) {
  return (
    <div className="empty">
      <span style={{ fontSize: 32 }}>{icon}</span>
      <span>{message}</span>
      {description && <span className="sub">{description}</span>}
      {actionLabel && onAction && (
        <button className="btn btn--ghost" onClick={onAction} style={{ marginTop: 4 }}>
          {actionLabel}
        </button>
      )}
    </div>
  )
}

/* ErrorBox — 错误态 + 重试 */
export function ErrorBox({ message, onRetry }) {
  return (
    <div className="error-box">
      <span style={{ fontSize: 32 }}>⚠️</span>
      <span>{message || '加载失败'}</span>
      {onRetry && (
        <button className="btn btn--ghost" onClick={onRetry}>
          <RefreshCw size={14} /> 重试
        </button>
      )}
    </div>
  )
}

/* 加载骨架 */
export function Skeleton({ lines = 3, height = 60 }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="skeleton" style={{ height: i === lines - 1 ? height * 0.6 : height }} />
      ))}
    </div>
  )
}
