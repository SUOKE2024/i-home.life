# Web 控制台开发规范（web-console.md）

> React Web 控制台（console-src），UI/UX 对齐 Flutter 移动端。所有事实基于当前代码。

## 技术栈

- React 18.3 + TypeScript 5.5 + Vite 5.4
- 路由：**react-router-dom 6.26**（`<Routes>`/`<Route>`）
- 状态管理：**zustand 4.5**（轻量 store）
- HTTP：**原生 fetch**（非 axios，封装在 `ApiClient`）
- 测试：**Playwright 1.46**（e2e 视觉测试）
- UI：**无第三方 UI 库**（自定义组件 + CSS 变量）
- 版本：`"version": "1.3.0.0"`（package.json:4，四位，末位固定 0）

## 目录结构

```
console-src/
├── index.html               # 入口 HTML
├── package.json             # 依赖与脚本
├── vite.config.ts           # Vite 配置（base/proxy/build）
├── tsconfig.json            # TS 配置（strict/paths）
├── playwright.config.ts     # e2e 测试配置
└── src/
    ├── main.tsx             # 入口（BrowserRouter + 主题初始化）
    ├── App.tsx              # 路由表（37 页面）+ AuthGate + ErrorBoundary
    ├── pages/               # 37 个页面组件
    ├── components/          # 复用组件（layout/ workbench/ 通用）
    ├── services/            # 服务层（api-client/ theme/ agent-router/...）
    ├── hooks/               # 自定义 Hook（useAsync/ useResponsive）
    ├── tokens/              # 设计令牌（tokens.css + tokens.ts）
    └── types/               # 类型定义（domain/ chat）
```

## Vite 配置

