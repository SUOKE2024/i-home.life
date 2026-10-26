/**
 * 空间业态与状态口径 —— 与后端 app/models/space_asset.py 枚举逐项对齐。
 *
 * 对齐原则（索克生态一致）：业态枚举沿用索克生活 `_lodgeTypes`，
 * 前端不得另造词表；后端新增业态时此处必须同步，否则适配层会回落到 `other`。
 */

export type SpaceFormat =
  | 'herb_food_courtyard' // 药膳小院
  | 'forest_herbal_bath' // 森林药浴
  | 'kangyang_study' // 康养研学
  | 'seasonal_stay' // 节气旅居
  | 'wellness_resort' // 疗愈度假
  | 'cultural_site' // 文旅点位
  | 'elderly_home' // 适老住宅（后端枚举）
  | 'elderly_residence' // 适老住宅（历史演示数据口径）
  | 'other';

/** 改造状态机：与后端 RENOVATION_STATUSES 一致（pending_assessment 为初始态） */
export type SpaceStatus =
  | 'pending_assessment'
  | 'assessed'
  | 'in_renovation'
  | 'delivered'
  | 'operating';

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

export const SPACE_FORMAT_LABEL: Record<SpaceFormat, string> = {
  herb_food_courtyard: '药膳小院',
  forest_herbal_bath: '森林药浴',
  kangyang_study: '康养研学',
  seasonal_stay: '节气旅居',
  wellness_resort: '疗愈度假',
  cultural_site: '文旅点位',
  elderly_home: '适老住宅',
  elderly_residence: '适老住宅',
  other: '其他业态'
};

export const SPACE_STATUS_LABEL: Record<SpaceStatus, string> = {
  pending_assessment: '待评估',
  assessed: '已评估',
  in_renovation: '改造中',
  delivered: '已交付',
  operating: '运营中'
};

export const SPACE_STATUS_TONE: Record<SpaceStatus, 'gray' | 'gold' | 'blue' | 'green'> = {
  pending_assessment: 'gray',
  assessed: 'gray',
  in_renovation: 'gold',
  delivered: 'blue',
  operating: 'green'
};

/** 四维就绪度满分（与后端 compute_smart_readiness 权重一致） */
export const READINESS_MAX = { device: 30, sensing: 25, scene: 25, compliance: 20 } as const;
