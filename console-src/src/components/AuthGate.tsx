/**
 * AuthGate — 控制台 v2 认证守卫
 *
 * 对齐 Flutter AuthGate（flutter_app lib/.../auth_gate.dart）：
 *   1. 无 token → 立即跳转登录页（不发请求，避免无谓 401）
 *   2. 有 token → 调 getCurrentUser 校验有效性；401 → 清理 + 跳转；200 → 放行
 *   3. 注册全局 onUnauthorized 回调，后续任何请求 401 同样跳转登录页
 *
 * 跳转目标携带 redirect 参数，登录后回到来源页（对齐 login.html 的 redirect 约定）。
 * 项目约定：PASETO 无状态，后端不维护会话，故每次进入控制台需校验一次 token。
 */
import { useEffect, useState, type ReactNode } from 'react';
import { apiClient } from '../services/api-client';

export default function AuthGate({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;

    /** 跳转登录页，携带当前路径作为 redirect（登录成功后回到来源页） */
    const redirectToLogin = () => {
      const fullPath = window.location.pathname + window.location.search;
      window.location.href = `/login.html?redirect=${encodeURIComponent(fullPath)}`;
    };

    const token = apiClient.getToken();
    if (!token) {
      // 无 token：直接跳转，不发请求
      redirectToLogin();
      return;
    }

    // 注册全局 401 回调：后续任何请求 401 时统一跳转（替代 api-client 的硬编码回退）
    apiClient.onUnauthorized = redirectToLogin;

    // 校验 token 有效性（对齐 Flutter AuthGate 的 token 验证逻辑）
    (async () => {
      const r = await apiClient.getCurrentUser();
      if (cancelled) return;
      if (!r.isSuccess) {
        // token 无效/过期：api-client 已清理 token，这里只需跳转
        redirectToLogin();
        return;
      }
      setReady(true);
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  if (!ready) {
    // 校验中：渲染轻量加载态，避免未授权内容闪现（对齐 Flutter 启动闪屏体验）
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
          color: 'var(--text-muted, #888)',
          fontSize: '14px',
        }}
      >
        正在验证登录状态…
      </div>
    );
  }

  return <>{children}</>;
}
