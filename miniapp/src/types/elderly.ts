/**
 * 适老改造套餐与补贴预估口径。
 *
 * 套餐编码以后端 /partial-renovation/quick-install/packages 实际输出为准，
 * 后端新增套餐（如 PKG-48H-KITCHEN）前端需直接可用，故编码保持字符串类型，
 * 已知适老编码仅作提示，不做穷举限制。
 */
export type ElderlyPackageCode = string;

/** 已知适老套餐编码（仅作常量引用，非类型穷举） */
export const ELDERLY_PACKAGE_CODES = {
  bath: 'PKG-ELDERLY-BATH',
  room: 'PKG-ELDERLY-ROOM',
  full: 'PKG-ELDERLY-FULL'
} as const;

export type ElderlyDesignDimension = '尺寸适配' | '操作便利' | '方言识别' | '安全性能';

export interface ElderlyPackage {
  code: ElderlyPackageCode;
  name: string;
  tagline: string;
  price: number;
  priceLabel: string;
  unit: string;
  tags: string[];
  designDims: ElderlyDesignDimension[];
  subsidyCategory: string;
  cover: string;
  /** 改造工期（小时），后端 duration_hours；缺失时不展示 */
  durationHours?: number;
  /** 包含项 / 不含项 / 质保（后端 inclusions / excludes / warranty） */
  inclusions?: string[];
  excludes?: string[];
  warranty?: string;
  /** 是否平台标注的适老主题套餐（后端 elderly_theme） */
  elderlyTheme?: boolean;
}

export interface SubsidyEstimate {
  packageCode: string;
  packageName: string;
  min: number;
  max: number;
  minLabel: string;
  maxLabel: string;
  isEstimate: boolean;
  basisNote: string;
  warnings: string[];
  disclaimer: string;
  /** 后端确定性单值估算（有值时页面优先展示单值，不渲染伪区间） */
  exact?: number;
  exactLabel?: string;
  /** 补贴后个人应付 */
  netPayable?: number;
  netPayableLabel?: string;
}

export interface ElderlyPackagesResult {
  packages: ElderlyPackage[];
  disclosure: string;
}
