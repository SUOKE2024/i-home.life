import { create } from 'zustand';
import type { UserInfo } from '@/types/user';

interface AppState {
  /** 当前登录业主信息（login / getHomeOverview 后写入） */
  user: UserInfo | null;
  /** 当前选中空间（智控页空间切换共享） */
  currentSpaceId: string | null;
  setUser: (user: UserInfo) => void;
  setCurrentSpace: (spaceId: string) => void;
}

export const useAppStore = create<AppState>((set) => ({
  user: null,
  currentSpaceId: null,
  setUser: (user) => set({ user }),
  setCurrentSpace: (currentSpaceId) => set({ currentSpaceId })
}));