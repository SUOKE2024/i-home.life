/**
 * 数据层统一入口（真实后端优先 + 演示数据降级）。
 *
 * 调用方（页面）只认 `callFunction(name, payload)`，不关心数据来源；
 * 数据来源在 store.dataSource 中显式标记，页面据此展示「演示数据」标识，
 * 避免把演示数据当生产数据对外展示（项目诚实边界，见 README）。
 *
 * 降级触发条件（任一）：
 *   - 当前端无登录通道（H5 / 支付宝 / 抖音）或未登录；
 *   - 后端接口未部署（404）、服务异常（5xx）、网络不可达；
 *   - 后端已部署但该租户尚无数据 → 不降级，返回真实空集（空态由页面处理）。
 */
import { ALLOW_DEMO_FALLBACK } from '@/config/env';
import type { HomeAlert, HomeOverview, UserInfo } from '@/types/user';
import type { HealthMetric, HealthRecord, HealthRecordsResult, HealthSummaryItem } from '@/types/health';
import type { ElderlyPackagesResult, SubsidyEstimate } from '@/types/elderly';
import type { SceneAutomation } from '@/types/scene';
import type { SmartDevice } from '@/types/device';
import type { Space } from '@/types/space';
import type { RenovationProject } from '@/types/project';
import {
  elderlyApi,
  memberApi,
  projectApi,
  sceneApi,
  smartHomeApi,
  spaceAssetApi,
  type ProjectDto,
  type ProjectTypeCode,
  type SceneDto,
  type SmartDeviceDto,
  type SpaceAssetDto
} from './api';
import {
  toDevice,
  toPackage,
  toProject,
  toScene,
  toSpace,
  toSubsidyEstimate,
  toUserInfo
} from './adapters';
import { ApiError } from './request';
import { ensureSession, getCachedUser, getSessionState } from './session';

// ── 数据来源状态（页面用于展示「演示数据」标识）──

export type DataSource = 'live' | 'demo' | 'unknown';

let dataSource: DataSource = 'unknown';
let lastReason = '';
const sourceListeners = new Set<(source: DataSource, reason: string) => void>();

export function getDataSource(): { source: DataSource; reason: string } {
  return { source: dataSource, reason: lastReason };
}

export function subscribeDataSource(listener: (source: DataSource, reason: string) => void): () => void {
  sourceListeners.add(listener);
  return () => sourceListeners.delete(listener);
}

function markSource(source: DataSource, reason = ''): void {
  dataSource = source;
  lastReason = reason;
  sourceListeners.forEach((listener) => listener(source, reason));
}

// ── 轻量缓存：一次页面加载内避免重复请求（TTL 5s，下拉刷新可穿透）──

const CACHE_TTL = 5000;
interface CacheEntry<T> {
  at: number;
  value: T;
}
const cache = new Map<string, CacheEntry<unknown>>();

async function cached<T>(key: string, loader: () => Promise<T>): Promise<T> {
  const hit = cache.get(key) as CacheEntry<T> | undefined;
  if (hit && Date.now() - hit.at < CACHE_TTL) return hit.value;
  const value = await loader();
  cache.set(key, { at: Date.now(), value });
  return value;
}

export function invalidateCache(): void {
  cache.clear();
}

// ── 演示数据加载（沿用 src/data/<name>.ts 约定）──

async function loadDemo<T>(name: string, payload?: Record<string, unknown>): Promise<T> {
  let demoModule: { default: (data?: Record<string, unknown>) => unknown };
  try {
    demoModule = await import(`../data/${name}`);
  } catch (err) {
    console.error(`[Data] 未找到本地数据源 src/data/${name}.ts`, err);
    throw new Error(`本地数据源缺失：${name}`);
  }
  return demoModule.default(payload) as T;
}

/**
 * 写操作/真实动作的前置校验：未登录直接失败，绝不回落到演示数据。
 * 消息刻意写明「演示数据不会执行真实动作」——业主需要知道这一下没生效。
 */
