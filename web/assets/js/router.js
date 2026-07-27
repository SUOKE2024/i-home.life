/* ============================================
 * 索克家居 · 客户端路由管理器 (Router)
 * 基于 hash 的轻量级 SPA 路由
 *
 * 使用方式:
 *   <script src="assets/js/component-base.js"></script>
 *   <script src="assets/js/router.js"></script>
 *
 *   const router = new Router();
 *   router.on('/dashboard', () => renderDashboard());
 *   router.on('/projects/:id', (params) => showProject(params.id));
 *   router.start();
 * ============================================ */

'use strict';

(() => {

  class Router {
    constructor(options = {}) {
      /** @type {string} 路由模式: 'hash' */
      this.mode = options.mode || 'hash';

      /** @type {string} 内容渲染目标选择器 */
      this.target = options.target || '#content';

      /** @type {string} 默认路由 */
      this.defaultRoute = options.defaultRoute || '/dashboard';

      /** @type {Array<{pattern:RegExp, keys:string[], handler:Function}>} */
      this._routes = [];

      /** @type {Function|null} 全局前置守卫 */
      this._beforeEach = null;

      /** @type {Function|null} 全局后置钩子 */
      this._afterEach = null;

      /** @type {string|null} 当前路径 */
      this._current = null;

      /** @type {boolean} */
      this._started = false;

      /** @type {Array<{el:HTMLElement, route:string|RegExp, activeClass:string}>} */
      this._navLinks = [];

      // 绑定 hashchange
      this._onHashChange = this._onHashChange.bind(this);
    }

    /* ── 路由注册 ── */

    /**
     * 注册路由
     * @param {string} path - 路由路径，支持 :param 参数
     * @param {Function} handler - 路由处理函数，接收 (params, query)
     * @returns {Router}
     *
     * 示例:
     *   router.on('/dashboard', () => { ... });
     *   router.on('/projects/:id', (params) => { ... });
     */
    on(path, handler) {
      if (typeof handler !== 'function') {
        console.warn('[Router] handler must be a function for path:', path);
        return this;
      }

      const keys = [];
      // 将 :param 转为正则命名组
      const pattern = path
        .replace(/[.+?^${}()|[\]\\]/g, '\\$&')
        .replace(/:(\w+)/g, (_, key) => {
          keys.push(key);
          return '([^/]+)';
        });

      this._routes.push({
        pattern: new RegExp('^' + pattern + '$'),
        keys,
        handler,
        _path: path,
      });

      return this;
    }

    /**
     * 批量注册路由
     * @param {Object<string, Function>} routes - { path: handler }
     */
    batch(routes) {
      for (const [path, handler] of Object.entries(routes)) {
        this.on(path, handler);
      }
      return this;
    }

    /* ── 导航守卫 ── */

    /**
     * 全局前置守卫
     * @param {(to:string, params:Object, query:Object) => boolean|string|void} guard
     *   返回 false 或字符串（重定向路径）可阻止导航
     */
    beforeEach(guard) {
      this._beforeEach = guard;
      return this;
    }

    /**
     * 全局后置钩子
     * @param {(to:string, params:Object, query:Object) => void} hook
     */
    afterEach(hook) {
      this._afterEach = hook;
      return this;
    }

    /* ── 导航链接绑定 ── */

    /**
     * 绑定导航链接，自动管理 active 状态
     * 页面中的 <a href="#/path"> 链接会自动响应
     *
     * @param {string} [activeClass='active'] - 激活时的 CSS 类名
     * @param {string} [selector] - 导航链接选择器，默认所有带有 data-route 属性的链接
     */
    bindNavLinks(activeClass = 'active', selector) {
      const links = document.querySelectorAll(selector || 'a[data-route], [data-nav] a');
      this._navLinks = [];

      links.forEach(link => {
        const route = link.getAttribute('data-route') || link.hash?.slice(1) || link.getAttribute('href')?.replace(/^#/, '') || '';
        // 去除首尾斜杠统一格式
        const normalized = route.replace(/^\/+|\/+$/g, '');
        this._navLinks.push({ el: link, route: normalized, activeClass });

        link.addEventListener('click', (e) => {
          if (link.getAttribute('href')?.startsWith('#')) {
            e.preventDefault();
            this.navigate(normalized);
          }
        });
      });

      return this;
    }

    /** 更新导航链接的 active 状态 */
    _updateActiveLinks(currentPath) {
      const clean = currentPath.replace(/^\/+|\/+$/g, '');
      for (const { el, route, activeClass } of this._navLinks) {
        const match = route === clean ||
          (route && clean.startsWith(route)) ||
          el.hash?.slice(1)?.replace(/^\/+|\/+$/g, '') === clean;
        el.classList.toggle(activeClass, !!match);
        if (match) el.setAttribute('aria-current', 'page');
        else el.removeAttribute('aria-current');
      }
    }

    /* ── 导航 ── */

    /**
     * 编程式导航
     * @param {string} path - 目标路径
     * @param {Object} [state] - 附加状态（存入 history）
     */
    navigate(path, state) {
      if (!path && path !== '') path = this.defaultRoute;
      // 确保以 # 开头
      const hash = path.startsWith('#') ? path : '#' + path.replace(/^\/+/, '');
      const currentHash = location.hash || '#';

      if (hash === currentHash) {
        // 相同路径，强制执行处理（支持刷新）
        this._handleRoute(path);
        return;
      }

      location.hash = hash.slice(1);
    }

    /**
     * 替换当前路由（不产生历史记录）
     */
    replace(path) {
      const hash = path.startsWith('#') ? path : '#' + path.replace(/^\/+/, '');
      const url = location.pathname + location.search + hash;
      history.replaceState(null, '', url);
      this._handleRoute(path);
    }

    /* ── 内部处理 ── */

    /** hashchange 事件处理 */
    _onHashChange() {
      const path = this._getPath();
      this._handleRoute(path);
    }

    /** 获取当前路径（去掉 #，确保以 / 开头） */
    _getPath() {
      let path = (location.hash || '#/' + this.defaultRoute).replace(/^#\/?/, '/');
      if (!path || path === '/') path = this.defaultRoute;
      return path;
    }

    /** 解析查询参数 */
    _parseQuery(hash) {
      const query = {};
      const idx = hash.indexOf('?');
      if (idx === -1) return { path: hash, query };
      const qs = hash.slice(idx + 1);
      const path = hash.slice(0, idx);
      for (const part of qs.split('&')) {
        const [k, v] = part.split('=');
        if (k) query[decodeURIComponent(k)] = v ? decodeURIComponent(v) : '';
      }
      return { path, query };
    }

    /** 核心路由处理 */
    _handleRoute(rawPath) {
      const cleanPath = rawPath.replace(/^#/, '').replace(/^\/+/, '/');
      const { path, query } = this._parseQuery(cleanPath);

      // 查找匹配路由
      let matched = null;
      let params = {};

      for (const route of this._routes) {
        const m = path.match(route.pattern);
        if (m) {
          matched = route;
          for (let i = 0; i < route.keys.length; i++) {
            params[route.keys[i]] = decodeURIComponent(m[i + 1]);
          }
          break;
        }
      }

      // 前置守卫
      if (this._beforeEach) {
        const result = this._beforeEach(path, params, query);
        if (result === false) return;
        if (typeof result === 'string') {
          this.navigate(result);
          return;
        }
      }

      // 更新导航链接状态
      this._updateActiveLinks(path);

      // 更新当前路径
      this._current = path;

      // 执行路由处理
      if (matched) {
        try {
          matched.handler(params, query);
        } catch (e) {
          console.error('[Router] error handling route:', path, e);
        }
      } else {
        // 未匹配路由，触发自定义事件
        window.dispatchEvent(new CustomEvent('router:not-found', { detail: { path, query } }));
        console.warn('[Router] no handler for route:', path);
      }

      // 后置钩子
      if (this._afterEach) {
        this._afterEach(path, params, query);
      }
    }

    /* ── 生命周期 ── */

    /** 启动路由 */
    start() {
      if (this._started) return this;
      this._started = true;

      window.addEventListener('hashchange', this._onHashChange);

      // 处理当前 URL 或默认路由
      const path = this._getPath();
      if (path !== this.defaultRoute || !this._current) {
        this._handleRoute(path);
      }

      return this;
    }

    /** 停止路由监听 */
    stop() {
      this._started = false;
      window.removeEventListener('hashchange', this._onHashChange);
      return this;
    }

    /** 获取当前路径 */
    get currentPath() {
      return this._current;
    }
  }

  // ── 预设路由表（与 admin.html 导航一致） ──
  const PRESET_ROUTES = {
    '/dashboard': { icon: '📊', label: '仪表盘' },
    '/projects': { icon: '🏠', label: '项目管理' },
    '/budget': { icon: '💰', label: '预算管理' },
    '/procurement': { icon: '📦', label: '采购管理' },
    '/construction': { icon: '🔨', label: '施工管理' },
    '/settlements': { icon: '📋', label: '结算管理' },
    '/materials': { icon: '🧱', label: '物料库' },
    '/users': { icon: '👥', label: '用户管理' },
    '/quality': { icon: '✅', label: '质检管理' },
    '/settings': { icon: '⚙️', label: '设置' },
    '/workbench': { icon: '💬', label: '工作台' },
    '/studio': { icon: '🎨', label: 'AI 设计台' },
  };

  // 暴露到全局
  window.Router = Router;
  window.ROUTER_PRESETS = PRESET_ROUTES;

})();
