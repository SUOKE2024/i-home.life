/* ============================================
 * 索克家居 · 基础组件库 (ComponentBase)
 * 提供: 状态管理 / 事件总线 / Toast / Modal
 *
 * 使用方式:
 *   <script src="assets/js/component-base.js"></script>
 *   然后通过全局对象 ComponentBase 调用:
 *   ComponentBase.Store, ComponentBase.Events,
 *   ComponentBase.toast(), ComponentBase.Modal
 * ============================================ */

'use strict';

(() => {

  /* ==========================================
   * 1. 事件总线 (发布/订阅模式)
   * ========================================== */
  class EventBus {
    constructor() {
      this._listeners = {};
    }

    /** 订阅事件 */
    on(event, fn, opts = {}) {
      if (typeof fn !== 'function') return () => {};
      const key = `${event}$${opts.priority || 0}`;
      if (!this._listeners[event]) this._listeners[event] = [];
      this._listeners[event].push({ fn, once: !!opts.once, key });
      return () => this.off(event, fn);
    }

    /** 订阅一次性事件 */
    once(event, fn) {
      return this.on(event, fn, { once: true });
    }

    /** 取消订阅 */
    off(event, fn) {
      if (!this._listeners[event]) return;
      if (!fn) { delete this._listeners[event]; return; }
      this._listeners[event] = this._listeners[event].filter(l => l.fn !== fn);
      if (!this._listeners[event].length) delete this._listeners[event];
    }

    /** 发布事件 */
    emit(event, detail = {}) {
      const listeners = this._listeners[event];
      if (!listeners || !listeners.length) return;

      // 快照防止回调中修改数组
      const snapshot = [...listeners];
      for (const l of snapshot) {
        try { l.fn(detail); } catch (e) { console.error(`[EventBus] ${event} handler error:`, e); }
        if (l.once) this.off(event, l.fn);
      }
    }

    /** 获取事件订阅数（调试用） */
    listenerCount(event) {
      return (this._listeners[event] || []).length;
    }

    /** 销毁所有订阅 */
    destroy() {
      this._listeners = {};
    }
  }

  /* ==========================================
   * 2. 简单状态管理
   * ========================================== */
  class Store {
    /**
     * @param {Object} initialState - 初始状态
     */
    constructor(initialState = {}) {
      this._state = { ...initialState };
      this._bus = new EventBus();
      this._prevState = {};
    }

    /** 获取状态（浅拷贝） */
    get state() {
      return { ...this._state };
    }

    /** 获取单个值 */
    get(key) {
      return this._state[key];
    }

    /**
     * 更新状态（浅合并）
     * @param {Object} partial - 部分状态更新
     */
    set(partial = {}) {
      this._prevState = { ...this._state };
      Object.assign(this._state, partial);
      for (const key of Object.keys(partial)) {
        if (this._prevState[key] !== this._state[key]) {
          this._bus.emit('change:' + key, { key, value: this._state[key], prev: this._prevState[key] });
        }
      }
      this._bus.emit('change', { state: this.state, prev: this._prevState });
    }

    /** 重置为初始状态 */
    reset(initialState = {}) {
      this._prevState = { ...this._state };
      this._state = { ...initialState };
      this._bus.emit('reset', { state: this.state });
    }

    /** 订阅状态变化 */
    onChange(fn) {
      return this._bus.on('change', fn);
    }

    /** 订阅特定 key 变化 */
    onKeyChange(key, fn) {
      return this._bus.on('change:' + key, fn);
    }

    /** 销毁 */
    destroy() {
      this._bus.destroy();
      this._state = {};
    }
  }

  /* ==========================================
   * 3. Toast 通知组件
   * ========================================== */
  const Toast = {
    _container: null,
    _timer: null,
    _defaultDuration: 3000,

    /** 确保容器存在 */
    _ensureContainer() {
      if (this._container && document.body.contains(this._container)) return;
      // 尝试复用已有的 .toast-container
      let el = document.querySelector('.toast-container');
      if (!el) {
        el = document.createElement('div');
        el.className = 'toast-container';
        el.setAttribute('role', 'status');
        el.setAttribute('aria-live', 'polite');
        document.body.appendChild(el);
      }
      this._container = el;
    },

    /**
     * 显示 Toast 通知
     * @param {string} message - 消息内容
     * @param {'success'|'error'|'warning'|'info'} [type='info'] - 通知类型
     * @param {number} [duration=3000] - 显示时长(ms)
     */
    show(message, type = 'info', duration) {
      this._ensureContainer();

      const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
      const item = document.createElement('div');
      item.className = `toast-item toast-${type}`;
      item.innerHTML = `<span class="toast-icon" aria-hidden="true">${icons[type] || icons.info}</span><span>${String(message)}</span>`;

      // 点击关闭
      item.addEventListener('click', () => this._dismiss(item));

      this._container.appendChild(item);

      // 触发动画
      requestAnimationFrame(() => {
        requestAnimationFrame(() => item.classList.add('show'));
      });

      // 自动关闭
      const dur = duration != null ? duration : this._defaultDuration;
      if (dur > 0) {
        const timer = setTimeout(() => this._dismiss(item), dur);
        item._dismissTimer = timer;
      }

      return item;
    },

    _dismiss(item) {
      if (!item || !item.classList) return;
      if (item._dismissTimer) clearTimeout(item._dismissTimer);
      item.classList.remove('show');
      item.addEventListener('transitionend', () => {
        if (item.parentNode) item.parentNode.removeChild(item);
      }, { once: true });
      // 兜底清理
      setTimeout(() => {
        if (item.parentNode) item.parentNode.removeChild(item);
      }, 400);
    },

    /** 快捷方法: 成功 */
    success(msg, dur) { return this.show(msg, 'success', dur); },

    /** 快捷方法: 错误 */
    error(msg, dur) { return this.show(msg, 'error', dur); },

    /** 快捷方法: 警告 */
    warning(msg, dur) { return this.show(msg, 'warning', dur); },

    /** 快捷方法: 信息 */
    info(msg, dur) { return this.show(msg, 'info', dur); },

    /** 清除所有 Toast */
    clear() {
      if (!this._container) return;
      while (this._container.firstChild) {
        this._dismiss(this._container.firstChild);
      }
    },
  };

  /* ==========================================
   * 4. Modal 弹窗组件
   * ========================================== */
  class Modal {
    /**
     * @param {Object} options
     * @param {string} [options.title] - 标题
     * @param {string|HTMLElement} [options.content] - 内容
     * @param {Array<{text:string, type:string, onClick:Function}>} [options.buttons] - 底部按钮
     * @param {boolean} [options.closeOnOverlay=true] - 点击遮罩关闭
     * @param {boolean} [options.closeOnEsc=true] - ESC 关闭
     * @param {string} [options.size] - 'sm' | 'md' | 'lg'
     */
    constructor(options = {}) {
      this.options = {
        closeOnOverlay: true,
        closeOnEsc: true,
        size: 'md',
        ...options,
      };
      this._el = null;
      this._visible = false;
      this._onEsc = (e) => {
        if (e.key === 'Escape' && this._visible) this.close();
      };
    }

    /** 创建 DOM */
    _build() {
      const sizes = { sm: '360px', md: '480px', lg: '640px' };
      const width = sizes[this.options.size] || sizes.md;

      const overlay = document.createElement('div');
      overlay.className = 'modal-overlay';
      overlay.innerHTML = `
        <div class="modal-card" style="max-width:${width}" role="dialog" aria-modal="true" aria-labelledby="modal-title-${Date.now()}">
          <div class="modal-header">
            <h3 id="modal-title-${Date.now()}">${this.options.title || ''}</h3>
            <button class="modal-close" aria-label="关闭">✕</button>
          </div>
          <div class="modal-body"></div>
          ${this.options.buttons ? '<div class="modal-footer"></div>' : ''}
        </div>`;

      this._el = overlay;

      // 关闭按钮
      overlay.querySelector('.modal-close').addEventListener('click', () => this.close());

      // 内容
      const body = overlay.querySelector('.modal-body');
      if (typeof this.options.content === 'string') {
        body.innerHTML = this.options.content;
      } else if (this.options.content instanceof HTMLElement) {
        body.appendChild(this.options.content);
      }

      // 按钮
      if (this.options.buttons) {
        const footer = overlay.querySelector('.modal-footer');
        for (const btn of this.options.buttons) {
          const el = document.createElement('button');
          el.className = `btn ${btn.type === 'primary' ? 'btn-primary' : btn.type === 'danger' ? 'btn-danger' : 'btn-ghost'}`;
          el.textContent = btn.text;
          el.addEventListener('click', async (e) => {
            if (btn.onClick) {
              const result = btn.onClick(e);
              // 如果返回 false，不自动关闭
              if (result === false) return;
              if (result instanceof Promise) {
                try { const resolved = await result; if (resolved === false) return; } catch (_) { return; }
              }
            }
            this.close();
          });
          footer.appendChild(el);
        }
      }

      // 遮罩点击
      if (this.options.closeOnOverlay) {
        overlay.addEventListener('click', (e) => {
          if (e.target === overlay) this.close();
        });
      }
    },

    /** 打开 Modal */
    open() {
      if (this._visible) return;
      if (!this._el) this._build();

      document.body.appendChild(this._el);
      document.body.style.overflow = 'hidden';

      this._visible = true;

      requestAnimationFrame(() => {
        requestAnimationFrame(() => this._el.classList.add('open'));
      });

      if (this.options.closeOnEsc) {
        document.addEventListener('keydown', this._onEsc);
      }

      return this;
    },

    /** 关闭 Modal */
    close() {
      if (!this._visible || !this._el) return;

      this._visible = false;
      this._el.classList.remove('open');

      document.removeEventListener('keydown', this._onEsc);
      document.body.style.overflow = '';

      this._el.addEventListener('transitionend', () => {
        if (this._el && this._el.parentNode) {
          this._el.parentNode.removeChild(this._el);
        }
      }, { once: true });

      // 兜底清理
      setTimeout(() => {
        if (this._el && this._el.parentNode) {
          this._el.parentNode.removeChild(this._el);
        }
      }, 400);
    },

    /** 切换 */
    toggle() {
      if (this._visible) this.close();
      else this.open();
    },

    /** 销毁 */
    destroy() {
      this.close();
      this._el = null;
    },

    // ── 静态快捷方法 ──

    /** 确认对话框 */
    static confirm(title, message, onConfirm, onCancel) {
      const modal = new Modal({
        title: title || '确认操作',
        content: `<p>${message || '确定要执行此操作吗？'}</p>`,
        buttons: [
          { text: '取消', type: 'ghost', onClick: () => { if (onCancel) onCancel(); } },
          { text: '确定', type: 'primary', onClick: () => { if (onConfirm) onConfirm(); } },
        ],
      });
      return modal.open();
    },

    /** 提示对话框 */
    static alert(title, message) {
      const modal = new Modal({
        title: title || '提示',
        content: `<p>${message || ''}</p>`,
        buttons: [{ text: '知道了', type: 'primary' }],
      });
      return modal.open();
    },
  }

  /* ==========================================
   * 暴露到全局
   * ========================================== */
  const api = {
    EventBus,
    Store,
    Toast,
    Modal,
    // 全局共享的单例
    events: new EventBus(),
    store: new Store(),
  };

  // 兼容：如果已有 ComponentBase，合并而非覆盖
  if (window.ComponentBase) {
    Object.assign(window.ComponentBase, api);
  } else {
    window.ComponentBase = api;
  }

})();