async function requireLive(): Promise<void> {
  if (getSessionState() === 'authenticated') return;
  const ok = await ensureSession();
  if (!ok) throw new ApiError('当前未登录，操作未执行（演示数据不会触发真实动作）', 401);
}

/**
 * 真实数据优先，失败降级演示数据。
 * 认证类失败静默降级（用户无感知），服务类失败打印一次告警便于排障。
 */
async function liveOrDemo<T>(
  name: string,
  live: () => Promise<T>,
  demo: () => Promise<T>
): Promise<T> {
  if (!ALLOW_DEMO_FALLBACK) {
    await requireLive();
    const data = await live();
    markSource('live');
    return data;
  }

  try {
    await requireLive();
    const data = await live();
    markSource('live');
    return data;
  } catch (err) {
    const apiError = err as ApiError;
    const reason = apiError?.isAuthError
      ? '未登录'
      : apiError?.isNetworkError
        ? '网络不可达'
        : apiError?.message || '服务异常';
    if (!apiError?.isAuthError) {
      console.warn(`[Data] ${name} 实时数据不可用（${reason}），已降级为演示数据`);
    }
    markSource('demo', reason);
    return demo();
  }
}

// ── 真实数据读取（带缓存）──

const fetchAssets = () => cached<SpaceAssetDto[]>('assets', () => spaceAssetApi.list());
const fetchProjects = () => cached<ProjectDto[]>('projects', () => projectApi.list());

function resolveProjectId(assets: SpaceAssetDto[], spaceId?: string): string | null {
  if (assets.length === 0) return null;
  const target = spaceId ? assets.find((item) => item.id === spaceId) : assets[0];
  return (target || assets[0]).project_id || null;
}

function buildAlerts(spaces: Space[], projects: RenovationProject[], assets: SpaceAssetDto[]): HomeAlert[] {
  const alerts: HomeAlert[] = [];

  const pending = spaces.filter((item) => item.status === 'pending_assessment');
  if (pending.length > 0) {
    alerts.push({
      id: 'alert-pending',
      type: 'service',
      title: `${pending.length} 处空间待评估`,
      desc: '完成空间资产勘测后可生成智能化就绪度与改造方案',
      time: '待处理'
    });
  }

  const active = projects.find((item) => !item.delivered);
  if (active) {
    alerts.push({
      id: 'alert-project',
      type: 'project',
      title: `${active.name} · ${active.nextMilestone}`,
      desc: '项目按六阶段透明化交付推进，可查看阶段明细',
      time: active.updatedAt || '近期'
    });
  }

  const complianceRisk = assets.filter(
    (item) => item.accessibility_status === 'fail' || item.fire_safety_status === 'fail'
  );
  if (complianceRisk.length > 0) {
    alerts.push({
      id: 'alert-compliance',
      type: 'health',
      title: `${complianceRisk.length} 处空间合规项待整改`,
      desc: '无障碍或消防合规检查未通过，建议优先安排整改',
      time: '待整改'
    });
  }

  const lowReadiness = spaces.filter((item) => item.score > 0 && item.score < 60);
  if (lowReadiness.length > 0) {
    alerts.push({
      id: 'alert-readiness',
      type: 'device',
      title: `${lowReadiness.length} 处空间智能就绪度偏低`,
      desc: '接入智能设备、环境感知与场景自动化可提升就绪度',
      time: '建议关注'
    });
  }

  return alerts.slice(0, 4);
}

// ── 健康记录映射（仅识别明确指标，未知指标不猜测）──

const HEALTH_METRIC_MAP: Record<string, { metric: HealthMetric; label: string; unit: string }> = {
  heart_rate: { metric: 'heart_rate', label: '心率', unit: 'bpm' },
  heartrate: { metric: 'heart_rate', label: '心率', unit: 'bpm' },
  spo2: { metric: 'spo2', label: '血氧', unit: '%' },
  blood_oxygen: { metric: 'spo2', label: '血氧', unit: '%' },
  sleep: { metric: 'sleep_quality', label: '睡眠质量', unit: '分' },
  sleep_quality: { metric: 'sleep_quality', label: '睡眠质量', unit: '分' },
  steps: { metric: 'steps', label: '步数', unit: '步' },
  step_count: { metric: 'steps', label: '步数', unit: '步' },
  fall: { metric: 'fall_detection', label: '跌倒检测', unit: '次' },
  fall_detection: { metric: 'fall_detection', label: '跌倒检测', unit: '次' }
};