[vite.config.ts](file:///Users/netsong/Developer/i-home.life/console-src/vite.config.ts)：

- `base: '/console/'` —— 生产路径，Nginx 服务 `web/console/`
- `build.outDir: '../web/console'` —— 构建产物输出到后端 web 目录
- `server.port: 5173`（strictPort）+ proxy `/api`→`localhost:8000` + `/ws`→`ws://localhost:8000`
- `preview.port: 4173`

**开发联调**：Vite 5173 + FastAPI 8000，proxy 转发。后端 CORS 已配置 `http://localhost:5173`（[app/config.py:212](file:///Users/netsong/Developer/i-home.life/app/config.py)）。

## 入口与路由

[main.tsx](file:///Users/netsong/Developer/i-home.life/console-src/src/main.tsx)：

```tsx
initTheme();  // 启动时应用持久化主题，避免 FOUC
ReactDOM.createRoot(...).render(
  <React.StrictMode>
    <BrowserRouter basename="/console">  {/* 注意 basename */}
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
```

[App.tsx](file:///Users/netsong/Developer/i-home.life/console-src/src/App.tsx) 路由结构：

```tsx
<AuthGate>                          {/* 认证守卫，包裹所有路由 */}
  <ErrorBoundary resetOnLocationChange>
    <Routes>
      <Route path="/" element={<WorkbenchPage />} />
      <Route path="/projects" element={<ProjectsPage />} />
      ...  // 37 个路由
      <Route path="*" element={<NotFoundPage />} />  {/* 真 404 */}
    </Routes>
  </ErrorBoundary>
</AuthGate>
```

**新增页面必须**：
1. 在 `src/pages/` 创建 `XxxPage.tsx`
2. 在 `App.tsx` 加 `<Route path="/xxx" element={<XxxPage />} />`
3. 路径用 kebab-case（如 `/change-orders`、`/ai-render`）

## 认证守卫（AuthGate）

[components/AuthGate.tsx](file:///Users/netsong/Developer/i-home.life/console-src/src/components/AuthGate.tsx) 包裹所有路由：

1. **无 token** → 立即跳 `/login.html?redirect=...`（不发请求）
2. **有 token** → 调 `getCurrentUser` 校验；401 → 清理 + 跳登录；200 → 放行
3. 注册全局 `onUnauthorized` 回调，后续任何请求 401 统一跳转

**PASETO 无状态**：后端不维护会话，每次进入控制台需校验一次 token（对齐 Flutter AuthGate）。

跳转目标携带 redirect 参数，登录后回到来源页。

## API 客户端

[services/api-client.ts](file:///Users/netsong/Developer/i-home.life/console-src/src/services/api-client.ts) `ApiClient` 单例：

```typescript
const TOKEN_KEY = 'paseto_token';  // 与 Flutter/旧静态页共享
const BASE_URL = '';  // 同源，Vite proxy /api → localhost:8000

class ApiClient {
  getToken(): string { return localStorage.getItem(TOKEN_KEY) ?? ''; }
  setToken(token): void { localStorage.setItem(TOKEN_KEY, token); }
  clearToken(): void { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem('user_info'); }
  async request<T>(path, options): Promise<ApiResult<T>> { ... }
}
```

- Token 存 `localStorage` key `paseto_token`（**与 Flutter shared_preferences 跨端共享**同源时登录态）
- `ApiResult<T>` 模式：`{ isSuccess, status, data?, error? }`（对齐 Flutter Result 模式）
- 401 自动 `clearToken` + 触发 `onUnauthorized` 回调
- 请求头自动注入 `Authorization: Bearer {token}`

**禁止**直接用 `fetch`，必须走 `ApiClient` 单例（统一 token/401 处理）。

## 状态管理（zustand）

用 zustand 创建 store，非 React Context：

```typescript
// services/store.ts 模式
import { create } from 'zustand';
const useStore = create((set) => ({ ... }));
```

部分页面用 `useContext`（如 WorkbenchPage），但新代码推荐 zustand。

## 样式方案

**无第三方 UI 库**，用 CSS 变量 + 自定义组件：

- [tokens/tokens.css](file:///Users/netsong/Developer/i-home.life/console-src/src/tokens/tokens.css) —— 设计令牌（颜色/间距/字体 CSS 变量）
- [tokens/tokens.ts](file:///Users/netsong/Developer/i-home.life/console-src/src/tokens/tokens.ts) —— TS 类型定义
- 组件级样式用 `.css` 文件（如 `layout.css`、`workbench.css`）
- 自定义组件：`SuokeButton` / `SuokeCard` / `Badge` / `LoadingSkeleton` / `EmptyState` / `ErrorBoundary`

**新增组件优先复用** `components/` 下现有组件，勿引入 antd/Material UI。

## 主题

[services/theme.ts](file:///Users/netsong/Developer/i-home.life/console-src/src/services/theme.ts) `initTheme()`：

- 启动时从 localStorage 读取主题，应用 `data-theme` 属性
- 支持白天/夜间模式（对齐 Flutter ThemeState）
- 避免 FOUC（Flash of Unstyled Content）

## 测试（Playwright）

[playwright.config.ts](file:///Users/netsong/Developer/i-home.life/console-src/playwright.config.ts) e2e 视觉测试：

```bash
cd console-src
npm run test:visual    # playwright test
```

- 测试文件在 `console-src/tests/`
- 无单元测试框架（无 Jest/Vitest），测试靠 Playwright + 后端 pytest

## 构建与部署

```bash
cd console-src
npm run dev        # 开发：Vite 5173 + proxy 后端 8000
npm run build      # tsc --noEmit + vite build → 输出到 ../web/console/
npm run preview    # 预览构建产物 4173
```

- 构建产物输出到 `web/console/`，由 Nginx `/console/` 路径服务
- `console_v2_enabled` feature flag 控制是否对外可见（[config.py:467](file:///Users/netsong/Developer/i-home.life/app/config.py)）
- 关闭时回退旧静态页（`web/workbench.html` 等 18 页保留作回滚资产）

## 与旧静态页（web/）的关系

- `web/` 是旧静态页（HTML + JS），`console-src/` 是新 React 控制台
- 两者**共享** `localStorage` key `paseto_token`（同源），登录态互通
- 新控制台逐步替代旧静态页，旧页保留作回滚
- 旧静态页资源版本号 `?v=20260731c` 由 `scripts/bump-version.sh` 管理（独立于 console-src）

## 禁止事项

- ❌ 引入 axios（项目用原生 fetch 封装 ApiClient）
- ❌ 引入 antd/Material UI/Tailwind（项目用自定义组件 + CSS 变量）
- ❌ 引入 Redux（项目用 zustand）
- ❌ 直接用 `fetch`（走 ApiClient 单例）
- ❌ 路由不加 AuthGate 守卫
- ❌ 新页面不在 App.tsx 注册路由
- ❌ 路径不用 kebab-case

## 版本号同步

`console-src/package.json` 的 `"version": "X.Y.Z.0"`（四位，末位固定 0），随语义版本升级，详见 `.claude/templates/version-bump.md`。
