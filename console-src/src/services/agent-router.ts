/**
 * 索克家居 · 自然语言 → Agent 路由器（TS 迁移自 web/assets/js/agent-router.js）
 *
 * 迁移内容：
 *   1. AGENT_INFO 表（agent-router.js:261-304）：9 核心 + ~30 扩展 agent 的 {name, emoji, color}
 *   2. patterns 关键词表（agent-router.js:8-209）：关键词 → agent 匹配
 *   3. route(text) 路由函数（agent-router.js:212-258）：关键词评分 + 置信度 + 澄清
 *
 * color 引用 tokens.ts 的 agent 色（而非 CSS 变量字符串），便于 TS 直接消费。
 */

import { tokens } from '../tokens/tokens';
import type { AgentKey } from '../types/chat';

export interface AgentInfo {
  key: string;
  name: string;
  emoji: string;
  /** hex 色值（来自 tokens） */
  color: string;
}

/** Agent 显示信息表 — 对齐 agent-router.js:261-304 + suoke_theme.dart:115-122 */
const AGENT_INFO: Record<string, AgentInfo> = {
  master:                 { key: 'master',                 name: '总控',       emoji: '🏠', color: tokens.agentMaster },
  design:                 { key: 'design',                 name: '设计',       emoji: '📐', color: tokens.agentDesign },
  budget:                 { key: 'budget',                 name: '预算',       emoji: '💰', color: tokens.agentBudget },
  procurement:            { key: 'procurement',            name: '采购',       emoji: '🛒', color: tokens.agentProcurement },
  construction:           { key: 'construction',           name: '施工',       emoji: '🔨', color: tokens.agentConstruction },
  quality:                { key: 'quality',                name: '质检',       emoji: '✅', color: tokens.agentQuality },
  settlement:             { key: 'settlement',             name: '结算',       emoji: '🧾', color: tokens.agentSettlement },
  support:                { key: 'support',                name: '客服',       emoji: '🎧', color: tokens.agentSupport },
  admin:                  { key: 'admin',                  name: '管理',       emoji: '⚙️', color: tokens.accent },
  ar_measurement:         { key: 'ar_measurement',         name: 'AR测量',     emoji: '📏', color: tokens.agentDesign },
  floorplans:             { key: 'floorplans',             name: '户型',       emoji: '📋', color: tokens.agentDesign },
  structural:             { key: 'structural',             name: '土建结构',   emoji: '🏗️', color: tokens.agentConstruction },
  lighting:               { key: 'lighting',               name: '灯光',       emoji: '💡', color: tokens.agentDesign },
  smart_home:             { key: 'smart_home',             name: '智能家居',   emoji: '🤖', color: tokens.agentConstruction },
  scene_automation:       { key: 'scene_automation',       name: '场景',       emoji: '🔄', color: tokens.agentDesign },
  custom_furniture:       { key: 'custom_furniture',       name: '定制家具',   emoji: '🪚', color: tokens.agentDesign },
  tasks:                  { key: 'tasks',                  name: '任务',       emoji: '📝', color: tokens.agentConstruction },
  change_orders:          { key: 'change_orders',          name: '变更',       emoji: '📋', color: tokens.agentConstruction },
  crews:                  { key: 'crews',                  name: '工程队',     emoji: '👷', color: tokens.agentConstruction },
  vr_panorama:            { key: 'vr_panorama',            name: 'VR全景',     emoji: '🥽', color: tokens.agentDesign },
  ai_render:              { key: 'ai_render',              name: 'AI渲染',     emoji: '🎨', color: tokens.agentDesign },
  sketch_to_3d:           { key: 'sketch_to_3d',           name: '草图转3D',   emoji: '✏️', color: tokens.agentDesign },
  soft_furnishing:        { key: 'soft_furnishing',        name: '软装',       emoji: '🛋️', color: tokens.agentDesign },
  hard_decoration:        { key: 'hard_decoration',        name: '硬装',       emoji: '🧱', color: tokens.agentConstruction },
  takeoff:                { key: 'takeoff',                name: '工程量',     emoji: '📊', color: tokens.agentConstruction },
  points:                 { key: 'points',                 name: '积分',       emoji: '⭐', color: tokens.agentMaster },
  cad_import:             { key: 'cad_import',             name: 'CAD导入',    emoji: '📐', color: tokens.agentDesign },
  kitchen:                { key: 'kitchen',                name: '厨房',       emoji: '🍳', color: tokens.agentDesign },
  bathroom:               { key: 'bathroom',               name: '卫浴',       emoji: '🛁', color: tokens.agentDesign },
  mep:                    { key: 'mep',                    name: '水电暖通',   emoji: '🔧', color: tokens.agentConstruction },
  appliance:              { key: 'appliance',              name: '家电',       emoji: '📺', color: tokens.agentProcurement },
  furniture_catalog:      { key: 'furniture_catalog',      name: '家具',       emoji: '🪑', color: tokens.agentProcurement },
  door_window_waterproof: { key: 'door_window_waterproof', name: '门窗防水',   emoji: '🚪', color: tokens.agentConstruction },
  files:                  { key: 'files',                  name: '文件',       emoji: '📁', color: tokens.agentMaster },
  products:               { key: 'products',               name: '产品',       emoji: '🏷️', color: tokens.agentProcurement },
  identity:               { key: 'identity',               name: '身份认证',   emoji: '🆔', color: tokens.agentMaster },
  voice:                  { key: 'voice',                  name: '语音',       emoji: '🎙️', color: tokens.agentMaster },
  notifications:          { key: 'notifications',          name: '通知',       emoji: '🔔', color: tokens.agentMaster },
  ifc_export:             { key: 'ifc_export',             name: 'BIM导出',    emoji: '🏗️', color: tokens.agentDesign },
};

