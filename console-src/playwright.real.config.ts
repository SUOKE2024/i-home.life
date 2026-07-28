import { defineConfig, devices } from '@playwright/test';

/**
 * 真实后端 E2E 配置 — 驱动真实浏览器调生产/本地后端
 *
 * 与 playwright.config.ts 区别：
 *   - 不启动 vite preview（连真实后端 console 静态产物）
 *   - 不做视觉回归（无 toHaveScreenshot）
 *   - 串行 + 长 timeout（真实网络 + SSE 流式 + 文件上传）
 *
 * 用法：
 *   连生产：npx playwright test --config=playwright.real.config.ts
 *   连本地：E2E_BASE_URL=http://127.0.0.1:8081/console/ npx playwright test --config=playwright.real.config.ts
 *
 * 本地后端需先起 uvicorn（port 8000）+ nginx（port 8081 代理 /console/ + /api/），
 * 或用 vite dev（5173，自带 proxy）+ E2E_BASE_URL=http://localhost:5173/console/
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
