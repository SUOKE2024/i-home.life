/**
 * 后端 DTO → 页面视图模型适配层。
 *
 * 原则：
 *  - 只做「字段搬运 + 枚举翻译」，不虚增后端没有的数据：
 *    后端缺字段时输出占位值（如「待核算」），不编造金额、施工方、日期；
 *  - 派生值必须标注口径（如项目进度按阶段推断，与后端 phase 状态机一致）；
 *  - 枚举翻译表与后端模型逐项对齐，未知值一律回落到 `other` / 占位文案，不猜测。
 */
import type {
  ApiUser,
  ProjectDto,
  QuickInstallPackageDto,
  SceneDto,
  SmartDeviceDto,
  SpaceAssetDto,
  SubsidyPrecheckResult
} from './api';
import type { DeviceStatus, DeviceType, SmartDevice } from '@/types/device';
import { DEVICE_STATUS_TEXT, DEVICE_TYPE_META } from '@/types/device';
import type { ElderlyPackage, SubsidyEstimate } from '@/types/elderly';
import type { ProjectStage, RenovationProject } from '@/types/project';
import { PROJECT_STAGE_LABEL, PROJECT_STAGE_ORDER, stageIndexOf } from '@/types/project';
import type { SceneAutomation, SceneType } from '@/types/scene';
import type { ReadinessBreakdown, Space, SpaceFormat, SpaceStatus } from '@/types/space';
import { SPACE_FORMAT_LABEL } from '@/types/space';
import type { UserInfo } from '@/types/user';
import { formatMoney } from '@/utils/format';

/**
 * 业态封面占位图。
 * 后端 space_assets 当前无封面上传字段，正式运营前需替换为自有 CDN 资源
 * （见 README「上线待办」）。第三方占位图仅用于演示与灰度，不可作为生产视觉资产。
 */
const COVER_BY_FORMAT: Record<SpaceFormat, string> = {
  herb_food_courtyard: 'https://picsum.photos/id/598/750/400',
  forest_herbal_bath: 'https://picsum.photos/id/1036/750/400',
  kangyang_study: 'https://picsum.photos/id/1082/750/400',
  seasonal_stay: 'https://picsum.photos/id/1015/750/400',
  wellness_resort: 'https://picsum.photos/id/1018/750/400',
  cultural_site: 'https://picsum.photos/id/225/750/400',
  elderly_home: 'https://picsum.photos/id/787/750/400',
  elderly_residence: 'https://picsum.photos/id/787/750/400',
  other: 'https://picsum.photos/id/1084/750/400'
};

const PROJECT_COVER = 'https://picsum.photos/id/1080/750/400';

/** 后端 BUSINESS_FORMATS → 前端 SpaceFormat（未知回落 other） */
export function toSpaceFormat(raw: string): SpaceFormat {
  const known = Object.keys(SPACE_FORMAT_LABEL) as SpaceFormat[];
  return known.includes(raw as SpaceFormat) ? (raw as SpaceFormat) : 'other';
}

/** 后端 RENOVATION_STATUSES → 前端 SpaceStatus（未知回落待评估） */
export function toSpaceStatus(raw: string): SpaceStatus {
  const known: SpaceStatus[] = [
    'pending_assessment',
    'assessed',
    'in_renovation',
    'delivered',
    'operating'
  ];
  return known.includes(raw as SpaceStatus) ? (raw as SpaceStatus) : 'pending_assessment';
}

/**
 * 四维就绪度（与后端 space_asset_service.compute_smart_readiness 同权重）：
 * 设备接入 30 / 环境感知 25 / 场景编排 25 / 合规就绪 20，无数据计 0 不虚增。
 */
