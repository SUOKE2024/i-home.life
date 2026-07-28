/**
 * SuokeLayout — 响应式布局壳
 *
 * 对齐 Flutter 无底栏的聊天为中心架构：
 *   mobile/tablet (≤1024px) → 全屏 children，对齐 Flutter HomePage（无导航 chrome）
 *   desktop (>1024px)       → SideNav 侧栏 + 主内容区（Web 增强，直达 27 页）
 *
 * 主内容区在桌面端限制最大宽度（避免超宽屏下聊天列过宽），对齐 AIChatPage 居中阅读体验。
 */

import type { ReactNode } from 'react';
import { useResponsive } from '../../hooks/useResponsive';
import SideNav from './SideNav';

export interface SuokeLayoutProps {
  children: ReactNode;
  /** 主内容是否居中限宽（工作台=true，全宽表格=false），默认 true */
  constrained?: boolean;
}

export default function SuokeLayout({ children, constrained = true }: SuokeLayoutProps) {
  const bp = useResponsive();
  const isDesktop = bp === 'desktop';

  if (!isDesktop) {
    // 窄屏：全屏，对齐 Flutter（无侧栏无底栏）
    return <div className="wb-layout wb-layout--mobile" data-testid="wb-layout">{children}</div>;
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
