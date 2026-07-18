/* ============================================
 * 索克家居 · Service Worker
 * PWA 离线缓存策略
 * - 静态资源：缓存优先（stale-while-revalidate）
 * - API 请求：网络优先，失败降级缓存
 * - WebSocket：不拦截
 * 版本：1.0.18
 * ============================================ */

const CACHE_VERSION = 'suoke-v1.0.18';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const RUNTIME_CACHE = `${CACHE_VERSION}-runtime`;

// 预缓存核心资源（安装时缓存）
const PRECACHE_URLS = [
  '/',
  '/index.html',
  '/demo.html',
  '/workbench.html',
  '/login.html',
  '/settings.html',
  '/admin.html',
  '/studio.html',
  '/3d-viewer.html',
  '/vr-viewer.html',
  '/our-story.html',
  '/project-detail.html',
  '/materials.html',
  '/quality-report.html',
  '/manifest.json',
  '/assets/css/workbench.css',
  '/assets/js/api-client.js',
  '/assets/js/im-client.js',
  '/assets/js/agent-router.js',
  '/assets/js/message-renderers.js',
  '/assets/js/analytics.js',
  '/assets/js/echarts.min.js',
  '/assets/images/icons/desktop/suoke-favicon-32.png',
  '/assets/images/icons/desktop/suoke-logo-128.png',
  '/assets/images/icons/desktop/suoke-logo-512.png',
  '/assets/guide/user-guide.html',
  '/assets/legal/privacy-policy.html',
  '/assets/legal/terms-of-service.html',
];

// 不缓存的路径（API、WebSocket、后端资源）
const NEVER_CACHE = [
  '/api/',
  '/ws/',
  '/health',
  '/openapi.json',
  '/docs',
  '/redoc',
];

// ── 安装：预缓存核心资源 ──
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
      .catch(err => console.warn('SW precache 失败:', err))
  );
});

// ── 激活：清理旧缓存 ──
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys
          .filter(key => !key.startsWith(CACHE_VERSION))
          .map(key => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

// ── 请求拦截 ──
self.addEventListener('fetch', (event) => {
  const req = event.request;

  // 只处理 GET 请求
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // 不缓存 API / WebSocket / 后端资源
  if (NEVER_CACHE.some(path => url.pathname.startsWith(path) || url.pathname === path)) {
    return; // 直接走网络
  }

  // 跨域请求：网络优先
  if (url.origin !== self.location.origin) {
    event.respondWith(
      fetch(req).catch(() => caches.match(req))
    );
    return;
  }

  // 同源静态资源：stale-while-revalidate
  event.respondWith(
    caches.match(req).then(cached => {
      const fetchPromise = fetch(req)
        .then(res => {
          // 只缓存成功响应
          if (res && res.status === 200 && res.type === 'basic') {
            const resClone = res.clone();
            caches.open(RUNTIME_CACHE).then(cache => cache.put(req, resClone));
          }
          return res;
        })
        .catch(() => cached); // 网络失败返回缓存
      return cached || fetchPromise;
    })
  );
});

// ── 消息通信：支持前端触发更新 ──
self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
