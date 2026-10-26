/**
 * 运行环境与后端接入配置。
 *
 * API 基址优先级：
 *   1. 构建期注入 process.env.TARO_APP_API_BASE（config/index.ts defineConstants）
 *   2. 平台默认值：小程序端直连生产域名；H5 走同源 /api（dev 由 devServer 代理）
 *
 * 生产域名必须已在小程序后台「服务器域名 → request 合法域名」登记，
 * 否则微信侧会直接拦截请求（本地开发可在开发者工具勾选「不校验合法域名」）。
 */

const DEFAULT_API_BASE = 'https://i-home.life/api';

function resolveApiBase(): string {
  const injected = process.env.TARO_APP_API_BASE;
  if (injected) return injected.replace(/\/+$/, '');
  // H5：同源部署，dev 由 Taro devServer proxy 转发，prod 由 nginx 反代
  if (process.env.TARO_ENV === 'h5') return '/api';
  return DEFAULT_API_BASE;
}

export const API_BASE = resolveApiBase();

/** 单次请求超时（毫秒）。小程序端弱网常见，8s 内必回，避免白屏等待。 */
export const REQUEST_TIMEOUT = 8000;

/** 本地会话键（access/refresh 分开存，便于单独轮换） */
export const TOKEN_KEY = 'suoke_access_token';
export const REFRESH_TOKEN_KEY = 'suoke_refresh_token';
export const USER_KEY = 'suoke_user_info';

/**
 * 允许接口不可用时回落到演示数据。
 *
 * 由构建期常量注入（config/index.ts defineConstants）：
 *   - 开发构建（NODE_ENV=development）默认 true，方便无后端联调；
 *   - 生产构建默认 **false**——接口挂了就如实显示错误态，绝不拿演示数据冒充真实资产。
 * 需要强制打开时显式 `TARO_APP_ALLOW_DEMO_FALLBACK=true npm run build:weapp`。
 *
 * 注意：无论此开关如何，**写操作永不降级**（见 services/adapters.ts）。
 */
export const ALLOW_DEMO_FALLBACK = process.env.TARO_APP_ALLOW_DEMO_FALLBACK === 'true';

/** 客户端版本号（与 package.json 同步，埋点与反馈用） */
export const CLIENT_VERSION = '1.1.0';