function pickNumeric(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    for (const key of ['value', 'val', 'score', 'count', 'bpm', 'percent']) {
      const candidate = record[key];
      if (typeof candidate === 'number' && Number.isFinite(candidate)) return candidate;
    }
    const firstNumber = Object.values(record).find(
      (item): item is number => typeof item === 'number' && Number.isFinite(item)
    );
    return firstNumber ?? null;
  }
  return null;
}

function mapHealthRecords(raw: Array<Record<string, unknown>>): HealthRecordsResult {
  const records: HealthRecord[] = [];
  const latestByMetric = new Map<HealthMetric, HealthRecord>();

  raw.forEach((item) => {
    const monitorType = String(item.monitor_type || '');
    const meta = HEALTH_METRIC_MAP[monitorType];
    if (!meta) return; // 未知指标直接丢弃，不做猜测映射
    const numeric = pickNumeric(item.value);
    if (numeric === null) return;

    const alertLevel = String(item.alert_level || 'normal');
    const record: HealthRecord = {
      id: String(item.id || `${monitorType}-${records.length}`),
      member: '空间监测',
      relation: '设备采集',
      metric: meta.metric,
      metricLabel: meta.label,
      value: numeric,
      unit: meta.unit,
      valueText: `${numeric}`,
      normal: alertLevel === 'normal' || alertLevel === 'info' || alertLevel === 'none',
      recordedAt: String(item.recorded_at || '').replace('T', ' ').slice(5, 16)
    };
    records.push(record);
    if (!latestByMetric.has(meta.metric)) latestByMetric.set(meta.metric, record);
  });

  const summary: HealthSummaryItem[] = Array.from(latestByMetric.values()).map((record) => ({
    metric: record.metric,
    label: record.metricLabel,
    valueText: record.valueText,
    unit: record.unit,
    normal: record.normal
  }));

  return {
    records,
    summary,
    disclaimer: '健康数据来自空间内监测设备采集，仅作趋势参考，不构成医疗诊断。'
  };
}

// ── 对外统一入口 ──

export async function callFunction<T = unknown>(
  name: string,
  payload?: Record<string, unknown>
): Promise<T> {
  const result = await route(name, payload);
  return result as T;
}

