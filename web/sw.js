/**
 * sw.js — Self-destructing service worker
 *
 * CACHE_VERSION: increment when changing the service worker strategy.
 * The old PWA (pre-v1.2.3) used this sw.js for offline caching.
 * After migrating to Flutter web build, the PWA now uses
 * flutter_service_worker.js. This self-destructing sw.js exists solely
 * to clean up old registrations from returning visitors' browsers.
 *
 * Migration strategy:
 *   1. Deploy this self-destructing sw.js alongside the new Flutter PWA.
 *      On activate, it unregisters itself, triggering the browser to
 *      look for a new service worker on the next navigation.
 *   2. After a grace period (30-90 days, covering all active users),
 *      remove this file entirely. Returning visitors will register
 *      flutter_service_worker.js directly.
 *   3. Increment CACHE_VERSION if you need to force a re-sweep
 *      (e.g., if the old SW had a different scope).
 */
const CACHE_VERSION = 7;
self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    self.registration.unregister().then(() => {
      return self.clients.matchAll({ type: 'window' });
    }).then((clients) => {
      clients.forEach((client) => {
        client.navigate(client.url);
      });
    })
  );
});
