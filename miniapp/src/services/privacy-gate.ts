/**
 * 微信小程序隐私授权门（`__usePrivacyCheck__` 配套）
 *
 * 微信要求：开启 `__usePrivacyCheck__` 后，调用隐私接口前必须先取得用户同意。
 * 本仓采用「在 `wx.onNeedPrivacyAuthorization` 回调里弹窗征询」的方式：
 *
 *   - 不依赖把弹窗节点挂到 App 根节点（Taro 的 App 只渲染页面 children，
 *     额外兄弟节点在部分基础库不保证渲染）；
 *   - 不依赖 `<button open-type="agreePrivacyAuthorization">`（Taro 的
 *     Button 类型未覆盖该 open-type，强行 as any 会绕过类型门禁）。
 *
 * 与索克生活小程序 `src/services/privacy-gate.ts` 同口径，便于后续抽公共包。
 * `wx` 的隐私 API 未包含在 @tarojs/taro 类型里，这里做最小声明并用
 * `globalThis.wx` 访问，避免污染全局命名空间。
 */

import Taro from '@tarojs/taro';

export interface PrivacyResolveResult {
  event: 'agree' | 'disagree';
  buttonId?: string;
}

export interface WeappPrivacyApi {
  onNeedPrivacyAuthorization?: (
    callback: (resolve: (result: PrivacyResolveResult) => void, eventInfo?: unknown) => void
  ) => void;
  openPrivacyContract?: (options?: { success?: () => void; fail?: (err: unknown) => void }) => void;
  getPrivacySetting?: (options: {
    success?: (res: { needAuthorization?: boolean; privacyContractName?: string }) => void;
    fail?: (err: unknown) => void;
  }) => void;
}

/** 仅在微信小程序端返回 wx 对象，其余端返回 null */
export function getWeappPrivacyApi(): WeappPrivacyApi | null {
  if (process.env.TARO_ENV !== 'weapp') return null;
  const globalRef = globalThis as unknown as { wx?: WeappPrivacyApi };
  return globalRef.wx && typeof globalRef.wx === 'object' ? globalRef.wx : null;
}

let installed = false;

/**
 * 安装隐私授权弹窗。幂等：重复调用只注册一次，避免热更新/多入口注册出多个监听导致竞态。
 * 返回是否成功安装（非微信端或基础库过低时返回 false，调用方无需报错）。
 */
export function installWeappPrivacyGate(): boolean {
  if (installed) return true;

  const api = getWeappPrivacyApi();
  if (!api?.onNeedPrivacyAuthorization) {
    console.info('[PrivacyGate] 当前端未提供隐私授权 API，跳过隐私门安装');
    return false;
  }

  api.onNeedPrivacyAuthorization((resolve) => {
    Taro.showModal({
      title: '隐私保护提示',
      content:
        '为了向你提供空间资产管理、智能家居控制与康养服务，我们需要收集必要的信息。\n\n' +
        '点击「同意」即表示你已阅读并同意《索克家居隐私政策》。你可以在「我的 - 用户协议与隐私」中随时查看。',
      confirmText: '同意',
      cancelText: '不同意',
      confirmColor: '#8A6415',
      success: (res) => {
        if (res.confirm) {
          resolve({ event: 'agree' });
          return;
        }
        resolve({ event: 'disagree' });
        Taro.showToast({ title: '未同意隐私政策，部分功能不可用', icon: 'none' });
      },
      fail: () => {
        // 弹窗都无法展示时按不同意处理，避免隐私接口被静默放行
        resolve({ event: 'disagree' });
      },
    }).catch(() => resolve({ event: 'disagree' }));
  });

  installed = true;
  console.info('[PrivacyGate] 隐私授权门已安装');
  return true;
}

/** 打开微信官方《小程序隐私保护指引》 */
export function openPrivacyContract(): Promise<boolean> {
  const api = getWeappPrivacyApi();
  if (!api?.openPrivacyContract) {
    Taro.showToast({ title: '当前环境不支持查看隐私指引', icon: 'none' });
    return Promise.resolve(false);
  }
  return new Promise((resolve) => {
    api.openPrivacyContract?.({
      success: () => resolve(true),
      fail: (err) => {
        console.warn('[PrivacyGate] 打开隐私保护指引失败:', err);
        Taro.showToast({ title: '打开失败，请稍后重试', icon: 'none' });
        resolve(false);
      },
    });
  });
}

/** 查询当前用户是否需要重新授权 */
export function getPrivacySetting(): Promise<{
  needAuthorization: boolean;
  privacyContractName: string;
} | null> {
  const api = getWeappPrivacyApi();
  if (!api?.getPrivacySetting) return Promise.resolve(null);
  return new Promise((resolve) => {
    api.getPrivacySetting?.({
      success: (res) =>
        resolve({
          needAuthorization: Boolean(res.needAuthorization),
          privacyContractName: res.privacyContractName || '小程序隐私保护指引',
        }),
      fail: () => resolve(null),
    });
  });
}
