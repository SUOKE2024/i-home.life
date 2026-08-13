import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 索克家居 i-home.life Web App — Vite 配置
// 本地开发：Vite dev + FastAPI (8000)，proxy /api /ws 到后端
// 生产构建：npm run build → dist/（由 Nginx / 部署脚本同步到站点根）
export default defineConfig({
  plugins: [react()],
  base: '/',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    assetsDir: 'assets',
    sourcemap: true,
  },
  server: {
    port: 5273,
    strictPort: true,
    // 允许 dev server 读取仓库根目录（DocsPage 经 ?raw 引入 assets/guide + assets/legal）
    fs: {
      allow: ['..'],
    },
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
    port: 4273,
    strictPort: true,
  },
})
