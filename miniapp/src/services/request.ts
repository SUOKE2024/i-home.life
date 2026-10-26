/**
 * 统一请求层（Taro.request 封装）。
 *
 * 设计要点：
 *  - 认证沿用项目既有 PASETO 口径（后端 /api/auth/*），不使用 JWT；
 *  - 401 触发一次「单飞刷新」：并发请求共享同一次 /auth/refresh，
 *    避免 SPA 多组件重复轮换导致 refresh 族被撤销；
 *  - 错误信息必须透出给用户：FastAPI 422 的 detail 是数组，需拍平为字符串，
 *    直接渲染对象在小程序端会报错；
 *  - 网络失败与业务失败分开：网络失败 status=0，业务失败带 HTTP 码。
 */
import Taro from '@tarojs/taro';
import { API_BASE, REQUEST_TIMEOUT, REFRESH_TOKEN_KEY, TOKEN_KEY } from '@/config/env';

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export interface RequestOptions {
  method?: HttpMethod;
  data?: Record<string, unknown> | undefined;
  /** 默认 true；公开接口（如健康检查）传 false 可不带 Authorization */
  auth?: boolean;
  /** 内部使用：401 重试标记 */
  retried?: boolean;
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }

  /** 401/403 可提示重新登录；0 为网络不可达 */
  get isAuthError(): boolean {
    return this.status === 401 || this.status === 403;
  }

  get isNetworkError(): boolean {
    return this.status === 0;
  }
}

// ── 令牌存取（小程序 storage，跨端共享登录态）──

export function getAccessToken(): string {
  try {
    return (Taro.getStorageSync(TOKEN_KEY) as string) || '';
  } catch {
    return '';
  }
}

export function getRefreshToken(): string {
  try {
    return (Taro.getStorageSync(REFRESH_TOKEN_KEY) as string) || '';
  } catch {
    return '';
  }
}

export function setTokens(accessToken?: string, refreshToken?: string): void {
  try {
    if (accessToken) Taro.setStorageSync(TOKEN_KEY, accessToken);
    if (refreshToken) Taro.setStorageSync(REFRESH_TOKEN_KEY, refreshToken);
  } catch (err) {
    console.error('[Request] 令牌写入失败', err);
  }
}

export function clearTokens(): void {
  try {
    Taro.removeStorageSync(TOKEN_KEY);
    Taro.removeStorageSync(REFRESH_TOKEN_KEY);
  } catch (err) {
    console.error('[Request] 令牌清理失败', err);
  }
}

/** FastAPI 错误体拍平：detail 可能是字符串、对象或 [{loc, msg}] 数组 */
function extractMessage(body: unknown, status: number): string {
  const payload = (body || {}) as Record<string, unknown>;
  const detail = payload.detail ?? payload.message ?? payload.error;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (typeof item === 'string') return item;
        const record = (item || {}) as Record<string, unknown>;
        const loc = Array.isArray(record.loc)
          ? record.loc.filter((part) => part !== 'body').join('.')
          : '';
        return [loc, String(record.msg || record.type || '')].filter(Boolean).join(': ');
      })
      .filter(Boolean);
    return parts.length ? parts.join('；') : `HTTP ${status}`;
  }
  if (detail && typeof detail === 'object') return JSON.stringify(detail);
  if (typeof detail === 'string' && detail) return detail;
  return `HTTP ${status}`;
}

let refreshPromise: Promise<boolean> | null = null;

/**
 * 刷新访问令牌（单飞）。成功返回 true 并更新本地令牌。
 * 失败即清理本地会话，由调用方引导重新登录。
 */
export function refreshSession(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;
  const refreshToken = getRefreshToken();
  if (!refreshToken) return Promise.resolve(false);

  refreshPromise = (async () => {
    try {
      const res = await Taro.request({
        url: `${API_BASE}/auth/refresh`,
        method: 'POST',
        timeout: REQUEST_TIMEOUT,
        header: { 'Content-Type': 'application/json' },
        data: { refresh_token: refreshToken }
      });
      if (res.statusCode < 200 || res.statusCode >= 300) return false;
      const data = (res.data || {}) as Record<string, string>;
      if (!data.access_token) return false;
      setTokens(data.access_token, data.refresh_token);
      return true;
    } catch (err) {
      console.warn('[Request] 令牌刷新失败', err);
      return false;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

/**
 * 发起请求并返回响应体。
 * @throws ApiError 业务错误（带 status）或网络错误（status=0）
 */
export async function request<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', data, auth = true, retried = false } = options;
  const header: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = auth ? getAccessToken() : '';
  if (token) header.Authorization = `Bearer ${token}`;

  let res: Taro.request.SuccessCallbackResult<unknown>;
  try {
    res = await Taro.request({
      url: path.startsWith('http') ? path : `${API_BASE}${path}`,
      method,
      data,
      header,
      timeout: REQUEST_TIMEOUT
    });
  } catch (err) {
    console.error('[Request] 网络请求失败', path, err);
    throw new ApiError('网络连接失败，请检查网络后重试', 0);
  }

  const { statusCode } = res;
  if (statusCode >= 200 && statusCode < 300) {
    return res.data as T;
  }

  // 401：尝试刷新一次后重放（仅当请求本身带认证）
  if (statusCode === 401 && auth && !retried) {
    const refreshed = await refreshSession();
    if (refreshed) {
      return request<T>(path, { ...options, retried: true });
    }
    clearTokens();
  }

  throw new ApiError(extractMessage(res.data, statusCode), statusCode);
}

export const get = <T = unknown>(path: string, options: Omit<RequestOptions, 'method' | 'data'> = {}) =>
  request<T>(path, { ...options, method: 'GET' });

export const post = <T = unknown>(
  path: string,
  data?: Record<string, unknown>,
  options: Omit<RequestOptions, 'method' | 'data'> = {}
) => request<T>(path, { ...options, method: 'POST', data });

export const patch = <T = unknown>(
  path: string,
  data?: Record<string, unknown>,
  options: Omit<RequestOptions, 'method' | 'data'> = {}
) => request<T>(path, { ...options, method: 'PATCH', data });
