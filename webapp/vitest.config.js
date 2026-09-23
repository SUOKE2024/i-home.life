import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// webapp 前端自动化测试配置（2026-09-22 引入，评估报告 X3「前端零测试」落地）
// 生产构建仍走 vite.config.js；本文件仅服务 `npm test`（jsdom + React 组件测试）
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    // RTL 依赖全局 afterEach 注册自动 cleanup，故开启 globals
    globals: true,
    include: ['src/**/*.test.{js,jsx}'],
    restoreMocks: true,
  },
})
