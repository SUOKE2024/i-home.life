/* ============================================
 * 索克家居 · 应用壳组件 (AppShell)
 * 提供统一的侧边栏导航 / 顶部栏 / 内容区域
 *
 * 使用方式 1 - Web Component:
 *   <app-shell app-title="管理后台" user-phone="138****8000">
 *     <div slot="content">页面内容</div>
 *   </app-shell>
 *
 * 使用方式 2 - JavaScript API（无需 Web Component）:
 *   AppShell.create({
 *     container: document.body,
 *     title: '管理后台',
 *     navItems: [...],
 *     onNavigate: (path) => { ... },
 *   });
 *
 * 依赖: workbench.css（可选，提供基础样式）
 * ============================================ */

'use strict';

(() => {

  // ── 默认导航项（与 admin.html 一致，加上扩展路由） ──
  const DEFAULT_NAV_ITEMS = [
    { path: '/dashboard', icon: '📊', label: '仪表盘' },
    { path: '/projects', icon: '🏠', label: '项目管理' },
    { path: '/budget', icon: '💰', label: '预算管理' },
    { path: '/procurement', icon: '📦', label: '采购管理' },
    { path: '/construction', icon: '🔨', label: '施工管理' },
    { path: '/settlements', icon: '📋', label: '结算管理' },
    { path: '/materials', icon: '🧱', label: '物料库' },
    { path: '/users', icon: '👥', label: '用户管理' },
    { path: '/quality', icon: '✅', label: '质检管理' },
    // 扩展路由
    { path: '/settings', icon: '⚙️', label: '系统设置', section: 'bottom' },
    { path: '/workbench', icon: '💬', label: '工作台', external: true, href: 'workbench.html' },
    { path: '/studio', icon: '🎨', label: 'AI 设计台', external: true, href: 'studio.html' },
  ];

  // ── HTML 模板 ──
  const SHELL_HTML = `
    <style>
      /* ── 仅在 Web Component 内生效的 scoped 样式 ── */
      :host {
        --_bg-panel: var(--bg-panel, #12121d);
        --_bg-deep: var(--bg-deep, #08080f);
        --_border: var(--border, #1e1e32);
        --_text: var(--text-primary, #e8e6e1);
        --_text-secondary: var(--text-secondary, #8a8894);
        --_text-muted: var(--text-muted, #5a5866);
        --_accent: var(--accent, #c9973b);
        --_accent-bright: var(--accent-bright, #e0aa4a);
        --_font: var(--font-sans, -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif);
        display: flex;
        min-height: 100vh;
        min-height: 100dvh;
        font-family: var(--_font);
        color: var(--_text);
        background: var(--_bg-deep);
      }

      /* ── 跳过链接 ── */
      .skip-link {
        position: absolute;
        top: -100px;
        left: 8px;
        background: var(--_accent);
        color: var(--_bg-deep);
        padding: 8px 14px;
        border-radius: 8px;
        z-index: 999;
        font-size: 0.75rem;
        font-weight: 600;
        text-decoration: none;
      }
      .skip-link:focus { top: 8px; }

      /* ── 侧边栏 ── */
      .sidebar {
        width: 220px;
        background: var(--_bg-panel);
        border-right: 1px solid var(--_border);
        display: flex;
        flex-direction: column;
        flex-shrink: 0;
        position: fixed;
        top: 0;
        left: 0;
        bottom: 0;
        z-index: 30;
        transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
      }

      .sb-header {
        padding: 16px;
        border-bottom: 1px solid var(--_border);
        display: flex;
        align-items: center;
        gap: 10px;
      }

      .sb-header .logo-icon {
        font-size: 1.4rem;
        line-height: 1;
      }

      .sb-header h2 {
        font-size: 0.95rem;
        color: var(--_accent);
        white-space: nowrap;
        font-weight: 700;
      }

      .sb-header .sub {
        font-size: 0.6rem;
        color: var(--_text-muted);
        margin-top: 2px;
      }

      .sb-nav {
        flex: 1;
        overflow-y: auto;
        padding: 8px 0;
        scrollbar-width: thin;
      }
      .sb-nav::-webkit-scrollbar { width: 4px; }
      .sb-nav::-webkit-scrollbar-thumb { background: var(--_border); border-radius: 2px; }

      .sb-nav a {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 16px;
        font-size: 0.8rem;
        color: var(--_text-secondary);
        transition: all 0.15s;
        border-left: 3px solid transparent;
        text-decoration: none;
        cursor: pointer;
      }

      .sb-nav a:hover,
      .sb-nav a.active {
        color: var(--_text);
        background: rgba(201, 151, 59, 0.08);
        border-left-color: var(--_accent);
      }

      .sb-nav a .ico {
        font-size: 0.95rem;
        width: 22px;
        text-align: center;
        flex-shrink: 0;
      }

      .sb-divider {
        height: 1px;
        background: var(--_border);
        margin: 8px 12px;
      }

      .sb-footer {
        padding: 12px 16px;
        border-top: 1px solid var(--_border);
        font-size: 0.65rem;
        color: var(--_text-muted);
      }

      /* ── 主内容区 ── */
      .main {
        flex: 1;
        margin-left: 220px;
        display: flex;
        flex-direction: column;
        min-height: 100vh;
        min-height: 100dvh;
      }

      .topbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 12px 20px;
        background: var(--_bg-panel);
        border-bottom: 1px solid var(--_border);
        position: sticky;
        top: 0;
        z-index: 20;
        gap: 12px;
        min-height: 52px;
      }

      .topbar h1 {
        font-size: 1rem;
        font-weight: 600;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .topbar .user-area {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 0.75rem;
        color: var(--_text-secondary);
        flex-shrink: 0;
      }

      .topbar .user-area ::slotted(*),
      .topbar .user-area slot {
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .topbar button,
      .topbar a.btn-link {
        padding: 5px 12px;
        border: 1px solid var(--_border);
        border-radius: 6px;
        background: transparent;
        color: var(--_text-secondary);
        cursor: pointer;
        font-family: inherit;
        font-size: 0.7rem;
        transition: all 0.15s;
        text-decoration: none;
        display: inline-flex;
        align-items: center;
      }

      .topbar button:hover,
      .topbar a.btn-link:hover {
        border-color: var(--_accent);
        color: var(--_accent);
      }

      /* 移动端菜单按钮 */
      .menu-toggle {
        display: none;
        background: none;
        border: none;
        color: var(--_text);
        font-size: 1.3rem;
        cursor: pointer;
        padding: 4px 8px;
        line-height: 1;
      }

      .menu-overlay {
        display: none;
        position: fixed;
        inset: 0;
        background: rgba(0,0,0,0.5);
        z-index: 25;
      }

      /* ── 内容区 ── */
      .content {
        padding: 20px;
        flex: 1;
        overflow-y: auto;
      }

      /* ── 响应式 ── */
      @media (max-width: 1023px) {
        .sidebar { width: 180px; }
        .main { margin-left: 180px; }
      }

      @media (max-width: 767px) {
        .menu-toggle { display: block; }
        .sidebar {
          transform: translateX(-100%);
          width: 240px;
          box-shadow: 2px 0 16px rgba(0,0,0,0.4);
        }
        .sidebar.open { transform: translateX(0); }
        .menu-overlay.open { display: block; }
        .main { margin-left: 0; }
        .content { padding: 12px; }
        .topbar { padding: 10px 14px; }
      }

      @media (max-width: 480px) {
        .topbar h1 { font-size: 0.85rem; }
      }

      @media (prefers-reduced-motion: reduce) {
        .sidebar { transition: none; }
      }
    </style>

    <!-- 跳过链接 -->
    <a href="#app-content" class="skip-link" tabindex="0">跳到主内容</a>

    <!-- 遮罩层 -->
    <div class="menu-overlay" part="overlay"></div>

    <!-- 侧边栏 -->
    <nav class="sidebar" part="sidebar" role="navigation" aria-label="主导航">
      <div class="sb-header" part="sidebar-header">
        <span class="logo-icon" id="logo-icon">🏠</span>
        <div>
          <h2 id="sb-title">管理后台</h2>
          <div class="sub" id="sb-sub"></div>
        </div>
      </div>
      <div class="sb-nav" id="sb-nav" part="sidebar-nav"></div>
      <div class="sb-footer" id="sb-footer" part="sidebar-footer">V5.60 · PASETO</div>
    </nav>

    <!-- 主内容 -->
    <div class="main" part="main">
      <header class="topbar" part="topbar">
        <button class="menu-toggle" id="menu-toggle" aria-label="打开菜单">☰</button>
        <h1 id="page-title">📊 仪表盘</h1>
        <div class="user-area" part="user-area">
          <slot name="user-actions"></slot>
        </div>
      </header>
      <main class="content" id="app-content" part="content" role="main" aria-live="polite">
        <slot name="content"></slot>
      </main>
    </div>
  `;

  /* ==========================================
   * Web Component: <app-shell>
   * ========================================== */
  class AppShellElement extends HTMLElement {
    constructor() {
      super();
      this._navItems = [...DEFAULT_NAV_ITEMS];
      this._currentPath = '';
    }

    connectedCallback() {
      this.attachShadow({ mode: 'open' });
      this.shadowRoot.innerHTML = SHELL_HTML;

      // 读取属性
      this._appTitle = this.getAttribute('app-title') || '管理后台';
      this._userPhone = this.getAttribute('user-phone') || '';
      this._logoIcon = this.getAttribute('logo-icon') || '🏠';
      this._footerText = this.getAttribute('footer-text') || 'V5.60 · PASETO';

      // 解析 data-nav-items（JSON 格式）
      const navData = this.getAttribute('data-nav-items');
      if (navData) {
        try { this._navItems = JSON.parse(navData); } catch (_) {}
      }

      this._render();
      this._bindEvents();
    }

    disconnectedCallback() {
      // 清理
      const overlay = this.shadowRoot.querySelector('.menu-overlay');
      if (overlay) overlay.removeEventListener('click', this._closeMenu);
    }

    static get observedAttributes() {
      return ['app-title', 'user-phone', 'current-path', 'logo-icon', 'footer-text'];
    }

    attributeChangedCallback(name, oldVal, newVal) {
      if (oldVal === newVal) return;
      switch (name) {
        case 'app-title':
          this._appTitle = newVal;
          this._updateTitle();
          break;
        case 'user-phone':
          this._userPhone = newVal;
          break;
        case 'current-path':
          this._currentPath = newVal || '';
          this._updateActiveLink();
          this._updatePageTitle();
          break;
        case 'logo-icon':
          this._logoIcon = newVal;
          this._updateLogo();
          break;
        case 'footer-text':
          this._footerText = newVal;
          this._updateFooter();
          break;
      }
    }

    _render() {
      // 标题
      this._updateTitle();
      this._updateLogo();
      this._updateFooter();

      // 导航
      const nav = this.shadowRoot.getElementById('sb-nav');
      if (!nav) return;

      let html = '';
      let lastSection = null;

      for (const item of this._navItems) {
        // section 分隔符
        if (item.section && item.section !== lastSection) {
          if (lastSection !== null) html += '<div class="sb-divider" part="nav-divider"></div>';
          lastSection = item.section;
        }

        const isExternal = item.external || item.href;
        const href = isExternal ? (item.href || item.path) : ('#' + item.path.replace(/^\/+/, ''));

        html += `
          <a href="${href}" data-route="${item.path}" part="nav-link"
             ${isExternal ? 'target="_blank" rel="noopener"' : ''}
             tabindex="0" aria-label="${item.label}">
            <span class="ico" aria-hidden="true">${item.icon || '📄'}</span> ${item.label}
          </a>`;
      }

      nav.innerHTML = html;
    }

    _bindEvents() {
      const nav = this.shadowRoot.getElementById('sb-nav');
      const menuToggle = this.shadowRoot.getElementById('menu-toggle');
      const overlay = this.shadowRoot.querySelector('.menu-overlay');
      const sidebar = this.shadowRoot.querySelector('.sidebar');

      // 导航点击
      if (nav) {
        nav.addEventListener('click', (e) => {
          const link = e.target.closest('a');
          if (!link) return;

          const route = link.getAttribute('data-route');
          if (link.hasAttribute('target')) return; // 外部链接不拦截

          e.preventDefault();

          // 派发自定义事件
          this.dispatchEvent(new CustomEvent('app-navigate', {
            detail: { path: route, label: link.textContent.trim().replace(/^[^\s]+\s*/, '') },
            bubbles: true,
            composed: true,
          }));

          // 设置 hash
          location.hash = route.replace(/^\/+/, '');

          // 移动端关闭菜单
          this._closeMenu();
        });
      }

      // 移动端菜单切换
      this._closeMenu = () => {
        sidebar.classList.remove('open');
        overlay.classList.remove('open');
      };

      if (menuToggle) {
        menuToggle.addEventListener('click', () => {
          sidebar.classList.toggle('open');
          overlay.classList.toggle('open');
        });
      }

      if (overlay) {
        overlay.addEventListener('click', this._closeMenu);
      }
    }

    _updateTitle() {
      const el = this.shadowRoot.getElementById('sb-title');
      if (el) el.textContent = this._appTitle;
    }

    _updateLogo() {
      const el = this.shadowRoot.getElementById('logo-icon');
      if (el) el.textContent = this._logoIcon;
    }

    _updateFooter() {
      const el = this.shadowRoot.getElementById('sb-footer');
      if (el) el.textContent = this._footerText;
    }

    _updateActiveLink() {
      const nav = this.shadowRoot.getElementById('sb-nav');
      if (!nav) return;
      const clean = this._currentPath.replace(/^\/+|\/+$/g, '');
      nav.querySelectorAll('a').forEach(a => {
        const route = (a.getAttribute('data-route') || '').replace(/^\/+|\/+$/g, '');
        const active = route === clean || (route && clean.startsWith(route + '/'));
        a.classList.toggle('active', active);
        if (active) a.setAttribute('aria-current', 'page');
        else a.removeAttribute('aria-current');
      });
    }

    _updatePageTitle() {
      const el = this.shadowRoot.getElementById('page-title');
      if (!el) return;
      const item = this._navItems.find(n => n.path === this._currentPath);
      if (item) {
        el.textContent = `${item.icon || ''} ${item.label}`;
      }
    }

    // ── Public API ──

    /** 设置页面标题 */
    setTitle(title) {
      const el = this.shadowRoot.getElementById('page-title');
      if (el) el.textContent = title;
    }

    /** 更新导航项 */
    setNavItems(items) {
      this._navItems = items;
      this._render();
    }

    /** 获取内容区域 DOM 元素 */
    get contentEl() {
      return this.querySelector('[slot="content"]') || this.shadowRoot.getElementById('app-content');
    }
  }

  // 注册 Web Component（只注册一次）
  if (!customElements.get('app-shell')) {
    customElements.define('app-shell', AppShellElement);
  }

  /* ==========================================
   * 纯 JavaScript API（无需 Web Component）
   * ========================================== */
  const AppShell = {
    /**
     * 创建应用壳布局
     * @param {Object} opts
     * @param {HTMLElement} [opts.container] - 挂载容器
     * @param {string} [opts.title] - 应用标题
     * @param {string} [opts.subtitle] - 副标题
     * @param {string} [opts.footer] - 底部文字
     * @param {Array} [opts.navItems] - 自定义导航项
     * @param {Function} [opts.onNavigate] - 导航回调 (path, label) => void
     * @param {string} [opts.logoIcon] - Logo 图标
     * @param {string} [opts.userPhone] - 用户手机号
     * @param {Array<HTMLElement>} [opts.userActions] - 顶部栏右侧操作按钮/元素
     * @returns {{ shell: HTMLElement, sidebar: HTMLElement, topbar: HTMLElement, content: HTMLElement, setActive: Function, setTitle: Function, destroy: Function }}
     */
    create(opts = {}) {
      const {
        container = document.body,
        title = '管理后台',
        subtitle = '',
        footer = 'V5.60 · PASETO',
        navItems = DEFAULT_NAV_ITEMS,
        onNavigate = null,
        logoIcon = '🏠',
        userPhone = '',
        userActions = [],
      } = opts;

      const wrapper = document.createElement('div');
      wrapper.id = 'app-shell';
      wrapper.style.cssText = 'display:flex;min-height:100vh;min-height:100dvh;';

      // 侧边栏
      const sidebar = document.createElement('nav');
      sidebar.className = 'sidebar';
      sidebar.setAttribute('role', 'navigation');
      sidebar.setAttribute('aria-label', '主导航');
      sidebar.innerHTML = `
        <div class="sb-header">
          <span style="font-size:1.4rem;line-height:1">${logoIcon}</span>
          <div><h2 style="font-size:0.95rem;color:var(--accent, #c9973b);white-space:nowrap;margin:0">${title}</h2>
          ${subtitle ? `<div style="font-size:0.6rem;color:var(--text-muted, #5a5866);margin-top:2px">${subtitle}</div>` : ''}</div>
        </div>
        <div class="sb-nav" style="flex:1;overflow-y:auto;padding:8px 0"></div>
        <div class="sb-footer" style="padding:12px 16px;border-top:1px solid var(--border, #1e1e32);font-size:0.65rem;color:var(--text-muted, #5a5866)">${footer}</div>`;

      // 填充导航
      const navContainer = sidebar.querySelector('.sb-nav');
      let lastSection = null;
      for (const item of navItems) {
        if (item.section && item.section !== lastSection) {
          if (lastSection !== null) {
            const divider = document.createElement('div');
            divider.style.cssText = 'height:1px;background:var(--border, #1e1e32);margin:8px 12px';
            navContainer.appendChild(divider);
          }
          lastSection = item.section;
        }

        const isExternal = item.external || item.href;
        const a = document.createElement('a');
        a.setAttribute('data-route', item.path);
        a.setAttribute('aria-label', item.label);
        a.style.cssText = 'display:flex;align-items:center;gap:10px;padding:10px 16px;font-size:0.8rem;color:var(--text-secondary, #8a8894);transition:all 0.15s;border-left:3px solid transparent;text-decoration:none;cursor:pointer';
        a.innerHTML = `<span class="ico" style="font-size:0.95rem;width:22px;text-align:center">${item.icon || '📄'}</span> ${item.label}`;

        if (isExternal) {
          a.href = item.href || item.path;
          a.target = '_blank';
          a.rel = 'noopener';
        } else {
          a.href = '#' + item.path.replace(/^\/+/, '');
          a.addEventListener('click', (e) => {
            e.preventDefault();
            if (onNavigate) onNavigate(item.path, item.label);
            location.hash = item.path.replace(/^\/+/, '');
          });
        }

        // hover/active 样式通过事件
        a.addEventListener('mouseenter', () => {
          if (!a.classList.contains('active')) {
            a.style.color = 'var(--text-primary, #e8e6e1)';
            a.style.background = 'rgba(201,151,59,0.08)';
          }
        });
        a.addEventListener('mouseleave', () => {
          if (!a.classList.contains('active')) {
            a.style.color = '';
            a.style.background = '';
          }
        });

        navContainer.appendChild(a);
      }

      // 移动端菜单按钮
      const menuToggle = document.createElement('button');
      menuToggle.className = 'menu-toggle';
      menuToggle.setAttribute('aria-label', '打开菜单');
      menuToggle.textContent = '☰';
      menuToggle.style.cssText = 'display:none;background:none;border:none;color:var(--text-primary, #e8e6e1);font-size:1.3rem;cursor:pointer;padding:4px 8px;line-height:1';

      const overlay = document.createElement('div');
      overlay.className = 'menu-overlay';
      overlay.style.cssText = 'display:none;position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:25';

      const closeMenu = () => {
        sidebar.classList.remove('open');
        overlay.classList.remove('open');
      };

      menuToggle.addEventListener('click', () => {
        sidebar.classList.toggle('open');
        overlay.classList.toggle('open');
      });
      overlay.addEventListener('click', closeMenu);

      // 顶部栏
      const topbar = document.createElement('header');
      topbar.className = 'topbar';
      topbar.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:12px 20px;background:var(--bg-panel, #12121d);border-bottom:1px solid var(--border, #1e1e32);position:sticky;top:0;z-index:20;gap:12px;min-height:52px';
      topbar.innerHTML = `<h1 style="font-size:1rem;font-weight:600;margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">📊 ${title}</h1>`;

      const userArea = document.createElement('div');
      userArea.style.cssText = 'display:flex;align-items:center;gap:8px;font-size:0.75rem;color:var(--text-secondary, #8a8894);flex-shrink:0';
      if (userPhone) {
        const phoneSpan = document.createElement('span');
        phoneSpan.textContent = userPhone;
        userArea.appendChild(phoneSpan);
      }
      for (const actionEl of userActions) {
        if (actionEl instanceof HTMLElement) userArea.appendChild(actionEl);
      }
      topbar.appendChild(menuToggle);
      topbar.querySelector('h1').after(menuToggle);
      topbar.appendChild(userArea);

      // 内容区
      const content = document.createElement('main');
      content.className = 'content';
      content.id = 'app-content';
      content.setAttribute('role', 'main');
      content.setAttribute('aria-live', 'polite');
      content.style.cssText = 'padding:20px;flex:1;overflow-y:auto';

      // 主区域
      const main = document.createElement('div');
      main.className = 'main';
      main.style.cssText = 'flex:1;margin-left:220px;display:flex;flex-direction:column;min-height:100vh;min-height:100dvh';
      main.appendChild(topbar);
      main.appendChild(content);

      wrapper.appendChild(sidebar);
      wrapper.appendChild(overlay);
      wrapper.appendChild(main);

      container.appendChild(wrapper);

      // 注入 sidebar/topbar 响应式样式
      const styleEl = document.createElement('style');
      styleEl.textContent = `
        #app-shell .sidebar { width: 220px; background: var(--bg-panel, #12121d); border-right: 1px solid var(--border, #1e1e32); display: flex; flex-direction: column; flex-shrink: 0; position: fixed; top: 0; left: 0; bottom: 0; z-index: 30; transition: transform 0.25s cubic-bezier(0.4,0,0.2,1); }
        @media (max-width: 1023px) { #app-shell .sidebar { width: 180px; } #app-shell .main { margin-left: 180px; } }
        @media (max-width: 767px) {
          #app-shell .menu-toggle { display: block; }
          #app-shell .sidebar { transform: translateX(-100%); width: 240px; box-shadow: 2px 0 16px rgba(0,0,0,0.4); }
          #app-shell .sidebar.open { transform: translateX(0); }
          #app-shell .menu-overlay.open { display: block; }
          #app-shell .main { margin-left: 0; }
          #app-shell .content { padding: 12px; }
        }
      `;
      wrapper.appendChild(styleEl);

      // 返回 API
      return {
        shell: wrapper,
        sidebar,
        topbar,
        content,
        /** 设置当前激活的导航 */
        setActive(path) {
          const clean = (path || '').replace(/^\/+|\/+$/g, '');
          sidebar.querySelectorAll('a[data-route]').forEach(a => {
            const route = (a.getAttribute('data-route') || '').replace(/^\/+|\/+$/g, '');
            const active = route === clean || (route && clean.startsWith(route + '/'));
            if (active) {
              a.classList.add('active');
              a.style.color = 'var(--text-primary, #e8e6e1)';
              a.style.background = 'rgba(201,151,59,0.08)';
              a.style.borderLeftColor = 'var(--accent, #c9973b)';
              a.setAttribute('aria-current', 'page');
            } else {
              a.classList.remove('active');
              a.style.color = '';
              a.style.background = '';
              a.style.borderLeftColor = '';
              a.removeAttribute('aria-current');
            }
          });
          // 关闭移动端菜单
          if (window.innerWidth < 768) closeMenu();
        },
        /** 设置页面标题 */
        setTitle(titleText) {
          const h1 = topbar.querySelector('h1');
          if (h1) h1.textContent = titleText;
        },
        /** 销毁应用壳 */
        destroy() {
          wrapper.remove();
        },
      };
    },
  };

  // 暴露到全局
  window.AppShell = AppShell;
  window.AppShellElement = AppShellElement;

})();
