import type { Space } from './space';
import type { RenovationProject } from './project';

export type UserRole = 'owner';

export interface UserInfo {
  id: string;
  nickname: string;
  avatar: string;
  phone: string;
  role: UserRole;
  roleLabel: string;
  memberSince: string;
}

export type HomeAlertType = 'device' | 'health' | 'project' | 'service';

export interface HomeAlert {
  id: string;
  type: HomeAlertType;
  title: string;
  desc: string;
  time: string;
}

export interface HomeStats {
  spaceCount: number;
  deviceOnline: number;
  deviceTotal: number;
  activeProjectCount: number;
}

export interface HomeOverview {
  user: UserInfo;
  healthScore: number;
  scoreDelta: number;
  stats: HomeStats;
  spaces: Space[];
  activeProject: RenovationProject | null;
  alerts: HomeAlert[];
}