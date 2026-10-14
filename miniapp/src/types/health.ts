export type HealthMetric = 'heart_rate' | 'spo2' | 'sleep_quality' | 'steps' | 'fall_detection';

export interface HealthRecord {
  id: string;
  member: string;
  relation: string;
  metric: HealthMetric;
  metricLabel: string;
  value: number;
  unit: string;
  valueText: string;
  normal: boolean;
  recordedAt: string;
}

export interface HealthSummaryItem {
  metric: HealthMetric;
  label: string;
  valueText: string;
  unit: string;
  normal: boolean;
}

export interface HealthRecordsResult {
  records: HealthRecord[];
  summary: HealthSummaryItem[];
  disclaimer: string;
}