/** 获取 agent 显示信息（未知 key 回退 master） */
export function getAgentInfo(key: string): AgentInfo {
  return AGENT_INFO[key] ?? AGENT_INFO.master;
}

/** 8 核心 agent key（对齐 suoke_theme.dart agentColor 8 色） */
export const CORE_AGENTS: string[] = [
  'master', 'design', 'budget', 'procurement', 'construction', 'quality', 'settlement', 'support',
];

/** 后端 agent_type → 前端 agent key 映射（对齐 ai_chat_page.dart _backendToAgent） */
const BACKEND_TO_AGENT: Record<string, string> = {
  master: 'master',
  homeowner: 'master',
  design: 'design',
  designer: 'design',
  budget: 'budget',
  procurement: 'procurement',
  construction: 'construction',
  contractor: 'construction',
  quality: 'quality',
  settlement: 'settlement',
  support: 'support',
  admin: 'admin',
};

/** 后端 agent_type → 前端 key */
export function backendToAgent(backendType: string): string {
  return BACKEND_TO_AGENT[backendType] ?? backendType ?? 'master';
}

/** 前端 agent key → 后端 agent_type（对齐 ai_chat_page.dart _agentToBackend） */
export function agentToBackend(agent: string): string {
  // 多数 key 与后端一致，少数需映射
  const map: Record<string, string> = {
    master: 'master',
    design: 'design',
    budget: 'budget',
    procurement: 'procurement',
    construction: 'construction',
    quality: 'quality',
    settlement: 'settlement',
    support: 'support',
    admin: 'admin',
  };
  return map[agent] ?? agent;
}

interface KeywordPattern {
  agent: string;
  keywords: string[];
}

