export type ElderlyPackageCode = 'PKG-ELDERLY-BATH' | 'PKG-ELDERLY-ROOM' | 'PKG-ELDERLY-FULL';

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
}

export interface ElderlyPackagesResult {
  packages: ElderlyPackage[];
  disclosure: string;
}