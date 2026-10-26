/**
 * 后端接口封装（与 app/api/* 一一对应，路径以生产 OpenAPI 为准）。
 *
 * 约定：
 *  - 只做「请求 + 类型声明」，不做视图模型转换（转换见 services/adapters.ts）；
 *  - 字段类型按后端 OpenAPI 实际输出声明，空值一律允许 null，避免适配层猜类型；
 *  - 未在页面使用的接口不在此声明，保持文件可读。
 */
import { get, patch, post } from './request';

// ── 认证与用户 ──

export interface ApiUser {
  id: string;
  phone: string | null;
  name: string;
  role: string;
  sub_role: string | null;
  avatar_url: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  refresh_token: string;
  expires_in: number;
  user: ApiUser;
}

export const authApi = {
  /** 小程序静默登录：wx.login code → PASETO */
  miniprogramLogin: (code: string, profile?: { nickname?: string; avatar_url?: string }) =>
    post<TokenResponse>('/auth/miniprogram/login', { code, ...(profile || {}) }, { auth: false }),

  /** 手机号快速验证并绑定（getPhoneNumber code） */
  bindPhone: (code: string) =>
    post<ApiUser>('/auth/miniprogram/bind-phone', { code }),

  me: () => get<ApiUser>('/auth/me'),

  logout: (refreshToken: string) =>
    post<void>('/auth/logout', { refresh_token: refreshToken })
};

// ── 空间资产台账 ──

export interface SpaceAssetDto {
  id: string;
  owner_id: string;
  project_id: string | null;
  name: string;
  province: string;
  city: string;
  district: string | null;
  address: string | null;
  building_area_sqm: number | null;
  room_count: number | null;
  asset_category: string;
  business_format: string;
  renovation_status: string;
  smart_ready: boolean;
  smart_readiness_score: number;
  matter_device_count: number;
  sensor_count: number;
  scene_automation_count: number;
  fire_safety_status: string;
  accessibility_status: string;
  retrofit_package_code: string | null;
  created_at: string;
}

export interface PortfolioSummaryDto {
  total_assets: number;
  by_category: Record<string, number>;
  by_status: Record<string, number>;
  by_city: Record<string, number>;
  avg_smart_readiness: number;
  smart_ready_count: number;
  total_area_sqm: number;
  platform_role: string;
  note: string;
}

export interface ReadinessBreakdownDto {
  asset_id: string;
  score: number;
  smart_ready: boolean;
  breakdown: {
    device_access?: { score: number; max: number; count: number };
    environment_sensing?: { score: number; max: number; count: number };
    scene_automation?: { score: number; max: number; count: number };
    compliance?: { score: number; max: number; accessibility: string; fire_safety: string };
  };
}

export const spaceAssetApi = {
  list: () => get<SpaceAssetDto[]>('/space-assets'),
  summary: () => get<PortfolioSummaryDto>('/space-assets/summary'),
  readiness: (assetId: string) => get<ReadinessBreakdownDto>(`/space-assets/${assetId}/readiness`)
};

// ── 改造项目 ──

