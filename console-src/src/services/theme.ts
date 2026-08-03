/**
 * 主题工具 — 控制台 light/dark/system 三态管理
 *
 * 对齐 Flutter ThemeState（flutter_app/lib/main.dart）：
 *   - 'system' 模式由 matchMedia('(prefers-color-scheme: light)') 解析为 light/dark
 *   - 持久化到 localStorage 'settings_theme_mode'
 *   - 在 main.tsx 启动时调用 initTheme() 避免 FOUC
 *
 * 设计：data-theme 属性只写 'light' | 'dark'（已解析），system 信息保留在 state。
 */

export type ThemeMode = 'light' | 'dark' | 'system';
export const THEME_KEY = 'settings_theme_mode';

export function readStoredMode(): ThemeMode {
  const v = localStorage.getItem(THEME_KEY);
  return v === 'light' || v === 'dark' || v === 'system' ? v : 'system';
}

/** 将 mode 解析为实际 light/dark（system 跟随 OS 偏好） */
export function resolveTheme(mode: ThemeMode): 'light' | 'dark' {
  if (mode === 'system') {
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  }
  return mode;
}

/** 写 data-theme 属性（仅 light/dark，已解析），并同步浏览器顶栏颜色 */
export function applyResolvedTheme(resolved: 'light' | 'dark'): void {
  document.documentElement.setAttribute('data-theme', resolved);
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) {
    meta.setAttribute('content', resolved === 'light' ? '#f8f7f4' : '#08080f');
  }
}

/** 应用某个 mode：持久化 + 解析 + 写属性 */
export function applyTheme(mode: ThemeMode): void {
  localStorage.setItem(THEME_KEY, mode);
  applyResolvedTheme(resolveTheme(mode));
}

/** 启动时初始化：读存储 + 应用，避免主题 FOUC（在 main.tsx 渲染前调用） */
export function initTheme(): void {
  applyResolvedTheme(resolveTheme(readStoredMode()));
}
