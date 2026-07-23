/* ============================================
 * 索克家居 · IM WebSocket 客户端
 * 适配后端契约：{ event: string, data: object }
 * 端点：/ws/{project_id}?token=PASETO
 * 项目约定：跨端同步 < 3 秒
 * ============================================ */

const IMClient = {
  ws: null,
  url: '',
  token: '',
  projectId: '',
  currentUserId: '',
  reconnectAttempts: 0,
  maxReconnect: 5,
  reconnectDelay: 1000,
  reconnectTimer: null,
  // 事件订阅：{ event: [callback, ...] }
  listeners: {},
  statusCallbacks: [],
  // 已渲染消息 ID 集合（防重复回推）
  renderedIds: new Set(),

  // 后端 BASE URL（与 ApiClient 一致）
  _baseUrl() {
    if (window.ApiClient && ApiClient.BASE_URL) return ApiClient.BASE_URL;
    return window.location.hostname === 'localhost'
      ? (window.API_BASE_URL || '')
      : '';
  },

  // 建立 WebSocket 连接
  connect(paseto, projectId, currentUserId = '') {
    this.token = paseto;
    this.projectId = projectId;
    this.currentUserId = currentUserId;
    const base = this._baseUrl();
    // http(s) → ws(s)
    const wsBase = base
      .replace(/^http:/, 'ws:')
      .replace(/^https:/, 'wss:');
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // 若 base 为空（同源），用当前 host
    const host = wsBase || `${protocol}//${window.location.host}`;
    this.url = `${host}/ws/${encodeURIComponent(projectId)}?token=${encodeURIComponent(paseto)}`;

    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
          this.reconnectAttempts = 0;
          this._notifyStatus('connected');
          // 等待服务端 "connected" 事件后再 resolve
          // 兜底：1 秒后无论如何 resolve（避免卡死）
          setTimeout(() => resolve(), 1000);
        };

        this.ws.onmessage = (event) => {
          try {
            const raw = JSON.parse(event.data);
            // 后端格式：{ event: string, data: object }
            const evt = raw.event || 'message';
            const data = raw.data || {};
            if (evt === 'connected') {
              // 连接确认
              return;
            }
            this._dispatch(evt, data);
          } catch (e) {
            console.warn('IMClient: 解析消息失败', e);
          }
        };

        this.ws.onerror = (err) => {
          console.error('IMClient: WebSocket 错误', err);
          this._notifyStatus('error');
        };

        this.ws.onclose = () => {
          this._notifyStatus('disconnected');
          this._scheduleReconnect();
        };
      } catch (e) {
        reject(e);
      }
    });
  },

  // 订阅事件
  on(event, callback) {
    if (!this.listeners[event]) this.listeners[event] = [];
    this.listeners[event].push(callback);
    return () => this.off(event, callback);
  },
  off(event, callback) {
    const arr = this.listeners[event];
    if (!arr) return;
    const idx = arr.indexOf(callback);
    if (idx >= 0) arr.splice(idx, 1);
  },
  _dispatch(event, data) {
    const arr = this.listeners[event] || [];
    arr.forEach(cb => {
      try { cb(data); } catch (e) { console.error('IMClient: 回调异常', e); }
    });
  },

  // 发送原始消息（{ event, data }）
  _send(event, data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ event, data }));
      return true;
    }
    console.warn('IMClient: 连接未就绪，无法发送');
    return false;
  },

  // 发送聊天消息（客户端广播；持久化应通过 REST POST /api/chat/messages）
  sendChatMessage(content, messageType = 'text', mentions = []) {
    return this._send('chat.message', {
      content,
      message_type: messageType,
      mentions,
    });
  },

  // 注册状态回调（兼容旧接口）
  onStatusChange(callback) {
    this.statusCallbacks.push(callback);
  },
  _notifyStatus(status) {
    this.statusCallbacks.forEach(cb => {
      try { cb(status); } catch (e) { console.error('IMClient: 状态回调异常', e); }
    });
  },

  // 标记消息已渲染（防回推重复）
  markRendered(messageId) {
    if (messageId) this.renderedIds.add(messageId);
  },
  hasRendered(messageId) {
    return messageId && this.renderedIds.has(messageId);
  },

  // 重连调度
  _scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnect) {
      this._notifyStatus('failed');
      console.warn('IMClient: 已达最大重连次数，停止重连');
      return;
    }
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
    console.log(`IMClient: ${delay}ms 后重连（第 ${this.reconnectAttempts} 次）`);
    this._notifyStatus('reconnecting');
    this.reconnectTimer = setTimeout(() => {
      if (this.token && this.projectId) {
        this.connect(this.token, this.projectId, this.currentUserId);
      }
    }, delay);
  },

  // 主动关闭
  close() {
    this.maxReconnect = 0; // 阻止重连
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.onclose = null; // 避免触发重连
      this.ws.close();
      this.ws = null;
    }
  },
};

// 暴露到全局
window.IMClient = IMClient;
