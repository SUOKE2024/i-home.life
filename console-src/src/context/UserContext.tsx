import { createContext, useContext, type ReactNode } from 'react';
import type { User } from '../types/domain';

/**
 * UserContext — 当前登录用户上下文（v1.15.4 供应商工作台引入）
 *
 * AuthGate 校验 token 成功后注入用户；SideNav/页面经 useUser() 读取 role
 * 做导航权限过滤（/admin 仅管理员、供应商组仅供应商，后端 403 兜底）。
 */
export interface UserContextValue {
  user: User | null;
  setUser: (user: User | null) => void;
}

export const UserContext = createContext<UserContextValue>({
  user: null,
  setUser: () => {},
});

export function UserProvider({
  value,
  children,
}: {
  value: UserContextValue;
  children: ReactNode;
}) {
  return <UserContext.Provider value={value}>{children}</UserContext.Provider>;
}

export function useUser(): UserContextValue {
  return useContext(UserContext);
}
