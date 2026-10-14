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
  | 'service_robot';

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