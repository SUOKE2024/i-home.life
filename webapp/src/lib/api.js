/**
 * 索克家居 WebApp API 客户端 — PASETO 封装（项目约定：PASETO 而非 JWT）
 *
 * 与后端 app/api/* 对齐；token 存 localStorage key 'paseto_token'（跨端共享登录态）。
 * 同源请求，dev 由 Vite proxy /api → localhost:8000。
 */

const TOKEN_KEY = 'paseto_token'

let onUnauthorizedCb = null

export function setOnUnauthorized(cb) {
  onUnauthorizedCb = cb
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem('user_info')
}

function buildUrl(path) {
  if (path.startsWith('http')) return path
  return path.startsWith('/') ? path : `/${path}`
}

/**
 * 统一请求。返回 { isSuccess, status, data, error }。
 * 401 → 清 token + 触发全局未授权回调（跳登录）。
 */
export async function request(path, options = {}) {
  const token = getToken()
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) }
  if (token) headers['Authorization'] = `Bearer ${token}`
  try {
    const res = await fetch(buildUrl(path), { ...options, headers })
    if (res.status === 401) {
      clearToken()
      if (onUnauthorizedCb) onUnauthorizedCb()
      return { isSuccess: false, status: 401, error: '认证过期，请重新登录' }
    }
    if (res.ok) {
      const data = await res.json().catch(() => undefined)
      return { isSuccess: true, status: res.status, data }
    }
    const errorBody = await res.json().catch(() => undefined)
    const error =
      (errorBody && (errorBody.detail || errorBody.message)) || `HTTP ${res.status}`
    return { isSuccess: false, status: res.status, error }
  } catch (err) {
    return { isSuccess: false, status: 0, error: err instanceof Error ? err.message : String(err) }
  }
}

// ──────────────────────────────────────────────────────────────
// 认证
// ──────────────────────────────────────────────────────────────

export async function login(phone, password) {
  const r = await request('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ phone, password }),
  })
  if (r.isSuccess && r.data && r.data.access_token) {
    setToken(r.data.access_token)
    localStorage.setItem('user_info', JSON.stringify(r.data.user || {}))
  }
  return r
}

export async function register(phone, name, password, role = 'homeowner') {
  const r = await request('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ phone, name, password, role }),
  })
  if (r.isSuccess && r.data && r.data.access_token) {
    setToken(r.data.access_token)
    localStorage.setItem('user_info', JSON.stringify(r.data.user || {}))
  }
  return r
}

export async function me() {
  return request('/api/auth/me')
}

export async function logout() {
  const r = await request('/api/auth/logout', { method: 'POST' })
  clearToken()
  return r
}

// ──────────────────────────────────────────────────────────────
// 运营商一键登录（阿里云号码认证 H5）
// ──────────────────────────────────────────────────────────────

/** 获取 H5 一键登录鉴权 Token（后端调用 GetAuthToken，返回 accessToken/jwtToken） */
export async function getOneClickAuthToken() {
  return request('/api/auth/oneclick/h5/auth-token', { method: 'POST' })
}

/** H5 一键登录：用 JS SDK 返回的 spToken 换取 PASETO Token */
export async function oneClickH5Login(spToken) {
  const r = await request('/api/auth/oneclick/h5/login', {
    method: 'POST',
    body: JSON.stringify({ sp_token: spToken }),
  })
  if (r.isSuccess && r.data && r.data.access_token) {
    setToken(r.data.access_token)
    localStorage.setItem('user_info', JSON.stringify(r.data.user || {}))
  }
  return r
}

// ──────────────────────────────────────────────────────────────
// 演示账号（对齐 scripts/seed.py 体验账户 / 123456）
// ──────────────────────────────────────────────────────────────