export interface ProjectDto {
  id: string;
  name: string;
  description: string | null;
  address: string | null;
  total_area: number | null;
  status: string;
  phase: string;
  project_type: string | null;
  house_type: string | null;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

/** 后端 ProjectCreate.project_type 枚举（app/schemas/project.py），不可自造值 */
export type ProjectTypeCode =
  | 'full_renovation'
  | 'hard_decoration'
  | 'soft_furnishing'
  | 'curtain'
  | 'kitchen'
  | 'bathroom'
  | 'electrical'
  | 'carpentry'
  | 'painting'
  | 'plumbing'
  | 'masonry'
  | 'installation';

// 用 type 而非 interface：type 具备隐式索引签名，可直接作为 request 的 JSON body
export type ProjectCreatePayload = {
  name: string;
  project_type?: ProjectTypeCode;
  address?: string | null;
  total_area?: number | null;
  house_type?: string | null;
  description?: string | null;
  contact_name?: string | null;
  contact_phone?: string | null;
  source?: 'manual' | 'ar_measure';
};

export const projectApi = {
  list: () => get<ProjectDto[]>('/projects'),
  detail: (projectId: string) => get<ProjectDto>(`/projects/${projectId}`),
  /** 提交改造需求（业主自建项目，落库即出现在项目列表） */
  create: (payload: ProjectCreatePayload) => post<ProjectDto>('/projects', payload)
};

// ── 智能家居（智控）──

export interface SmartSchemeDto {
  id: string;
  project_id: string;
  room_name: string;
  room_type: string;
  protocol: string;
  hub_brand: string | null;
  device_count: number;
  total_price: number;
  status: string;
}

export interface SmartDeviceDto {
  id: string;
  scheme_id: string;
  device_type: string;
  device_name: string;
  brand: string | null;
  model: string | null;
  room_name: string;
  protocol: string;
  control_mode: string;
  power_w: number | null;
  price: number | null;
  features: Record<string, unknown> | null;
  status: string;
  created_at: string;
}

export interface DeviceCommandResult {
  device_id: string;
  device_name: string | null;
  action: string;
  params: Record<string, unknown>;
  accepted: boolean;
  action_status: string;
  note: string | null;
  /** 命令下发的设备状态快照（部分协议返回，可能为空） */
  state: Record<string, unknown> | null;
  async_queued: boolean;
}

export const smartHomeApi = {
  schemes: (projectId: string) => get<SmartSchemeDto[]>(`/smart-home/schemes/project/${projectId}`),
  devices: (schemeId: string) => get<SmartDeviceDto[]>(`/smart-home/schemes/${schemeId}/devices`),
  command: (deviceId: string, action: string, params: Record<string, unknown> = {}) =>
    post<DeviceCommandResult>(`/smart-home/devices/${deviceId}/command`, { action, params })
};

// ── 场景自动化 ──

export interface SceneDto {
  id: string;
  project_id: string;
  scheme_id: string | null;
  scene_name: string;
  scene_type: string;
  trigger_condition: Record<string, unknown> | null;
  actions: Array<Record<string, unknown>> | null;
  ecosystem: string | null;
  enabled: boolean;
  priority: number;
  updated_at: string;
}

export interface SceneExecuteResult {
  scene_id: string;
  scene_name: string;
  executed: boolean;
  actions: unknown[];
  triggered_at: string;
  async_queued: boolean;
}

export const sceneApi = {
  list: (projectId: string) => get<SceneDto[]>(`/scene-automation/scenes/project/${projectId}`),
  execute: (sceneId: string) => post<SceneExecuteResult>(`/scene-automation/scenes/${sceneId}/execute`),
  toggle: (sceneId: string, enabled: boolean) =>
    patch<SceneDto>(`/scene-automation/scenes/${sceneId}`, { enabled })
};

// ── 康养 · 适老改造 ──

export interface QuickInstallPackageDto {
  /** 后端公开视图主键为 package_code（非 code） */
  package_code: string;
  name: string;
  scope_type?: string;
  duration_hours?: number;
  duration_days?: number;
  fixed_price?: number;
  dry_construction?: boolean;
  zero_relocation?: boolean;
  inclusions?: string[];
  excludes?: string[];
  warranty?: string;
  elderly_theme?: boolean;
  subsidy_category?: string;
  elderly_design?: Record<string, string>;
  accessibility_standard?: string;
  target_occupant?: string[];
}

/**
 * 补贴预检返回（app/services/elderly_subsidy_service.py 实际输出）。
 * 注意：金额是确定性单值 total_subsidy / net_payable，不是区间——
 * 前端不得渲染成「¥X–¥X」。
 */
export interface SubsidyPrecheckResult {
  is_estimate?: boolean;
  policy_profile?: string;
  policy_version?: string;
  region?: string;
  subsidy_rate?: number;
  max_subsidy_per_unit?: number | null;
  source?: string;
  disclaimer?: string;
  items?: Array<Record<string, unknown>>;
  total_price?: number;
  total_subsidy?: number;
  net_payable?: number;
  warnings?: string[];
  [key: string]: unknown;
}

export const elderlyApi = {
  packages: () => get<QuickInstallPackageDto[]>('/partial-renovation/quick-install/packages'),
  subsidyProfiles: () => get<Array<Record<string, unknown>>>('/elderly-adaptation/subsidy-profiles'),
  subsidyPrecheck: (payload: {
    package_code?: string;
    items?: Array<Record<string, unknown>>;
    policy_profile?: string;
    region?: string;
  }) => post<SubsidyPrecheckResult>('/elderly-adaptation/subsidy-precheck', payload)
};

// ── AI 管家 ──

export interface ConciergeReply {
  agent_type: string;
  reply: string;
}

export interface AiQaSource {
  domain: string;
  title: string;
  citation: string;
  snippet: string;
}

export interface AiQaResult {
  query: string;
  answer: string;
  sources: AiQaSource[];
  match_type: 'knowledge_base' | 'no_match';
  honest_note: string;
}

export const aiApi = {
  /** 客服 Agent（真实 LLM 回复） */
  concierge: (message: string, context?: string) =>
    post<ConciergeReply>('/agents/concierge/chat', { message, ...(context ? { context } : {}) }),

  /** 装修知识库问答（带引用，未命中诚实降级） */
  search: (query: string) => post<AiQaResult>('/ai-qa/search', { query }),

  faq: () => get<Array<Record<string, unknown>>>('/ai-qa/faq')
};

// ── 会员权益与健康 ──

export interface PointsAccountDto {
  id: string;
  user_id: string;
  account_type: string;
  balance: number;
  total_earned: number;
  total_spent: number;
  level: string;
}

export const memberApi = {
  points: () => get<PointsAccountDto>('/points/account'),
  healthRecords: (projectId: string) =>
    get<Array<Record<string, unknown>>>(`/health-monitor/records/project/${projectId}`)
};

// ── 埋点（公开端点，失败静默）──

export function track(event: string, props: Record<string, unknown> = {}): void {
  post('/analytics/collect', {
    v: '1.0.0',
    events: [
      {
        type: 'track',
        event,
        props,
        ts: Date.now(),
        platform: process.env.TARO_ENV
      }
    ]
  }, { auth: false }).catch(() => {
    // 埋点不得阻塞业务，失败仅本地留痕
    console.info('[Analytics] 事件上报失败', event);
  });
}
