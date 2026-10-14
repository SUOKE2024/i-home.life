export type SpaceFormat =
  | 'herb_food_courtyard'
  | 'forest_herbal_bath'
  | 'kangyang_study'
  | 'seasonal_stay'
  | 'elderly_residence';

export type SpaceStatus = 'assessed' | 'in_renovation' | 'delivered' | 'operating';

export interface ReadinessBreakdown {
  device: number;
  sensing: number;
  scene: number;
  compliance: number;
}

export interface Space {
  id: string;
  name: string;
  format: SpaceFormat;
  formatLabel: string;
  city: string;
  area: number;
  status: SpaceStatus;
  score: number;
  cover: string;
  deviceCount: number;
  readiness: ReadinessBreakdown;
  packageCode?: string;
  createTime: string;
}

export const SPACE_STATUS_LABEL: Record<SpaceStatus, string> = {
  assessed: '已评估',
  in_renovation: '改造中',
  delivered: '已交付',
  operating: '运营中'
};

export const SPACE_STATUS_TONE: Record<SpaceStatus, 'gray' | 'gold' | 'blue' | 'green'> = {
  assessed: 'gray',
  in_renovation: 'gold',
  delivered: 'blue',
  operating: 'green'
};