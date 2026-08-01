import { test, expect } from '@playwright/test';

/**
 * 令牌渲染校验 — 批次 1 验证 tokens 契约正确落地
 *
 * 批次 2 起 / 路由改为 WorkbenchPage，PlaceholderHome 迁至 /tokens 供令牌调试。
 *
 * 验证点（对齐设计文档 §4.2 + 令牌修补）：
 *   1. textMuted 计算值 = #6B6978（Web 由 #5a5866 升级，对齐 Flutter WCAG AA）
 *   2. radius-md 计算值 = 12px（对齐 Flutter SuokeDesignTokens.radius=12.0）
 *   3. PlaceholderHome 截图匹配 baseline（仅 desktop 断点）
 */
test.describe('设计令牌渲染', () => {
  // mock feature-flags 避免 401 重定向 login.html（PlaceholderHome mount 时调 getFeatureFlags）
  // 注：vite preview 继承 server.proxy，本地后端在跑时未 mock 的 /api 会 401 触发重定向
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('paseto_token', 'mock-token-tokens');
      // 固定暗色主题：F5 起 initTheme() 在 system 模式下随 OS 偏好解析，
      // Playwright headless 默认 light 会导致 /tokens 渲染为浅色令牌，断言漂移。
      // 令牌 baseline 与断言基于暗色，故强制 dark。
      localStorage.setItem('settings_theme_mode', 'dark');
    });
    await page.route('**/api/config/feature-flags', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ console_v2_enabled: true }),
      });
    });
    // mock /api/auth/me：AuthGate 会校验 token 有效性，未 mock 则 401 重定向 login.html
    await page.route('**/api/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'mock-user',
          name: '测试用户',
          email: 'test@suoke',
          role: 'homeowner',
        }),
      });
    });
  });

  test('textMuted 色块为 #6B6978', async ({ page }) => {
    await page.goto('./tokens');
    const swatch = page.getByTestId('token-swatch--textMuted');
    await expect(swatch).toBeVisible();
    // 色块的 span 子元素 background = #6B6978 → rgb(107, 105, 120)
    const colorSpan = swatch.locator('span').first();
    const bg = await colorSpan.evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(bg).toBe('rgb(107, 105, 120)'); // #6B6978
  });

  test('radius-md 演示块圆角为 12px', async ({ page }) => {
    await page.goto('./tokens');
    const demo = page.getByTestId('radius-demo--md');
    await expect(demo).toBeVisible();
    const radius = await demo.evaluate((el) => getComputedStyle(el).borderRadius);
    expect(radius).toBe('12px');
  });

  test('PlaceholderHome 截图匹配 baseline（desktop）', async ({ page }) => {
    // 仅 desktop 断点生成 baseline，对齐设计文档 §9.4
    test.skip(test.info().project.name !== 'desktop', '仅 desktop 断点');
    await page.goto('./tokens');
    await expect(page).toHaveScreenshot('tokens-desktop.png');
  });
});
