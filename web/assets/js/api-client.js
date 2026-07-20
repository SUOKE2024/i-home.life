/* ============================================
 * 索克家居 · API 客户端（PASETO 认证）
 * 项目约定：不用 JWT，使用 PASETO
 * 部署后同源调用，无需硬编码地址
 * ============================================ */

const ApiClient = {
  // 后端 BASE URL（部署后同源，localhost 开发时使用环境变量或默认地址）
  BASE_URL: (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? (window.API_BASE_URL || '')
    : '',

  // PASETO 令牌存储
  getToken() {
    return localStorage.getItem('paseto_token') || '';
  },
  setToken(token) {
    localStorage.setItem('paseto_token', token);
  },
  clearToken() {
    localStorage.removeItem('paseto_token');
    localStorage.removeItem('user_info');
  },

  // 构建完整 URL
  _url(path) {
    if (path.startsWith('http')) return path;
    return this.BASE_URL + (path.startsWith('/') ? path : '/' + path);
  },

  // 基础请求封装（Agent LLM 调用默认 180s 超时，其他 30s）
  async request(path, options = {}) {
    const token = this.getToken();
    const headers = {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    // 自动超时：Agent 端点 180s，其他 30s
    const isAgentCall = path.includes('/api/agents/');
    const timeoutMs = options.timeout || (isAgentCall ? 180000 : 30000);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(this._url(path), {
        ...options,
        headers,
        signal: controller.signal,
      });
      if (res.status === 401) {
        this.clearToken();
        window.location.href = '/login.html';
        throw new Error('认证过期，请重新登录');
      }
      return this._handleResponse(res);
    } catch (err) {
      if (err.name === 'AbortError') {
        throw new Error(`请求超时（${Math.round(timeoutMs / 1000)}秒），请稍后重试`);
      }
      throw err;
    } finally {
      clearTimeout(timer);
    }
  },

  async _handleResponse(res) {
    if (!res.ok) {
      const err = new Error(`HTTP ${res.status}`);
      err.status = res.status;
      try { err.body = await res.json(); } catch (_) { err.body = null; }
      throw err;
    }
    return res.json();
  },

  // 认证：登录（phone + password）
  async login(phone, password) {
    const data = await this.request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ phone, password }),
    });
    if (data.access_token) {
      this.setToken(data.access_token);
      if (data.user) {
        localStorage.setItem('user_info', JSON.stringify(data.user));
      }
    }
    return data;
  },

  // 认证：注册（后端返回 TokenResponse，注册即登录）
  async register(phone, password, name, role = 'homeowner', subRole = null) {
    const body = { phone, password, name, role };
    if (subRole) body.sub_role = subRole;
    const data = await this.request('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    if (data.access_token) {
      this.setToken(data.access_token);
      if (data.user) {
        localStorage.setItem('user_info', JSON.stringify(data.user));
      }
    }
    return data;
  },

  // 当前用户
  async getCurrentUser() {
    const cached = localStorage.getItem('user_info');
    if (cached) {
      try { return JSON.parse(cached); } catch (_) {}
    }
    const data = await this.request('/api/auth/me');
    if (data.id) {
      localStorage.setItem('user_info', JSON.stringify(data));
      return data;
    }
    return data;
  },

  // ── WebAuthn / FIDO2 / Passkey ──

  // 注册：开始
  async webauthnRegisterBegin(deviceName) {
    return this.request('/api/auth/webauthn/register/begin', {
      method: 'POST',
      body: JSON.stringify({ device_name: deviceName }),
    });
  },

  // 注册：完成
  async webauthnRegisterComplete(params) {
    return this.request('/api/auth/webauthn/register/complete', {
      method: 'POST',
      body: JSON.stringify({
        credential: params.credential,
        device_name: params.device_name,
        transports: params.transports,
      }),
    });
  },

  // 登录：开始（获取挑战）
  async webauthnLoginBegin(phone) {
    return this.request('/api/auth/webauthn/login/begin', {
      method: 'POST',
      body: JSON.stringify({ phone: phone || null }),
    });
  },

  // 登录：完成（验证断言，返回 PASETO Token）
  async webauthnLoginComplete(credential) {
    const data = await this.request('/api/auth/webauthn/login/complete', {
      method: 'POST',
      body: JSON.stringify({ credential: credential }),
    });
    if (data.access_token) {
      this.setToken(data.access_token);
      if (data.user) {
        localStorage.setItem('user_info', JSON.stringify(data.user));
      }
    }
    return data;
  },

  // 列出当前用户的 Passkey
  async listPasskeys() {
    return this.request('/api/auth/webauthn/credentials');
  },

  // 删除 Passkey
  async deletePasskey(credentialId) {
    return this.request(`/api/auth/webauthn/credentials/${credentialId}`, {
      method: 'DELETE',
    });
  },

  // 别名：与 WebAuthn 契约命名对齐（等价于 listPasskeys / deletePasskey）
  async listWebauthnCredentials() {
    return this.listPasskeys();
  },
  async deleteWebauthnCredential(credentialId) {
    return this.deletePasskey(credentialId);
  },

  // 项目列表（后端返回数组）
  async getProjects() {
    const data = await this.request('/api/projects');
    return Array.isArray(data) ? data : (data.items || []);
  },

  // 项目详情
  async getProject(projectId) {
    return this.request(`/api/projects/${projectId}`);
  },

  // 创建项目
  async createProject(data) {
    return this.request('/api/projects', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // 更新项目
  async updateProject(projectId, data) {
    return this.request(`/api/projects/${projectId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  // 删除项目
  async deleteProject(projectId) {
    return this.request(`/api/projects/${projectId}`, {
      method: 'DELETE',
    });
  },

  // Agent 通用聊天（自然语言路由）
  async chat(message, agentType = 'orchestrator', projectId = null) {
    const body = { message, agent_type: agentType };
    if (projectId) body.project_id = projectId;
    return this.request('/api/agents/chat', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  },

  // Agent 聊天（支持多轮对话历史）
  async chatWithAgent(message, agentType = 'orchestrator', projectId = null, history = []) {
    const body = { message, agent_type: agentType };
    if (projectId) body.project_id = projectId;
    if (history && history.length > 0) body.history = history;
    return this.request('/api/agents/chat', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  },

  // L4 自适应学习：Agent 反馈
  async submitAgentFeedback(data) {
    return this.request('/api/agents/feedback', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // 各专业 Agent
  async chatDesign(message, projectId = null) {
    return this.request('/api/agents/design', {
      method: 'POST',
      body: JSON.stringify({ message, project_id: projectId }),
    });
  },
  async chatBudget(message, projectId = null) {
    return this.request('/api/agents/budget', {
      method: 'POST',
      body: JSON.stringify({ message, project_id: projectId }),
    });
  },
  async chatProcurement(message, projectId = null) {
    return this.request('/api/agents/procurement', {
      method: 'POST',
      body: JSON.stringify({ message, project_id: projectId }),
    });
  },
  async chatConstruction(message, projectId = null) {
    return this.request('/api/agents/construction', {
      method: 'POST',
      body: JSON.stringify({ message, project_id: projectId }),
    });
  },

  // 施工任务
  async getConstructionTasks(projectId) {
    return this.request(`/api/construction/tasks/${projectId}`);
  },
  // 施工日志
  async getConstructionLogs(taskId) {
    return this.request(`/api/construction/logs/${taskId}`);
  },
  // 质检
  async getInspections(taskId) {
    return this.request(`/api/construction/inspections/${taskId}`);
  },
  // 进度预警
  async getProgressAlerts(projectId) {
    return this.request(`/api/construction/progress-alerts/${projectId}`);
  },
  // 里程碑
  async getMilestones(projectId) {
    return this.request(`/api/construction/milestones/${projectId}`);
  },
  // 质量问题
  async getQualityIssues(projectId) {
    return this.request(`/api/construction/quality-issues/${projectId}`);
  },
  // 获取项目所有任务的质检记录（聚合）
  async getProjectInspections(projectId) {
    const tasks = await this.getConstructionTasks(projectId);
    const taskList = Array.isArray(tasks) ? tasks : (tasks.items || []);
    const allInspections = [];
    for (const task of taskList) {
      try {
        const inspections = await this.getInspections(task.id);
        const list = Array.isArray(inspections) ? inspections : [];
        list.forEach(inv => { inv._task_id = task.id; inv._task_name = task.title || task.name || ''; });
        allInspections.push(...list);
      } catch (_) { /* 任务无质检记录时跳过 */ }
    }
    return allInspections;
  },
  // F38 AI 图像质检分析
  async analyzeInspectionImages(data) {
    return this.request('/api/construction/inspections/analyze', {
      method: 'POST', body: JSON.stringify(data),
    });
  },
  // 创建质检记录
  async createInspection(data) {
    return this.request('/api/construction/inspections', {
      method: 'POST', body: JSON.stringify(data),
    });
  },

  // 申领任务
  async claimTask(taskId) {
    return this.request('/api/tasks/claim', {
      method: 'POST', body: JSON.stringify({ task_id: taskId }),
    });
  },
  // 项目关联任务
  async getProjectTasks(projectId) {
    return this.request(`/api/tasks/project/${projectId}`);
  },

  // 预算
  async getBudget(projectId) {
    return this.request(`/api/budgets/project/${projectId}`);
  },
  // 创建预算
  async createBudget(data) {
    return this.request('/api/budgets', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },
  // 从 BOM 物料清单生成预算
  async generateBudgetFromBom(projectId) {
    return this.request(`/api/budgets/generate-from-bom/${projectId}`, {
      method: 'POST',
    });
  },
  // F10 AI 分项预算
  async generateBudgetPlan(message) {
    return this.request('/api/budgets/generate-plan', {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
  },
  // F11 多方案预算对比
  async compareBudgetPlans(message) {
    return this.request('/api/budgets/compare-plans', {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
  },
  // F12 预算差异检查
  async budgetVarianceCheck(data) {
    return this.request('/api/budgets/variance-check', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },
  // F13 预算模板库
  async listBudgetTemplates() {
    return this.request('/api/budgets/templates');
  },
  // F13 应用预算模板
  async applyBudgetTemplate(templateCode, area = null) {
    return this.request('/api/budgets/templates/apply', {
      method: 'POST',
      body: JSON.stringify({ template_code: templateCode, area }),
    });
  },
  // 更新预算行
  async updateBudgetLine(lineId, data) {
    return this.request(`/api/budgets/lines/${lineId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  // 采购订单
  async getProcurementOrders(projectId) {
    return this.request(`/api/procurement/orders/${projectId}`);
  },
  async getProcurementOrder(orderId) {
    return this.request(`/api/procurement/orders/detail/${orderId}`);
  },
  async createProcurementOrder(data) {
    return this.request('/api/procurement/orders', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },
  async updateProcurementOrder(orderId, data) {
    return this.request(`/api/procurement/orders/${orderId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },
  async updateOrderStatus(orderId, statusVal) {
    return this.request(`/api/procurement/orders/${orderId}/status?status=${encodeURIComponent(statusVal)}`, {
      method: 'PATCH',
    });
  },
  async deleteProcurementOrder(orderId) {
    return this.request(`/api/procurement/orders/${orderId}`, {
      method: 'DELETE',
    });
  },
  // 采购报价
  async getQuotations(projectId) {
    return this.request(`/api/procurement/quotations/${projectId}`);
  },
  async createQuotation(data) {
    return this.request('/api/procurement/quotations', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },
  // 供应商
  async getSuppliers() {
    return this.request('/api/procurement/suppliers');
  },
  async createSupplier(data) {
    return this.request('/api/procurement/suppliers', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },
  // 比价
  async compareQuotes(data) {
    return this.request('/api/procurement/compare', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // ============ F33/F34 采购增强 ============

  // F33 从 BOM 生成比价报告
  async createComparison(projectId, bomId = null) {
    return this.request('/api/procurement-enhanced/comparisons', {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId, bom_id: bomId }),
    });
  },
  // F33 项目比价报告列表
  async getProjectComparisons(projectId) {
    return this.request(`/api/procurement-enhanced/comparisons/project/${projectId}`);
  },
  // F33 比价报告详情
  async getComparison(comparisonId) {
    return this.request(`/api/procurement-enhanced/comparisons/${comparisonId}`);
  },
  // F33 AI 供应商匹配
  async aiMatchSuppliers(bomItemId, location = null) {
    return this.request('/api/procurement-enhanced/ai-match', {
      method: 'POST',
      body: JSON.stringify({ bom_item_id: bomItemId, location }),
    });
  },
  // F33 删除比价报告
  async deleteComparison(comparisonId) {
    return this.request(`/api/procurement-enhanced/comparisons/${comparisonId}`, {
      method: 'DELETE',
    });
  },

  // F34 创建担保支付
  async createEscrow(orderId) {
    return this.request('/api/procurement-enhanced/escrow', {
      method: 'POST',
      body: JSON.stringify({ order_id: orderId }),
    });
  },
  // F34 担保支付详情
  async getEscrow(escrowId) {
    return this.request(`/api/procurement-enhanced/escrow/${escrowId}`);
  },
  // F34 按订单查询担保支付
  async getOrderEscrow(orderId) {
    return this.request(`/api/procurement-enhanced/escrow/order/${orderId}`);
  },
  // F34 按项目查询担保支付
  async getEscrowPaymentsByProject(projectId) {
    return this.request(`/api/procurement-enhanced/escrow/project/${projectId}`);
  },
  // F34 买家付款
  async buyerPayEscrow(escrowId) {
    return this.request(`/api/procurement-enhanced/escrow/${escrowId}/pay`, { method: 'POST' });
  },
  // F34 释放资金给供应商
  async releaseEscrow(escrowId) {
    return this.request(`/api/procurement-enhanced/escrow/${escrowId}/release`, { method: 'POST' });
  },
  // F34 申请退款
  async refundEscrow(escrowId, reason) {
    return this.request(`/api/procurement-enhanced/escrow/${escrowId}/refund`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    });
  },
  // F34 发起争议
  async disputeEscrow(escrowId, reason) {
    return this.request(`/api/procurement-enhanced/escrow/${escrowId}/dispute`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    });
  },
  // F34 解决争议（refunded / supplier_received）
  async resolveEscrow(escrowId, resolution) {
    return this.request(`/api/procurement-enhanced/escrow/${escrowId}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ resolution }),
    });
  },

  // F34 创建物流单
  async createLogistics(orderId, carrier, shipFrom = null, shipTo = null) {
    return this.request('/api/procurement-enhanced/logistics', {
      method: 'POST',
      body: JSON.stringify({ order_id: orderId, carrier, ship_from: shipFrom, ship_to: shipTo }),
    });
  },
  // F34 物流详情
  async getLogistics(trackingId) {
    return this.request(`/api/procurement-enhanced/logistics/${trackingId}`);
  },
  // F34 更新物流轨迹
  async updateLogistics(trackingId, data) {
    return this.request(`/api/procurement-enhanced/logistics/${trackingId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },
  // F34 按订单查询物流
  async getOrderLogistics(orderId) {
    return this.request(`/api/procurement-enhanced/logistics/order/${orderId}`);
  },
  // F34 按项目查询物流追踪
  async getLogisticsByProject(projectId) {
    return this.request(`/api/procurement-enhanced/logistics/project/${projectId}`);
  },

  // F34 样品索要
  async createSample(projectId, supplierId, materialId = null, sampleType = '实物') {
    return this.request('/api/procurement-enhanced/samples', {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId, supplier_id: supplierId, material_id: materialId, sample_type: sampleType }),
    });
  },
  // F34 项目样品列表
  async getProjectSamples(projectId) {
    return this.request(`/api/procurement-enhanced/samples/project/${projectId}`);
  },
  // F34 更新样品状态
  async updateSample(sampleId, status, notes = null) {
    const body = { status };
    if (notes !== null) body.notes = notes;
    return this.request(`/api/procurement-enhanced/samples/${sampleId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    });
  },

  // 结算
  async getSettlement(projectId) {
    return this.request(`/api/settlements/project/${projectId}`);
  },

  // ============ F15 支付管理 ============

  // 项目支付记录列表
  async getPayments(projectId) {
    return this.request(`/api/payments/project/${projectId}`);
  },

  // 发起支付（分阶段支付节点）
  async createPayment(data) {
    return this.request('/api/payments', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // 支付详情
  async getPayment(paymentId) {
    return this.request(`/api/payments/${paymentId}`);
  },

  // 确认支付（pending/failed → paid）
  async confirmPayment(paymentId, data) {
    return this.request(`/api/payments/${paymentId}/confirm`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // 退款（paid → refunded）
  async refundPayment(paymentId, data) {
    return this.request(`/api/payments/${paymentId}/refund`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // 标记失败（pending/failed → failed）
  async failPayment(paymentId, data) {
    return this.request(`/api/payments/${paymentId}/fail`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // F15 电子发票开具
  async generateInvoice(paymentId, data) {
    return this.request(`/api/payments/${paymentId}/invoice`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // 里程碑聚合
  async getPaymentMilestones(projectId) {
    return this.request(`/api/payments/milestones/${projectId}`);
  },

  // F15 分阶段支付节点
  async getPaymentSchedule(projectId) {
    return this.request(`/api/payments/schedule/${projectId}`);
  },

  // F15 最终结算报告
  async getFinalSettlement(projectId) {
    return this.request(`/api/payments/final-settlement/${projectId}`);
  },
  async createSettlement(data) {
    return this.request('/api/settlements', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },
  async generateSettlementFromBudget(projectId) {
    return this.request(`/api/settlements/generate-from-budget/${projectId}`, {
      method: 'POST',
    });
  },
  async confirmSettlement(projectId) {
    return this.request(`/api/settlements/confirm/${projectId}`, {
      method: 'POST',
    });
  },
  async generateMilestoneSettlement(data) {
    return this.request('/api/settlements/milestone', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },
  async listSettlementMilestones() {
    return this.request('/api/settlements/milestones');
  },
  async checkSettlementAnomalies(data) {
    return this.request('/api/settlements/anomaly-check', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },
  async attachSettlementAnomalies(projectId, anomalies, autoMarkLines = true) {
    return this.request(`/api/settlements/anomaly-attach/${projectId}`, {
      method: 'POST',
      body: JSON.stringify({ anomalies, auto_mark_lines: autoMarkLines }),
    });
  },
  async requestSettlementReview(projectId, reason, reviewerId = null) {
    return this.request(`/api/settlements/request-review/${projectId}`, {
      method: 'POST',
      body: JSON.stringify({ reason, reviewer_id: reviewerId }),
    });
  },
  async approveSettlementReview(projectId) {
    return this.request(`/api/settlements/approve-review/${projectId}`, {
      method: 'POST',
    });
  },
  async generateReconciliation(data) {
    return this.request('/api/settlements/reconciliation', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },
  async autoSettlement(data) {
    return this.request('/api/settlements/auto-settlement', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },
  async exportSettlement(projectId) {
    return this.request(`/api/settlements/export/${projectId}`);
  },

  // 变更单（审批）
  async getChangeOrders(projectId) {
    return this.request(`/api/change-orders/project/${projectId}`);
  },
  async approveChangeOrder(changeId, decision) {
    const endpoint = decision === 'approve' ? 'approve' : 'cancel';
    return this.request(`/api/change-orders/${changeId}/${endpoint}`, {
      method: 'POST',
    });
  },

  // ============ 物料 / BOM ============

  // 物料分类列表
  async getMaterialCategories() {
    return this.request('/api/materials/categories');
  },

  // 物料列表（可选品类筛选 / 关键字搜索）
  async getMaterials(params = {}) {
    const qs = new URLSearchParams();
    if (params.category_id) qs.set('category_id', params.category_id);
    if (params.keyword) qs.set('keyword', params.keyword);
    if (params.skip != null) qs.set('skip', params.skip);
    if (params.limit != null) qs.set('limit', params.limit);
    const query = qs.toString();
    return this.request(`/api/materials${query ? '?' + query : ''}`);
  },

  // 物料详情
  async getMaterial(materialId) {
    return this.request(`/api/materials/${materialId}`);
  },

  // 手动新增 BOM 项
  async addBOMItem(data) {
    return this.request('/api/materials/bom', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // F6 BOM 自动生成（基于项目房间面积/类型）
  async generateBOM(projectId) {
    return this.request(`/api/materials/bom/generate/${projectId}`, {
      method: 'POST',
    });
  },

  // 获取项目 BOM 列表
  async getProjectBOM(projectId) {
    return this.request(`/api/materials/bom/${projectId}`);
  },

  // BOM 汇总（按品类聚合）
  async getBOMSummary(projectId) {
    return this.request(`/api/materials/bom/${projectId}/summary`);
  },

  // F7 BOM Excel 导出（返回 Blob）
  async exportBOM(projectId) {
    const token = this.getToken();
    const res = await fetch(this._url(`/api/materials/bom/${projectId}/export`), {
      headers: token ? { 'Authorization': `Bearer ${token}` } : {},
    });
    if (!res.ok) {
      const err = new Error(`HTTP ${res.status}`);
      err.status = res.status;
      throw err;
    }
    return res.blob();
  },

  // 删除 BOM 项
  async deleteBOMItem(bomId) {
    return this.request(`/api/materials/bom/${bomId}`, { method: 'DELETE' });
  },

  // 文件上传
  async uploadFile(file, projectId, category = 'photo') {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('project_id', projectId);
    formData.append('category', category);
    const token = this.getToken();
    const res = await fetch(this._url('/api/files/upload'), {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData,
    });
    return this._handleResponse(res);
  },

  // 文件列表
  async getFiles(projectId) {
    return this.request(`/api/files/project/${projectId}`);
  },

  // 下载文件
  async downloadFile(attachmentId) {
    const token = this.getToken();
    const res = await fetch(this._url(`/api/files/download/${attachmentId}`), {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    if (!res.ok) throw await this._handleError(res);
    return res.blob();
  },

  // 删除文件
  async deleteFileAttachment(attachmentId) {
    return this.request(`/api/files/${attachmentId}`, { method: 'DELETE' });
  },

  // ============ 位置服务（高德地图） ============

  // 搜索附近楼盘/小区
  async searchLocation(keywords, city, limit = 10) {
    const params = new URLSearchParams({ keywords });
    if (city) params.append('city', city);
    if (limit) params.append('limit', limit);
    return this.request(`/api/location/search?${params}`);
  },

  // 地址转经纬度
  async geocodeLocation(address, city) {
    const params = new URLSearchParams({ address });
    if (city) params.append('city', city);
    return this.request(`/api/location/geocode?${params}`);
  },

  // 地址智能提示
  async autocompleteLocation(keywords, city, limit = 5) {
    const params = new URLSearchParams({ keywords });
    if (city) params.append('city', city);
    if (limit) params.append('limit', limit);
    return this.request(`/api/location/autocomplete?${params}`);
  },

  // ============ 语音处理 ============

  // 处理语音输入文本
  async processVoice(text, projectId = null) {
    const body = { text };
    if (projectId) body.project_id = projectId;
    return this.request('/api/voice/process', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  },

  // ============ F40 三方协作 IM ============

  // 获取项目聊天房间信息
  async getChatRoom(projectId) {
    return this.request(`/api/chat/rooms/${projectId}`);
  },

  // 加载历史 IM 消息（默认 50 条）
  async getChatMessages(projectId, limit = 50) {
    return this.request(`/api/chat/messages/${projectId}?limit=${limit}`);
  },

  // 发送 IM 消息（持久化 + WebSocket 广播）
  async sendChatMessage(data) {
    return this.request('/api/chat/messages', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // 标记消息已读
  async markMessageRead(messageId) {
    return this.request(`/api/chat/messages/${messageId}/read`, { method: 'POST' });
  },

  // 未读消息数
  async getUnreadCount(projectId) {
    return this.request(`/api/chat/unread/${projectId}`);
  },

  // ============ 测量 survey / AR 扫描 ============

  async createSurvey(data) {
    return this.request('/api/surveys', { method: 'POST', body: JSON.stringify(data) });
  },
  async getSurveys(projectId) {
    return this.request(`/api/surveys/project/${projectId}`);
  },
  async getSurvey(surveyId) {
    return this.request(`/api/surveys/${surveyId}`);
  },
  async updateSurvey(surveyId, data) {
    return this.request(`/api/surveys/${surveyId}`, { method: 'PUT', body: JSON.stringify(data) });
  },
  async deleteSurvey(surveyId) {
    return this.request(`/api/surveys/${surveyId}`, { method: 'DELETE' });
  },
  async checkARDevice() {
    return this.request('/api/surveys/device-check');
  },
  async createARSession(data) {
    return this.request('/api/surveys/ar/sessions', { method: 'POST', body: JSON.stringify(data) });
  },
  async getARSessions(projectId) {
    return this.request(`/api/surveys/ar/sessions/project/${projectId}`);
  },
  async getARSession(sessionId) {
    return this.request(`/api/surveys/ar/sessions/${sessionId}`);
  },
  async startARScan(sessionId) {
    return this.request(`/api/surveys/ar/sessions/${sessionId}/start`, { method: 'POST' });
  },
  async processARScan(sessionId, data) {
    return this.request(`/api/surveys/ar/sessions/${sessionId}/process`, { method: 'POST', body: JSON.stringify(data) });
  },
  async getARAccuracy(sessionId) {
    return this.request(`/api/surveys/ar/sessions/${sessionId}/accuracy`);
  },
  async applyARSession(sessionId) {
    return this.request(`/api/surveys/ar/sessions/${sessionId}/apply`, { method: 'POST' });
  },
  async deleteARSession(sessionId) {
    return this.request(`/api/surveys/ar/sessions/${sessionId}`, { method: 'DELETE' });
  },

  // ============ 工程量计算 takeoff ============

  async takeoffWall(data) {
    return this.request('/api/takeoff/wall', { method: 'POST', body: JSON.stringify(data) });
  },
  async takeoffSlab(data) {
    return this.request('/api/takeoff/slab', { method: 'POST', body: JSON.stringify(data) });
  },
  async takeoffFloor(data) {
    return this.request('/api/takeoff/floor', { method: 'POST', body: JSON.stringify(data) });
  },
  async takeoffPaint(data) {
    return this.request('/api/takeoff/paint', { method: 'POST', body: JSON.stringify(data) });
  },
  async takeoffProject(projectId) {
    return this.request('/api/takeoff/project', { method: 'POST', body: JSON.stringify({ project_id: projectId }) });
  },

  // ============ 户型 floorplans ============

  async getFloorplans(projectId) {
    return this.request(`/api/floorplans/project/${projectId}`);
  },
  async getFloorplan(planId) {
    return this.request(`/api/floorplans/${planId}`);
  },
  async createFloorplan(data) {
    return this.request('/api/floorplans', { method: 'POST', body: JSON.stringify(data) });
  },
  async updateFloorplan(planId, data) {
    return this.request(`/api/floorplans/${planId}`, { method: 'PUT', body: JSON.stringify(data) });
  },
  async deleteFloorplan(planId) {
    return this.request(`/api/floorplans/${planId}`, { method: 'DELETE' });
  },

  // ============ VR 全景 ============

  async createVRPanorama(data) {
    return this.request('/api/vr/panoramas', { method: 'POST', body: JSON.stringify(data) });
  },
  async getVRPanoramas(projectId) {
    return this.request(`/api/vr/panoramas/project/${projectId}`);
  },
  async getVRPanorama(panoramaId) {
    return this.request(`/api/vr/panoramas/${panoramaId}`);
  },
  async renderVRPanorama(panoramaId) {
    return this.request(`/api/vr/panoramas/${panoramaId}/render`, { method: 'POST' });
  },
  async addVRHotspot(panoramaId, data) {
    return this.request(`/api/vr/panoramas/${panoramaId}/hotspots`, { method: 'POST', body: JSON.stringify(data) });
  },
  async getVRHotspots(panoramaId) {
    return this.request(`/api/vr/panoramas/${panoramaId}/hotspots`);
  },
  async deleteVRHotspot(panoramaId, hotspotIndex) {
    return this.request(`/api/vr/hotspots/${panoramaId}/${hotspotIndex}`, { method: 'DELETE' });
  },
  async deleteVRPanorama(panoramaId) {
    return this.request(`/api/vr/panoramas/${panoramaId}`, { method: 'DELETE' });
  },
  async createVRScene(data) {
    return this.request('/api/vr/scenes', { method: 'POST', body: JSON.stringify(data) });
  },
  async getVRScenes(projectId) {
    return this.request(`/api/vr/scenes/project/${projectId}`);
  },
  async getVRScene(sceneId) {
    return this.request(`/api/vr/scenes/${sceneId}`);
  },
  async updateVRScene(sceneId, data) {
    return this.request(`/api/vr/scenes/${sceneId}`, { method: 'PATCH', body: JSON.stringify(data) });
  },
  async deleteVRScene(sceneId) {
    return this.request(`/api/vr/scenes/${sceneId}`, { method: 'DELETE' });
  },

  // ============ AI 图生图 ai-image ============

  async createAIImageJob(data) {
    return this.request('/api/ai-image/jobs', { method: 'POST', body: JSON.stringify(data) });
  },
  async getAIImageJobs(projectId) {
    return this.request(`/api/ai-image/jobs/project/${projectId}`);
  },
  async getAIImageJob(jobId) {
    return this.request(`/api/ai-image/jobs/${jobId}`);
  },
  async processAIImageJob(jobId) {
    return this.request(`/api/ai-image/jobs/${jobId}/process`, { method: 'POST' });
  },
  async getAIImageJobStatus(jobId) {
    return this.request(`/api/ai-image/jobs/${jobId}/status`);
  },
  async deleteAIImageJob(jobId) {
    return this.request(`/api/ai-image/jobs/${jobId}`, { method: 'DELETE' });
  },
  async getAIImagePresets() {
    return this.request('/api/ai-image/presets');
  },
  async createAIImagePreset(data) {
    return this.request('/api/ai-image/presets', { method: 'POST', body: JSON.stringify(data) });
  },
  async getAIImagePreset(presetId) {
    return this.request(`/api/ai-image/presets/${presetId}`);
  },
  async applyAIImagePreset(data) {
    return this.request('/api/ai-image/jobs/apply-preset', { method: 'POST', body: JSON.stringify(data) });
  },
  async batchAIImageJobs(data) {
    return this.request('/api/ai-image/jobs/batch', { method: 'POST', body: JSON.stringify(data) });
  },

  // ============ 厨房设计 kitchen ============

  async createKitchenDesign(data) {
    return this.request('/api/kitchen/designs', { method: 'POST', body: JSON.stringify(data) });
  },
  async getKitchenDesigns(projectId) {
    return this.request(`/api/kitchen/designs/project/${projectId}`);
  },
  async getKitchenDesign(designId) {
    return this.request(`/api/kitchen/designs/${designId}`);
  },
  async autoLayoutKitchen(designId) {
    return this.request(`/api/kitchen/designs/${designId}/auto-layout`, { method: 'POST' });
  },
  async getKitchenWorkflow(designId) {
    return this.request(`/api/kitchen/designs/${designId}/workflow`);
  },
  async getKitchenCompliance(designId) {
    return this.request(`/api/kitchen/designs/${designId}/compliance`);
  },
  async addKitchenComponent(designId, data) {
    return this.request(`/api/kitchen/designs/${designId}/components`, { method: 'POST', body: JSON.stringify(data) });
  },
  async getKitchenComponents(designId) {
    return this.request(`/api/kitchen/designs/${designId}/components`);
  },
  async deleteKitchenComponent(componentId) {
    return this.request(`/api/kitchen/components/${componentId}`, { method: 'DELETE' });
  },
  async deleteKitchenDesign(designId) {
    return this.request(`/api/kitchen/designs/${designId}`, { method: 'DELETE' });
  },

  // ============ 卫生间设计 bathroom ============

  async createBathroomDesign(data) {
    return this.request('/api/bathroom/designs', { method: 'POST', body: JSON.stringify(data) });
  },
  async getBathroomDesigns(projectId) {
    return this.request(`/api/bathroom/designs/project/${projectId}`);
  },
  async getBathroomDesign(designId) {
    return this.request(`/api/bathroom/designs/${designId}`);
  },
  async autoLayoutBathroom(designId) {
    return this.request(`/api/bathroom/designs/${designId}/auto-layout`, { method: 'POST' });
  },
  async getBathroomDrain(designId) {
    return this.request(`/api/bathroom/designs/${designId}/drain`);
  },
  async getBathroomWaterproof(designId) {
    return this.request(`/api/bathroom/designs/${designId}/waterproof`);
  },
  async getBathroomVentilation(designId) {
    return this.request(`/api/bathroom/designs/${designId}/ventilation`);
  },
  async addBathroomFixture(designId, data) {
    return this.request(`/api/bathroom/designs/${designId}/fixtures`, { method: 'POST', body: JSON.stringify(data) });
  },
  async getBathroomFixtures(designId) {
    return this.request(`/api/bathroom/designs/${designId}/fixtures`);
  },
  async deleteBathroomFixture(fixtureId) {
    return this.request(`/api/bathroom/fixtures/${fixtureId}`, { method: 'DELETE' });
  },
  async deleteBathroomDesign(designId) {
    return this.request(`/api/bathroom/designs/${designId}`, { method: 'DELETE' });
  },

  // ============ 厨卫水电 mep-kb ============

  async createMEPKBPlan(data) {
    return this.request('/api/mep-kb/plans', { method: 'POST', body: JSON.stringify(data) });
  },
  async getMEPKBPlans(projectId) {
    return this.request(`/api/mep-kb/plans/project/${projectId}`);
  },
  async getMEPKBPlan(planId) {
    return this.request(`/api/mep-kb/plans/${planId}`);
  },
  async autoGenerateMEPKB(planId) {
    return this.request(`/api/mep-kb/plans/${planId}/auto-generate`, { method: 'POST' });
  },
  async getMEPKBCircuits(planId) {
    return this.request(`/api/mep-kb/plans/${planId}/circuits`);
  },
  async getMEPKBEquipotential(planId) {
    return this.request(`/api/mep-kb/plans/${planId}/equipotential`);
  },
  async getMEPKBGas(planId) {
    return this.request(`/api/mep-kb/plans/${planId}/gas`);
  },
  async addMEPKBPoint(planId, data) {
    return this.request(`/api/mep-kb/plans/${planId}/points`, { method: 'POST', body: JSON.stringify(data) });
  },
  async getMEPKBPoints(planId) {
    return this.request(`/api/mep-kb/plans/${planId}/points`);
  },
  async deleteMEPKBPoint(pointId) {
    return this.request(`/api/mep-kb/points/${pointId}`, { method: 'DELETE' });
  },
  async deleteMEPKBPlan(planId) {
    return this.request(`/api/mep-kb/plans/${planId}`, { method: 'DELETE' });
  },

  // ============ 硬装 hard-decoration ============

  async createHardDecorationScheme(data) {
    return this.request('/api/hard-decoration/schemes', { method: 'POST', body: JSON.stringify(data) });
  },
  async getHardDecorationSchemes(projectId) {
    return this.request(`/api/hard-decoration/schemes/project/${projectId}`);
  },
  async getHardDecorationScheme(schemeId) {
    return this.request(`/api/hard-decoration/schemes/${schemeId}`);
  },
  async tileLayout(schemeId, data) {
    return this.request(`/api/hard-decoration/schemes/${schemeId}/tile-layout`, { method: 'POST', body: JSON.stringify(data) });
  },
  async paintUsage(schemeId, data) {
    return this.request(`/api/hard-decoration/schemes/${schemeId}/paint-usage`, { method: 'POST', body: JSON.stringify(data) });
  },
  async ceilingDesign(schemeId, data) {
    return this.request(`/api/hard-decoration/schemes/${schemeId}/ceiling-design`, { method: 'POST', body: JSON.stringify(data) });
  },
  async getHardDecorationBudget(schemeId) {
    return this.request(`/api/hard-decoration/schemes/${schemeId}/budget`);
  },
  async addHardDecorationFloor(schemeId, data) {
    return this.request(`/api/hard-decoration/schemes/${schemeId}/floors`, { method: 'POST', body: JSON.stringify(data) });
  },
  async addHardDecorationWall(schemeId, data) {
    return this.request(`/api/hard-decoration/schemes/${schemeId}/walls`, { method: 'POST', body: JSON.stringify(data) });
  },
  async addHardDecorationCeiling(schemeId, data) {
    return this.request(`/api/hard-decoration/schemes/${schemeId}/ceilings`, { method: 'POST', body: JSON.stringify(data) });
  },
  async getHardDecorationFloors(schemeId) {
    return this.request(`/api/hard-decoration/schemes/${schemeId}/floors`);
  },
  async getHardDecorationWalls(schemeId) {
    return this.request(`/api/hard-decoration/schemes/${schemeId}/walls`);
  },
  async getHardDecorationCeilings(schemeId) {
    return this.request(`/api/hard-decoration/schemes/${schemeId}/ceilings`);
  },
  async deleteHardDecorationScheme(schemeId) {
    return this.request(`/api/hard-decoration/schemes/${schemeId}`, { method: 'DELETE' });
  },

  // ============ 门窗/防水 door-window-waterproof ============

  async createDoorWindow(data) {
    return this.request('/api/door-window-waterproof/door-windows', { method: 'POST', body: JSON.stringify(data) });
  },
  async getDoorWindows(projectId) {
    return this.request(`/api/door-window-waterproof/door-windows/project/${projectId}`);
  },
  async getDoorWindow(specId) {
    return this.request(`/api/door-window-waterproof/door-windows/${specId}`);
  },
  async recommendDoorWindow(data) {
    return this.request('/api/door-window-waterproof/door-windows/recommend', { method: 'POST', body: JSON.stringify(data) });
  },
  async deleteDoorWindow(specId) {
    return this.request(`/api/door-window-waterproof/door-windows/${specId}`, { method: 'DELETE' });
  },
  async createWaterproof(data) {
    return this.request('/api/door-window-waterproof/waterproof', { method: 'POST', body: JSON.stringify(data) });
  },
  async getWaterproofs(projectId) {
    return this.request(`/api/door-window-waterproof/waterproof/project/${projectId}`);
  },
  async getWaterproof(planId) {
    return this.request(`/api/door-window-waterproof/waterproof/${planId}`);
  },
  async computeWaterproofArea(planId, data) {
    return this.request(`/api/door-window-waterproof/waterproof/${planId}/compute-area`, { method: 'POST', body: JSON.stringify(data) });
  },
  async validateWaterproof(planId) {
    return this.request(`/api/door-window-waterproof/waterproof/${planId}/validation`);
  },
  async deleteWaterproof(planId) {
    return this.request(`/api/door-window-waterproof/waterproof/${planId}`, { method: 'DELETE' });
  },

  // ============ 土建 structural ============

  async createWall(data) {
    return this.request('/api/structural/walls', { method: 'POST', body: JSON.stringify(data) });
  },
  async getWalls(projectId) {
    return this.request(`/api/structural/projects/${projectId}/walls`);
  },
  async getWall(wallId) {
    return this.request(`/api/structural/walls/${wallId}`);
  },
  async updateWall(wallId, data) {
    return this.request(`/api/structural/walls/${wallId}`, { method: 'PUT', body: JSON.stringify(data) });
  },
  async deleteWall(wallId) {
    return this.request(`/api/structural/walls/${wallId}`, { method: 'DELETE' });
  },
  async createBeam(data) {
    return this.request('/api/structural/beams', { method: 'POST', body: JSON.stringify(data) });
  },
  async getBeams(projectId) {
    return this.request(`/api/structural/projects/${projectId}/beams`);
  },
  async getBeam(beamId) {
    return this.request(`/api/structural/beams/${beamId}`);
  },
  async updateBeam(beamId, data) {
    return this.request(`/api/structural/beams/${beamId}`, { method: 'PUT', body: JSON.stringify(data) });
  },
  async deleteBeam(beamId) {
    return this.request(`/api/structural/beams/${beamId}`, { method: 'DELETE' });
  },
  async createColumn(data) {
    return this.request('/api/structural/columns', { method: 'POST', body: JSON.stringify(data) });
  },
  async getColumns(projectId) {
    return this.request(`/api/structural/projects/${projectId}/columns`);
  },
  async getColumn(columnId) {
    return this.request(`/api/structural/columns/${columnId}`);
  },
  async updateColumn(columnId, data) {
    return this.request(`/api/structural/columns/${columnId}`, { method: 'PUT', body: JSON.stringify(data) });
  },
  async deleteColumn(columnId) {
    return this.request(`/api/structural/columns/${columnId}`, { method: 'DELETE' });
  },
  async createSlab(data) {
    return this.request('/api/structural/slabs', { method: 'POST', body: JSON.stringify(data) });
  },
  async getSlabs(projectId) {
    return this.request(`/api/structural/projects/${projectId}/slabs`);
  },
  async getSlab(slabId) {
    return this.request(`/api/structural/slabs/${slabId}`);
  },
  async updateSlab(slabId, data) {
    return this.request(`/api/structural/slabs/${slabId}`, { method: 'PUT', body: JSON.stringify(data) });
  },
  async deleteSlab(slabId) {
    return this.request(`/api/structural/slabs/${slabId}`, { method: 'DELETE' });
  },
  async createFoundation(data) {
    return this.request('/api/structural/foundations', { method: 'POST', body: JSON.stringify(data) });
  },
  async getFoundations(projectId) {
    return this.request(`/api/structural/projects/${projectId}/foundations`);
  },
  async getFoundation(foundationId) {
    return this.request(`/api/structural/foundations/${foundationId}`);
  },
  async deleteFoundation(foundationId) {
    return this.request(`/api/structural/foundations/${foundationId}`, { method: 'DELETE' });
  },
  async selectFoundation(foundationId) {
    return this.request(`/api/structural/foundations/${foundationId}/select`, { method: 'POST' });
  },
  async recommendFoundation(data) {
    return this.request('/api/structural/foundations/recommend', { method: 'POST', body: JSON.stringify(data) });
  },
  async createLoadEstimate(data) {
    return this.request('/api/structural/load-estimates', { method: 'POST', body: JSON.stringify(data) });
  },
  async getLoadEstimates(projectId) {
    return this.request(`/api/structural/projects/${projectId}/load-estimates`);
  },
  async getLoadEstimate(estimateId) {
    return this.request(`/api/structural/load-estimates/${estimateId}`);
  },
  async deleteLoadEstimate(estimateId) {
    return this.request(`/api/structural/load-estimates/${estimateId}`, { method: 'DELETE' });
  },
  async computeLoad(data) {
    return this.request('/api/structural/load-estimates/compute', { method: 'POST', body: JSON.stringify(data) });
  },
  async createCompliance(data) {
    return this.request('/api/structural/compliance', { method: 'POST', body: JSON.stringify(data) });
  },
  async getCompliance(projectId) {
    return this.request(`/api/structural/projects/${projectId}/compliance`);
  },
  async getComplianceById(complianceId) {
    return this.request(`/api/structural/compliance/${complianceId}`);
  },
  async deleteCompliance(complianceId) {
    return this.request(`/api/structural/compliance/${complianceId}`, { method: 'DELETE' });
  },
  async createQuantityCalc(data) {
    return this.request('/api/structural/quantity-calcs', { method: 'POST', body: JSON.stringify(data) });
  },
  async getQuantityCalcs(projectId) {
    return this.request(`/api/structural/projects/${projectId}/quantity-calcs`);
  },
  async getQuantityCalc(calcId) {
    return this.request(`/api/structural/quantity-calcs/${calcId}`);
  },
  async deleteQuantityCalc(calcId) {
    return this.request(`/api/structural/quantity-calcs/${calcId}`, { method: 'DELETE' });
  },
  async autoCalcQuantity(data) {
    return this.request('/api/structural/quantity-calcs/auto-calc', { method: 'POST', body: JSON.stringify(data) });
  },
  async addQuantityLineItem(calcId, data) {
    return this.request(`/api/structural/quantity-calcs/${calcId}/line-items`, { method: 'POST', body: JSON.stringify(data) });
  },
  async deleteQuantityLineItem(itemId) {
    return this.request(`/api/structural/quantity-calcs/line-items/${itemId}`, { method: 'DELETE' });
  },

  // ============ 水电点位 mep ============

  async mepPlan(data) {
    return this.request('/api/mep/plan', { method: 'POST', body: JSON.stringify(data) });
  },
  async mepAppliances(data) {
    return this.request('/api/mep/appliances', { method: 'POST', body: JSON.stringify(data) });
  },
  async mepComplianceCheck(data) {
    return this.request('/api/mep/compliance-check', { method: 'POST', body: JSON.stringify(data) });
  },
  async mepRoomStandards(roomType) {
    return this.request(`/api/mep/room-standards/${roomType}`);
  },

  // ============ 灯光设计 lighting ============

  async createLightingScheme(data) {
    return this.request('/api/lighting/schemes', { method: 'POST', body: JSON.stringify(data) });
  },
  async getLightingSchemes(projectId) {
    return this.request(`/api/lighting/schemes/project/${projectId}`);
  },
  async getLightingScheme(schemeId) {
    return this.request(`/api/lighting/schemes/${schemeId}`);
  },
  async aiDesignLighting(schemeId) {
    return this.request(`/api/lighting/schemes/${schemeId}/ai-design`, { method: 'POST' });
  },
  async addLightingFixture(schemeId, data) {
    return this.request(`/api/lighting/schemes/${schemeId}/fixtures`, { method: 'POST', body: JSON.stringify(data) });
  },
  async getLightingFixtures(schemeId) {
    return this.request(`/api/lighting/schemes/${schemeId}/fixtures`);
  },
  async deleteLightingFixture(fixtureId) {
    return this.request(`/api/lighting/fixtures/${fixtureId}`, { method: 'DELETE' });
  },
  async getLightingIlluminance(schemeId) {
    return this.request(`/api/lighting/schemes/${schemeId}/illuminance`);
  },
  async deleteLightingScheme(schemeId) {
    return this.request(`/api/lighting/schemes/${schemeId}`, { method: 'DELETE' });
  },

  // ============ 电器 appliances ============

  async createApplianceCategory(data) {
    return this.request('/api/appliances/categories', { method: 'POST', body: JSON.stringify(data) });
  },
  async getApplianceCategories() {
    return this.request('/api/appliances/categories');
  },
  async getApplianceCategory(catId) {
    return this.request(`/api/appliances/categories/${catId}`);
  },
  async updateApplianceCategory(catId, data) {
    return this.request(`/api/appliances/categories/${catId}`, { method: 'PUT', body: JSON.stringify(data) });
  },
  async deleteApplianceCategory(catId) {
    return this.request(`/api/appliances/categories/${catId}`, { method: 'DELETE' });
  },
  async createAppliance(data) {
    return this.request('/api/appliances', { method: 'POST', body: JSON.stringify(data) });
  },
  async searchAppliances(params = {}) {
    const qs = new URLSearchParams();
    if (params.keyword) qs.set('keyword', params.keyword);
    if (params.category_id) qs.set('category_id', params.category_id);
    if (params.project_id) qs.set('project_id', params.project_id);
    const query = qs.toString();
    return this.request(`/api/appliances/search${query ? '?' + query : ''}`);
  },
  async getAppliance(applianceId) {
    return this.request(`/api/appliances/${applianceId}`);
  },
  async updateAppliance(applianceId, data) {
    return this.request(`/api/appliances/${applianceId}`, { method: 'PUT', body: JSON.stringify(data) });
  },
  async deleteAppliance(applianceId) {
    return this.request(`/api/appliances/${applianceId}`, { method: 'DELETE' });
  },
  async addAppliancePoint(data) {
    return this.request('/api/appliances/points', { method: 'POST', body: JSON.stringify(data) });
  },
  async getAppliancePoints(projectId) {
    return this.request(`/api/appliances/projects/${projectId}/points`);
  },
  async getAppliancePoint(pointId) {
    return this.request(`/api/appliances/points/${pointId}`);
  },
  async updateAppliancePoint(pointId, data) {
    return this.request(`/api/appliances/points/${pointId}`, { method: 'PUT', body: JSON.stringify(data) });
  },
  async deleteAppliancePoint(pointId) {
    return this.request(`/api/appliances/points/${pointId}`, { method: 'DELETE' });
  },
  async calcApplianceLoad(projectId) {
    return this.request(`/api/appliances/projects/${projectId}/load-calc`, { method: 'POST' });
  },
  async getApplianceLoadCalcs(projectId) {
    return this.request(`/api/appliances/projects/${projectId}/load-calcs`);
  },
  async matchApplianceCabinet(data) {
    return this.request('/api/appliances/cabinet-match', { method: 'POST', body: JSON.stringify(data) });
  },
  async getApplianceEmbeddingPlan(projectId) {
    return this.request(`/api/appliances/projects/${projectId}/embedding-plan`);
  },
  async recommendRoomAppliances(roomId) {
    return this.request(`/api/appliances/rooms/${roomId}/recommend`);
  },

  // ============ 软装 soft-furnishing ============

  async createSoftFurnishingScheme(data) {
    return this.request('/api/soft-furnishing/schemes', { method: 'POST', body: JSON.stringify(data) });
  },
  async getSoftFurnishingSchemes(projectId) {
    return this.request(`/api/soft-furnishing/schemes/project/${projectId}`);
  },
  async getSoftFurnishingScheme(schemeId) {
    return this.request(`/api/soft-furnishing/schemes/${schemeId}`);
  },
  async deleteSoftFurnishingScheme(schemeId) {
    return this.request(`/api/soft-furnishing/schemes/${schemeId}`, { method: 'DELETE' });
  },
  async aiMatchSoftFurnishing(schemeId) {
    return this.request(`/api/soft-furnishing/schemes/${schemeId}/ai-match`, { method: 'POST' });
  },
  async getSoftFurnishingColorHarmony(schemeId) {
    return this.request(`/api/soft-furnishing/schemes/${schemeId}/color-harmony`);
  },
  async getSoftFurnishingBudget(schemeId) {
    return this.request(`/api/soft-furnishing/schemes/${schemeId}/budget`);
  },
  async addSoftFurnishingItem(schemeId, data) {
    return this.request(`/api/soft-furnishing/schemes/${schemeId}/items`, { method: 'POST', body: JSON.stringify(data) });
  },
  async getSoftFurnishingItems(schemeId) {
    return this.request(`/api/soft-furnishing/schemes/${schemeId}/items`);
  },
  async deleteSoftFurnishingItem(itemId) {
    return this.request(`/api/soft-furnishing/items/${itemId}`, { method: 'DELETE' });
  },
  async updateSoftFurnishingItemStatus(itemId, status) {
    return this.request(`/api/soft-furnishing/items/${itemId}/status`, { method: 'PATCH', body: JSON.stringify({ status }) });
  },
  async createStorageSystem(schemeId, data) {
    return this.request(`/api/soft-furnishing/schemes/${schemeId}/storage`, { method: 'POST', body: JSON.stringify(data) });
  },
  async getStorageSystems(schemeId) {
    return this.request(`/api/soft-furnishing/schemes/${schemeId}/storage`);
  },
  async getStorageCapacity(storageId) {
    return this.request(`/api/soft-furnishing/storage/${storageId}/capacity`);
  },
  async recommendStorage(data) {
    return this.request('/api/soft-furnishing/storage/recommend', { method: 'POST', body: JSON.stringify(data) });
  },

  // ============ 定制家具 custom-furniture ============

  async createCustomFurnitureDesign(data) {
    return this.request('/api/custom-furniture/designs', { method: 'POST', body: JSON.stringify(data) });
  },
  async getCustomFurnitureDesigns(projectId) {
    return this.request(`/api/custom-furniture/designs/project/${projectId}`);
  },
  async getCustomFurnitureDesign(designId) {
    return this.request(`/api/custom-furniture/designs/${designId}`);
  },
  async deleteCustomFurnitureDesign(designId) {
    return this.request(`/api/custom-furniture/designs/${designId}`, { method: 'DELETE' });
  },
  async parametricCustomFurniture(designId, data) {
    return this.request(`/api/custom-furniture/designs/${designId}/parametric`, { method: 'POST', body: JSON.stringify(data) });
  },
  async addFurnitureModule(designId, data) {
    return this.request(`/api/custom-furniture/designs/${designId}/modules`, { method: 'POST', body: JSON.stringify(data) });
  },
  async getFurnitureModules(designId) {
    return this.request(`/api/custom-furniture/designs/${designId}/modules`);
  },
  async deleteFurnitureModule(moduleId) {
    return this.request(`/api/custom-furniture/modules/${moduleId}`, { method: 'DELETE' });
  },
  async generateFurnitureBOM(designId, data) {
    return this.request(`/api/custom-furniture/designs/${designId}/bom`, { method: 'POST', body: JSON.stringify(data) });
  },
  async getFurnitureBOM(designId) {
    return this.request(`/api/custom-furniture/designs/${designId}/bom`);
  },
  async getFurniturePrice(designId) {
    return this.request(`/api/custom-furniture/designs/${designId}/price`);
  },
  async getFurniturePanels(designId) {
    return this.request(`/api/custom-furniture/designs/${designId}/panels`);
  },
  async validateFurnitureDesign(designId) {
    return this.request(`/api/custom-furniture/designs/${designId}/validation`);
  },

  // ============ 家具品类库 furniture-catalog ============

  async getFurnitureCatalog(params = {}) {
    const qs = new URLSearchParams();
    if (params.category) qs.set('category', params.category);
    if (params.style) qs.set('style', params.style);
    if (params.keyword) qs.set('keyword', params.keyword);
    const query = qs.toString();
    return this.request(`/api/furniture-catalog${query ? '?' + query : ''}`);
  },
  async createFurnitureCatalogItem(data) {
    return this.request('/api/furniture-catalog', { method: 'POST', body: JSON.stringify(data) });
  },
  async recommendFurniture(data) {
    const qs = new URLSearchParams();
    if (data.room_type) qs.set('room_type', data.room_type);
    if (data.style) qs.set('style', data.style);
    if (data.budget) qs.set('budget', data.budget);
    return this.request(`/api/furniture-catalog/recommend?${qs}`);
  },
  async getFurnitureCatalogItem(itemId) {
    return this.request(`/api/furniture-catalog/${itemId}`);
  },
  async updateFurnitureCatalogItem(itemId, data) {
    return this.request(`/api/furniture-catalog/${itemId}`, { method: 'PATCH', body: JSON.stringify(data) });
  },
  async deleteFurnitureCatalogItem(itemId) {
    return this.request(`/api/furniture-catalog/${itemId}`, { method: 'DELETE' });
  },
  async getFurnitureARPlacement(itemId, data) {
    const qs = new URLSearchParams();
    if (data.room_id) qs.set('room_id', data.room_id);
    if (data.position) qs.set('position', data.position);
    return this.request(`/api/furniture-catalog/${itemId}/ar-placement?${qs}`);
  },
  async getSimilarFurniture(itemId) {
    return this.request(`/api/furniture-catalog/${itemId}/similar`);
  },

  // ============ 智能家居 smart-home ============

  async createSmartHomeScheme(data) {
    return this.request('/api/smart-home/schemes', { method: 'POST', body: JSON.stringify(data) });
  },
  async getSmartHomeSchemes(projectId) {
    return this.request(`/api/smart-home/schemes/project/${projectId}`);
  },
  async getSmartHomeScheme(schemeId) {
    return this.request(`/api/smart-home/schemes/${schemeId}`);
  },
  async deleteSmartHomeScheme(schemeId) {
    return this.request(`/api/smart-home/schemes/${schemeId}`, { method: 'DELETE' });
  },
  async autoRecommendSmartHome(schemeId) {
    return this.request(`/api/smart-home/schemes/${schemeId}/auto-recommend`, { method: 'POST' });
  },
  async getSmartHomeWiring(schemeId) {
    return this.request(`/api/smart-home/schemes/${schemeId}/wiring`);
  },
  async getSmartHomeProtocolAdvice(schemeId) {
    return this.request(`/api/smart-home/schemes/${schemeId}/protocol-advice`);
  },
  async getSmartHomePrice(schemeId) {
    return this.request(`/api/smart-home/schemes/${schemeId}/price`);
  },
  async addSmartDevice(schemeId, data) {
    return this.request(`/api/smart-home/schemes/${schemeId}/devices`, { method: 'POST', body: JSON.stringify(data) });
  },
  async getSmartDevices(schemeId) {
    return this.request(`/api/smart-home/schemes/${schemeId}/devices`);
  },
  async deleteSmartDevice(deviceId) {
    return this.request(`/api/smart-home/devices/${deviceId}`, { method: 'DELETE' });
  },

  // ============ 场景编辑 scene-automation ============

  async createScene(data) {
    return this.request('/api/scene-automation/scenes', { method: 'POST', body: JSON.stringify(data) });
  },
  async getScenes(projectId) {
    return this.request(`/api/scene-automation/scenes/project/${projectId}`);
  },
  async recommendScene(data) {
    const qs = new URLSearchParams();
    if (data.room_type) qs.set('room_type', data.room_type);
    if (data.occasion) qs.set('occasion', data.occasion);
    return this.request(`/api/scene-automation/scenes/recommend?${qs}`);
  },
  async parseScene(text) {
    return this.request('/api/scene-automation/scenes/parse', { method: 'POST', body: JSON.stringify({ text }) });
  },
  async getScene(sceneId) {
    return this.request(`/api/scene-automation/scenes/${sceneId}`);
  },
  async updateScene(sceneId, data) {
    return this.request(`/api/scene-automation/scenes/${sceneId}`, { method: 'PATCH', body: JSON.stringify(data) });
  },
  async deleteScene(sceneId) {
    return this.request(`/api/scene-automation/scenes/${sceneId}`, { method: 'DELETE' });
  },
  async simulateScene(sceneId) {
    return this.request(`/api/scene-automation/scenes/${sceneId}/simulate`, { method: 'POST' });
  },
  async syncScene(sceneId) {
    return this.request(`/api/scene-automation/scenes/${sceneId}/sync`, { method: 'POST' });
  },
  async createEcosystem(data) {
    return this.request('/api/scene-automation/ecosystems', { method: 'POST', body: JSON.stringify(data) });
  },
  async getEcosystems(projectId) {
    return this.request(`/api/scene-automation/ecosystems/project/${projectId}`);
  },
  async deleteEcosystem(ecosystemId) {
    return this.request(`/api/scene-automation/ecosystems/${ecosystemId}`, { method: 'DELETE' });
  },

  // ============ 实名认证 identity ============

  async submitIdentityVerification(data) {
    return this.request('/api/identity/submit', { method: 'POST', body: JSON.stringify(data) });
  },
  async getIdentityStatus() {
    return this.request('/api/identity/status');
  },
  async listPendingVerifications() {
    return this.request('/api/identity/pending');
  },
  async reviewIdentityVerification(verificationId, data) {
    return this.request(`/api/identity/${verificationId}/review`, { method: 'POST', body: JSON.stringify(data) });
  },

  // ============ 积分系统 points ============

  async getPointsAccount(userId = null) {
    return this.request(userId ? `/api/points/account/${userId}` : '/api/points/account');
  },
  async getPointsTransactions(params = {}) {
    const qs = new URLSearchParams();
    if (params.limit) qs.set('limit', params.limit);
    if (params.offset) qs.set('offset', params.offset);
    const query = qs.toString();
    return this.request(`/api/points/transactions${query ? '?' + query : ''}`);
  },
  async getPointsRules() {
    return this.request('/api/points/rules');
  },
  async earnPoints(data) {
    return this.request('/api/points/earn', { method: 'POST', body: JSON.stringify(data) });
  },
  async getPointsMall() {
    return this.request('/api/points/mall');
  },
  async redeemPoints(data) {
    return this.request('/api/points/redeem', { method: 'POST', body: JSON.stringify(data) });
  },
  async getRedemptions() {
    return this.request('/api/points/redemptions');
  },
  async getPointsRanking() {
    return this.request('/api/points/ranking');
  },
  async recomputeRanking() {
    return this.request('/api/points/ranking/recompute', { method: 'POST' });
  },

  // ============ 工程队匹配 crews ============

  async getCrews() {
    return this.request('/api/crews');
  },
  async createCrew(data) {
    return this.request('/api/crews', { method: 'POST', body: JSON.stringify(data) });
  },
  async getCrew(crewId) {
    return this.request(`/api/crews/${crewId}`);
  },
  async matchCrews(data) {
    return this.request('/api/crews/match', { method: 'POST', body: JSON.stringify(data) });
  },
  async getCrewMatches(projectId) {
    return this.request(`/api/crews/matches/${projectId}`);
  },
  async updateCrewMatchStatus(matchId, status) {
    return this.request(`/api/crews/matches/${matchId}/status`, { method: 'POST', body: JSON.stringify({ status }) });
  },

  // ============ 服务者匹配 workers ============

  async getWorkers() {
    return this.request('/api/workers');
  },
  async createWorker(data) {
    return this.request('/api/workers', { method: 'POST', body: JSON.stringify(data) });
  },
  async getWorker(workerId) {
    return this.request(`/api/workers/${workerId}`);
  },
  async matchWorkers(data) {
    return this.request('/api/workers/match', { method: 'POST', body: JSON.stringify(data) });
  },
  async getWorkerMatches(projectId) {
    return this.request(`/api/workers/matches/${projectId}`);
  },
  async updateWorkerMatchStatus(matchId, status) {
    return this.request(`/api/workers/matches/${matchId}/status`, { method: 'PATCH', body: JSON.stringify({ status }) });
  },

  // ============ 任务协调 tasks ============

  async createTask(data) {
    return this.request('/api/tasks', { method: 'POST', body: JSON.stringify(data) });
  },
  async getTaskPool(params = {}) {
    const qs = new URLSearchParams();
    if (params.role) qs.set('role', params.role);
    if (params.skill) qs.set('skill', params.skill);
    const query = qs.toString();
    return this.request(`/api/tasks/pool${query ? '?' + query : ''}`);
  },
  async getProjectTasks(projectId) {
    return this.request(`/api/tasks/project/${projectId}`);
  },
  async getMyTasks() {
    return this.request('/api/tasks/mine');
  },
  async claimTask(taskId) {
    return this.request('/api/tasks/claim', { method: 'POST', body: JSON.stringify({ task_id: taskId }) });
  },
  async getTaskCandidates(taskId) {
    return this.request(`/api/tasks/${taskId}/candidates`);
  },
  async assignTask(data) {
    return this.request('/api/tasks/assign', { method: 'POST', body: JSON.stringify(data) });
  },
  async completeTask(taskId, data) {
    return this.request(`/api/tasks/${taskId}/complete`, { method: 'POST', body: JSON.stringify(data) });
  },

  // ============ 产品/服务管理 products ============

  async createProduct(data) {
    return this.request('/api/products', { method: 'POST', body: JSON.stringify(data) });
  },
  async getProducts(params = {}) {
    const qs = new URLSearchParams();
    if (params.category) qs.set('category', params.category);
    if (params.keyword) qs.set('keyword', params.keyword);
    if (params.supplier_id) qs.set('supplier_id', params.supplier_id);
    const query = qs.toString();
    return this.request(`/api/products${query ? '?' + query : ''}`);
  },
  async getMyProducts() {
    return this.request('/api/products/mine');
  },
  async getProduct(productId) {
    return this.request(`/api/products/${productId}`);
  },
  async updateProduct(productId, data) {
    return this.request(`/api/products/${productId}`, { method: 'PUT', body: JSON.stringify(data) });
  },
  async publishProduct(productId) {
    return this.request(`/api/products/${productId}/publish`, { method: 'POST' });
  },

  // 拍照上架 camera_scan
  async cameraScanProduct(formData) {
    return this.request('/api/products/camera/scan', {
      method: 'POST',
      body: formData,
      headers: {},  // let browser set multipart/form-data boundary
    });
  },
  async cameraConfirmProduct(formData) {
    return this.request('/api/products/camera/confirm', {
      method: 'POST',
      body: formData,
    });
  },

  // ============ 批量产品上传 / AI 文案 ============

  // 批量上传产品（Excel/CSV）
  async uploadProductBatch(formData, aiAssisted = false) {
    const url = aiAssisted
      ? '/api/products/batch/upload?ai_assisted=true'
      : '/api/products/batch/upload';
    return this.request(url, {
      method: 'POST',
      body: formData,
      headers: {},
    });
  },

  // 获取批量上传模板下载链接
  async getBatchUploadTemplate() {
    return this.request('/api/products/batch/template');
  },

  // 查询 AI 文案生成任务状态
  async getAICopyJobStatus(batchId) {
    return this.request(`/api/products/batch/ai-jobs/${batchId}`);
  },

  // ============ 通知 / 设备推送令牌 ============

  // 注册/更新设备推送令牌（每用户每平台仅保留一条活跃记录）
  async registerDevice(data) {
    return this.request('/api/notifications/register-device', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // 列出当前用户的活跃设备
  async listMyDevices() {
    return this.request('/api/notifications/devices');
  },

  // 注销设备推送令牌（软删除）
  async unregisterDevice(deviceId) {
    return this.request(`/api/notifications/devices/${deviceId}`, {
      method: 'DELETE',
    });
  },

  // 健康检查
  async health() {
    return fetch(this._url('/health')).then(r => r.json());
  },

  // ── 管理后台 ──

  // 获取所有用户列表
  async getAdminUsers() {
    return this.request('/api/admin/users');
  },

  // 获取单个用户详情
  async getAdminUserDetail(userId) {
    return this.request(`/api/admin/users/${userId}`);
  },

  // 切换用户状态
  async toggleAdminUserStatus(userId, isActive) {
    return this.request(`/api/admin/users/${userId}/status`, {
      method: 'PUT',
      body: JSON.stringify({ is_active: isActive }),
    });
  },

  // ── 全局错误拦截 ──
  initGlobalErrorHandler() {
    // 处理未捕获的 fetch 异常
    const originalFetch = window.fetch;
    window.fetch = async function(...args) {
      try {
        const resp = await originalFetch.apply(this, args);
        // 如果是 500 错误，统一提示
        if (resp.status >= 500) {
          const path = typeof args[0] === 'string' ? args[0] : args[0]?.url || '';
          console.error('[ApiClient] 服务器错误:', resp.status, path);
          // 触发自定义事件供外部监听
          window.dispatchEvent(new CustomEvent('api:server-error', {
            detail: { status: resp.status, path, method: args[1]?.method || 'GET' }
          }));
        }
        return resp;
      } catch (e) {
        if (e instanceof TypeError && e.message.includes('fetch')) {
          console.error('[ApiClient] 网络错误:', e.message);
          window.dispatchEvent(new CustomEvent('api:network-error', {
            detail: { message: '网络连接失败，请检查网络后重试' }
          }));
        }
        throw e;
      }
    };
  },
};

// 暴露到全局
ApiClient.initGlobalErrorHandler();
window.ApiClient = ApiClient;
