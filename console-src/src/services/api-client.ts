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
          window.location.href = '/login.html';
        }
        return { isSuccess: false, status: 401, error: '认证过期，请重新登录' };
      }
      const data = res.ok ? await res.json().catch(() => undefined) : undefined;
      return {
        isSuccess: res.ok,
        status: res.status,
        data: data as T | undefined,
        error: res.ok ? undefined : `HTTP ${res.status}`,
      };
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

  /** 查询语音任务列表（GET /api/voice/tasks） */
  async listVoiceTasks(): Promise<ApiResult<unknown[]>> {
    return this.request<unknown[]>('/api/voice/tasks');
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

  // ──────────────────────────────────────────────────────────────────
  //  业务域 API — 批次 4 接入（对齐 app/api/*.py）
  // ──────────────────────────────────────────────────────────────────

  /** 当前用户信息（GET /api/auth/me，对齐 UserResponse） */
  async getCurrentUser<T = import('../types/domain').User>(): Promise<ApiResult<T>> {
    return this.request<T>('/api/auth/me');
  }

  /** 退出登录（POST /api/auth/logout，清理本地 token） */
  async logout(): Promise<void> {
    try {
      await this.request('/api/auth/logout', { method: 'POST' });
    } catch {
      // 后端 logout 失败也清本地
    }
    this.clearToken();
  }

  /** 项目列表（GET /api/projects，对齐 ProjectListResponse[]） */
  async listProjects<T = import('../types/domain').Project[]>(
  ): Promise<ApiResult<T>> {
    return this.request<T>('/api/projects');
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
