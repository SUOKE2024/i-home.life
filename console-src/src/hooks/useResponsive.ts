/**
 * useResponsive — 响应式断点 hook
 *
 * 断点对齐设计文档 §3.3：
 *   mobile  ≤768px   全屏工作台，对齐 Flutter（无底栏）
 *   tablet  769-1024 同 mobile（避免侧栏挤压）
 *   desktop >1024px  SideNav + 主内容区
 *
 * SSR 安全：首屏返回 'desktop'（与 Vite preview 一致），客户端 mount 后立即校正。
 */

import { useEffect, useState } from 'react';

export type Breakpoint = 'mobile' | 'tablet' | 'desktop';

const DESKTOP_MIN = 1025; // >1024
const TABLET_MIN = 769; // >768

function computeBreakpoint(width: number): Breakpoint {
  if (width >= DESKTOP_MIN) return 'desktop';
  if (width >= TABLET_MIN) return 'tablet';
  return 'mobile';
}

export function useResponsive(): Breakpoint {
  const [bp, setBp] = useState<Breakpoint>(() => {
    if (typeof window === 'undefined') return 'desktop';
    return computeBreakpoint(window.innerWidth);
  });

  useEffect(() => {
    const onResize = () => setBp(computeBreakpoint(window.innerWidth));
    window.addEventListener('resize', onResize);
    // 首次校正
    setBp(computeBreakpoint(window.innerWidth));
    return () => window.removeEventListener('resize', onResize);
  }, []);

  return bp;
}

/** 便捷布尔：是否桌面（含侧栏） */
export function useIsDesktop(): boolean {
  return useResponsive() === 'desktop';
}