export function computeReadiness(input: {
  deviceCount: number;
  sensorCount: number;
  sceneCount: number;
  accessibility: string;
  fireSafety: string;
}): ReadinessBreakdown {
  const device = Math.min(30, input.deviceCount * 3);
  const sensing = Math.min(25, input.sensorCount * 2.5);
  const scene = Math.min(25, input.sceneCount * 5);
  let compliance = 0;
  if (input.accessibility === 'pass') compliance += 10;
  else if (input.accessibility === 'warning') compliance += 5;
  if (input.fireSafety === 'pass') compliance += 10;
  else if (input.fireSafety === 'warning') compliance += 5;
  return {
    device: Math.round(device),
    sensing: Math.round(sensing),
    scene: Math.round(scene),
    compliance: Math.round(compliance)
  };
}

export function toSpace(asset: SpaceAssetDto): Space {
  const format = toSpaceFormat(asset.business_format);
  const readiness = computeReadiness({
    deviceCount: asset.matter_device_count || 0,
    sensorCount: asset.sensor_count || 0,
    sceneCount: asset.scene_automation_count || 0,
    accessibility: asset.accessibility_status || 'unknown',
    fireSafety: asset.fire_safety_status || 'unknown'
  });
  const score =
    typeof asset.smart_readiness_score === 'number'
      ? Math.round(asset.smart_readiness_score)
      : readiness.device + readiness.sensing + readiness.scene + readiness.compliance;

  return {
    id: asset.id,
    name: asset.name,
    format,
    formatLabel: SPACE_FORMAT_LABEL[format],
    city: [asset.city, asset.district].filter(Boolean).join(' · ') || asset.province,
    area: Math.round(asset.building_area_sqm ?? 0),
    status: toSpaceStatus(asset.renovation_status),
    score,
    cover: COVER_BY_FORMAT[format],
    deviceCount: asset.matter_device_count || 0,
    readiness,
    packageCode: asset.retrofit_package_code || undefined,
    createTime: (asset.created_at || '').slice(0, 10)
  };
}

/** 后端 7 阶段（initiation…completed）→ 前端 6 阶段展示口径 */
const PHASE_TO_STAGE: Record<string, ProjectStage> = {
  initiation: 'design',
  design: 'design',
  budget: 'budget',
  procurement: 'procurement',
  construction: 'construction',
  quality: 'qa',
  settlement: 'settlement',
  completed: 'settlement'
};

const BACKEND_PHASE_LABEL: Record<string, string> = {
  initiation: '立项',
  design: '设计',
  budget: '预算',
  procurement: '采购',
  construction: '施工',
  quality: '质检',
  settlement: '结算',
  completed: '已竣工'
};

export function toProject(dto: ProjectDto, spaceName?: string): RenovationProject {
  const delivered = dto.status === 'completed' || dto.phase === 'completed';
  // initiation = 需求刚提交、尚未勘测：不能显示成「设计阶段」，否则业主以为已动工
  const pending = dto.phase === 'initiation';
  const stage = PHASE_TO_STAGE[dto.phase] || 'design';
  const currentIndex = stageIndexOf(stage);
  // 进度按阶段推断（后端未下发完成率）：6 阶段均分，竣工记 100%
  const progress = delivered
    ? 100
    : pending
      ? 0
      : Math.round((currentIndex / PROJECT_STAGE_ORDER.length) * 100);
  const nextStage = PROJECT_STAGE_ORDER[currentIndex + 1];

  return {
    id: dto.id,
    name: dto.name,
    spaceName: spaceName || dto.address || `${dto.house_type || '空间'} · ${dto.total_area ?? 0}㎡`,
    cover: PROJECT_COVER,
    stage,
    statusLabel: pending ? '待勘测' : PROJECT_STAGE_LABEL[stage],
    pending,
    progress,
    nextMilestone: delivered
      ? '已交付 · 运营交接完成'
      : pending
        ? '待顾问联系 · 上门勘测'
        : nextStage
          ? `进入${PROJECT_STAGE_LABEL[nextStage]}阶段`
          : '结算收尾',
    nextDate: (dto.updated_at || '').slice(5, 10),
    contractor: '待指派',
    budget: '待核算',
    delivered,
    updatedAt: (dto.updated_at || '').replace('T', ' ').slice(0, 16)
  };
}

