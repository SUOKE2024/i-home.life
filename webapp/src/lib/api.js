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

export async function register(phone, name, password) {
  const r = await request('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ phone, name, password }),
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
