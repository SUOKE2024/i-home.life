import { defineConfig, devices } from '@playwright/test';

/**
 * 真实后端 E2E 配置 — 驱动真实浏览器调生产/本地后端
 *
 * 与 playwright.config.ts 区别：
 *   - 不启动 vite preview（连生产 http://118.31.223.213:8081/console/）
 *   - 不做视觉回归（无 toHaveScreenshot）
 *   - 串行 + 长 timeout（真实网络 + SSE 流式）
 *
 * 用法：npx playwright test --config=playwright.real.config.ts
 */

const BASE = process.env.E2E_BASE_URL ?? 'http://118.31.223.213:8081/console/';

export default defineConfig({
  testDir: './tests/real',
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: 'list',
  timeout: 60000,
  use: {
    baseURL: BASE,
    trace: 'on',
    ignoreHTTPSErrors: true,
  },
  projects: [
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
  ],
});