export const DEMO_ACCOUNTS = [
  { phone: '13800138000', label: '业主 · 张先生', hint: '完整演示项目（推荐）', role: 'homeowner', landing: '/' },
  { phone: '13900139000', label: '设计师 · 李设计师', hint: 'AI 设计工作台', role: 'designer', landing: '/console/' },
  { phone: '13700137000', label: '供应链 · 供应商', hint: '采购与供应', role: 'supplier', landing: '/console/procurement' },
  { phone: '13600136000', label: '监理', hint: '质检验收', role: 'contractor', landing: '/console/quality' },
  { phone: '13500135000', label: '管理员', hint: '平台全功能', role: 'admin', landing: '/' },
]

/** 一键演示登录：用指定演示账号直接换取 PASETO Token */
export async function demoLogin(phone = DEMO_ACCOUNTS[0].phone) {
  return login(phone, '123456')
}

// ──────────────────────────────────────────────────────────────
// 微信开放平台「网站应用」扫码登录
// ──────────────────────────────────────────────────────────────

/** 获取微信扫码授权链接（后端签发防 CSRF state，前端整页跳转） */
export async function wechatAuthorizeUrl() {
  return request('/api/auth/wechat/authorize-url')
}

/** 微信回调登录：code/state 换 PASETO Token */
export async function wechatLogin(code, state) {
  const r = await request('/api/auth/wechat/login', {
    method: 'POST',
    body: JSON.stringify({ code, state }),
  })
  if (r.isSuccess && r.data && r.data.access_token) {
    setToken(r.data.access_token)
    localStorage.setItem('user_info', JSON.stringify(r.data.user || {}))
  }
  return r
}

// ──────────────────────────────────────────────────────────────
// 聚合看板
// ──────────────────────────────────────────────────────────────

export async function getDashboardOverview() {
  return request('/api/dashboard/overview')
}

// ──────────────────────────────────────────────────────────────
// 项目
// ──────────────────────────────────────────────────────────────

export async function listProjects() {
  return request('/api/projects')
}

export async function getProject(projectId) {
  return request(`/api/projects/${encodeURIComponent(projectId)}`)
}

// 家的生命线：空间 / 预警 / 里程碑（健康分由预警严重度在前端估算）
export async function getFloorplans(projectId) {
  return request(`/api/floorplans/project/${projectId}`)
}
export async function getFloorplan(planId) {
  return request(`/api/floorplans/${planId}`)
}
export async function getProgressAlerts(projectId) {
  return request(`/api/construction/progress-alerts/${projectId}`)
}
export async function getMilestones(projectId) {
  return request(`/api/construction/milestones/${projectId}`)
}
// 首页 Feed：A2UI 8 类主动卡片（按项目现有数据组合，诚实标注）
export async function getFeedCards(projectId) {
  return request(`/api/feed/${projectId}`)
}

export async function createProject(data) {
  return request('/api/projects', { method: 'POST', body: JSON.stringify(data) })
}

