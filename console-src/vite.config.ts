import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// 索克家居 Web 控制台 v2 — Vite 配置
// 生产路径 /console/，由 Nginx 直接服务 web/console/ 静态产物
// 本地开发：Vite dev (5173) + FastAPI (8000)，proxy /api /ws 到后端
export default defineConfig({
  plugins: [react()],
  base: '/console/',
  build: {
    outDir: '../web/console',
    emptyOutDir: true,
    assetsDir: 'assets',
    sourcemap: true,
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
  preview: {
    port: 4173,
    strictPort: true,
  },
});
