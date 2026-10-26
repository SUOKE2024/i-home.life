export type DeviceType =
  | 'light'
  | 'curtain'
  | 'ac'
  | 'lock'
  | 'environment_sensor'
  | 'fall_radar'
  | 'emergency_call'
  | 'care_bed'
  | 'health_monitor'
  | 'service_robot'
  | 'other';

export type DeviceStatus = 'on' | 'off' | 'monitoring' | 'standby' | 'charging' | 'offline';

export interface SmartDevice {
  id: string;
  spaceId: string;
  name: string;
  room: string;
  type: DeviceType;
  typeLabel: string;
  badge: string;
  switchable: boolean;
  status: DeviceStatus;
  statusText: string;
  valueText: string;
  online: boolean;
}

export type DeviceAction = 'toggle';

export interface ControlDeviceInput {
  deviceId: string;
  action: DeviceAction;
}

/** 设备类型展示口径（未知类型统一显示「其他设备」，不猜测品类） */
export const DEVICE_TYPE_META: Record<DeviceType, { label: string; badge: string; switchable: boolean }> = {
  light: { label: '智能灯光', badge: '灯', switchable: true },
  curtain: { label: '智能窗帘', badge: '帘', switchable: true },
  ac: { label: '空调温控', badge: '空', switchable: true },
  lock: { label: '智能门锁', badge: '锁', switchable: false },
  environment_sensor: { label: '环境感知', badge: '感', switchable: false },
  fall_radar: { label: '跌倒雷达', badge: '跌', switchable: false },
  emergency_call: { label: '紧急呼叫', badge: '呼', switchable: false },
  care_bed: { label: '护理床', badge: '床', switchable: false },
  health_monitor: { label: '健康监测', badge: '健', switchable: false },
  service_robot: { label: '服务机器人', badge: '机', switchable: false },
  other: { label: '其他设备', badge: '设', switchable: false }
};

export const DEVICE_STATUS_TEXT: Record<DeviceStatus, string> = {
  on: '开启',
  off: '关闭',
  monitoring: '监测中',
  standby: '待机',
  charging: '充电中',
  offline: '离线'
};
