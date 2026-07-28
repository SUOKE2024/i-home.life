import { defineConfig, devices } from '@playwright/test';

/**
 * 索克家居 Web 控制台 v2 — Playwright 视觉回归配置
 *
 * 策略：toHaveScreenshot 对比，每页 ×2 断点（desktop 1440 / mobile 375）
 * webServer 启动 vite preview (4173)，复用已运行实例（本地调试友好）
 */
export default defineConfig({
  testDir: './tests/visual',
  fullyParallel: false, // 视觉回归串行避免抖动
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? 'github' : 'list',
  expect: {
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.01, // 1% 容差，抗字体/抗锯齿差异
    },
  },
  webServer: {
    command: 'npm run preview',
    port: 4173,
    reuseExistingServer: !process.env.CI,
    timeout: 60000,
  },
  use: {
    baseURL: 'http://localhost:4173/console/',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
    {
      // 移动端断点用 chromium（批次1验证令牌渲染无需webkit）；批次3+若需Safari行为再装webkit
      name: 'mobile',
      use: { ...devices['Desktop Chrome'], viewport: { width: 375, height: 812 } },
    },
  ],
});
