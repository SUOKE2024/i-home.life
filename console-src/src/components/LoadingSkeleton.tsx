/**
 * LoadingSkeleton — 对齐 Flutter loading_skeleton.dart
 *
 * 骨架屏占位，shimmer 动画
 */

import type { CSSProperties } from 'react';

export interface LoadingSkeletonProps {
  width?: number | string;
  height?: number | string;
  radius?: number | string;
  style?: CSSProperties;
  testId?: string;
}

export default function LoadingSkeleton({
  width = '100%',
  height = 14,
  radius = 'var(--radius-input)',
  style,
  testId,
}: LoadingSkeletonProps) {
  return (
    <div
      data-testid={testId}
      style={{
        width: typeof width === 'number' ? `${width}px` : width,
        height: typeof height === 'number' ? `${height}px` : height,
        borderRadius: typeof radius === 'number' ? `${radius}px` : radius,
        background: 'linear-gradient(90deg, var(--surface2) 25%, var(--surface3) 50%, var(--surface2) 75%)',
        backgroundSize: '200% 100%',
        animation: 'wb-skeleton-shimmer 1.4s infinite',
        ...style,
      }}
    >
      <style>{`@keyframes wb-skeleton-shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`}</style>
    </div>
  );
}
