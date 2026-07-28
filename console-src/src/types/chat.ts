/**
 * 聊天消息类型定义 — 对齐 Flutter ChatMessage + Web message-renderers.js
 *
 * cardType 联合类型覆盖 message-renderers.js 的卡片类型。
 * 批次 2 实现 text/settlement/quote/camera-scan 4 类，其余卡片 MessageCard 分发时返回 fallback。
 */

export type AgentKey =
  | 'master'
  | 'design'
  | 'budget'
  | 'procurement'
  | 'construction'
  | 'quality'
  | 'settlement'
  | 'support'
  | 'admin'
  | 'ar_measurement'
  | 'floorplans'
  | 'structural'
  | 'lighting'
  | 'smart_home'
  | 'scene_automation'
  | 'custom_furniture'
  | 'tasks'
  | 'change_orders'
  | 'crews'
  | 'vr_panorama'
  | 'ai_render'
  | 'sketch_to_3d'
  | 'soft_furnishing'
  | 'hard_decoration'
  | 'takeoff'
  | 'points'
  | 'cad_import'
  | 'kitchen'
  | 'bathroom'
  | 'mep'
  | 'appliance'
  | 'furniture_catalog'
  | 'door_window_waterproof'
  | 'files'
  | 'products'
  | 'identity'
  | 'voice'
  | 'notifications'
  | 'ifc_export';

/** 卡片类型联合（对齐 message-renderers.js 的 render 方法分发） */
export type CardType =
  | 'text'
  | 'task_card'
  | 'photo'
  | 'approval'
  | 'document'
  | 'budget'
  | 'payment'
  | 'quote'
  | 'bom'
  | 'settlement'
  | 'camera-scan'
  | 'ar_scan_trigger'
  | string; // 允许后端扩展未知类型，MessageCard 返回 fallback

export interface ChatMessage {
  id: string;
  role: 'user' | 'agent';
  /** agent key，user 消息为 undefined */
  agent?: AgentKey | string;
  /** 文本内容（卡片消息为标题/摘要） */
  content: string;
  /** ISO 时间戳 */
  timestamp: string;
  /** 卡片类型，默认 'text' */
  cardType?: CardType;
  /** 卡片 payload（按 cardType 结构不同） */
  payload?: Record<string, unknown>;
  /** 展示名（覆盖默认 agent 名） */
  displayName?: string;
  /** 是否连续消息（与前一条同 sender，隐藏 meta） */
  isConsecutive?: boolean;
  /** Agent 思考步骤（v1.1.29） */
  thinkingSteps?: string[];
  /** Agent 置信度（0-1） */
  confidence?: number;
  /** A2UI 卡片（v1.2.3，批次 4 接入） */
  a2uiCards?: unknown[];
}

/** 构造用户文本消息 */
export function userTextMessage(text: string): ChatMessage {
  return {
    id: `u-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    role: 'user',
    content: text,
    timestamp: new Date().toISOString(),
    cardType: 'text',
  };
}

/** 构造 Agent 文本消息（可空内容，作为流式占位） */
export function agentTextMessage(text: string, agent: string): ChatMessage {
  return {
    id: `a-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    role: 'agent',
    agent,
    content: text,
    timestamp: new Date().toISOString(),
    cardType: 'text',
  };
}

/** SSE 事件类型（对齐 Flutter SseEventType） */
export type SseEventType = 'meta' | 'token' | 'thinking_step' | 'done' | 'error';

export interface SseEvent {
  type: SseEventType;
  content?: string;
  agentType?: string;
  sessionId?: string;
  messageType?: string;
  cardPayload?: Record<string, unknown>;
  a2uiCards?: unknown[];
}