async function route(name: string, payload?: Record<string, unknown>): Promise<unknown> {
  switch (name) {
    case 'login': {
      const ok = await liveOrDemo<{ ok: boolean; user: UserInfo }>(
        'login',
        async () => {
          const cachedUser = getCachedUser();
          if (!cachedUser) throw new ApiError('缺少用户信息', 401);
          return { ok: true, user: toUserInfo(cachedUser) };
        },
        async () => ({ ok: false, user: (await loadDemo<HomeOverview>('getHomeOverview')).user })
      );
      return ok;
    }

    case 'getHomeOverview':
      return liveOrDemo<HomeOverview>(
        'getHomeOverview',
        async () => {
          const [assets, projects] = await Promise.all([fetchAssets(), fetchProjects()]);
          const spaces = assets.map(toSpace);
          const mappedProjects = projects.map((item) => {
            const asset = assets.find((candidate) => candidate.project_id === item.id);
            return toProject(item, asset?.name);
          });
          const cachedUser = getCachedUser();
          const healthScore =
            spaces.length > 0
              ? Math.round(spaces.reduce((sum, item) => sum + item.score, 0) / spaces.length)
              : 0;
          const deviceTotal = assets.reduce((sum, item) => sum + (item.matter_device_count || 0), 0);

          return {
            user: cachedUser
              ? toUserInfo(cachedUser)
              : {
                  id: '',
                  nickname: '索克业主',
                  avatar: '',
                  phone: '',
                  role: 'owner',
                  roleLabel: '业主',
                  memberSince: ''
                },
            healthScore,
            scoreDelta: 0, // 后端暂无历史曲线，不做虚构涨幅
            stats: {
              spaceCount: spaces.length,
              deviceOnline: deviceTotal,
              deviceTotal,
              activeProjectCount: mappedProjects.filter((item) => !item.delivered).length
            },
            spaces,
            activeProject: mappedProjects.find((item) => !item.delivered) || null,
            alerts: buildAlerts(spaces, mappedProjects, assets)
          };
        },
        () => loadDemo<HomeOverview>('getHomeOverview')
      );

    case 'getSpaces':
      return liveOrDemo<{ spaces: Space[] }>(
        'getSpaces',
        async () => ({ spaces: (await fetchAssets()).map(toSpace) }),
        () => loadDemo<{ spaces: Space[] }>('getSpaces')
      );

    case 'getProjects':
      return liveOrDemo<{ projects: RenovationProject[] }>(
        'getProjects',
        async () => {
          const [projects, assets] = await Promise.all([fetchProjects(), fetchAssets()]);
          return {
            projects: projects.map((item) => {
              const asset = assets.find((candidate) => candidate.project_id === item.id);
              return toProject(item, asset?.name);
            })
          };
        },
        () => loadDemo<{ projects: RenovationProject[] }>('getProjects')
      );

    case 'submitRenovationDemand': {
      // 写操作绝不降级：演示数据不能伪造「需求已提交」，否则业主以为已留资而实际进不了派单池。
      await requireLive();
      const input = (payload || {}) as {
        name?: string;
        projectType?: ProjectTypeCode;
        address?: string;
        totalArea?: number;
        houseType?: string;
        description?: string;
        contactName?: string;
        contactPhone?: string;
      };
      const name = (input.name || '').trim();
      if (!name) throw new ApiError('请填写需求名称', 400);

      const created = await projectApi.create({
        name,
        project_type: input.projectType,
        address: input.address?.trim() || null,
        total_area: typeof input.totalArea === 'number' ? input.totalArea : null,
        house_type: input.houseType?.trim() || null,
        description: input.description?.trim() || null,
        contact_name: input.contactName?.trim() || null,
        contact_phone: input.contactPhone?.trim() || null,
        source: 'manual'
      });
      // 新项目必须立刻出现在列表里，不能等缓存过期
      invalidateCache();
      markSource('live');
      return { projectId: created.id, name: created.name, phase: created.phase };
    }

    case 'getDevices':
      return liveOrDemo<{ devices: SmartDevice[] }>(
        'getDevices',
        async () => {
          const spaceId = payload?.spaceId as string | undefined;
          const assets = await fetchAssets();
          const projectId = resolveProjectId(assets, spaceId);
          if (!projectId) return { devices: [] };
          const targetSpaceId = (spaceId || assets[0]?.id) as string;
          const deviceDtos = await cached<SmartDeviceDto[]>(`devices:${projectId}`, async () => {
            const schemes = await smartHomeApi.schemes(projectId);
            const lists = await Promise.all(
              schemes.map((scheme) => smartHomeApi.devices(scheme.id).catch(() => []))
            );
            return lists.flat();
          });
          return {
            devices: deviceDtos.map((item) => ({ ...toDevice(item), spaceId: targetSpaceId }))
          };
        },
        () => loadDemo<{ devices: SmartDevice[] }>('getDevices', payload)
      );

    case 'getScenes':
      return liveOrDemo<{ scenes: SceneAutomation[] }>(
        'getScenes',
        async () => {
          const spaceId = payload?.spaceId as string | undefined;
          const assets = await fetchAssets();
          const projectId = resolveProjectId(assets, spaceId);
          if (!projectId) return { scenes: [] };
          const sceneDtos = await cached<SceneDto[]>(`scenes:${projectId}`, () =>
            sceneApi.list(projectId)
          );
          return { scenes: sceneDtos.map(toScene) };
        },
        () => loadDemo<{ scenes: SceneAutomation[] }>('getScenes', payload)
      );

    case 'controlDevice': {
      // 这是真实动作，不是读接口：降级会让业主看到「灯已开启」而设备根本没动。
      await requireLive();
      const deviceId = payload?.deviceId as string;
      if (!deviceId) throw new ApiError('缺少设备参数', 400);
      const result = await smartHomeApi.command(deviceId, 'toggle');
      if (!result.accepted) {
        throw new ApiError(result.note || '设备未响应，请稍后重试', 502);
      }
      const state = (result.state || {}) as Record<string, unknown>;
      const on = typeof state.on === 'boolean' ? state.on : undefined;
      const status = on === undefined ? 'on' : on ? 'on' : 'off';
      invalidateCache();
      markSource('live');

      return {
        device: {
          id: result.device_id,
          spaceId: '',
          name: result.device_name || '设备',
          room: '',
          type: 'other',
          typeLabel: '设备',
          badge: '设',
          switchable: true,
          status,
          statusText: status === 'on' ? '开启' : '关闭',
          valueText: '—',
          online: true
        }
      };
    }

    case 'executeScene': {
      // 同 controlDevice：场景执行会真实下发指令，降级等于骗人。
      await requireLive();
      const sceneId = payload?.sceneId as string;
      if (!sceneId) throw new ApiError('缺少场景参数', 400);
      const result = await sceneApi.execute(sceneId);
      if (!result.executed) {
        throw new ApiError('场景执行失败，请检查设备在线状态', 502);
      }
      markSource('live');
      return {
        sceneId: result.scene_id,
        executed: result.executed,
        executedAt: (result.triggered_at || '').replace('T', ' ').slice(0, 16) || '刚刚'
      };
    }

    case 'getElderlyPackages':
      return liveOrDemo<ElderlyPackagesResult>(
        'getElderlyPackages',
        async () => {
          const all = await cached('quickInstallPackages', () => elderlyApi.packages());
          const elderlyOnly = all.filter((item) => item.elderly_theme);
          const picked = elderlyOnly.length > 0 ? elderlyOnly : all;
          return {
            packages: picked.map(toPackage),
            disclosure:
              '以上为平台标准快装套餐一口价（干法施工、0 搬家）；具体方案以现场勘测与签约合同为准。'
          };
        },
        () => loadDemo<ElderlyPackagesResult>('getElderlyPackages')
      );

    case 'estimateSubsidy':
      return liveOrDemo<SubsidyEstimate>(
        'estimateSubsidy',
        async () => {
          const packageCode = payload?.packageCode as string;
          if (!packageCode) throw new ApiError('缺少套餐参数', 400);
          const all = await cached('quickInstallPackages', () => elderlyApi.packages());
          const pkg = all.find((item) => item.package_code === packageCode);
          if (!pkg) throw new ApiError('套餐不存在或已下架', 404);
          const result = await elderlyApi.subsidyPrecheck({ package_code: packageCode });
          return toSubsidyEstimate(result, {
            code: pkg.package_code,
            name: pkg.name
          });
        },
        () => loadDemo<SubsidyEstimate>('estimateSubsidy', payload)
      );

    case 'getHealthRecords':
      return liveOrDemo<HealthRecordsResult>(
        'getHealthRecords',
        async () => {
          const assets = await fetchAssets();
          const projectId =
            resolveProjectId(assets, payload?.spaceId as string | undefined) || assets[0]?.project_id;
          if (!projectId) {
            return { records: [], summary: [], disclaimer: '尚未关联改造项目，暂无健康监测数据。' };
          }
          const raw = await memberApi.healthRecords(projectId);
          return mapHealthRecords(raw);
        },
        () => loadDemo<HealthRecordsResult>('getHealthRecords')
      );

    default:
      throw new Error(`未实现的数据调用：${name}`);
  }
}
