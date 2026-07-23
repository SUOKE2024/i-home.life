/* ============================================
 * 索克家居 · 性能监控与行为埋点
 * - Web Vitals: LCP / CLS / INP / FID / TTFB
 * - 行为埋点: 页面浏览 / CTA 点击 / 表单提交 / 错误
 * - 上报策略: sendBeacon（页面卸载不丢数据）
 * 版本：1.0.0
 * ============================================ */

const Analytics = {
  // 上报端点（同源 /api/analytics 或第三方；当前降级为 console + localStorage）
  ENDPOINT: '/api/analytics/collect',
  // 是否启用调试模式（控制台输出）
  DEBUG: window.location.hostname === 'localhost',
  // 会话 ID（单次会话内唯一）
  sessionId: '',
  // 批量上报缓冲区
  queue: [],
  flushTimer: null,

  // ── 初始化 ──
  init() {
    this.sessionId = this._getSessionId();
    this._observeWebVitals();
    this._trackPageView();
    this._trackErrors();
    this._bindCTAEvents();
    // 页面卸载前flush
    window.addEventListener('pagehide', () => this._flush(true));
    window.addEventListener('beforeunload', () => this._flush(true));
  },

  // ── 会话 ID ──
  _getSessionId() {
    let sid = sessionStorage.getItem('suoke_sid');
    if (!sid) {
      sid = 'sid_' + Date.now() + '_' + Math.random().toString(36).slice(2, 10);
      sessionStorage.setItem('suoke_sid', sid);
    }
    return sid;
  },

  // ── Web Vitals 采集 ──
  _observeWebVitals() {
    // LCP (Largest Contentful Paint)
    this._observeLCP();
    // CLS (Cumulative Layout Shift)
    this._observeCLS();
    // INP / FID (Interaction to Next Paint / First Input Delay)
    this._observeINP();
    // TTFB (Time to First Byte)
    this._observeTTFB();
  },

  _observeLCP() {
    if (!('PerformanceObserver' in window)) return;
    try {
      const po = new PerformanceObserver((list) => {
        const entries = list.getEntries();
        const lastEntry = entries[entries.length - 1];
        this._sendMetric('LCP', lastEntry.startTime, { element: lastEntry.element?.tagName || '' });
      });
      po.observe({ type: 'largest-contentful-paint', buffered: true });
    } catch (e) { /* 浏览器不支持 */ }
  },

  _observeCLS() {
    if (!('PerformanceObserver' in window)) return;
    let clsValue = 0;
    try {
      const po = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (!entry.hadRecentInput) {
            clsValue += entry.value;
          }
        }
      });
      po.observe({ type: 'layout-shift', buffered: true });
      // 页面卸载时上报累计 CLS
      window.addEventListener('pagehide', () => {
        this._sendMetric('CLS', clsValue);
      });
    } catch (e) { /* 浏览器不支持 */ }
  },

  _observeINP() {
    if (!('PerformanceObserver' in window)) return;
    let maxDuration = 0;
    let interactionCount = 0;
    try {
      const po = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          const duration = entry.processingEnd - entry.startTime;
          if (duration > maxDuration) maxDuration = duration;
          interactionCount++;
        }
      });
      po.observe({ type: 'event', buffered: true });
      // 页面卸载时上报 INP（最长交互延迟）
      window.addEventListener('pagehide', () => {
        this._sendMetric('INP', maxDuration, { interactions: interactionCount });
      });
    } catch (e) { /* 浏览器不支持 */ }
  },

  _observeTTFB() {
    if (!('performance' in window) || !performance.timing) return;
    window.addEventListener('load', () => {
      const t = performance.timing;
      const ttfb = t.responseStart - t.navigationStart;
      if (ttfb > 0) this._sendMetric('TTFB', ttfb);
    });
  },

  // ── 页面浏览埋点 ──
  _trackPageView() {
    const data = {
      type: 'pageview',
      path: window.location.pathname,
      url: window.location.href,
      referrer: document.referrer,
      title: document.title,
      session_id: this.sessionId,
      ts: Date.now(),
    };
    this._enqueue(data);
  },

  // ── 错误采集 ──
  _trackErrors() {
    window.addEventListener('error', (e) => {
      this._enqueue({
        type: 'error',
        message: e.message,
        filename: e.filename,
        lineno: e.lineno,
        colno: e.colno,
        ts: Date.now(),
      });
    });
    window.addEventListener('unhandledrejection', (e) => {
      this._enqueue({
        type: 'error',
        message: 'unhandledrejection: ' + (e.reason?.message || e.reason || ''),
        ts: Date.now(),
      });
    });
  },

  // ── CTA 点击埋点（事件委托） ──
  _bindCTAEvents() {
    document.addEventListener('click', (e) => {
      const cta = e.target.closest('[data-narrative-cta], [data-cta], .btn-primary, .role-card, .quick-chip');
      if (!cta) return;
      const action = cta.dataset.narrativeCta || cta.dataset.cta || cta.dataset.question || 'click';
      this._enqueue({
        type: 'cta_click',
        action,
        text: (cta.textContent || '').trim().slice(0, 50),
        tag: cta.tagName,
        ts: Date.now(),
      });
    });

    // 表单提交埋点
    document.addEventListener('submit', (e) => {
      const form = e.target;
      this._enqueue({
        type: 'form_submit',
        form_id: form.id || '',
        action: form.action || '',
        ts: Date.now(),
      });
    });
  },

  // ── 指标上报 ──
  _sendMetric(name, value, extra = {}) {
    this._enqueue({
      type: 'web_vital',
      metric: name,
      value: Math.round(value * 100) / 100,
      rating: this._rateMetric(name, value),
      ...extra,
      ts: Date.now(),
    });
  },

  // ── 指标评级 ──
  _rateMetric(name, value) {
    const thresholds = {
      LCP: [2500, 4000],   // good / needs improvement / poor (ms)
      CLS: [0.1, 0.25],
      INP: [200, 500],
      FID: [100, 300],
      TTFB: [800, 1800],
    };
    const t = thresholds[name];
    if (!t) return 'unknown';
    if (value <= t[0]) return 'good';
    if (value <= t[1]) return 'needs-improvement';
    return 'poor';
  },

  // ── 入队 ──
  _enqueue(data) {
    data.session_id = this.sessionId;
    data.page = window.location.pathname;
    this.queue.push(data);
    if (this.DEBUG) console.log('[Analytics]', data);
    // 批量上报：满 10 条或 5 秒
    if (this.queue.length >= 10) {
      this._flush();
    } else if (!this.flushTimer) {
      this.flushTimer = setTimeout(() => this._flush(), 5000);
    }
  },

  // ── 上报 ──
  _flush(useBeacon = false) {
    if (this.flushTimer) {
      clearTimeout(this.flushTimer);
      this.flushTimer = null;
    }
    if (this.queue.length === 0) return;
    const batch = this.queue.splice(0);
    const payload = JSON.stringify({ events: batch, v: '1.0.0' });

    if (useBeacon && navigator.sendBeacon) {
      // 页面卸载时用 sendBeacon（不丢数据）
      navigator.sendBeacon(this.ENDPOINT, payload);
    } else {
      // 普通上报
      fetch(this.ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload,
        keepalive: true,
      }).catch(() => {
        // 上报失败：存 localStorage 待重试（最多 50 条）
        try {
          const retry = JSON.parse(localStorage.getItem('suoke_analytics_retry') || '[]');
          retry.push(...batch);
          localStorage.setItem('suoke_analytics_retry', JSON.stringify(retry.slice(-50)));
        } catch (_) {}
      });
    }
  },

  // ── 手动埋点 API ──
  track(event, props = {}) {
    this._enqueue({ type: 'custom', event, ...props, ts: Date.now() });
  },
};

// 自动初始化
Analytics.init();
window.Analytics = Analytics;
