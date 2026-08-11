/**
 * 索克家居 API 客户端 — 最小 PASETO 封装（批次 1）
 *
 * 与 web/assets/js/api-client.js 共享 localStorage key 'paseto_token'，
 * 跨端共享登录态（旧静态页登录后新控制台直接复用 token）。
 * 完整 api-client 迁移（login/register/projects 等）留后续批次。
 *
 * 项目约定：PASETO 而非 JWT。
 */

const TOKEN_KEY = 'paseto_token';
const BASE_URL = ''; // 同源，Vite proxy /api → localhost:8000

export interface ApiResult<T = unknown> {
  isSuccess: boolean;
  status: number;
  data?: T;
  error?: string;
}

export class ApiClient {
  private static _instance: ApiClient;

  static get instance(): ApiClient {
    if (!this._instance) this._instance = new ApiClient();
    return this._instance;
  }

  /** 未授权回调（由应用层设置） */
  onUnauthorized: (() => void) | null = null;

  getToken(): string {
    return localStorage.getItem(TOKEN_KEY) ?? '';
  }

  setToken(token: string): void {
    localStorage.setItem(TOKEN_KEY, token);
  }

  clearToken(): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem('user_info');
  }

  private buildUrl(path: string): string {
    if (path.startsWith('http')) return path;
    return BASE_URL + (path.startsWith('/') ? path : '/' + path);
  }

  async request<T = unknown>(path: string, options: RequestInit = {}): Promise<ApiResult<T>> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...((options.headers as Record<string, string>) ?? {}),
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    try {
      const res = await fetch(this.buildUrl(path), { ...options, headers });
      if (res.status === 401) {
        this.clearToken();
        if (this.onUnauthorized) {
          this.onUnauthorized();
        } else {
          window.location.href = '/login.html?redirect=/console/';
        }
        return { isSuccess: false, status: 401, error: '认证过期，请重新登录' };
      }
      if (res.ok) {
        const data = await res.json().catch(() => undefined);
        return { isSuccess: true, status: res.status, data: data as T | undefined };
      }
      // 非 2xx（非 401）：优先解析后端 detail/message，无则回退 HTTP {status}
      // 对齐 uploadFile/downloadBlob 的错误体解析，让前端展示真实后端错误而非裸状态码
      const errorBody = await res.json().catch(() => undefined);
      const error =
        (errorBody?.detail as string) ?? (errorBody?.message as string) ?? `HTTP ${res.status}`;
      return { isSuccess: false, status: res.status, error };
    } catch (err) {
      return {
        isSuccess: false,
        status: 0,
        error: err instanceof Error ? err.message : String(err),
      };
    }
  }

  /** 读取 feature flags（含 console_v2_enabled） */
  async getFeatureFlags(): Promise<Record<string, unknown> | null> {
    const result = await this.request<Record<string, unknown>>('/api/config/feature-flags');
    return result.isSuccess && result.data ? result.data : null;
  }

  // ──────────────────────────────────────────────────────────────────
  //  文件上传 / 二进制下载 — CAD / Sketch-to-3D / IFC 导出
  // ──────────────────────────────────────────────────────────────────

  /**
   * multipart 文件上传，返回 JSON 响应。
   * 不设 Content-Type，让浏览器自动添加 multipart boundary。
   */
  async uploadFile<T = unknown>(
    path: string,
    file: File,
    extraFields: Record<string, string> = {},
  ): Promise<ApiResult<T>> {
    const token = this.getToken();
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const formData = new FormData();
    formData.append('file', file);
    for (const [key, value] of Object.entries(extraFields)) {
      formData.append(key, value);
    }

    try {
      const res = await fetch(this.buildUrl(path), {
        method: 'POST',
        headers,
        body: formData,
      });
      if (res.status === 401) {
        this.clearToken();
        if (this.onUnauthorized) this.onUnauthorized();
        else window.location.href = '/login.html?redirect=/console/';
        return { isSuccess: false, status: 401, error: '认证过期，请重新登录' };
      }
      const data = res.ok ? await res.json().catch(() => undefined) : undefined;
      const errorBody = !res.ok ? await res.json().catch(() => undefined) : undefined;
      return {
        isSuccess: res.ok,
        status: res.status,
        data: data as T | undefined,
        error: res.ok ? undefined : (errorBody?.detail ?? `HTTP ${res.status}`),
      };
    } catch (err) {
      return {
        isSuccess: false,
        status: 0,
        error: err instanceof Error ? err.message : String(err),
      };
    }
  }

  /**
   * POST JSON 请求并下载二进制文件（blob）。
   * 用于 IFC 导出等返回 FileResponse 的端点。
   */
  async downloadBlob(
    path: string,
    body: Record<string, unknown> = {},
  ): Promise<{ isSuccess: boolean; status: number; blob?: Blob; filename?: string; error?: string }> {
    const token = this.getToken();
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    try {
      const res = await fetch(this.buildUrl(path), {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
      });
      if (res.status === 401) {
        this.clearToken();
        if (this.onUnauthorized) this.onUnauthorized();
        else window.location.href = '/login.html?redirect=/console/';
        return { isSuccess: false, status: 401, error: '认证过期，请重新登录' };
      }
      if (!res.ok) {
        const errorBody = await res.json().catch(() => undefined);
        return {
          isSuccess: false,
          status: res.status,
          error: errorBody?.detail ?? `HTTP ${res.status}`,
        };
      }
      const blob = await res.blob();
      // 从 Content-Disposition 提取文件名
      const cd = res.headers.get('content-disposition') ?? '';
      const filenameMatch = cd.match(/filename="?([^"]+)"?/);
      return {
        isSuccess: true,
        status: res.status,
        blob,
        filename: filenameMatch?.[1] ?? 'download.ifc',
      };
    } catch (err) {
      return {
        isSuccess: false,
        status: 0,
        error: err instanceof Error ? err.message : String(err),
      };
    }
  }

  // ──────────────────────────────────────────────────────────────────
  //  聊天 SSE 流式 — 对齐 Flutter SseService.streamChat + api-client.js streamChat
  // ──────────────────────────────────────────────────────────────────

  /**
   * SSE 流式聊天。返回 AsyncGenerator，逐个 yield 解析后的事件。
   *
   * 后端 /api/agents/chat/stream 返回 text/event-stream，事件格式：
   *   data: {json}\n\n（json.event 标识事件类型，对齐 Flutter sse_service.dart:141）
   * type ∈ {meta, token, thinking_step, done, error}
   *
   * 用 fetch + ReadableStream 手动解析（EventSource 不支持 POST + Authorization header）。
   */
  async *streamChat(
    text: string,
    opts: {
      agentType?: string;
      projectId?: string | null;
      history?: Array<{ role: string; content: string; agent_type?: string }>;
      sessionId?: string | null;
    } = {},
  ): AsyncGenerator<import('../types/chat').SseEvent, void, unknown> {
    const token = this.getToken();
    const res = await fetch(this.buildUrl('/api/agents/chat/stream'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        message: text,
        agent_type: opts.agentType ?? 'master',
        project_id: opts.projectId ?? null,
        history: opts.history ?? [],
        session_id: opts.sessionId ?? null,
        stream: true,
      }),
    });

    if (res.status === 401) {
      this.clearToken();
      if (this.onUnauthorized) {
        this.onUnauthorized();
      } else {
        // v1.2.7: 带 redirect 参数，登录后回到 /console/（而非旧 workbench.html）
        window.location.href = '/login.html?redirect=/console/';
      }
      throw new Error('认证过期，请重新登录');
    }
    if (!res.ok || !res.body) {
      throw new Error(`SSE 连接失败: HTTP ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // SSE 事件以 \n\n 分隔
        let sep: number;
        while ((sep = buffer.indexOf('\n\n')) >= 0) {
          const rawEvent = buffer.slice(0, sep);
          buffer = buffer.slice(sep + 2);
          const evt = parseSseEvent(rawEvent);
          if (evt) yield evt;
          if (evt?.type === 'done' || evt?.type === 'error') return;
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  // ──────────────────────────────────────────────────────────────────
  //  语音智能体编排 — 迁移自 api-client.js:954-966
  // ──────────────────────────────────────────────────────────────────

  /** 启动语音任务编排（POST /api/voice/orchestrate） */
  async orchestrateVoice(
    text: string,
    projectId?: string | null,
  ): Promise<ApiResult> {
    return this.request('/api/voice/orchestrate', {
      method: 'POST',
      body: JSON.stringify({ text, project_id: projectId ?? null }),
    });
  }

  /** 查询语音任务列表（GET /api/voice/orchestrate/tasks）
   *  v1.2.7 修正：tasks 端点定义在 voice_orchestrate.py（prefix=/voice/orchestrate），
   *  非 voice.py。旧路径 /api/voice/tasks 返回 404。
   *  端点受 feature flag 门控，未启用时返回 503（业务层处理降级）。
   */
  async listVoiceTasks(): Promise<ApiResult<unknown[]>> {
    return this.request<unknown[]>('/api/voice/orchestrate/tasks');
  }

  // ──────────────────────────────────────────────────────────────────
  //  Agent 会话管理 — 对齐 Flutter ApiClient.getAgentSession
  // ──────────────────────────────────────────────────────────────────

  /** 获取会话详情（含历史消息） */
  async getAgentSession(sessionId: string): Promise<ApiResult> {
    return this.request(`/api/agents/sessions/${encodeURIComponent(sessionId)}`);
  }

  /** 列出当前用户会话 */
  async listAgentSessions(): Promise<ApiResult<unknown[]>> {
    return this.request<unknown[]>('/api/agents/sessions');
  }

  /**
   * 提交 Agent 回复反馈（POST /api/agents/feedback，对齐 app/api/agents.py:1879）。
   * L4 自适应学习：like 会被 BaseAgent.think() 作为 few-shot 注入同 agent 后续 prompt。
   */
  async submitAgentFeedback(payload: {
    agent_name: string;
    feedback_type: 'like' | 'dislike';
    user_message: string;
    agent_reply: string;
    session_id?: string | null;
    rating?: number;
    comment?: string;
  }): Promise<ApiResult> {
    return this.request('/api/agents/feedback', {
      method: 'POST',
      body: JSON.stringify({
        agent_name: payload.agent_name,
        feedback_type: payload.feedback_type,
        user_message: payload.user_message,
        agent_reply: payload.agent_reply,
        session_id: payload.session_id ?? null,
        rating: payload.rating ?? null,
        comment: payload.comment ?? '',
      }),
    });
  }

  // ──────────────────────────────────────────────────────────────────
  //  业务域 API — 批次 4 接入（对齐 app/api/*.py）
  // ──────────────────────────────────────────────────────────────────

  /** 当前用户信息（GET /api/auth/me，对齐 UserResponse） */
  async getCurrentUser<T = import('../types/domain').User>(): Promise<ApiResult<T>> {
    return this.request<T>('/api/auth/me');
  }

  /** 退出登录（PASETO 无状态，本地清理 token 即可，对齐 Flutter settings_page._logout） */
  async logout(): Promise<void> {
    this.clearToken();
  }

  /** 项目列表（GET /api/projects，对齐 ProjectListResponse[]） */
  async listProjects<T = import('../types/domain').Project[]>(
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/projects');
  }

  /** 项目详情（GET /api/projects/{id}，对齐 ProjectResponse） */
  async getProject<T = import('../types/domain').Project>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/projects/${encodeURIComponent(projectId)}`);
  }

  /** 项目 BOM 清单（GET /api/materials/bom/{projectId}） */
  async getProjectBom<T = import('../types/domain').BomItem[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/materials/bom/${encodeURIComponent(projectId)}`);
  }

  /** 仪表盘概览（GET /api/dashboard/overview）— v1.2.9 Bento Dashboard 跨项目聚合 */
  async getDashboardOverview(): Promise<
    ApiResult<{
      projects: { total: number; draft: number; in_progress: number; completed: number };
      budget: { total_estimated: number; total_actual: number; utilization: number };
    }>
  > {
    return this.request('/api/dashboard/overview');
  }

  /** 创建项目（POST /api/projects） */
  async createProject<T = import('../types/domain').Project>(
    data: import('../types/domain').ProjectCreateInput,
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/projects', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /** 项目预算（GET /api/budgets/project/{id}） */
  async getBudget<T = import('../types/domain').Budget>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/budgets/project/${encodeURIComponent(projectId)}`);
  }

  /** 施工任务列表（GET /api/construction/tasks/{projectId}） */
  async getConstructionTasks<T = import('../types/domain').ConstructionTask[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/construction/tasks/${encodeURIComponent(projectId)}`);
  }

  /** 采购订单列表（GET /api/procurement/orders/{projectId}） */
  async getProcurementOrders<T = import('../types/domain').ProcurementOrder[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/procurement/orders/${encodeURIComponent(projectId)}`);
  }

  /** 项目结算单（GET /api/settlements/project/{projectId}） */
  async getSettlement<T = import('../types/domain').Settlement>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/settlements/project/${encodeURIComponent(projectId)}`);
  }

  /** 项目任务列表（GET /api/tasks/project/{projectId}） */
  async getProjectTasks<T = import('../types/domain').TaskListResponse>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/tasks/project/${encodeURIComponent(projectId)}`);
  }

  /** 我的任务（GET /api/tasks/mine） */
  async getMyTasks<T = import('../types/domain').TaskListResponse>(
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/tasks/mine');
  }

  // ──────────────────────────────────────────────────────────────────
  //  业务域 API — 批次 6 接入（物料/变更/工程队/智能家居/场景）
  // ──────────────────────────────────────────────────────────────────

  /** 物料分类列表（GET /api/materials/categories） */
  async getMaterialCategories<T = import('../types/domain').MaterialCategory[]>(
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/materials/categories');
  }

  /** 物料列表（GET /api/materials） */
  async getMaterials<T = import('../types/domain').Material[]>(
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/materials');
  }

  /** 项目变更单列表（GET /api/change-orders/project/{projectId}） */
  async getChangeOrders<T = import('../types/domain').ChangeOrder[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/change-orders/project/${encodeURIComponent(projectId)}`);
  }

  /** 工程队列表（GET /api/crews） */
  async getCrews<T = import('../types/domain').ConstructionCrew[]>(
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/crews');
  }

  /** 项目工程队匹配结果（GET /api/crews/matches/{projectId}） */
  async getCrewMatches<T = import('../types/domain').CrewMatch[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/crews/matches/${encodeURIComponent(projectId)}`);
  }

  /** 项目智能家居方案列表（GET /api/smart-home/schemes/project/{projectId}） */
  async getSmartHomeSchemes<T = import('../types/domain').SmartHomeScheme[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/smart-home/schemes/project/${encodeURIComponent(projectId)}`);
  }

  /** 项目场景自动化列表（GET /api/scene-automation/scenes/project/{projectId}） */
  async getSceneAutomations<T = import('../types/domain').SceneAutomation[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/scene-automation/scenes/project/${encodeURIComponent(projectId)}`);
  }

  // ──────────────────────────────────────────────────────────────────
  //  业务域 API — 批次 7 接入（户型/灯光/软装/厨房/卫浴/门窗防水）
  // ──────────────────────────────────────────────────────────────────

  /** 项目户型方案列表（GET /api/floorplans/project/{projectId}） */
  async getFloorPlans<T = import('../types/domain').FloorPlan[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/floorplans/project/${encodeURIComponent(projectId)}`);
  }

  /** 项目正向工程量算量（GET /api/takeoff/project/{projectId}）— 对齐 quantity_takeoff_service.ForwardTakeoffResult
   *  flag: forward_takeoff_enabled（关闭时后端返 503，提示走 POST /takeoff/wall 手工计算） */
  async getProjectTakeoff<T = import('../types/domain').ForwardTakeoffResult>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/takeoff/project/${encodeURIComponent(projectId)}`);
  }

  /** 项目土建构件列表（GET /api/structural/projects/{projectId}/{type}）— type ∈ walls|beams|columns|slabs */
  async getStructuralItems<T = unknown>(
    projectId: string,
    kind: 'walls' | 'beams' | 'columns' | 'slabs',
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/structural/projects/${encodeURIComponent(projectId)}/${kind}`);
  }

  /** 电器分类列表（GET /api/appliances/categories） */
  async getApplianceCategories<T = import('../types/domain').ApplianceCategory[]>(): Promise<ApiResult<T>> {
    return this.request<T>('/api/appliances/categories');
  }

  /** 电器搜索/筛选（GET /api/appliances/search）— 对齐 app/api/appliance.py:113 */
  async searchAppliances<T = import('../types/domain').Appliance[]>(
    params: { categoryId?: string; keyword?: string } = {},
  ): Promise<ApiResult<T>> {
    const qs = new URLSearchParams();
    if (params.categoryId) qs.set('category_id', params.categoryId);
    if (params.keyword) qs.set('keyword', params.keyword);
    const query = qs.toString();
    return this.request<T>(`/api/appliances/search${query ? `?${query}` : ''}`);
  }

  /** 产品/服务列表（GET /api/products）— 全局，user 维度 */
  async getProducts<T = import('../types/domain').Product[]>(): Promise<ApiResult<T>> {
    return this.request<T>('/api/products');
  }

  /** 家具品类库列表（GET /api/furniture-catalog）— 全局 */
  async getFurnitureCatalog<T = import('../types/domain').FurnitureCatalogItem[]>(): Promise<ApiResult<T>> {
    return this.request<T>('/api/furniture-catalog');
  }

  /** 项目硬装方案列表（GET /api/hard-decoration/schemes/project/{projectId}） */
  async getHardDecorationSchemes<T = import('../types/domain').HardDecorationScheme[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/hard-decoration/schemes/project/${encodeURIComponent(projectId)}`);
  }

  /** 房型水电点位标准（GET /api/mep/room-standards/{roomType}）— 对齐 mep_service.ROOM_MEP_STANDARDS */
  async getMepRoomStandard<T = import('../types/domain').MepRoomStandard>(
    roomType: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/mep/room-standards/${encodeURIComponent(roomType)}`);
  }

  /** 项目 VR 全景图列表（GET /api/vr/panoramas/project/{projectId}） */
  async getVRPanoramas<T = import('../types/domain').VRPanoramaListItem[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/vr/panoramas/project/${encodeURIComponent(projectId)}`);
  }

  /** 项目灯光方案列表（GET /api/lighting/schemes/project/{projectId}） */
  async getLightingSchemes<T = import('../types/domain').LightingScheme[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/lighting/schemes/project/${encodeURIComponent(projectId)}`);
  }

  /** 项目软装方案列表（GET /api/soft-furnishing/schemes/project/{projectId}） */
  async getSoftFurnishingSchemes<T = import('../types/domain').SoftFurnishingScheme[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/soft-furnishing/schemes/project/${encodeURIComponent(projectId)}`);
  }

  /** 项目厨房设计列表（GET /api/kitchen/designs/project/{projectId}） */
  async getKitchenDesigns<T = import('../types/domain').KitchenDesign[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/kitchen/designs/project/${encodeURIComponent(projectId)}`);
  }

  /** 项目卫浴设计列表（GET /api/bathroom/designs/project/{projectId}） */
  async getBathroomDesigns<T = import('../types/domain').BathroomDesign[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/bathroom/designs/project/${encodeURIComponent(projectId)}`);
  }

  /** 项目门窗规格列表（GET /api/door-window-waterproof/door-windows/project/{projectId}） */
  async getDoorWindowSpecs<T = import('../types/domain').DoorWindowSpec[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/door-window-waterproof/door-windows/project/${encodeURIComponent(projectId)}`);
  }

  /** 项目防水方案列表（GET /api/door-window-waterproof/waterproof/project/{projectId}） */
  async getWaterproofPlans<T = import('../types/domain').WaterproofPlan[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/door-window-waterproof/waterproof/project/${encodeURIComponent(projectId)}`);
  }

  // ── 定制家具（app/api/custom_furniture.py）──

  /** 项目定制家具设计列表（GET /api/custom-furniture/designs/project/{projectId}） */
  async getCustomFurnitureDesigns<T = import('../types/domain').CustomFurnitureDesign[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/custom-furniture/designs/project/${encodeURIComponent(projectId)}`);
  }

  /** 设计模块列表（GET /api/custom-furniture/designs/{designId}/modules） */
  async getFurnitureModules<T = import('../types/domain').FurnitureModule[]>(
    designId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/custom-furniture/designs/${encodeURIComponent(designId)}/modules`);
  }

  /** 设计 BOM（GET /api/custom-furniture/designs/{designId}/bom） */
  async getFurnitureBom<T = import('../types/domain').FurnitureBOMItem[]>(
    designId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/custom-furniture/designs/${encodeURIComponent(designId)}/bom`);
  }

  /** 设计价格估算（GET /api/custom-furniture/designs/{designId}/price） */
  async getFurniturePrice<T = import('../types/domain').FurniturePriceEstimate>(
    designId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/custom-furniture/designs/${encodeURIComponent(designId)}/price`);
  }

  /** 设计板材计算（GET /api/custom-furniture/designs/{designId}/panels） */
  async getFurniturePanels<T = import('../types/domain').FurniturePanelCompute>(
    designId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/custom-furniture/designs/${encodeURIComponent(designId)}/panels`);
  }

  /** 设计规格校验（GET /api/custom-furniture/designs/{designId}/validation） */
  async getFurnitureValidation<T = import('../types/domain').FurnitureValidation>(
    designId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/custom-furniture/designs/${encodeURIComponent(designId)}/validation`);
  }

  // ── 质检（app/api/construction.py 内 quality 端点）──

  /** 项目质量问题列表（GET /api/construction/quality-issues/{projectId}，可按 phase/status/severity 筛选） */
  async getQualityIssues<T = import('../types/domain').QualityIssue[]>(
    projectId: string,
    params: { phase?: string; status?: string; severity?: string } = {},
  ): Promise<ApiResult<T>> {
    const qs = new URLSearchParams();
    if (params.phase) qs.set('phase', params.phase);
    if (params.status) qs.set('status', params.status);
    if (params.severity) qs.set('severity', params.severity);
    const query = qs.toString();
    return this.request<T>(
      `/api/construction/quality-issues/${encodeURIComponent(projectId)}${query ? `?${query}` : ''}`,
    );
  }

  /** 阶段质检清单（GET /api/construction/quality-checklist/{phase}） */
  async getQualityChecklist<T = import('../types/domain').QualityChecklist>(
    phase: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/construction/quality-checklist/${encodeURIComponent(phase)}`);
  }

  // ── AI 渲染（app/api/ai_render.py）──

  /** AI 渲染能力（GET /api/ai-render/capabilities） */
  async getAIRenderCapabilities<T = import('../types/domain').AIRenderCapabilities>(): Promise<ApiResult<T>> {
    return this.request<T>('/api/ai-render/capabilities');
  }

  // ──────────────────────────────────────────────────────────────────
  //  业务域 API — 批次 12：CAD / Sketch-to-3D / IFC 导出
  // ──────────────────────────────────────────────────────────────────

  /** CAD DXF 导入解析（POST /api/cad-import/dxf，multipart upload） */
  async importCadDxf<T = import('../types/domain').CADImportResult>(
    file: File,
  ): Promise<ApiResult<T>> {
    return this.uploadFile<T>('/api/cad-import/dxf', file);
  }

  /** 草图分析（POST /api/sketch-to-3d/analyze，multipart upload） */
  async analyzeSketch<T = import('../types/domain').SketchAnalysisResult>(
    file: File,
    description: string = '',
  ): Promise<ApiResult<T>> {
    return this.uploadFile<T>('/api/sketch-to-3d/analyze', file, { description });
  }

  /** 草图转 3D 生成（POST /api/sketch-to-3d/generate-3d，multipart upload） */
  async generate3dFromSketch<T = import('../types/domain').Sketch3DResponse>(
    file: File,
    description: string = '',
    style: string = 'modern',
  ): Promise<ApiResult<T>> {
    return this.uploadFile<T>('/api/sketch-to-3d/generate-3d', file, { description, style });
  }

  /** 草图转 3D 支持格式（GET /api/sketch-to-3d/supported-formats） */
  async getSketchSupportedFormats<T = import('../types/domain').SketchSupportedFormats>(
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/sketch-to-3d/supported-formats');
  }

  /** 导出结构 IFC（POST /api/bim/export/structural/{projectId}，返回 FileResponse） */
  async exportStructuralIfc(
    projectId: string,
    options: import('../types/domain').IFCExportRequest,
  ) {
    return this.downloadBlob(
      `/api/bim/export/structural/${encodeURIComponent(projectId)}`,
      options as unknown as Record<string, unknown>,
    );
  }

  /** 导出设计 IFC（POST /api/bim/export/design/{planId}，返回 FileResponse） */
  async exportDesignIfc(
    planId: string,
    options: import('../types/domain').IFCExportRequest,
  ) {
    return this.downloadBlob(
      `/api/bim/export/design/${encodeURIComponent(planId)}`,
      options as unknown as Record<string, unknown>,
    );
  }

  // ──────────────────────────────────────────────────────────────────
  //  业务域 API — 批次 13：设计方案生成 + 动线分析
  // ──────────────────────────────────────────────────────────────────

  /**
   * 生成设计方案（POST /api/agents/design）。
   * 后端 DesignerAgent.generate_layouts 为纯算法、确定性（无 LLM），可安全做真实后端 E2E。
   * 对齐 app/api/agents.py:1268 DesignRequest { message, project_id?, room_info? }。
   */
  async requestDesign<T = import('../types/domain').DesignPlanResult>(
    message: string,
    roomInfo?: string,
    projectId?: string,
  ): Promise<ApiResult<T>> {
    const body: Record<string, unknown> = { message };
    if (roomInfo) body.room_info = roomInfo;
    if (projectId) body.project_id = projectId;
    return this.request<T>('/api/agents/design', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  /**
   * 动线分析（POST /api/agents/design/circulation）。
   * 纯算法：访客/家务/居住三动线评分 + 冲突检测 + 优化建议。确定性，无 LLM。
   * 对齐 app/agents/designer.py:186 analyze_circulation(rooms)。
   */
  async analyzeCirculation<T = import('../types/domain').CirculationAnalysisResult>(
    rooms: import('../types/domain').CirculationRoom[],
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/agents/design/circulation', {
      method: 'POST',
      body: JSON.stringify({ rooms }),
    });
  }

  /**
   * 生成 2-3 套设计方案（讨论式方案交互，POST /api/agents/design/proposals）。
   * LLM 主路径；LLM 不可用时后端降级为确定性单方案（source=fallback）。
   * 对齐 app/api/agents.py:1320 generate_design_proposals。
   */
  async generateDesignProposals<T = import('../types/domain').DesignProposalResult>(
    requirement: string,
    sessionId?: string,
  ): Promise<ApiResult<T>> {
    const body: Record<string, unknown> = { requirement };
    if (sessionId) body.session_id = sessionId;
    return this.request<T>('/api/agents/design/proposals', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  /**
   * 修订指定设计方案（讨论式方案交互，POST /api/agents/design/proposals/{id}/revise）。
   * 对齐 app/api/agents.py:1341 revise_design_proposal。
   */
  async reviseDesignProposal<T = import('../types/domain').DesignProposalReviseResult>(
    proposalId: string,
    change: string,
    sessionId?: string,
  ): Promise<ApiResult<T>> {
    const body: Record<string, unknown> = { change };
    if (sessionId) body.session_id = sessionId;
    return this.request<T>(`/api/agents/design/proposals/${encodeURIComponent(proposalId)}/revise`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  // ──────────────────────────────────────────────────────────────────
  //  B2B 装企交付（v1.4.x，借鉴"卖结果不卖功能"交付式产品）
  //  对齐 app/api/b2b_delivery.py：POST 落库 / GET 列表 / 详情 / 状态流转
  // ──────────────────────────────────────────────────────────────────

  /** 创建交付单（POST /api/b2b/delivery）→ 整包：设计方案+报价+施工计划 */
  async createDelivery<T = import('../types/domain').DeliveryPackage>(
    payload: {
      name?: string;
      area: number;
      style?: string;
      budget?: number;
      requirements?: string;
      rooms?: string;
      projectId?: string | null;
      asyncMode?: boolean;
    },
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/b2b/delivery', {
      method: 'POST',
      body: JSON.stringify({
        name: payload.name ?? '整装交付',
        area: payload.area,
        style: payload.style ?? 'modern',
        budget: payload.budget ?? 0,
        requirements: payload.requirements ?? '',
        rooms: payload.rooms ?? '客厅,卧室,厨房,卫生间',
        project_id: payload.projectId ?? null,
        async_mode: payload.asyncMode ?? false,
      }),
    });
  }

  /** 交付单列表（GET /api/b2b/delivery，当前用户强隔离） */
  async listDeliveries<T = import('../types/domain').DeliveryListItem[]>(
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/b2b/delivery');
  }

  /** 交付单详情（GET /api/b2b/delivery/{id}，整包快照） */
  async getDelivery<T = import('../types/domain').DeliveryOrderDetail>(
    orderId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/b2b/delivery/${encodeURIComponent(orderId)}`);
  }

  /** 交付单状态流转（PUT /api/b2b/delivery/{id}/status） */
  async updateDeliveryStatus<T = import('../types/domain').DeliveryOrderDetail>(
    orderId: string,
    status: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/b2b/delivery/${encodeURIComponent(orderId)}/status`, {
      method: 'PUT',
      body: JSON.stringify({ status }),
    });
  }

  // ──────────────────────────────────────────────────────────────────
  //  v1.5.0 F41-F47 新增功能（对齐 app/api/ 下各模块）
  // ──────────────────────────────────────────────────────────────────

  // ── F41 适老改造（app/api/elderly_adaptation.py）──

  /** 项目适老改造方案列表（GET /api/elderly-adaptation/schemes/project/{projectId}） */
  async getElderlyAdaptationSchemes<T = import('../types/domain').ElderlyAdaptationScheme[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/elderly-adaptation/schemes/project/${encodeURIComponent(projectId)}`);
  }

  /** 创建适老改造方案（POST /api/elderly-adaptation/schemes） */
  async createElderlyAdaptationScheme<T = import('../types/domain').ElderlyAdaptationScheme>(
    data: { project_id: string; name: string; occupant_type: string },
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/elderly-adaptation/schemes', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /** 方案合规校验（POST /api/elderly-adaptation/schemes/{id}/validate，GB 50763-2012） */
  async validateElderlyAdaptationScheme<T = import('../types/domain').ElderlyAdaptationValidation>(
    schemeId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/elderly-adaptation/schemes/${encodeURIComponent(schemeId)}/validate`, {
      method: 'POST',
    });
  }

  // ── F42 局部焕新（app/api/partial_renovation.py）──

  /** 局部焕新模板列表（GET /api/partial-renovation/templates） */
  async getPartialRenovationTemplates<T = import('../types/domain').PartialRenovationTemplate[]>(
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/partial-renovation/templates');
  }

  /** 项目局部焕新计划列表（GET /api/partial-renovation/plans/project/{projectId}） */
  async getPartialRenovationPlans<T = import('../types/domain').PartialRenovationPlan[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/partial-renovation/plans/project/${encodeURIComponent(projectId)}`);
  }

  /** 创建局部焕新计划（POST /api/partial-renovation/plans，按模板生成） */
  async createPartialRenovationPlan<T = import('../types/domain').PartialRenovationPlan>(
    data: { project_id: string; name: string; scope_type: string; budget_level: string },
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/partial-renovation/plans', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // ── F43 资金托管深化（app/api/escrow_trustee.py）──

  /** 开通存管账户（POST /api/escrow/trustee-accounts） */
  async createEscrowTrusteeAccount<T = import('../types/domain').EscrowTrusteeAccount>(
    data: {
      escrow_payment_id: string;
      trustee_type: string;
      account_no_masked: string;
      interest_to_owner: boolean;
      release_rule?: string;
    },
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/escrow/trustee-accounts', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /** 项目存管账户列表（GET /api/escrow/project/{projectId}/trustee-accounts） */
  async listEscrowTrusteeAccounts<T = import('../types/domain').EscrowTrusteeAccount[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/escrow/project/${encodeURIComponent(projectId)}/trustee-accounts`);
  }

  /** 存管账户详情（GET /api/escrow/trustee-accounts/{id}） */
  async getEscrowTrusteeAccount<T = import('../types/domain').EscrowTrusteeAccount>(
    accountId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/escrow/trustee-accounts/${encodeURIComponent(accountId)}`);
  }

  /** 节点验收双向确认（POST /api/escrow/trustee-accounts/{id}/acceptance，role=owner|contractor） */
  async confirmEscrowAcceptance<T = import('../types/domain').EscrowTrusteeAccount>(
    accountId: string,
    role: 'owner' | 'contractor',
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/escrow/trustee-accounts/${encodeURIComponent(accountId)}/acceptance`, {
      method: 'POST',
      body: JSON.stringify({ role }),
    });
  }

  /** 放款（POST /api/escrow/trustee-accounts/{id}/release） */
  async releaseEscrowFunds<T = import('../types/domain').EscrowTrusteeAccount>(
    accountId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/escrow/trustee-accounts/${encodeURIComponent(accountId)}/release`, {
      method: 'POST',
    });
  }

  /** 托管资金利息信息（GET /api/escrow/trustee-accounts/{id}/interest） */
  async getEscrowInterest<T = import('../types/domain').EscrowInterestInfo>(
    accountId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/escrow/trustee-accounts/${encodeURIComponent(accountId)}/interest`);
  }

  // ── F44 环保材料标签（app/api/eco_materials.py）──

  /** 按环保等级筛选材料（GET /api/eco-materials/materials?grade=） */
  async getEcoMaterials<T = import('../types/domain').MaterialEcoCertItem[]>(
    grade?: string,
  ): Promise<ApiResult<T>> {
    const qs = grade ? `?grade=${encodeURIComponent(grade)}` : '';
    return this.request<T>(`/api/eco-materials/materials${qs}`);
  }

  /** 环保等级数量统计（GET /api/eco-materials/grades） */
  async getEcoGrades<T = import('../types/domain').EcoGradeCounts>(): Promise<ApiResult<T>> {
    return this.request<T>('/api/eco-materials/grades');
  }

  /** 分配环保认证标签（POST /api/eco-materials/certs，已存在则更新） */
  async assignEcoCert<T = import('../types/domain').MaterialEcoCertItem>(
    data: { material_id: string; eco_grade: string; certification: string; source: string },
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/eco-materials/certs', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /** 环保合规校验报告（POST /api/eco-materials/validate，对标 HC-003） */
  async validateEcoCompliance<T = import('../types/domain').EcoComplianceReport>(
    materialIds: string[],
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/eco-materials/validate', {
      method: 'POST',
      body: JSON.stringify({ material_ids: materialIds }),
    });
  }

  // ── F45 方案前置决策（app/api/solution_first.py）──

  /** 生成 3 套前置方案 + 预算区间（POST /api/solution-first/generate） */
  async generateSolutionFirst<T = import('../types/domain').SolutionFirstPackage>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/solution-first/generate', {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId }),
    });
  }

  // ── F46 生态桥接优先级（app/api/ecosystem.py）──

  /** 生态桥接状态报告（GET /api/ecosystem/status，含诚实降级标注） */
  async getEcosystemStatus<T = import('../types/domain').EcosystemBridgeStatus>(): Promise<ApiResult<T>> {
    return this.request<T>('/api/ecosystem/status');
  }

  /** 生态桥接优先级列表（GET /api/ecosystem/bridges） */
  async getEcosystemBridges<T = import('../types/domain').EcosystemBridges>(): Promise<ApiResult<T>> {
    return this.request<T>('/api/ecosystem/bridges');
  }

  // ── F47 AI 装修问答（app/api/ai_qa.py）──

  /** 知识库问答搜索（POST /api/ai-qa/search，未命中诚实降级） */
  async searchAIQA<T = import('../types/domain').AIQAResult>(
    query: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/ai-qa/search', {
      method: 'POST',
      body: JSON.stringify({ query }),
    });
  }

  /** FAQ 话题列表（GET /api/ai-qa/faq，知识库 faq 域前 20 条） */
  async getAIQAFaq<T = import('../types/domain').AIQAFaq>(): Promise<ApiResult<T>> {
    return this.request<T>('/api/ai-qa/faq');
  }

  // ──────────────────────────────────────────────────────────────────
  //  缺口补齐批次：F11/F13 预算对比与模板、F18 厨卫水电、F35 服务商匹配、F40 协作 IM
  // ──────────────────────────────────────────────────────────────────

  // ── F11/F13 预算（app/api/budgets.py + app/agents/budget.py）──

  /** 多方案预算对比（POST /api/budgets/compare-plans，按面积生成经济/舒适/品质三档） */
  async compareBudgetPlans<T = import('../types/domain').BudgetCompareResult>(
    message: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/budgets/compare-plans', {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
  }

  /** 预算模板列表（GET /api/budgets/templates） */
  async listBudgetTemplates<T = import('../types/domain').BudgetTemplateList>(
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/budgets/templates');
  }

  /** 应用预算模板（POST /api/budgets/templates/apply，按面积等比缩放） */
  async applyBudgetTemplate<T = import('../types/domain').BudgetTemplateApplyResult>(
    templateCode: string,
    area?: number,
  ): Promise<ApiResult<T>> {
    const body: Record<string, unknown> = { template_code: templateCode };
    if (area != null) body.area = area;
    return this.request<T>('/api/budgets/templates/apply', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  // ── F18 厨卫水电（app/api/kitchen_bath_mep.py）──

  /** 项目厨卫水电方案列表（GET /api/mep-kb/plans/project/{projectId}） */
  async listKitchenBathMepPlans<T = import('../types/domain').KitchenBathMEPPlan[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/mep-kb/plans/project/${encodeURIComponent(projectId)}`);
  }

  /** 厨卫水电方案点位列表（GET /api/mep-kb/plans/{planId}/points） */
  async getKitchenBathMepPoints<T = import('../types/domain').MEPPoint[]>(
    planId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/mep-kb/plans/${encodeURIComponent(planId)}/points`);
  }

  /** 厨房回路设计（GET /api/mep-kb/plans/{planId}/circuits） */
  async getKitchenCircuits<T = import('../types/domain').MEPCircuitResult>(
    planId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/mep-kb/plans/${encodeURIComponent(planId)}/circuits`);
  }

  /** 等电位校验（GET /api/mep-kb/plans/{planId}/equipotential，GB 50096） */
  async getEquipotentialCheck<T = import('../types/domain').MEPEquipotentialResult>(
    planId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/mep-kb/plans/${encodeURIComponent(planId)}/equipotential`);
  }

  /** 燃气管道规划（GET /api/mep-kb/plans/{planId}/gas） */
  async getGasPlan<T = import('../types/domain').MEPGasResult>(
    planId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/mep-kb/plans/${encodeURIComponent(planId)}/gas`);
  }

  // ── F35 服务商匹配（app/api/workers.py）──

  /** 服务商列表（GET /api/workers，支持 role 过滤） */
  async listWorkers<T = import('../types/domain').ServiceWorker[]>(
    role?: string,
  ): Promise<ApiResult<T>> {
    const qs = role ? `?role=${encodeURIComponent(role)}` : '';
    return this.request<T>(`/api/workers${qs}`);
  }

  /** 智能匹配服务商（POST /api/workers/match，六维评分） */
  async matchWorkers<T = import('../types/domain').WorkerMatch[]>(
    payload: { project_id: string; role?: string; top_n?: number },
  ): Promise<ApiResult<T>> {
    const body: Record<string, unknown> = { project_id: payload.project_id };
    if (payload.role) body.role = payload.role;
    if (payload.top_n != null) body.top_n = payload.top_n;
    return this.request<T>('/api/workers/match', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  /** 项目服务商匹配记录（GET /api/workers/matches/{projectId}） */
  async getWorkerMatches<T = import('../types/domain').WorkerMatch[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/workers/matches/${encodeURIComponent(projectId)}`);
  }

  /** 更新匹配状态（PATCH /api/workers/matches/{matchId}/status?status=） */
  async updateWorkerMatchStatus<T = import('../types/domain').WorkerMatch>(
    matchId: string,
    status: 'shortlisted' | 'hired' | 'rejected',
  ): Promise<ApiResult<T>> {
    return this.request<T>(
      `/api/workers/matches/${encodeURIComponent(matchId)}/status?status=${encodeURIComponent(status)}`,
      { method: 'PATCH' },
    );
  }

  // ── F40 三方协作 IM（app/api/chat.py）──

  /** 获取（或创建）项目聊天室（GET /api/chat/rooms/{projectId}） */
  async getChatRoom<T = import('../types/domain').ChatRoom>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/chat/rooms/${encodeURIComponent(projectId)}`);
  }

  /** 项目消息列表（GET /api/chat/messages/{projectId}，含 Agent 自动回复标注） */
  async listChatMessages<T = import('../types/domain').ChatMessage[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/chat/messages/${encodeURIComponent(projectId)}`);
  }

  /** 发送消息（POST /api/chat/messages） */
  async sendChatMessage<T = import('../types/domain').ChatMessage>(
    payload: { project_id: string; content: string; message_type?: string },
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/chat/messages', {
      method: 'POST',
      body: JSON.stringify({
        project_id: payload.project_id,
        content: payload.content,
        message_type: payload.message_type ?? 'text',
      }),
    });
  }

  /** 查询聊天室内 Agent 成员（GET /api/chat/rooms/{roomId}/agents） */
  async listRoomAgents<T = import('../types/domain').ChatRoomAgents>(
    roomId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/chat/rooms/${encodeURIComponent(roomId)}/agents`);
  }

  // ──────────────────────────────────────────────────────────────────
  //  Agent 治理 — GB/Z 185 身份卡 / 工具批准 / Skill / 记忆 / A2A / MCP / Harness / Eval
  //  对齐 app/api/agent_identity.py、agent_approvals.py、agent_skills.py、
  //  agent_memory.py、a2a.py、mcp.py、harness_api.py、eval.py
  // ──────────────────────────────────────────────────────────────────

  // ── GB/Z 185 身份卡（app/api/agent_identity.py，flag: gbz185_agent_card_enabled）──

  /** 支持身份码的 Agent 列表（GET /api/agents/identity） */
  async listAgentIdentityCards<T = import('../types/domain').AgentIdentityListResponse>(
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/agents/identity');
  }

  /** 单个 Agent 身份卡（GET /api/agents/identity/{name}，28 位 AID + ACDL） */
  async getAgentIdentityCard<T = import('../types/domain').AgentIdentityCard>(
    name: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/agents/identity/${encodeURIComponent(name)}`);
  }

  // ── Agent 工具批准（app/api/agent_approvals.py）──

  /** 待批准请求列表（GET /api/agents/approvals，仅 pending） */
  async listAgentApprovals<T = import('../types/domain').AgentApprovalListResponse>(
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/agents/approvals');
  }

  /** 单条批准请求（GET /api/agents/approvals/{approvalId}） */
  async getAgentApproval<T = import('../types/domain').AgentApprovalItem>(
    approvalId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/agents/approvals/${encodeURIComponent(approvalId)}`);
  }

  /** 批准请求（POST /api/agents/approvals/{approvalId}/approve） */
  async approveAgentApproval<T = import('../types/domain').AgentApprovalItem>(
    approvalId: string,
    reason?: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/agents/approvals/${encodeURIComponent(approvalId)}/approve`, {
      method: 'POST',
      body: JSON.stringify({ reason: reason ?? null }),
    });
  }

  /** 拒绝请求（POST /api/agents/approvals/{approvalId}/reject） */
  async rejectAgentApproval<T = import('../types/domain').AgentApprovalItem>(
    approvalId: string,
    reason?: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/agents/approvals/${encodeURIComponent(approvalId)}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason: reason ?? null }),
    });
  }

  /** 执行已批准的工具调用（POST /api/agents/approvals/{approvalId}/execute） */
  async executeAgentApproval<T = import('../types/domain').AgentApprovalExecuteResponse>(
    approvalId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/agents/approvals/${encodeURIComponent(approvalId)}/execute`, {
      method: 'POST',
    });
  }

  // ── Agent Skill 资产（app/api/agent_skills.py，创建/导入受 agent_skill_enabled flag 控制）──

  /** Skill 列表（GET /api/agents/skills，支持 scope / include_archived 过滤） */
  async listAgentSkills<T = import('../types/domain').AgentSkillListResponse>(
    params: { scope?: string; includeArchived?: boolean } = {},
  ): Promise<ApiResult<T>> {
    const qs = new URLSearchParams();
    if (params.scope) qs.set('scope', params.scope);
    if (params.includeArchived) qs.set('include_archived', 'true');
    const query = qs.toString();
    return this.request<T>(`/api/agents/skills${query ? `?${query}` : ''}`);
  }

  /** 创建 Skill（POST /api/agents/skills，status=draft；flag 关闭返回 503） */
  async createAgentSkill<T = import('../types/domain').AgentSkillItem>(
    data: {
      name: string;
      description?: string;
      agent_name: string;
      system_prompt?: string;
      provider?: string;
      tools?: unknown[];
      cost_tier?: string;
      acceptance_criteria?: unknown[];
      owner_scope?: string;
      owner_id?: string | null;
    },
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/agents/skills', {
      method: 'POST',
      body: JSON.stringify({
        name: data.name,
        description: data.description ?? '',
        agent_name: data.agent_name,
        system_prompt: data.system_prompt ?? '',
        provider: data.provider ?? 'deepseek',
        tools: data.tools ?? [],
        cost_tier: data.cost_tier ?? 'standard',
        acceptance_criteria: data.acceptance_criteria ?? [],
        owner_scope: data.owner_scope ?? 'personal',
        owner_id: data.owner_id ?? null,
      }),
    });
  }

  /** Skill 详情（GET /api/agents/skills/{skillId}） */
  async getAgentSkill<T = import('../types/domain').AgentSkillItem>(
    skillId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/agents/skills/${encodeURIComponent(skillId)}`);
  }

  /** 更新 Skill（PUT /api/agents/skills/{skillId}，version+1） */
  async updateAgentSkill<T = import('../types/domain').AgentSkillItem>(
    skillId: string,
    data: Record<string, unknown>,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/agents/skills/${encodeURIComponent(skillId)}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  /** 软删除 Skill（DELETE /api/agents/skills/{skillId}） */
  async deleteAgentSkill(skillId: string): Promise<ApiResult<null>> {
    return this.request<null>(`/api/agents/skills/${encodeURIComponent(skillId)}`, {
      method: 'DELETE',
    });
  }

  /** 授权共享 Skill（POST /api/agents/skills/{skillId}/share） */
  async shareAgentSkill<T = import('../types/domain').AgentSkillItem>(
    skillId: string,
    data: { grant_to?: string[]; share_scope?: string },
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/agents/skills/${encodeURIComponent(skillId)}/share`, {
      method: 'POST',
      body: JSON.stringify({
        grant_to: data.grant_to ?? [],
        share_scope: data.share_scope ?? 'grant',
      }),
    });
  }

  /** 提升到 org 级（POST /api/agents/skills/{skillId}/promote，仅 admin） */
  async promoteAgentSkill<T = import('../types/domain').AgentSkillItem>(
    skillId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/agents/skills/${encodeURIComponent(skillId)}/promote`, {
      method: 'POST',
    });
  }

  /** 回退到指定 version（POST /api/agents/skills/{skillId}/rollback） */
  async rollbackAgentSkill<T = import('../types/domain').AgentSkillItem>(
    skillId: string,
    targetVersion: number,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/agents/skills/${encodeURIComponent(skillId)}/rollback`, {
      method: 'POST',
      body: JSON.stringify({ target_version: targetVersion }),
    });
  }

  /** 从 git URL 导入 Skill 包（POST /api/agents/skills/import，flag 关闭返回 503） */
  async importAgentSkill<T = import('../types/domain').AgentSkillItem>(
    data: { git_url: string; owner_scope?: string; owner_id?: string | null },
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/agents/skills/import', {
      method: 'POST',
      body: JSON.stringify({
        git_url: data.git_url,
        owner_scope: data.owner_scope ?? 'personal',
        owner_id: data.owner_id ?? null,
      }),
    });
  }

  /** 实例化 Skill 并执行测试消息（POST /api/agents/skills/{skillId}/instantiate） */
  async instantiateAgentSkill<T = import('../types/domain').AgentSkillInstantiateResponse>(
    skillId: string,
    testMessage: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/agents/skills/${encodeURIComponent(skillId)}/instantiate`, {
      method: 'POST',
      body: JSON.stringify({ test_message: testMessage }),
    });
  }

  // ── Agent 长期记忆（app/api/agent_memory.py）──

  /** 记忆列表（GET /api/agents/memory，支持 scope / project_id 过滤） */
  async listAgentMemories<T = import('../types/domain').AgentMemoryListResponse>(
    params: { scope?: string; projectId?: string } = {},
  ): Promise<ApiResult<T>> {
    const qs = new URLSearchParams();
    if (params.scope) qs.set('scope', params.scope);
    if (params.projectId) qs.set('project_id', params.projectId);
    const query = qs.toString();
    return this.request<T>(`/api/agents/memory${query ? `?${query}` : ''}`);
  }

  /** 手动保存一条记忆（POST /api/agents/memory，同 key+scope+project_id 覆盖更新） */
  async createAgentMemory<T = import('../types/domain').AgentMemoryItem>(
    data: {
      category: string;
      key: string;
      value: string;
      importance?: number;
      scope?: string;
      project_id?: string | null;
    },
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/agents/memory', {
      method: 'POST',
      body: JSON.stringify({
        category: data.category,
        key: data.key,
        value: data.value,
        importance: data.importance ?? 1,
        scope: data.scope ?? 'personal',
        project_id: data.project_id ?? null,
      }),
    });
  }

  /** 删除一条记忆（DELETE /api/agents/memory/{memoryId}） */
  async deleteAgentMemory(memoryId: string): Promise<ApiResult<null>> {
    return this.request<null>(`/api/agents/memory/${encodeURIComponent(memoryId)}`, {
      method: 'DELETE',
    });
  }

  // ── A2A 协议（app/api/a2a.py，任务下发/查询受 a2a_enabled flag 控制）──

  /** 已注册 Agent 列表（GET /api/a2a/agents） */
  async listA2AAgents<T = import('../types/domain').A2AAgentListResponse>(
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/a2a/agents');
  }

  /** 下发任务到指定 Agent（POST /api/a2a/tasks/send；flag 关闭返回 503） */
  async sendA2ATask<T = import('../types/domain').A2ATaskResponse>(
    data: { agent_name: string; message: string; project_id?: string | null },
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/a2a/tasks/send', {
      method: 'POST',
      body: JSON.stringify({
        agent_name: data.agent_name,
        message: data.message,
        project_id: data.project_id ?? null,
      }),
    });
  }

  /** 任务详情（GET /api/a2a/tasks/{taskId}；flag 关闭返回 503） */
  async getA2ATask<T = import('../types/domain').A2ATaskResponse>(
    taskId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/a2a/tasks/${encodeURIComponent(taskId)}`);
  }

  /** 任务状态（GET /api/a2a/tasks/{taskId}/status；flag 关闭返回 503） */
  async getA2ATaskStatus<T = import('../types/domain').A2ATaskStatusResponse>(
    taskId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/a2a/tasks/${encodeURIComponent(taskId)}/status`);
  }

  // ── MCP Server（app/api/mcp.py + app/mcp/server.py）──

  /** 服务器元信息（GET /api/mcp/manifest） */
  async getMCPManifest<T = import('../types/domain').MCPManifest>(): Promise<ApiResult<T>> {
    return this.request<T>('/api/mcp/manifest');
  }

  /** 工具列表（GET /api/mcp/tools，MCP 协议格式） */
  async listMCPTools<T = import('../types/domain').MCPToolsResponse>(): Promise<ApiResult<T>> {
    return this.request<T>('/api/mcp/tools');
  }

  /** 调用工具（POST /api/mcp/tools/call） */
  async callMCPTool<T = import('../types/domain').MCPToolCallResult>(
    name: string,
    arguments_: Record<string, unknown>,
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/mcp/tools/call', {
      method: 'POST',
      body: JSON.stringify({ name, arguments: arguments_ }),
    });
  }

  /** MRTR 待响应请求列表（GET /api/mcp/mrtr；flag mcp_mrtr_enabled 关闭返回 503） */
  async listMCPMrtr<T = import('../types/domain').MCPMrtrListResponse>(): Promise<ApiResult<T>> {
    return this.request<T>('/api/mcp/mrtr');
  }

  // ── Harness（app/api/harness_api.py）──

  /** Harness 运行时指标（GET /api/harness/metrics，登录即可） */
  async getHarnessMetrics<T = import('../types/domain').HarnessMetrics>(): Promise<ApiResult<T>> {
    return this.request<T>('/api/harness/metrics');
  }

  /** 执行轨迹（GET /api/harness/traces，admin；支持 agent_name/status/limit 过滤） */
  async getHarnessTraces<T = import('../types/domain').HarnessTracesResponse>(
    params: { agentName?: string; status?: string; limit?: number } = {},
  ): Promise<ApiResult<T>> {
    const qs = new URLSearchParams();
    if (params.agentName) qs.set('agent_name', params.agentName);
    if (params.status) qs.set('status', params.status);
    if (params.limit != null) qs.set('limit', String(params.limit));
    const query = qs.toString();
    return this.request<T>(`/api/harness/traces${query ? `?${query}` : ''}`);
  }

  /** 离线评估（GET /api/harness/eval，admin；返回最近 100 条轨迹指标） */
  async getHarnessEval<T = import('../types/domain').HarnessEvalResponse>(): Promise<ApiResult<T>> {
    return this.request<T>('/api/harness/eval');
  }

  /** Harness 健康检查（GET /api/harness/health，公开） */
  async getHarnessHealth<T = import('../types/domain').HarnessHealthResponse>(): Promise<ApiResult<T>> {
    return this.request<T>('/api/harness/health');
  }

  // ── 评估框架（app/api/eval.py，flag: eval_enabled 关闭时返回 run_id="disabled" 报告）──

  /** 评估维度列表（GET /api/eval/dimensions） */
  async getEvalDimensions<T = import('../types/domain').EvalDimensionsResponse>(): Promise<ApiResult<T>> {
    return this.request<T>('/api/eval/dimensions');
  }

  /** 最近评估报告（GET /api/eval/report） */
  async getEvalReport<T = import('../types/domain').EvalReport>(): Promise<ApiResult<T>> {
    return this.request<T>('/api/eval/report');
  }

  /** 触发一次评估运行（POST /api/eval/run，admin；baseline ∈ base_llm|keyword|full_system|mock） */
  async runEval<T = import('../types/domain').EvalReport>(
    baseline: string,
    outputPath?: string,
  ): Promise<ApiResult<T>> {
    const body: Record<string, unknown> = { baseline };
    if (outputPath) body.output_path = outputPath;
    return this.request<T>('/api/eval/run', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  /** Agent 质量漂移检测（GET /api/eval/drift，admin；v1.12.x） */
  async getEvalDrift<T = import('../types/domain').EvalDriftResponse>(
    windowDays = 7,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/eval/drift?window_days=${windowDays}`);
  }

  /** Agent 治理安全审计（GET /api/admin/agent-governance-audit，平台管理员；v1.12.x） */
  async getGovernanceAudit<T = import('../types/domain').GovernanceAuditResponse>(): Promise<ApiResult<T>> {
    return this.request<T>('/api/admin/agent-governance-audit');
  }

  // ──────────────────────────────────────────────────────────────────
  //  积分商城（app/api/points.py，前缀 /api/points）
  // ──────────────────────────────────────────────────────────────────

  /** 当前用户积分账户（GET /api/points/account） */
  async getPointsAccount<T = import('../types/domain').PointsAccount>(): Promise<ApiResult<T>> {
    return this.request<T>('/api/points/account');
  }

  /** 指定用户积分账户（GET /api/points/account/{userId}） */
  async getPointsUserAccount<T = import('../types/domain').PointsAccount>(
    userId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/points/account/${encodeURIComponent(userId)}`);
  }

  /** 当前用户积分流水（GET /api/points/transactions?offset=&limit=） */
  async getPointsTransactions<T = import('../types/domain').PointsTransaction[]>(
    offset = 0,
    limit = 20,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/points/transactions?offset=${offset}&limit=${limit}`);
  }

  /** 积分规则列表（GET /api/points/rules） */
  async getPointsRules<T = import('../types/domain').PointsRule[]>(): Promise<ApiResult<T>> {
    return this.request<T>('/api/points/rules');
  }

  /** 管理员调整积分（POST /api/points/earn，仅 admin） */
  async earnPoints<T = import('../types/domain').PointsTransaction>(
    data: import('../types/domain').PointsEarnInput,
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/points/earn', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /** 积分商城商品列表（GET /api/points/mall?category=） */
  async getPointsMall<T = import('../types/domain').PointsMallItem[]>(
    category?: string,
  ): Promise<ApiResult<T>> {
    const qs = category ? `?category=${encodeURIComponent(category)}` : '';
    return this.request<T>(`/api/points/mall${qs}`);
  }

  /** 积分兑换商品（POST /api/points/redeem，body: { item_id }） */
  async redeemPoints<T = import('../types/domain').PointsRedemption>(
    itemId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/points/redeem', {
      method: 'POST',
      body: JSON.stringify({ item_id: itemId }),
    });
  }

  /** 当前用户兑换记录（GET /api/points/redemptions） */
  async getPointsRedemptions<T = import('../types/domain').PointsRedemption[]>(
    offset = 0,
    limit = 20,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/points/redemptions?offset=${offset}&limit=${limit}`);
  }

  /** 积分排行榜（GET /api/points/ranking?role=&year=&category=&limit=） */
  async getPointsRanking<T = import('../types/domain').PointsRankingEntry[]>(
    params: { role?: string; year?: number; category?: string; limit?: number } = {},
  ): Promise<ApiResult<T>> {
    const qs = new URLSearchParams();
    if (params.role) qs.set('role', params.role);
    if (params.year != null) qs.set('year', String(params.year));
    if (params.category) qs.set('category', params.category);
    if (params.limit != null) qs.set('limit', String(params.limit));
    const query = qs.toString();
    return this.request<T>(`/api/points/ranking${query ? `?${query}` : ''}`);
  }

  /** 重新计算排行榜（POST /api/points/ranking/recompute，仅 admin） */
  async recomputePointsRanking<T = { message: string; count: number }>(
    year?: number,
  ): Promise<ApiResult<T>> {
    const qs = year != null ? `?year=${year}` : '';
    return this.request<T>(`/api/points/ranking/recompute${qs}`, {
      method: 'POST',
    });
  }

  // ──────────────────────────────────────────────────────────────────
  //  AI 图生图（app/api/ai_image.py，前缀 /api/ai-image）
  // ──────────────────────────────────────────────────────────────────

  /** 创建图生图任务（POST /api/ai-image/jobs） */
  async createAIImageJob<T = import('../types/domain').AIImageJob>(
    data: import('../types/domain').AIImageJobCreateInput,
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/ai-image/jobs', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /** 项目图生图任务列表（GET /api/ai-image/jobs/project/{projectId}，支持 status_filter） */
  async listAIImageJobs<T = import('../types/domain').AIImageJobListItem[]>(
    projectId: string,
    statusFilter?: string,
  ): Promise<ApiResult<T>> {
    const qs = statusFilter ? `?status_filter=${encodeURIComponent(statusFilter)}` : '';
    return this.request<T>(`/api/ai-image/jobs/project/${encodeURIComponent(projectId)}${qs}`);
  }

  /** 任务详情（GET /api/ai-image/jobs/{jobId}） */
  async getAIImageJob<T = import('../types/domain').AIImageJob>(
    jobId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/ai-image/jobs/${encodeURIComponent(jobId)}`);
  }

  /** 触发任务处理（POST /api/ai-image/jobs/{jobId}/process，仅 queued/failed 可处理） */
  async processAIImageJob<T = import('../types/domain').AIImageJob>(
    jobId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/ai-image/jobs/${encodeURIComponent(jobId)}/process`, {
      method: 'POST',
    });
  }

  /** 任务状态（GET /api/ai-image/jobs/{jobId}/status，含 cost_yuan/render_backend） */
  async getAIImageJobStatus<T = import('../types/domain').AIImageJobStatus>(
    jobId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/ai-image/jobs/${encodeURIComponent(jobId)}/status`);
  }

  /** 删除任务（DELETE /api/ai-image/jobs/{jobId}） */
  async deleteAIImageJob(jobId: string): Promise<ApiResult<null>> {
    return this.request<null>(`/api/ai-image/jobs/${encodeURIComponent(jobId)}`, {
      method: 'DELETE',
    });
  }

  /** 预设模板列表（GET /api/ai-image/presets，按使用次数降序） */
  async listAIImagePresets<T = import('../types/domain').AIImagePreset[]>(
    category?: string,
  ): Promise<ApiResult<T>> {
    const qs = category ? `?category=${encodeURIComponent(category)}` : '';
    return this.request<T>(`/api/ai-image/presets${qs}`);
  }

  /** 创建预设模板（POST /api/ai-image/presets） */
  async createAIImagePreset<T = import('../types/domain').AIImagePreset>(
    data: import('../types/domain').AIImagePresetCreateInput,
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/ai-image/presets', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /** 预设详情（GET /api/ai-image/presets/{presetId}） */
  async getAIImagePreset<T = import('../types/domain').AIImagePreset>(
    presetId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/ai-image/presets/${encodeURIComponent(presetId)}`);
  }

  /** 应用预设模板创建任务（POST /api/ai-image/jobs/apply-preset） */
  async applyAIImagePreset<T = import('../types/domain').AIImageJob>(
    data: import('../types/domain').AIImageApplyPresetInput,
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/ai-image/jobs/apply-preset', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /** 批量渲染（POST /api/ai-image/jobs/batch，preset_ids 至少 1 个） */
  async batchAIImageRender<T = import('../types/domain').AIImageJob[]>(
    data: import('../types/domain').AIImageBatchRenderInput,
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/ai-image/jobs/batch', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // ──────────────────────────────────────────────────────────────────
  //  身份认证（app/api/identity.py，前缀 /api/identity）
  // ──────────────────────────────────────────────────────────────────

  /** 提交实名认证（POST /api/identity/submit） */
  async submitIdentity<T = import('../types/domain').IdentityVerification>(
    data: import('../types/domain').IdentitySubmitInput,
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/identity/submit', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /** 当前用户认证状态（GET /api/identity/status） */
  async getIdentityStatus<T = import('../types/domain').IdentityStatus>(): Promise<ApiResult<T>> {
    return this.request<T>('/api/identity/status');
  }

  /** 待审核认证列表（GET /api/identity/pending，仅 admin，非 admin 返回 403） */
  async listPendingIdentities<T = import('../types/domain').IdentityVerification[]>(
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/identity/pending');
  }

  /** 审核认证（POST /api/identity/{verificationId}/review，仅 admin；status ∈ approved|rejected） */
  async reviewIdentity<T = import('../types/domain').IdentityVerification>(
    verificationId: string,
    status: 'approved' | 'rejected',
    reviewNote?: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/identity/${encodeURIComponent(verificationId)}/review`, {
      method: 'POST',
      body: JSON.stringify({ status, review_note: reviewNote ?? null }),
    });
  }

  // ──────────────────────────────────────────────────────────────────
  //  量房 / AR 空间测量（app/api/surveys.py，前缀 /api/surveys）
  // ──────────────────────────────────────────────────────────────────

  /** 创建量房记录（POST /api/surveys，rooms 至少 1 个） */
  async createSurvey<T = import('../types/domain').SurveyDetail>(
    data: import('../types/domain').SurveyCreateInput,
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/surveys', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /** 项目量房列表（GET /api/surveys/project/{projectId}） */
  async listSurveys<T = import('../types/domain').SurveyItem[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/surveys/project/${encodeURIComponent(projectId)}`);
  }

  /** 量房详情（GET /api/surveys/{surveyId}） */
  async getSurvey<T = import('../types/domain').SurveyDetail>(
    surveyId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/surveys/${encodeURIComponent(surveyId)}`);
  }

  /** 更新量房（PUT /api/surveys/{surveyId}，空字段不更新） */
  async updateSurvey<T = import('../types/domain').SurveyDetail>(
    surveyId: string,
    data: import('../types/domain').SurveyUpdateInput,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/surveys/${encodeURIComponent(surveyId)}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  /** 删除量房（DELETE /api/surveys/{surveyId}） */
  async deleteSurvey(surveyId: string): Promise<ApiResult<null>> {
    return this.request<null>(`/api/surveys/${encodeURIComponent(surveyId)}`, {
      method: 'DELETE',
    });
  }

  /** 应用量房数据生成户型（POST /api/surveys/{surveyId}/apply） */
  async applySurvey<T = Record<string, unknown>>(surveyId: string): Promise<ApiResult<T>> {
    return this.request<T>(`/api/surveys/${encodeURIComponent(surveyId)}/apply`, {
      method: 'POST',
    });
  }

  /** 设备能力检测（GET /api/surveys/device-check，LiDAR/摄像头/语音等） */
  async getSurveyDeviceCheck<T = import('../types/domain').SurveyDeviceCheck>(
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/surveys/device-check');
  }

  /** AR 设备能力检测（POST /api/surveys/ar/device-capability） */
  async detectARDeviceCapability<T = import('../types/domain').ARDeviceCapabilityResult>(
    data: import('../types/domain').ARDeviceCapabilityInput,
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/surveys/ar/device-capability', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /** 创建 AR 扫描会话（POST /api/surveys/ar/sessions） */
  async createARScanSession<T = import('../types/domain').ARScanSession>(
    data: import('../types/domain').ARScanSessionCreateInput,
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/surveys/ar/sessions', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /** 项目 AR 会话列表（GET /api/surveys/ar/sessions/project/{projectId}，支持 status_filter） */
  async listARScanSessions<T = import('../types/domain').ARScanSessionListItem[]>(
    projectId: string,
    statusFilter?: string,
  ): Promise<ApiResult<T>> {
    const qs = statusFilter ? `?status_filter=${encodeURIComponent(statusFilter)}` : '';
    return this.request<T>(
      `/api/surveys/ar/sessions/project/${encodeURIComponent(projectId)}${qs}`,
    );
  }

  /** AR 会话详情（GET /api/surveys/ar/sessions/{sessionId}） */
  async getARScanSession<T = import('../types/domain').ARScanSession>(
    sessionId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/surveys/ar/sessions/${encodeURIComponent(sessionId)}`);
  }

  /** 更新 AR 会话（PATCH /api/surveys/ar/sessions/{sessionId}） */
  async updateARScanSession<T = import('../types/domain').ARScanSession>(
    sessionId: string,
    data: import('../types/domain').ARScanSessionUpdateInput,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/surveys/ar/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  /** 开始 AR 扫描（POST /api/surveys/ar/sessions/{sessionId}/start，created/failed 可开始） */
  async startARScan<T = import('../types/domain').ARScanSession>(
    sessionId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/surveys/ar/sessions/${encodeURIComponent(sessionId)}/start`, {
      method: 'POST',
    });
  }

  /** 处理扫描数据（POST /api/surveys/ar/sessions/{sessionId}/process，解析 USDZ/GLB 生成精度报告） */
  async processARScan<T = Record<string, unknown>>(
    sessionId: string,
    data: import('../types/domain').ARProcessScanInput,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/surveys/ar/sessions/${encodeURIComponent(sessionId)}/process`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /** 精度校验报告（GET /api/surveys/ar/sessions/{sessionId}/accuracy） */
  async getARAccuracyReport<T = import('../types/domain').ARAccuracyReport>(
    sessionId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/surveys/ar/sessions/${encodeURIComponent(sessionId)}/accuracy`);
  }

  /** 应用 AR 扫描结果到量房（POST /api/surveys/ar/sessions/{sessionId}/apply，需 completed） */
  async applyARScanSession<T = Record<string, unknown>>(
    sessionId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/surveys/ar/sessions/${encodeURIComponent(sessionId)}/apply`, {
      method: 'POST',
    });
  }

  /** 删除 AR 会话（DELETE /api/surveys/ar/sessions/{sessionId}） */
  async deleteARScanSession(sessionId: string): Promise<ApiResult<null>> {
    return this.request<null>(`/api/surveys/ar/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'DELETE',
    });
  }

  /** 添加墙面特征（POST /api/surveys/ar/features，门/窗/洞口/梁/柱/管道/开关插座） */
  async addWallFeature<T = import('../types/domain').WallFeature>(
    data: import('../types/domain').WallFeatureCreateInput,
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/surveys/ar/features', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /** 墙面特征列表（GET /api/surveys/ar/features/{sessionId}，支持 room_name 过滤） */
  async listWallFeatures<T = import('../types/domain').WallFeature[]>(
    sessionId: string,
    roomName?: string,
  ): Promise<ApiResult<T>> {
    const qs = roomName ? `?room_name=${encodeURIComponent(roomName)}` : '';
    return this.request<T>(`/api/surveys/ar/features/${encodeURIComponent(sessionId)}${qs}`);
  }

  /** 添加测量校准点（POST /api/surveys/ar/points，AR 值 + 人工参考值） */
  async addMeasurementPoint<T = import('../types/domain').MeasurementPoint>(
    data: import('../types/domain').MeasurementPointCreateInput,
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/surveys/ar/points', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /** 测量校准点列表（GET /api/surveys/ar/points/{sessionId}） */
  async listMeasurementPoints<T = import('../types/domain').MeasurementPoint[]>(
    sessionId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/surveys/ar/points/${encodeURIComponent(sessionId)}`);
  }

  // ──────────────────────────────────────────────────────────────────
  //  能耗监测（app/api/energy.py，前缀 /api/energy）
  // ──────────────────────────────────────────────────────────────────

  /** 项目能耗记录（GET /api/energy/records/project/{project_id}） */
  async listEnergyRecords<T = import('../types/domain').EnergyMonitorItem[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/energy/records/project/${encodeURIComponent(projectId)}`);
  }

  /** 方案能耗报告（GET /api/energy/report/{scheme_id}，含趋势/设备排行/节能建议） */
  async getEnergyReport<T = import('../types/domain').EnergyReport>(
    schemeId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/energy/report/${encodeURIComponent(schemeId)}`);
  }

  /** 方案节能建议（GET /api/energy/tips/{scheme_id}） */
  async listEnergyTips<T = import('../types/domain').EnergySavingTip[]>(
    schemeId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/energy/tips/${encodeURIComponent(schemeId)}`);
  }

  /** 采纳节能建议（PATCH /api/energy/tips/{tip_id}/apply） */
  async applyEnergyTip<T = import('../types/domain').EnergySavingTip>(
    tipId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/energy/tips/${encodeURIComponent(tipId)}/apply`, {
      method: 'PATCH',
    });
  }

  // ──────────────────────────────────────────────────────────────────
  //  支付管理（app/api/payments.py，前缀 /api/payments）
  // ──────────────────────────────────────────────────────────────────

  /** 项目支付列表（GET /api/payments/project/{project_id}） */
  async listPayments<T = import('../types/domain').PaymentItem[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/payments/project/${encodeURIComponent(projectId)}`);
  }

  /** 支付进度节点（GET /api/payments/schedule/{project_id}） */
  async getPaymentSchedule<T = import('../types/domain').PaymentScheduleNode[]>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/payments/schedule/${encodeURIComponent(projectId)}`);
  }

  /** 最终结算报告（GET /api/payments/final-settlement/{project_id}） */
  async getFinalSettlement<T = import('../types/domain').FinalSettlementReport>(
    projectId: string,
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/payments/final-settlement/${encodeURIComponent(projectId)}`);
  }

  /** 确认支付（POST /api/payments/{payment_id}/confirm） */
  async confirmPayment<T = import('../types/domain').PaymentItem>(
    paymentId: string,
    data: { transaction_id?: string; evidence_url?: string; payer?: string; payee?: string; note?: string } = {},
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/payments/${encodeURIComponent(paymentId)}/confirm`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /** 退款（POST /api/payments/{payment_id}/refund） */
  async refundPayment<T = import('../types/domain').PaymentItem>(
    paymentId: string,
    data: { refund_amount: number; refund_reason?: string },
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/payments/${encodeURIComponent(paymentId)}/refund`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /** 开具发票（POST /api/payments/{payment_id}/invoice） */
  async invoicePayment<T = import('../types/domain').PaymentItem>(
    paymentId: string,
    data: { invoice_url?: string; payer?: string; payee?: string; note?: string } = {},
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/payments/${encodeURIComponent(paymentId)}/invoice`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /** 支付标记失败（POST /api/payments/{payment_id}/fail） */
  async failPayment<T = import('../types/domain').PaymentItem>(
    paymentId: string,
    data: { reason?: string; note?: string } = {},
  ): Promise<ApiResult<T>> {
    return this.request<T>(`/api/payments/${encodeURIComponent(paymentId)}/fail`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }
}

/**
 * 解析单个 SSE 原始事件块（"event: xxx\ndata: {...}"）为 SseEvent。
 * 兼容后端多种字段命名（content/message/text、agent/agent_type、message_type）。
 */
function parseSseEvent(raw: string): import('../types/chat').SseEvent | null {
  const lines = raw.split('\n');
  let eventType = 'token';
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith('event:')) {
      eventType = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim());
    }
  }

  if (dataLines.length === 0) return null;
  const dataStr = dataLines.join('\n');

  let payload: Record<string, unknown> = {};
  try {
    payload = JSON.parse(dataStr);
  } catch {
    // 非 JSON data，作为纯文本 content
    return { type: eventType as import('../types/chat').SseEventType, content: dataStr };
  }

  // 后端 /agents/chat/stream 在 JSON 的 event 字段标识事件类型（对齐 Flutter sse_service.dart:142）
  // 优先 payload.event/payload.type，fallback 到 SSE event: 行（标准 SSE）
  const payloadType = (payload.event as string) ?? (payload.type as string);
  if (payloadType) {
    eventType = payloadType;
  }

  const content =
    (payload.content as string) ??
    (payload.message as string) ??
    (payload.text as string) ??
    (payload.delta as string) ??
    '';
  const agentType =
    (payload.agent_type as string) ??
    (payload.agent as string) ??
    undefined;
  const sessionId = (payload.session_id as string) ?? (payload.sessionId as string) ?? undefined;
  const messageType =
    (payload.message_type as string) ??
    (payload.messageType as string) ??
    undefined;
  const cardPayload =
    (payload.card_payload as Record<string, unknown>) ??
    (payload.cardPayload as Record<string, unknown>) ??
    undefined;
  const a2uiCards = (payload.a2ui_cards as unknown[]) ?? (payload.a2uiCards as unknown[]) ?? undefined;

  return {
    type: eventType as import('../types/chat').SseEventType,
    content: content || undefined,
    agentType,
    sessionId,
    messageType,
    cardPayload,
    a2uiCards,
  };
}

export const apiClient = ApiClient.instance;