/** 当前阶段中文名（项目详情用，7 阶段口径不经前端压缩） */
export function backendPhaseLabel(phase: string): string {
  return BACKEND_PHASE_LABEL[phase] || phase;
}

const BACKEND_DEVICE_TYPE: Record<string, DeviceType> = {
  light: 'light',
  lighting: 'light',
  lamp: 'light',
  switch: 'light',
  curtain: 'curtain',
  curtain_motor: 'curtain',
  ac: 'ac',
  air_conditioner: 'ac',
  hvac: 'ac',
  thermostat: 'ac',
  lock: 'lock',
  smart_lock: 'lock',
  sensor: 'environment_sensor',
  environment_sensor: 'environment_sensor',
  temperature_sensor: 'environment_sensor',
  humidity_sensor: 'environment_sensor',
  air_quality_sensor: 'environment_sensor',
  fall_radar: 'fall_radar',
  mmwave_radar: 'fall_radar',
  emergency_button: 'emergency_call',
  emergency_call: 'emergency_call',
  care_bed: 'care_bed',
  health_monitor: 'health_monitor',
  smart_watch: 'health_monitor',
  robot: 'service_robot',
  service_robot: 'service_robot'
};

const BACKEND_DEVICE_STATUS: Record<string, DeviceStatus> = {
  on: 'on',
  off: 'off',
  online: 'standby',
  offline: 'offline',
  standby: 'standby',
  monitoring: 'monitoring',
  charging: 'charging',
  active: 'on',
  inactive: 'off'
};

export function toDevice(dto: SmartDeviceDto): SmartDevice {
  const type = BACKEND_DEVICE_TYPE[dto.device_type] || 'other';
  const meta = DEVICE_TYPE_META[type];
  const status = BACKEND_DEVICE_STATUS[dto.status] || 'standby';
  const online = status !== 'offline';

  return {
    id: dto.id,
    spaceId: dto.scheme_id,
    name: dto.device_name,
    room: dto.room_name || '未分区',
    type,
    typeLabel: meta.label,
    badge: meta.badge,
    switchable: meta.switchable && online,
    status,
    statusText: DEVICE_STATUS_TEXT[status],
    valueText: '—',
    online
  };
}

const BACKEND_SCENE_TYPE: Record<string, SceneType> = {
  manual: 'manual',
  scheduled: 'scheduled',
  timer: 'scheduled',
  triggered: 'triggered',
  sensor: 'triggered',
  geo: 'geo',
  geofence: 'geo',
  location: 'geo'
};

const SCENE_TYPE_LABEL: Record<SceneType, string> = {
  manual: '手动场景',
  scheduled: '定时场景',
  triggered: '触发场景',
  geo: '地理场景'
};

export function toScene(dto: SceneDto): SceneAutomation {
  const triggerKeys = dto.trigger_condition ? Object.keys(dto.trigger_condition) : [];
  let sceneType = BACKEND_SCENE_TYPE[dto.scene_type] || '';
  if (!sceneType && triggerKeys.length > 0) {
    // 后端未下发类型时按触发条件推断（时间 → 定时，其余 → 触发），仅用于展示分组
    sceneType = triggerKeys.some((key) => key.includes('time')) ? 'scheduled' : 'triggered';
  }
  const resolved = (sceneType || 'manual') as SceneType;

  return {
    id: dto.id,
    spaceId: dto.project_id,
    name: dto.scene_name,
    sceneType: resolved,
    sceneTypeLabel: SCENE_TYPE_LABEL[resolved],
    trigger: triggerKeys.length > 0 ? triggerKeys.join(' / ') : '手动执行',
    actions: `${dto.actions?.length ?? 0} 个动作`,
    enabled: dto.enabled,
    lastExecutedAt: (dto.updated_at || '').replace('T', ' ').slice(0, 16) || '—'
  };
}

