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