export async function updateProject(projectId, data) {
  return request(`/api/projects/${encodeURIComponent(projectId)}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function deleteProject(projectId) {
  return request(`/api/projects/${encodeURIComponent(projectId)}`, { method: 'DELETE' })
}

// ──────────────────────────────────────────────────────────────
// 预算
// ──────────────────────────────────────────────────────────────

export async function getBudgetByProject(projectId) {
  return request(`/api/budgets/project/${encodeURIComponent(projectId)}`)
}

// ──────────────────────────────────────────────────────────────
// 施工
// ──────────────────────────────────────────────────────────────

export async function getConstructionTasks(projectId) {
  return request(`/api/construction/tasks/${encodeURIComponent(projectId)}`)
}

export async function createConstructionTask(projectId, data) {
  return request(`/api/construction/tasks/${encodeURIComponent(projectId)}`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function getQualityIssues(projectId) {
  return request(`/api/construction/quality-issues/${encodeURIComponent(projectId)}`)
}

export async function getQualityChecklist(phase) {
  return request(`/api/construction/quality-checklist/${encodeURIComponent(phase)}`)
}

// QA Inspector Agent：生成验收报告（可选 include_chart → chart_b64 诊断图表 + chart_analysis 视觉解读）
export async function generateAcceptanceReport(payload) {
  return request('/api/agents/qa-inspector/acceptance-report', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

// ──────────────────────────────────────────────────────────────
// 采购
// ──────────────────────────────────────────────────────────────

export async function getProcurementOrders(projectId) {
  return request(`/api/procurement/orders/${encodeURIComponent(projectId)}`)
}

export async function createProcurementOrder(projectId, data) {
  return request(`/api/procurement/orders/${encodeURIComponent(projectId)}`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// ──────────────────────────────────────────────────────────────
// 结算
// ──────────────────────────────────────────────────────────────

export async function getSettlementByProject(projectId) {
  return request(`/api/settlements/project/${encodeURIComponent(projectId)}`)
}

// ──────────────────────────────────────────────────────────────
// 智能家居
// ──────────────────────────────────────────────────────────────

export async function getSmartHomeSchemes(projectId) {
  return request(`/api/smart-home/schemes/project/${encodeURIComponent(projectId)}`)
}

export async function createSmartHomeScheme(projectId, data) {
  return request(`/api/smart-home/schemes/project/${encodeURIComponent(projectId)}`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// ──────────────────────────────────────────────────────────────
// 物料
// ──────────────────────────────────────────────────────────────

export async function getMaterialCategories() {
  return request('/api/materials/categories')
}

export async function getMaterials() {
  return request('/api/materials')
}

export async function getMaterial(materialId) {
  return request(`/api/materials/${encodeURIComponent(materialId)}`)
}

export async function getMaterialCert(materialId) {
  return request(`/api/eco-materials/certs/${encodeURIComponent(materialId)}`)
}

export async function addBomItem(data) {
  return request('/api/materials/bom', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// ──────────────────────────────────────────────────────────────
// VR 全景 / AR 量房（视觉表现层）
// ──────────────────────────────────────────────────────────────

export async function getVRPanoramas(projectId) {
  return request(`/api/vr/panoramas/project/${encodeURIComponent(projectId)}`)
}

export async function getVRPanorama(panoramaId) {
  return request(`/api/vr/panoramas/${encodeURIComponent(panoramaId)}`)
}

export async function getVRScenes(projectId) {
  return request(`/api/vr/scenes/project/${encodeURIComponent(projectId)}`)
}

/** 供应商列表（M4 供应商实景展厅，设计 4.2） */
export async function listSuppliers() {
  return request('/api/procurement/suppliers')
}

// ── M4 服务商作品集展厅（设计 4.3）──

/** 工程队列表（服务商作品集） */
export async function listCrews() {
  return request('/api/crews')
}

/** 工程队匹配（用户漫游后发起接单） */
export async function matchCrews(data) {
  return request('/api/crews/match', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

/** 工程队作品集聚合（施工进度 + 质检时间线，设计 4.3） */
export async function getCrewPortfolio(crewId) {
  return request(`/api/crews/${encodeURIComponent(crewId)}/portfolio`)
}

// ── M4 服务商付费展厅：积分商城权益兑换（设计 4.3）──

/** 积分商城商品列表（category=vip 为展厅权益商品） */
export async function getMallItems(category) {
  const q = category ? `?category=${encodeURIComponent(category)}` : ''
  return request(`/api/points/mall${q}`)
}

/** 兑换服务商展厅权益（作品集置顶 / VR 实拍） */
export async function redeemCrewBenefit(crewId, itemId) {
  return request(`/api/crews/${encodeURIComponent(crewId)}/benefits/redeem`, {
    method: 'POST',
    body: JSON.stringify({ item_id: itemId }),
  })
}

/** 工程队展厅权益兑换记录 */
export async function getCrewBenefits(crewId) {
  return request(`/api/crews/${encodeURIComponent(crewId)}/benefits`)
}

// ── 设计 4.1 效果图漫游：AI 效果图发布为效果图全景（content_source=effect）──

/** 把 AI 效果图发布为效果图漫游全景（2D 平面预览，诚实标注非实景） */
export async function publishEffectRender(data) {
  return request('/api/vr/panoramas/from-effect-render', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// ──────────────────────────────────────────────────────────────
// 设计流程编排（风格/预算选供应商 → VR 效果图 → 可行性分析）
// ──────────────────────────────────────────────────────────────

export async function createDesignFlow(data) {
  return request('/api/design-flow', { method: 'POST', body: JSON.stringify(data) })
}

export async function getDesignFlow(flowId) {
  return request(`/api/design-flow/${encodeURIComponent(flowId)}`)
}

export async function matchDesignFlowSuppliers(flowId) {
  return request(`/api/design-flow/${encodeURIComponent(flowId)}/suppliers/match`, { method: 'POST' })
}

export async function selectDesignFlowSupplier(flowId, data) {
  return request(`/api/design-flow/${encodeURIComponent(flowId)}/suppliers/select`, {
    method: 'POST',
    body: JSON.stringify(data || {}),
  })
}

export async function renderDesignFlow(flowId) {
  return request(`/api/design-flow/${encodeURIComponent(flowId)}/render`, { method: 'POST' })
}

export async function generateDesignFlowDrawings(flowId) {
  return request(`/api/design-flow/${encodeURIComponent(flowId)}/drawings`, { method: 'POST' })
}

export async function getDesignFlowDrawings(flowId) {
  return request(`/api/design-flow/${encodeURIComponent(flowId)}/drawings`)
}

export async function adjustDesignFlow(flowId, data) {
  return request(`/api/design-flow/${encodeURIComponent(flowId)}/adjust`, {
    method: 'POST',
    body: JSON.stringify(data || {}),
  })
}

export async function confirmDesignFlow(flowId) {
  return request(`/api/design-flow/${encodeURIComponent(flowId)}/confirm`, { method: 'POST' })
}

export async function getDesignFlowFeasibility(flowId) {
  return request(`/api/design-flow/${encodeURIComponent(flowId)}/feasibility`)
}

export async function suggestDesignFlow(flowId) {
  return request(`/api/design-flow/${encodeURIComponent(flowId)}/suggest`, { method: 'POST' })
}

// ── 窗帘智能展厅（单店铺固定「官渡区帘享空间窗帘布艺经营部」）──

/** 窗帘展厅总览（店铺 + 系列 + 安装方式 + 灯光预设 + 展示区域） */
export async function getCurtainShowroomOverview() {
  return request('/api/curtain-showroom/overview')
}

/** 窗帘展品列表（可按系列/品牌/材质筛选，3D 换装数据源） */
export async function getCurtainShowroomProducts(filters = {}) {
  const params = new URLSearchParams()
  if (filters.series_id) params.set('series_id', filters.series_id)
  if (filters.brand) params.set('brand', filters.brand)
  if (filters.fabric) params.set('fabric', filters.fabric)
  const q = params.toString()
  return request(`/api/curtain-showroom/products${q ? `?${q}` : ''}`)
}

/** 上传真实面料贴图（multipart，三件套：texture/normal/roughness） */
export async function uploadCurtainMap(productId, mapType, file) {
  const token = getToken()
  const form = new FormData()
  form.append('file', file)
  try {
    const res = await fetch(
      `/api/curtain-showroom/products/${encodeURIComponent(productId)}/maps/${encodeURIComponent(mapType)}`,
      {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      },
    )
    if (res.status === 401) {
      clearToken()
      if (onUnauthorizedCb) onUnauthorizedCb()
      return { isSuccess: false, status: 401, error: '认证过期，请重新登录' }
    }
    if (res.ok) {
      const data = await res.json().catch(() => undefined)
      return { isSuccess: true, status: res.status, data }
    }
    const errorBody = await res.json().catch(() => undefined)
    const error = (errorBody && (errorBody.detail || errorBody.message)) || `HTTP ${res.status}`
    return { isSuccess: false, status: res.status, error }
  } catch (err) {
    return { isSuccess: false, status: 0, error: err instanceof Error ? err.message : String(err) }
  }
}

// ── P0 设备热点联动（2026-08-12）──

/** 3D 设备图层聚合：设备锚点 + 状态 + 关联场景 + 最近传感器快照 */
export async function getDeviceOverlay(projectId) {
  return request(`/api/vr/projects/${encodeURIComponent(projectId)}/device-overlay`)
}

/** 设备命令（3D 场景/语音入口，action_status 诚实标注） */
export async function deviceCommand(deviceId, body) {
  return request(`/api/smart-home/devices/${encodeURIComponent(deviceId)}/command`, {
    method: 'POST',
    body: JSON.stringify(body || {}),
  })
}

/** 场景执行（3D 场景/语音触发入口） */
export async function sceneExecute(sceneId, triggerSource = 'vr_overlay') {
  return request(`/api/scene-automation/scenes/${encodeURIComponent(sceneId)}/execute`, {
    method: 'POST',
    body: JSON.stringify({ trigger_source: triggerSource }),
  })
}

/** 检测设备 AR 能力并返回推荐方法 + 降级链（POST /api/surveys/ar/device-capability） */
export async function arDeviceCapability(body) {
  return request('/api/surveys/ar/device-capability', {
    method: 'POST',
    body: JSON.stringify(body || {}),
  })
}

// ── Web 麦克风 → 后端语音端点 ──

/** 语音文本处理（复用后端 /api/voice/process-enhanced：情绪检测 + Agent 路由） */
export async function processVoice(text, projectId = null) {
  return request('/api/voice/process-enhanced', {
    method: 'POST',
    body: JSON.stringify({ text, project_id: projectId, emotion_enabled: true }),
  })
}

// ── Web 定位 → 后端传感器端点 ──

/** 上传传感器快照（复用后端 /api/sensors/snapshot：GPS/IMU 落库 + 场景触发检查） */
export async function uploadSensorSnapshot(body) {
  return request('/api/sensors/snapshot', {
    method: 'POST',
    body: JSON.stringify(body || {}),
  })
}

/** 创建 AR 量房扫描会话（POST /api/surveys/ar/sessions） */
export async function createARScanSession(data) {
  return request('/api/surveys/ar/sessions', {
    method: 'POST',
    body: JSON.stringify(data || {}),
  })
}

/** 按项目列出 AR 量房扫描会话（GET /api/surveys/ar/sessions/project/:id） */
export async function listARSessions(projectId) {
  return request(`/api/surveys/ar/sessions/project/${encodeURIComponent(projectId)}`)
}

/** 开始扫描（POST /api/surveys/ar/sessions/:id/start） */
export async function startARScan(sessionId) {
  return request(`/api/surveys/ar/sessions/${encodeURIComponent(sessionId)}/start`, { method: 'POST' })
}

/** 处理扫描数据，解析房间/点云/精度（POST /api/surveys/ar/sessions/:id/process） */
export async function processARScan(sessionId, data) {
  return request(`/api/surveys/ar/sessions/${encodeURIComponent(sessionId)}/process`, {
    method: 'POST',
    body: JSON.stringify(data || {}),
  })
}

/** 获取精度校验报告（GET /api/surveys/ar/sessions/:id/accuracy） */
export async function getARScanAccuracy(sessionId) {
  return request(`/api/surveys/ar/sessions/${encodeURIComponent(sessionId)}/accuracy`)
}

/** 添加测量校准点（POST /api/surveys/ar/points） */
export async function addARMeasurementPoint(data) {
  return request('/api/surveys/ar/points', {
    method: 'POST',
    body: JSON.stringify(data || {}),
  })
}

/** 将 AR 扫描结果应用到测量记录 Survey（POST /api/surveys/ar/sessions/:id/apply） */
export async function applyARScanSession(sessionId) {
  return request(`/api/surveys/ar/sessions/${encodeURIComponent(sessionId)}/apply`, { method: 'POST' })
}

// ──────────────────────────────────────────────────────────────
// Agent 聊天（SSE 流式）
// ──────────────────────────────────────────────────────────────

/**
 * SSE 流式聊天（对齐后端 /api/agents/chat/stream 事件：meta/token/done/error/thinking_step）。
 * onEvent 回调事件对象 { event, data, raw }。
 */
export async function streamChat({ message, projectId, sessionId }, onEvent, signal) {
  const token = getToken()
  const body = { message }
  if (projectId) body.project_id = projectId
  if (sessionId) body.session_id = sessionId

  const res = await fetch('/api/agents/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok || !res.body) {
    const err = await res.json().catch(() => undefined)
    throw new Error((err && (err.detail || err.message)) || `HTTP ${res.status}`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let doneMeta = null

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data:')) continue
      const payloadStr = trimmed.slice(5).trim()
      let payload
      try {
        payload = JSON.parse(payloadStr)
      } catch {
        continue
      }
      const event = payload.event || payload.type || 'message'
      if (event === 'meta' && payload.data) doneMeta = payload.data
      onEvent({ event, data: payload.data ?? payload, raw: payload })
    }
  }
  return doneMeta
}

// ──────────────────────────────────────────────────────────────
// 全链路诊断（v1.10.x，管理端）
// ──────────────────────────────────────────────────────────────

export async function getDiagnosticsOverview() {
  return request('/api/diagnostics/overview')
}

export async function getDiagnosticsEndpoints() {
  return request('/api/diagnostics/endpoints')
}

export async function getDiagnosticsMetrics(hours = 24, category = '', endpoint = '') {
  const params = new URLSearchParams()
  params.set('hours', String(hours))
  if (category) params.set('category', category)
  if (endpoint) params.set('endpoint', endpoint)
  return request(`/api/diagnostics/metrics?${params}`)
}

export async function getDiagnosticsTraces({ limit = 50, endpoint = '', errorOnly = false, agent = '' } = {}) {
  const params = new URLSearchParams()
  params.set('limit', String(limit))
  if (endpoint) params.set('endpoint', endpoint)
  if (errorOnly) params.set('error_only', 'true')
  if (agent) params.set('agent', agent)
  return request(`/api/diagnostics/traces?${params}`)
}

export async function getDiagnosticsTraceDetail(traceId) {
  return request(`/api/diagnostics/traces/${encodeURIComponent(traceId)}`)
}

export async function getDiagnosticsAlerts(status = '') {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  return request(`/api/diagnostics/alerts?${params}`)
}

export async function acknowledgeDiagnosticsAlert(alertId) {
  return request(`/api/diagnostics/alerts/${encodeURIComponent(alertId)}/ack`, { method: 'POST' })
}

export async function resolveDiagnosticsAlert(alertId) {
  return request(`/api/diagnostics/alerts/${encodeURIComponent(alertId)}/resolve`, { method: 'POST' })
}

export async function getDiagnosticsRecommendations(status = '') {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  return request(`/api/diagnostics/recommendations?${params}`)
}

export async function dismissDiagnosticsRecommendation(recId) {
  return request(`/api/diagnostics/recommendations/${encodeURIComponent(recId)}/dismiss`, { method: 'POST' })
}

export async function getDiagnosticsRum(hours = 24) {
  return request(`/api/diagnostics/rum?hours=${hours}`)
}

/**
 * 前端 RUM（Core Web Vitals）上报 — 公开端点，后端按 diagnostics_rum_enabled 门控落库。
 * 每页仅上报一次（约 4 条事件），失败静默。
 */
export function reportWebVitals(metrics = {}) {  try {
    const events = Object.entries(metrics)
      .filter(([, v]) => typeof v === 'number' && v >= 0)
      .map(([metric, value]) => ({
        type: 'perf',
        metric,
        value: Math.round(value * (metric === 'cls' ? 1000 : 1)) / (metric === 'cls' ? 1000 : 1),
        page: window.location.pathname,
        session_id: window.sessionStorage.getItem('ihome_rum_sid') || '',
      }))
    if (!events.length) return
    navigator.sendBeacon(
      '/api/analytics/collect',
      new Blob([JSON.stringify({ events })], { type: 'application/json' }),
    )
  } catch {
    /* RUM 上报失败静默 */
  }
}