const SUBSIDY_CATEGORY_LABEL: Record<string, string> = {
  fall_prevention: '防跌倒改造',
  health_emergency: '健康应急',
  accessibility: '无障碍改造',
  smart_care: '智能照护',
  bathroom: '卫浴改造',
  other: '其他'
};

const DESIGN_DIMS = ['尺寸适配', '操作便利', '方言识别', '安全性能'] as const;

export function toPackage(dto: QuickInstallPackageDto): ElderlyPackage {
  const price = dto.fixed_price ?? 0;
  const tags: string[] = [];
  if (dto.dry_construction) tags.push('干法施工');
  if (dto.zero_relocation) tags.push('0 搬家');
  if (dto.duration_days) tags.push(`${dto.duration_days} 天完工`);
  else if (dto.duration_hours) tags.push(`${dto.duration_hours} 小时完工`);

  const dims = Object.keys(dto.elderly_design || {}).filter((key) =>
    (DESIGN_DIMS as readonly string[]).includes(key)
  ) as Array<(typeof DESIGN_DIMS)[number]>;

  return {
    code: dto.package_code,
    name: dto.name,
    tagline: (dto.inclusions || []).slice(0, 1).join('') || '一口价 · 标准快装',
    price,
    priceLabel: formatMoney(price),
    unit: dto.dry_construction ? '一口价 · 干法施工' : '一口价',
    tags,
    designDims: dims,
    subsidyCategory: SUBSIDY_CATEGORY_LABEL[dto.subsidy_category || ''] || '适老改造',
    cover: COVER_BY_FORMAT.elderly_home,
    durationHours: dto.duration_hours,
    inclusions: dto.inclusions,
    excludes: dto.excludes,
    warranty: dto.warranty,
    elderlyTheme: dto.elderly_theme ?? false
  };
}

/**
 * 补贴预检结果 → 预估视图。
 * 后端给出的是确定性单值（成交价 × 政策档案比例），不是区间；
 * 因此 min = max = total_subsidy，页面在 exactLabel 存在时优先展示单值，
 * 不把确定性结果渲染成「¥X–¥X」的伪区间。
 */
export function toSubsidyEstimate(
  result: SubsidyPrecheckResult,
  pkg: { code: string; name: string }
): SubsidyEstimate {
  const amount = Math.round(Number(result.total_subsidy ?? 0));
  const rate = Number(result.subsidy_rate ?? 0);
  const cap = Number(result.max_subsidy_per_unit ?? 0);
  const warnings = Array.isArray(result.warnings) ? result.warnings.map(String) : [];

  return {
    packageCode: pkg.code,
    packageName: pkg.name,
    min: amount,
    max: amount,
    minLabel: formatMoney(amount),
    maxLabel: formatMoney(amount),
    isEstimate: true,
    basisNote: `按全国基准政策档案 ${(rate * 100).toFixed(0)}% 比例估算${
      cap > 0 ? `，单件补贴上限 ${formatMoney(cap)}` : ''
    }；未接入地方官方目录。`,
    warnings,
    disclaimer:
      String(result.disclaimer || '') ||
      '预估结果仅供参考，非资格认定；实际补贴金额以主管部门核定为准。',
    exact: amount,
    exactLabel: formatMoney(amount),
    netPayable: Number(result.net_payable ?? 0),
    netPayableLabel: formatMoney(Number(result.net_payable ?? 0))
  };
}

const ROLE_LABEL: Record<string, string> = {
  homeowner: '业主',
  designer: '设计师',
  contractor: '施工方',
  supplier: '供应商',
  admin: '管理员',
  owner: '业主'
};

export function toUserInfo(user: ApiUser): UserInfo {
  return {
    id: user.id,
    nickname: user.name || '索克业主',
    avatar: user.avatar_url || '',
    phone: user.phone || '',
    role: 'owner',
    roleLabel: ROLE_LABEL[user.role] || '业主',
    memberSince: (user.created_at || '').slice(0, 10)
  };
}
