import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { setOnUnauthorized, reportWebVitals } from './lib/api'
import './styles/tokens.css'
import './styles/base.css'
import './styles/components.css'
import './styles/pages.css'

/* 全局 401：清登录态 → 回登录页 */
setOnUnauthorized(() => {
  if (!window.location.pathname.startsWith('/auth')) {
    window.location.href = '/auth'
  }
})

/* ── v1.10.x RUM：Core Web Vitals 采集（LCP/CLS/INP/FCP/TTFB） ──
 * 对齐 2026 行业前沿 Real User Monitoring；后端 diagnostics_rum_enabled
 * 门控落库，未开启时公开端点直接丢弃，前端零副作用。
 */
function initRum() {
  try {
    if (!('PerformanceObserver' in window) || !navigator.sendBeacon) return
    if (!window.sessionStorage.getItem('ihome_rum_sid')) {
      window.sessionStorage.setItem('ihome_rum_sid', `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`)
    }
    const metrics = {}

    // 导航计时：TTFB / FCP
    const nav = window.performance?.getEntriesByType?.('navigation')?.[0]
    if (nav) {
      metrics.ttfb = nav.responseStart
    }
    const fcpEntry = window.performance?.getEntriesByName?.('first-contentful-paint')?.[0]
    if (fcpEntry) metrics.fcp = fcpEntry.startTime

    const report = () => {
      if (Object.keys(metrics).length > 0) reportWebVitals(metrics)
    }

    // LCP
    try {
      const lcp = new PerformanceObserver((list) => {
        const entries = list.getEntries()
        const last = entries[entries.length - 1]
        if (last) metrics.lcp = last.startTime
      })
      lcp.observe({ type: 'largest-contentful-paint', buffered: true })
    } catch { /* noop */ }

    // CLS
    try {
      let clsValue = 0
      const cls = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (!entry.hadRecentInput) clsValue += entry.value
        }
        metrics.cls = clsValue
      })
      cls.observe({ type: 'layout-shift', buffered: true })
    } catch { /* noop */ }

    // INP（事件计时）
    try {
      const inp = new PerformanceObserver((list) => {
        const entries = list.getEntries()
        const worst = entries.reduce((acc, e) => (e.duration > acc.duration ? e : acc), { duration: 0 })
        if (worst.duration) metrics.inp = worst.duration
      })
      inp.observe({ type: 'event', buffered: true, durationThreshold: 40 })
    } catch { /* noop */ }

    // 页面卸载前上报
    window.addEventListener('pagehide', report, { once: true })
    // 兜底：5s 后若 LCP 已确定则上报
    window.setTimeout(report, 5000)
  } catch { /* RUM 初始化失败静默 */ }
}

initRum()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
