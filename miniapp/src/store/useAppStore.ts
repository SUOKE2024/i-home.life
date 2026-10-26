import { create } from 'zustand';
import type { UserInfo } from '@/types/user';

export type DataSourceState = 'live' | 'demo' | 'unknown';
export type SessionPhase = 'unknown' | 'authenticated' | 'guest';

interface AppState {
  /** 当前登录业主信息（getHomeOverview / auth/me 后写入） */
  user: UserInfo | null;
  /** 当前选中空间（智控页空间切换共享） */
  currentSpaceId: string | null;
  /** 数据来源：live=生产后端，demo=演示数据，unknown=尚未请求 */
  dataSource: DataSourceState;
  dataSourceReason: string;
  /** 会话状态：authenticated 才可访问受保护接口 */
  sessionPhase: SessionPhase;
  setUser: (user: UserInfo) => void;
  setCurrentSpace: (spaceId: string) => void;
  setDataSource: (source: DataSourceState, reason?: string) => void;
  setSessionPhase: (phase: SessionPhase) => void;
}

export const useAppStore = create<AppState>((set) => ({
  user: null,
  currentSpaceId: null,
  dataSource: 'unknown',
  dataSourceReason: '',
  sessionPhase: 'unknown',
  setUser: (user) => set({ user }),
  setCurrentSpace: (currentSpaceId) => set({ currentSpaceId }),
  setDataSource: (dataSource, dataSourceReason = '') => set({ dataSource, dataSourceReason }),
  setSessionPhase: (sessionPhase) => set({ sessionPhase })
}));
