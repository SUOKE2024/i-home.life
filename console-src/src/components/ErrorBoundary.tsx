/**
 * ErrorBoundary — 全局运行时错误兜底，避免单组件异常导致整站白屏
 *
 * 2026 健壮性基线：任一子树抛错时降级为友好错误卡，而非 React 默认白屏。
 * 提供「重试」（重置本边界状态）与「返回工作台」两个出口。
 *
 * 用法：
 *   <ErrorBoundary>...</ErrorBoundary>           // 路由级，重置后重渲染当前子树
 *   <ErrorBoundary resetOnLocationChange url={location.pathname}>...</ErrorBoundary>
 *
 * 注意：React ErrorBoundary 必须是 class 组件（ Hooks 无等价 API）。
 */

import { Component, type ErrorInfo, type ReactNode } from 'react';

export interface ErrorBoundaryProps {
  children: ReactNode;
  /** 路由变化时自动恢复（用于路由级边界，避免切走再回来仍停留在错误态） */
  resetOnLocationChange?: boolean;
  /** 配合 resetOnLocationChange，传入当前路径作为变更信号 */
  url?: string;
  /** 自定义降级前缀文案 */
  label?: string;
}

interface ErrorBoundaryState {
  hasError: boolean;
  message: string;
}

export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, message: '' };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, message: error.message ?? String(error) };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // 控制台留痕，便于排障（生产可对接 tracing，受 tracing_enabled flag 控制）
    // eslint-disable-next-line no-console
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  componentDidUpdate(prev: ErrorBoundaryProps): void {
    // 路由切换 → 自动复位，让用户能继续操作其他页面
    if (this.props.resetOnLocationChange && prev.url !== this.props.url && this.state.hasError) {
      this.setState({ hasError: false, message: '' });
    }
  }

  private handleReset = (): void => {
    this.setState({ hasError: false, message: '' });
  };

  private handleReload = (): void => {
    window.location.reload();
  };

  render(): ReactNode {
    if (!this.state.hasError) return this.props.children;

    const label = this.props.label ?? '页面';
    const msg = this.state.message;
    const truncated = msg.length > 160 ? `${msg.slice(0, 160)}…` : msg;

    return (
      <div className="wb-error-boundary" role="alert" data-testid="wb-error-boundary">
        <div className="wb-error-boundary__inner">
          <div className="wb-error-boundary__icon" aria-hidden="true">⚠️</div>
          <h1 className="wb-error-boundary__title">{label}出了点小问题</h1>
          <p className="wb-error-boundary__desc">
            索克家居遇到一个未预期的错误。您可以重试当前操作，或刷新页面恢复。
          </p>
          {truncated && (
            <pre className="wb-error-boundary__detail">{truncated}</pre>
          )}
          <div className="wb-error-boundary__actions">
            <button
              type="button"
              className="wb-error-boundary__btn wb-error-boundary__btn--primary"
              onClick={this.handleReset}
            >
              重试
            </button>
            <button
              type="button"
              className="wb-error-boundary__btn"
              onClick={this.handleReload}
            >
              刷新页面
            </button>
          </div>
        </div>
      </div>
    );
  }
}
