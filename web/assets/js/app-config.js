/* ============================================
 * 索克家居 · 应用配置（与 Flutter config.dart 对齐）
 * 集中管理版本号、超时、功能开关等常量
 * ============================================ */

const AppConfig = {
  // ── 版本号（与 Flutter 1.1.17+9 / 后端 config.py 对齐） ──

  /** 语义化版本号 */
  appVersion: '1.1.28',

  /** 前端资源版本标记（用于 CSS/JS 缓存刷新） */
  resourceVersion: 'v=20260724b',

  /** Service Worker 缓存版本 */
  cacheVersion: 'suoke-v20260724b',

  // ── API 配置 ──

  /** 通用 API 请求超时（ms） */
  requestTimeout: 30000,

  /** Agent LLM 调用超时（ms） */
  agentTimeout: 180000,

  /** API 重试最大次数 */
  maxRetries: 3,

  /** 重试指数退避基数（ms） */
  retryBaseDelay: 500,

  // ── 离线配置 ──

  /** 离线缓存 TTL（ms），默认 30 分钟 */
  cacheTTL: 30 * 60 * 1000,

  // ── 功能开关 ──

  /** 是否启用 Filament 3D 渲染引擎 */
  filamentEnabled: false,

  /** 是否启用 AI 渲染服务 */
  aiRenderEnabled: true,

  /** 是否启用语音情感路由 */
  voiceEmotionRoutingEnabled: true,

  /** 是否启用 Agent 自适应学习 */
  agentLearningEnabled: true,

  /** 是否启用 MCP Server */
  mcpEnabled: true,

  /** 3D WebGPU 网格阈值（超阈值强制 WebGL） */
  webgpuMeshThreshold: 500,

  // ── 业务常量 ──

  /** 项目装修阶段定义 */
  phases: [
    { key: 'initiation', label: '立项', color: '#E57373' },
    { key: 'design', label: '设计', color: '#64B5F6' },
    { key: 'budget', label: '预算', color: '#81C784' },
    { key: 'procurement', label: '采购', color: '#FFB74D' },
    { key: 'construction', label: '施工', color: '#BA68C8' },
    { key: 'inspection', label: '质检', color: '#4DD0E1' },
    { key: 'settlement', label: '结算', color: '#FFD54F' },
  ],

  /** 角色标签映射 */
  roleLabels: {
    admin: '管理员',
    homeowner: '业主',
    designer: '设计师',
    contractor: '施工方',
    supplier: '供应商',
    inspector: '监理',
    electrician: '电工',
    carpenter: '木工',
  },
};

// 暴露到全局
window.AppConfig = AppConfig;

// ── 同步 ApiClient 配置 ──
if (window.ApiClient) {
  window.ApiClient._maxRetries = AppConfig.maxRetries;
  window.ApiClient._retryBaseDelay = AppConfig.retryBaseDelay;
}

// ── 同步 OfflineCache 配置 ──
if (window.OfflineCache) {
  window.OfflineCache._ttlMs = AppConfig.cacheTTL;
}