/** 关键词映射表 — 迁移自 agent-router.js:8-209 */
const PATTERNS: KeywordPattern[] = [
  { agent: 'budget',       keywords: ['预算', '花了多少钱', '还剩多少', '支出', '费用', '超支', '成本', '价格', '多少钱', '报价', '账单', '付款', '支付'] },
  { agent: 'design',       keywords: ['设计', '方案', '图纸', '布局', '风格', '装修风格', '效果图', '改造', '改', '开放式', '打通', '隔断', 'CAD', '3D'] },
  { agent: 'construction', keywords: ['施工', '进度', '开工', '水电', '木工', '瓦工', '油漆', '泥工', '贴砖', '刷墙', '打孔', '拆', '今天干', '任务', '工序', '阶段'] },
  { agent: 'procurement',  keywords: ['采购', '买', '订购', '下单', '物流', '到货', '发货', '什么时候到', '供应商', '比价', '地砖', '瓷砖', '地板', '涂料', '材料', '发布产品', '上架', '我的产品', '修改产品', '下架', '库存', '改价格', '产品管理'] },
  { agent: 'quality',      keywords: ['质检', '验收', '检查', '问题', '毛病', '整改', '返工', '合格', '不合格', '检测', '偏差', '偏差多少'] },
  { agent: 'settlement',   keywords: ['结算', '对账', '尾款', '结清', '结账', '完工结算', '最终账单', '总账'] },
  { agent: 'support',      keywords: ['客服', '帮助', '怎么用', '怎么操作', '联系', '投诉', '建议', '反馈', '问题反馈'] },
  { agent: 'master',       keywords: ['总控', '统筹', '协调', '概况', '整体', '总结', '汇报', '状态', '什么时候完工', '还要多久'] },
  { agent: 'admin',        keywords: ['用户管理', '角色管理', '权限管理', '平台统计', '管理员', '禁用用户', '启用用户', '审核认证', '修改角色', '用户列表', '设为管理员', '平台数据', '全部项目', '所有用户', '实名认证'] },
  { agent: 'ar_measurement', keywords: ['AR', 'AR测量', '测量', '扫描', '量房', '激光', 'LiDAR', 'RoomPlan', '测距', '丈量', '拍照测量', '三维扫描', '空间测量', '面积测算', '户型测绘', '空间扫描', '距离测量', '3D扫描'] },
  { agent: 'kitchen',      keywords: ['厨房', '厨房设计', '橱柜', '三件套', '油烟机', '灶具', '操作台', '厨房动线', '黄金三角', '厨房水电', '厨房布局', '岛台', '中岛'] },
  { agent: 'bathroom',     keywords: ['卫生间', '浴室', '卫浴', '马桶', '淋浴', '花洒', '浴缸', '干湿分离', '三分离', '浴室柜', '台盆', '地漏', '坡度'] },
  { agent: 'mep',          keywords: ['水电点位', '暖通', '空调', '新风', '地暖', '暖气', 'MEP', '强弱电', '配电箱', '插座布置', '开关布置', '给排水', '管道', '冷热水'] },
  { agent: 'smart_home',   keywords: ['智能家居', '智能', '自动化', '传感器', '窗帘电机', '智能灯', 'Matter', 'Zigbee', '智能开关', '智能插座', '温控', '门锁'] },
  { agent: 'ai_render',    keywords: ['渲染', '效果图', '出图', '配色', '色调', '3D渲染', '2D渲染', '渲染图', '风格迁移'] },
  { agent: 'tasks',        keywords: ['任务', '待办', '交办', '分派', '安排', '谁来做', '施工任务', '任务列表', '安排任务'] },
];

export interface RouteResult {
  agent: string;
  confidence: number;
  needsClarify: boolean;
  clarifyMessage?: string;
}

/**
 * 自然语言 → Agent 路由（迁移自 agent-router.js:212-258）
 *
 * 策略：关键词评分，最高分 agent 胜出；置信度 < 0.3 或零命中 → needsClarify（回退 master）。
 * 注意：批次 2 实现 16 个高频 agent 的关键词（覆盖核心场景），完整 40 agent 路由批次 4 补全。
 */
export function route(text: string): RouteResult {
  if (!text || typeof text !== 'string') {
    return { agent: 'master', confidence: 0, needsClarify: false };
  }

  const lower = text.toLowerCase();
  const scores: Record<string, number> = {};

  for (const p of PATTERNS) {
    scores[p.agent] = 0;
    for (const kw of p.keywords) {
      if (text.includes(kw) || lower.includes(kw.toLowerCase())) {
        scores[p.agent] += 1;
      }
    }
  }

  let bestAgent = 'master';
  let bestScore = 0;
  for (const [agent, score] of Object.entries(scores)) {
    if (score > bestScore) {
      bestScore = score;
      bestAgent = agent;
    }
  }

  const confidence = bestScore === 0 ? 0 : Math.min(1, bestScore / Math.max(1, Math.ceil(text.length / 20)));

  if (confidence < 0.3 || bestScore === 0) {
    return {
      agent: 'master',
      confidence,
      needsClarify: true,
      clarifyMessage: '我理解你想了解一些信息。能更具体一些吗？比如想问预算、设计、施工进度还是其他？',
    };
  }

  return { agent: bestAgent, confidence, needsClarify: false };
}

/** 类型导出供外部使用 */
export type { AgentKey };
