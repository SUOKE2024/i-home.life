/**
 * 会话管理：小程序静默登录、会话恢复、手机号绑定、退出。
 *
 * 平台策略（诚实边界）：
 *  - 微信小程序：wx.login 静默登录（后端 /auth/miniprogram/login），无需授权弹窗；
 *  - 其他端（H5 / 支付宝 / 抖音）：后端暂无对应端登录通道，走「访客态 + 演示数据」，
 *    不伪造登录成功，也不把演示数据冒充真实账号数据。
 */
import Taro from '@tarojs/taro';
import { USER_KEY } from '@/config/env';
import { authApi, track, type ApiUser } from './api';
import { ApiError, clearTokens, getAccessToken, getRefreshToken, setTokens } from './request';

export type SessionState = 'unknown' | 'authenticated' | 'guest';

let cachedUser: ApiUser | null = null;
let sessionState: SessionState = 'unknown';
const listeners = new Set<(state: SessionState, user: ApiUser | null) => void>();

function notify(): void {
  listeners.forEach((listener) => listener(sessionState, cachedUser));
}

export function subscribeSession(listener: (state: SessionState, user: ApiUser | null) => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getSessionState(): SessionState {
  return sessionState;
}

export function getCachedUser(): ApiUser | null {
  if (cachedUser) return cachedUser;
  try {
    const cached = Taro.getStorageSync(USER_KEY) as ApiUser | '';
    if (cached && typeof cached === 'object' && cached.id) {
      cachedUser = cached;
      return cachedUser;
    }
  } catch (err) {
    console.warn('[Session] 本地用户信息读取失败', err);
  }
  return null;
}

function cacheUser(user: ApiUser | null): void {
  cachedUser = user;
  try {
    if (user) Taro.setStorageSync(USER_KEY, user);
    else Taro.removeStorageSync(USER_KEY);
  } catch (err) {
    console.warn('[Session] 本地用户信息写入失败', err);
  }
}

function setState(state: SessionState): void {
  sessionState = state;
  notify();
}

/** 是否具备静默登录能力（当前仅微信小程序端接入了后端登录通道） */
export function canSilentLogin(): boolean {
  return process.env.TARO_ENV === 'weapp';
}

/**
 * 静默登录：wx.login → code → 后端换 PASETO。
 * 后端未部署该端点（404/502/503）时返回 false，由上层降级为访客态，不弹错误打扰用户。
 */
export async function silentLogin(): Promise<boolean> {
  if (!canSilentLogin()) {
    setState('guest');
    return false;
  }
  try {
    const { code } = await Taro.login();
    if (!code) {
      setState('guest');
      return false;
    }
    const data = await authApi.miniprogramLogin(code);
    setTokens(data.access_token, data.refresh_token);
    cacheUser(data.user);
    setState('authenticated');
    track('login_success', { channel: 'miniprogram' });
    console.info('[Session] 静默登录成功', data.user.id);
    return true;
  } catch (err) {
    const apiError = err as ApiError;
    // 后端通道尚未上线：414/404/502/503 一律视为「暂不可用」，静默降级
    const unavailable = !apiError?.status || [404, 502, 503, 504].includes(apiError.status);
    console.warn('[Session] 静默登录未完成', apiError?.status, apiError?.message);
    if (!unavailable) {
      console.error('[Session] 登录异常（非可用性问题）', err);
    }
    setState('guest');
    return false;
  }
}

/**
 * 确保会话可用：有令牌则校验并刷新用户信息；无令牌则静默登录。
 * 返回 true 表示已登录（可访问受保护接口）。
 */
export async function ensureSession(): Promise<boolean> {
  if (sessionState === 'authenticated' && getAccessToken()) return true;

  if (getAccessToken()) {
    try {
      const user = await authApi.me();
      cacheUser(user);
      setState('authenticated');
      return true;
    } catch (err) {
      const apiError = err as ApiError;
      // 令牌失效（401 且刷新失败）→ 清理后重新静默登录
      if (apiError?.isAuthError) {
        clearTokens();
        cacheUser(null);
      } else if (apiError?.isNetworkError) {
        // 弱网：沿用本地缓存的用户信息，避免把已登录用户踢成访客
        if (getCachedUser()) {
          setState('authenticated');
          return true;
        }
      }
    }
  }

  return silentLogin();
}

/** 手机号快速验证（<button open-type="getPhoneNumber"> 回传 code） */
export async function bindPhone(code: string): Promise<ApiUser> {
  const user = await authApi.bindPhone(code);
  cacheUser(user);
  setState('authenticated');
  track('bind_phone_success', {});
  return user;
}

export async function logout(): Promise<void> {
  const refreshToken = getRefreshToken();
  if (refreshToken) {
    try {
      await authApi.logout(refreshToken);
    } catch (err) {
      console.warn('[Session] 服务端登出失败，本地会话照常清理', err);
    }
  }
  clearTokens();
  cacheUser(null);
  setState('guest');
  track('logout', {});
}

/** 应用启动调用：恢复会话，不阻塞首屏渲染 */
export async function bootstrapSession(): Promise<boolean> {
  try {
    return await ensureSession();
  } catch (err) {
    console.error('[Session] 会话初始化失败', err);
    setState('guest');
    return false;
  }
}
