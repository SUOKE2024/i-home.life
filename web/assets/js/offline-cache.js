/* ============================================
 * 索克家居 · 离线缓存服务
 * 与 Flutter 端 OfflineCacheService 对齐
 * ============================================ */

const OfflineCache = {
  // ── 配置 ──

  // localStorage 前缀（与 Flutter 端 offline_cache_ 前缀对齐）
  _prefix: 'offline_cache_',
  // 缓存 TTL（毫秒），默认 30 分钟
  _ttlMs: 30 * 60 * 1000,

  // ── 数据缓存 ──

  /**
   * 缓存数据
   * @param {string} key - 缓存键
   * @param {*} data - 数据内容
   */
  cacheData(key, data) {
    try {
      const entry = {
        _ts: Date.now(),
        data,
      };
      localStorage.setItem(this._prefix + key, JSON.stringify(entry));
    } catch (e) {
      console.warn('[OfflineCache] 缓存写入失败:', e.message);
    }
  },

  /**
   * 读取缓存
   * @param {string} key - 缓存键
   * @returns {*|null} 过期返回 null
   */
  getCachedData(key) {
    try {
      const raw = localStorage.getItem(this._prefix + key);
      if (!raw) return null;
      const entry = JSON.parse(raw);
      if (Date.now() - entry._ts > this._ttlMs) {
        localStorage.removeItem(this._prefix + key);
        return null;
      }
      return entry.data;
    } catch (e) {
      return null;
    }
  },

  /**
   * 清除指定缓存
   * @param {string} key - 缓存键
   */
  removeCache(key) {
    localStorage.removeItem(this._prefix + key);
  },

  /**
   * 清除所有离线缓存
   */
  clearAll() {
    const keys = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.startsWith(this._prefix)) keys.push(k);
    }
    keys.forEach(k => localStorage.removeItem(k));
  },

  // ── 同步队列（离线操作排队，网络恢复后回放） ──

  _syncQueueKey: 'offline_sync_queue',

  /**
   * 将操作加入同步队列
   * @param {object} operation - {method, path, body}
   */
  enqueueSyncOperation(operation) {
    const queue = this.getSyncQueue();
    queue.push({ ...operation, _ts: Date.now() });
    localStorage.setItem(this._syncQueueKey, JSON.stringify(queue));
  },

  /**
   * 获取同步队列
   * @returns {Array}
   */
  getSyncQueue() {
    try {
      const raw = localStorage.getItem(this._syncQueueKey);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  },

  /**
   * 移除已完成的同步操作
   * @param {number} index - 操作在队列中的索引
   */
  removeSyncOperation(index) {
    const queue = this.getSyncQueue();
    queue.splice(index, 1);
    localStorage.setItem(this._syncQueueKey, JSON.stringify(queue));
  },

  /**
   * 清空同步队列
   */
  clearSyncQueue() {
    localStorage.removeItem(this._syncQueueKey);
  },

  /**
   * 回放同步队列中的所有操作
   * @returns {Promise<{success: number, failed: number}>}
   */
  async replaySyncQueue() {
    const queue = this.getSyncQueue();
    if (queue.length === 0) return { success: 0, failed: 0 };

    let success = 0, failed = 0;
    const toRemove = [];

    for (let i = 0; i < queue.length; i++) {
      const op = queue[i];
      try {
        const result = await ApiClient.safeRequest(op.path, {
          method: op.method || 'POST',
          body: op.body ? JSON.stringify(op.body) : undefined,
        });
        if (result.success) {
          toRemove.push(i);
          success++;
        } else {
          failed++;
        }
      } catch {
        failed++;
      }
    }

    // 从后往前删除，避免索引偏移
    for (let i = toRemove.length - 1; i >= 0; i--) {
      this.removeSyncOperation(toRemove[i]);
    }

    return { success, failed };
  },

  // ── 网络状态 ──

  /** 检查是否在线 */
  isOnline() {
    return navigator.onLine !== false;
  },

  /**
   * 注册网络状态变化监听
   * @param {Function} onOnline - 上线回调
   * @param {Function} onOffline - 离线回调
   */
  onNetworkChange(onOnline, onOffline) {
    window.addEventListener('online', () => {
      if (onOnline) onOnline();
      // 自动回放同步队列
      this.replaySyncQueue().then(result => {
        if (result.success > 0 || result.failed > 0) {
          console.log(`[OfflineCache] 同步队列回放: ${result.success} 成功, ${result.failed} 失败`);
        }
      });
    });
    window.addEventListener('offline', () => {
      if (onOffline) onOffline();
    });
  },
};

// 暴露到全局
window.OfflineCache = OfflineCache;
