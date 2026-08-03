import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import { createReadStream, existsSync, statSync } from 'node:fs';
import { join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * dev 下回退服务旧静态页目录（../web），对齐生产 nginx root=web/。
 * 解决 AuthGate 无 token 跳转 /login.html 在 dev 环境 404 的问题
 * （此前 dev 只能手动注入 localStorage token，无法走登录页回跳）。
 */
function devWebStatic(): Plugin {
  const webRoot = fileURLToPath(new URL('../web', import.meta.url));
  const MIME: Record<string, string> = {
    '.html': 'text/html; charset=utf-8',
    '.htm': 'text/html; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.mjs': 'text/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.json': 'application/json',
    '.map': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.webp': 'image/webp',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.wasm': 'application/wasm',
    '.txt': 'text/plain; charset=utf-8',
  };
  return {
    name: 'ihome-dev-web-static',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = (req.url || '').split('?')[0];
        // 交给 Vite / 代理处理的路径（SPA、API、WS、开发资源）
        if (
          url.startsWith('/api')
          || url.startsWith('/ws')
          || url.startsWith('/console/') || url === '/console'
          || url.startsWith('/src/')
          || url.startsWith('/@')
          || url.startsWith('/node_modules/')
        ) {
          return next();
        }
        const filePath = normalize(join(webRoot, url === '/' ? 'index.html' : url));
        // 防目录穿越
        if (filePath !== webRoot && !filePath.startsWith(webRoot + '/')) {
          return next();
        }
        if (!existsSync(filePath)) return next();
        let target = filePath;
        if (statSync(target).isDirectory()) {
          target = join(target, 'index.html');
          if (!existsSync(target)) return next();
        }
        const ext = target.slice(target.lastIndexOf('.')).toLowerCase();
        res.setHeader('Content-Type', MIME[ext] ?? 'application/octet-stream');
        createReadStream(target).pipe(res);
      });
    },
  };
}

// 索克家居 Web 控制台 v2 — Vite 配置
// 生产路径 /console/，由 Nginx 直接服务 web/console/ 静态产物
// 本地开发：Vite dev (5173) + FastAPI (8000)，proxy /api /ws 到后端
export default defineConfig({
  plugins: [react(), devWebStatic()],
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
