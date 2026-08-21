import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// 索克家居 Web 控制台 v2 — Vite 配置
// 生产路径 /console/，构建产物输出到 webapp/dist/console/（由 Nginx root 直接服务）
// 本地开发：Vite dev (5173) + FastAPI (8000)，proxy /api /ws 到后端
export default defineConfig({
  plugins: [react()],
  base: '/console/',
  build: {
    outDir: '../webapp/dist/console',
    emptyOutDir: true,
    assetsDir: 'assets',
    sourcemap: true,
    rollupOptions: {
      output: {
        // 拆分 react 全家桶为独立 vendor chunk：缩小主包体积 + 利用浏览器长缓存
        // v1.15.10：移除已删除依赖 zustand（死依赖清理，避免 rollup 解析失败）
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
        },
      },
    },
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
