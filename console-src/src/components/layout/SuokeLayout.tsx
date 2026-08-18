/**
 * SuokeLayout — 响应式布局壳
 *
 * 对齐 Flutter 无底栏的聊天为中心架构：
 *   mobile/tablet (≤1024px) → 顶栏（汉堡 ☰ + 页面标题）+ 抽屉导航 + 全屏 children
 *   desktop (>1024px)       → SideNav 侧栏 + 主内容区（Web 增强，直达 27 页）
 *
 * 主内容区在桌面端限制最大宽度（避免超宽屏下聊天列过宽），对齐 AIChatPage 居中阅读体验。
 */

import { useEffect, useState, type ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { useResponsive } from '../../hooks/useResponsive';
import SideNav, { getNavTitle } from './SideNav';

export interface SuokeLayoutProps {
  children: ReactNode;
  /** 主内容是否居中限宽（工作台=true，全宽表格=false），默认 true */
  constrained?: boolean;
}

export default function SuokeLayout({ children, constrained = true }: SuokeLayoutProps) {
  const bp = useResponsive();
  const isDesktop = bp === 'desktop';
  const location = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);

  // 路由切换后自动关闭抽屉
  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  if (!isDesktop) {
    const title = getNavTitle(location.pathname) ?? '索克家居';
    return (
      <div className="wb-layout wb-layout--mobile" data-testid="wb-layout">
        <header className="wb-topbar" data-testid="wb-topbar">
          <button
            type="button"
            className="wb-topbar__menu"
            aria-label="打开导航菜单"
            aria-expanded={drawerOpen}
            onClick={() => setDrawerOpen(true)}
            data-testid="wb-topbar-menu"
          >
            ☰
          </button>
          <span className="wb-topbar__title">{title}</span>
        </header>
        {drawerOpen && (
          <div className="wb-drawer" data-testid="wb-drawer">
            <div
              className="wb-drawer__mask"
              onClick={() => setDrawerOpen(false)}
              data-testid="wb-drawer-mask"
            />
            <aside className="wb-drawer__panel" aria-label="导航抽屉">
              <SideNav />
            </aside>
          </div>
        )}
        {children}
      </div>
    );
  }

  return (
    <div className="wb-layout wb-layout--desktop" data-testid="wb-layout">
      <SideNav />
      <main
        className={`wb-layout__main ${constrained ? 'wb-layout__main--constrained' : ''}`}
        data-testid="wb-layout-main"
      >
        {children}
      </main>
    </div>
  );
}
