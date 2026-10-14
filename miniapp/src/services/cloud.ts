// 数据层统一调用入口：微信小程序 / 抖音 / 支付宝 / Web 预览
// 所有平台统一走 src/data/ 本地数据源，按调用名自动加载
// 文件约定：src/data/<functionName>.ts，默认导出 (data?: any) => T

export async function callFunction<T = any>(
  name: string,
  data?: Record<string, any>
): Promise<T> {
  let mockModule: { default: (payload?: Record<string, any>) => unknown };
  try {
    mockModule = await import(`../data/${name}`);
  } catch (err) {
    console.error(`[Data] 未找到本地数据源 src/data/${name}.ts`, err);
    throw new Error(`本地数据源缺失：${name}`);
  }
  return mockModule.default(data) as T;
}