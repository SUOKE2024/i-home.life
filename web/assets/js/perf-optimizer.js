/* ============================================
 * 索克家居 · 前端性能优化模块 — v1.1.26
 *
 * 功能:
 *   1. 图片懒加载 (IntersectionObserver + loading="lazy" fallback)
 *   2. 字体加载优化 (font-display swap + font loading API)
 *   3. 资源提示注入 (preconnect / preload / prefetch)
 *   4. 关键指标上报 (LCP / FID / CLS via web-vitals)
 *   5. prefers-reduced-motion 动画降级
 *   6. 长任务分割 (yield to main thread)
 * ============================================ */

(function () {
  'use strict';

  // ── 图片懒加载 ──
  function initLazyImages() {
    // 使用原生 loading="lazy" (Chrome 77+, Firefox 75+)
    // 对不支持原生懒加载的浏览器，使用 IntersectionObserver fallback
    const supportsNativeLazy = 'loading' in HTMLImageElement.prototype;

    if (!supportsNativeLazy) {
      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              const img = entry.target;
              // data-src → src
              if (img.dataset.src) {
                img.src = img.dataset.src;
              }
              // data-srcset → srcset
              if (img.dataset.srcset) {
                img.srcset = img.dataset.srcset;
              }
              img.removeAttribute('data-src');
              img.removeAttribute('data-srcset');
              observer.unobserve(img);
            }
          });
        },
        { rootMargin: '200px' }
      );

      document.querySelectorAll('img[data-src]').forEach((img) => {
        observer.observe(img);
      });
    }

    // 对 background-image 的懒加载（通过 data-bg 属性）
    const bgObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const el = entry.target;
            const bg = el.dataset.bg;
            if (bg) {
              el.style.backgroundImage = `url(${bg})`;
              el.removeAttribute('data-bg');
            }
            bgObserver.unobserve(el);
          }
        });
      },
      { rootMargin: '200px' }
    );

    document.querySelectorAll('[data-bg]').forEach((el) => {
      bgObserver.observe(el);
    });
  }

  // ── 字体加载状态报告 ──
  function monitorFontLoading() {
    if (!('fonts' in document)) return;

    document.fonts.ready.then(() => {
      document.documentElement.classList.add('fonts-loaded');
      performance.mark('fonts-ready');
    });
  }

  // ── 资源提示注入 ──
  function injectResourceHints() {
    const hints = [];

    // 根据当前页面自动注入 prefetch
    const path = window.location.pathname;

    // 工作台页面：预取设计工具
    if (path.includes('workbench') || path.includes('demo')) {
      hints.push(
        { rel: 'prefetch', href: '/studio.html', as: 'document' },
        { rel: 'prefetch', href: '/materials.html', as: 'document' }
      );
    }

    // 工作台页面：预取关键 API 域名
    if (path.includes('workbench')) {
      hints.push(
        { rel: 'preconnect', href: window.location.origin, crossorigin: false }
      );
    }

    hints.forEach(({ rel, href, as, crossorigin }) => {
      const link = document.createElement('link');
      link.rel = rel;
      link.href = href;
      if (as) link.setAttribute('as', as);
      if (crossorigin !== undefined) {
        link.crossOrigin = crossorigin ? 'anonymous' : null;
      }
      document.head.appendChild(link);
    });
  }

  // ── 动画降级 (prefers-reduced-motion) ──
  function applyReducedMotion() {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (mq.matches) {
      document.documentElement.classList.add('reduced-motion');
    }
    mq.addEventListener('change', (e) => {
      if (e.matches) {
        document.documentElement.classList.add('reduced-motion');
      } else {
        document.documentElement.classList.remove('reduced-motion');
      }
    });

    // 注入 CSS 变量用于全局降级
    const style = document.createElement('style');
    style.textContent = `
      .reduced-motion *,
      .reduced-motion *::before,
      .reduced-motion *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
        scroll-behavior: auto !important;
      }
    `;
    document.head.appendChild(style);
  }

  // ── 长任务 yield（避免阻塞主线程 >50ms）──
  function yieldToMain() {
    return new Promise((resolve) => {
      setTimeout(resolve, 0);
    });
  }

  async function runInIdle(task, chunks) {
    for (let i = 0; i < chunks; i++) {
      await yieldToMain();
      task(i);
    }
  }

  // ── Web Vitals 关键指标上报 ──
  function initWebVitals() {
    // LCP (Largest Contentful Paint)
    const lcpObserver = new PerformanceObserver((list) => {
      const entries = list.getEntries();
      const lastEntry = entries[entries.length - 1];
      if (lastEntry) {
        const lcp = lastEntry.renderTime || lastEntry.loadTime;
        recordMetric('LCP', Math.round(lcp));
      }
    });
    try {
      lcpObserver.observe({ type: 'largest-contentful-paint', buffered: true });
    } catch (e) {
      // 浏览器不支持
    }

    // FID (First Input Delay)
    const fidObserver = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        recordMetric('FID', Math.round(entry.processingStart - entry.startTime));
      }
    });
    try {
      fidObserver.observe({ type: 'first-input', buffered: true });
    } catch (e) {
      // 浏览器不支持
    }

    // CLS (Cumulative Layout Shift)
    let clsValue = 0;
    const clsObserver = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (!entry.hadRecentInput) {
          clsValue += entry.value;
        }
      }
    });
    try {
      clsObserver.observe({ type: 'layout-shift', buffered: true });
    } catch (e) {
      // 浏览器不支持
    }

    // 页面隐藏时上报 CLS
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        recordMetric('CLS', Math.round(clsValue * 1000) / 1000);
      }
    });

    // TTFB (Time To First Byte) - from Navigation Timing
    if (window.performance && performance.getEntriesByType) {
      const navEntries = performance.getEntriesByType('navigation');
      if (navEntries.length > 0) {
        const ttfb = navEntries[0].responseStart - navEntries[0].requestStart;
        recordMetric('TTFB', Math.round(ttfb));
      }
    }
  }

  function recordMetric(name, value) {
    // 记录到 console（开发模式）
    if (window.location.hostname === 'localhost') {
      console.debug(`[Perf] ${name}: ${value}`);
    }

    // 存储到 sessionStorage 供 analytics 读取
    try {
      const metrics = JSON.parse(sessionStorage.getItem('_web_vitals') || '{}');
      metrics[name] = value;
      metrics._timestamp = Date.now();
      sessionStorage.setItem('_web_vitals', JSON.stringify(metrics));

      // 如果 analytics 模块已加载，发送指标
      if (window.__reportWebVital) {
        window.__reportWebVital(name, value);
      }
    } catch (e) {
      // silent
    }
  }

  // ── DOM Ready 后执行 ──
  function onReady() {
    initLazyImages();
    monitorFontLoading();
    applyReducedMotion();

    // 非首页延迟注入资源提示
    if (document.readyState === 'complete') {
      injectResourceHints();
    } else {
      window.addEventListener('load', injectResourceHints);
    }

    // 延迟初始化 Web Vitals
    if (document.readyState === 'complete') {
      setTimeout(initWebVitals, 1000);
    } else {
      window.addEventListener('load', () => setTimeout(initWebVitals, 1000));
    }
  }

  // ── 启动 ──
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', onReady);
  } else {
    onReady();
  }

  // 暴露公共 API
  window.PerfOptimizer = {
    yieldToMain,
    runInIdle,
    recordMetric,
    injectResourceHints,
  };
})();
