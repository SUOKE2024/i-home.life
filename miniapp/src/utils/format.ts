/** 千分位数字格式化：6543 -> '6,543' */
export const formatNumber = (value: number): string =>
  value.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');

/** 人民币金额格式化：9800 -> '¥9,800' */
export const formatMoney = (value: number): string => `¥${formatNumber(Math.round(value))}`;