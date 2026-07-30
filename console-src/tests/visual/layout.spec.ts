import { test, expect } from '@playwright/test';

/**
 * SuokeLayout 响应式视觉回归 — 批次 3
 *
 * 三断点验证（对齐设计文档 §3.3 + 批次 3 裁决）：
 *   1. mobile (375px)  — 无侧栏，工作台全屏（对齐 Flutter 无底栏）
 *   2. tablet (768px)  — 无侧栏，工作台全屏
 *   3. desktop (1440px)— SideNav 侧栏 + 主内容区
 *
 * mock 策略同 workbench.spec.ts（paseto_token + SSE/voice 拦截）
 */

const SSE_RESPONSE =
  'event: meta\ndata: {"agent_type":"master","session_id":"test"}\n\n' +
  'event: done\ndata: {"content":"你好"}\n\n';

test.describe('SuokeLayout 响应式', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('paseto_token', 'test-paseto-token-batch3');
    });
    await page.route('**/api/agents/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: SSE_RESPONSE,
      });
    });
    await page.route('**/api/voice/orchestrate/tasks', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });
  });

  test('mobile 375px — 无侧栏，工作台全屏', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/');
    await expect(page.getByTestId('wb-page')).toBeVisible();
    // 侧栏不存在
    await expect(page.getByTestId('wb-sidenav')).toHaveCount(0);
    // 空状态可见
    await expect(page.getByTestId('wb-empty')).toBeVisible();
    await expect(page).toHaveScreenshot('layout-mobile.png');
  });

  test('tablet 768px — 无侧栏，工作台全屏', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto('/');
    await expect(page.getByTestId('wb-page')).toBeVisible();
    await expect(page.getByTestId('wb-sidenav')).toHaveCount(0);
    await expect(page).toHaveScreenshot('layout-tablet.png');
  });

  test('desktop 1440px — SideNav 侧栏 + 主内容区', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/');
    // 侧栏可见
    await expect(page.getByTestId('wb-sidenav')).toBeVisible();
    // 工作台主内容可见
    await expect(page.getByTestId('wb-page')).toBeVisible();
    // 侧栏含工作台项（活跃）
    await expect(page.getByTestId('wb-sidenav-item--root')).toHaveAttribute('aria-current', 'page');
    await expect(page).toHaveScreenshot('layout-desktop.png');
  });

  test('desktop 侧栏导航切换到设计页（真实页，批次 13）', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/');
    await expect(page.getByTestId('wb-sidenav')).toBeVisible();
    // 点击"设计"（批次 13 已从占位升级为真实 DesignPage）
    await page.getByTestId('wb-sidenav-item--design').click();
    await expect(page.getByTestId('wb-design-page')).toBeVisible();
    // 设计项活跃
    await expect(page.getByTestId('wb-sidenav-item--design')).toHaveAttribute('aria-current', 'page');
    // 返回工作台（点侧栏工作台项）
    await page.getByTestId('wb-sidenav-item--root').click();
    await expect(page.getByTestId('wb-page')).toBeVisible();
    await expect(page.getByTestId('wb-sidenav-item--root')).toHaveAttribute('aria-current', 'page');
  });

  test('mobile 头像点击进入设置（全屏，无侧栏）', async ({ page }) => {
    // 设置页现为真实页（批次 4），需 mock /api/auth/me
    await page.route('**/api/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'u1', phone: '138', name: '测试', role: 'homeowner', is_active: true, is_verified: true, created_at: '2026-01-01T00:00:00Z' }),
      });
    });
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/');
    await page.getByTestId('wb-header-avatar').click();
    // 设置页（真实页，批次 4）
    await expect(page.getByTestId('wb-settings-page')).toBeVisible();
    // mobile 下设置页也无侧栏
    await expect(page.getByTestId('wb-sidenav')).toHaveCount(0);
  });
});
