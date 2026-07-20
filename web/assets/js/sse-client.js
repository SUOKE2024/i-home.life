/* ============================================
 * 索克家居 · SSE 流式客户端
 * 与 Flutter 端 SseService 对齐
 *
 * 协议格式：data: {"event": "meta"|"token"|"done", ...}\n\n
 * ============================================ */

const SseClient = {
  // ── 事件类型（与 Flutter SseEventType 对齐） ──

  EventType: {
    META: 'meta',
    TOKEN: 'token',
    DONE: 'done',
  },

  // ── SSE 流式请求 ──

  /**
   * 发起 SSE 流式连接
   * @param {string} path - API 路径（如 /api/agents/chat）
   * @param {object} body - 请求体
   * @param {object} callbacks - 事件回调 {onMeta, onToken, onDone, onError}
   * @returns {object} { abort } - 返回中止函数
   */
  async connect(path, body = {}, callbacks = {}) {
    const { onMeta, onToken, onDone, onError } = callbacks;

    const token = localStorage.getItem('paseto_token') || '';
    const controller = new AbortController();

    try {
      const res = await fetch(path, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!res.ok) {
        let errMsg = `HTTP ${res.status}`;
        try {
          const errBody = await res.json();
          errMsg = errBody.detail || errMsg;
        } catch (_) {}
        if (onError) onError(new Error(errMsg));
        if (onDone) onDone({});
        return { abort: () => {} };
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let doneReceived = false;

      const processLine = (line) => {
        if (!line.startsWith('data: ')) return;
        const jsonStr = line.substring(6).trim();
        if (!jsonStr) return;
        try {
          const event = JSON.parse(jsonStr);
          switch (event.event) {
            case 'meta':
              if (onMeta) onMeta(event);
              break;
            case 'token':
              if (onToken) onToken(event);
              break;
            case 'done':
              doneReceived = true;
              if (onDone) onDone(event);
              break;
            default:
              // 未知事件类型，作为 token 处理
              if (onToken) onToken(event);
          }
        } catch (_) {
          // 非 JSON 行（如注释行 ": heartbeat"），忽略
        }
      };

      // 持续读取流
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // 按 \n\n 分割事件
        const parts = buffer.split('\n\n');
        buffer = parts.pop(); // 最后一个可能不完整，保留在 buffer

        for (const part of parts) {
          const lines = part.split('\n');
          for (const line of lines) {
            processLine(line.trim());
          }
        }
      }

      // 处理剩余 buffer
      if (buffer.trim()) {
        const lines = buffer.split('\n');
        for (const line of lines) {
          processLine(line.trim());
        }
      }

      // 如果后端未发送 done 事件，自动补发
      if (!doneReceived) {
        if (onDone) onDone({ event: 'done', auto: true });
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        // 用户主动取消，不报错
        return { abort: () => {} };
      }
      if (onError) onError(err);
      if (onDone) onDone({ event: 'done', error: err.message });
    }

    return {
      abort: () => controller.abort(),
    };
  },

  // ── 便捷方法 ──

  /**
   * Agent 聊天流式请求
   * @param {string} message - 用户消息
   * @param {string} agentType - Agent 类型
   * @param {string|null} projectId - 项目 ID
   * @param {object} callbacks - 同 connect
   */
  chatStream(message, agentType = 'orchestrator', projectId = null, callbacks = {}) {
    const body = { message, agent_type: agentType };
    if (projectId) body.project_id = projectId;
    return this.connect('/api/agents/chat', body, callbacks);
  },

  /**
   * 预算生成流式请求
   * @param {string} message - 用户需求描述
   * @param {object} callbacks - 同 connect
   */
  budgetStream(message, callbacks = {}) {
    return this.connect('/api/budgets/generate-plan', { message }, callbacks);
  },

  /**
   * AI 渲染流式请求
   * @param {object} body - 渲染参数
   * @param {object} callbacks - 同 connect
   */
  renderStream(body, callbacks = {}) {
    return this.connect('/api/ai-render/2d', body, callbacks);
  },
};

// 暴露到全局
window.SseClient = SseClient;
