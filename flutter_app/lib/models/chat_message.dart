import 'package:flutter/material.dart';

/// 消息类型枚举，涵盖 Web 端全部 22 种消息类型
enum ChatMessageType {
  text,
  task_card,
  photo,
  approval,
  document,
  budget,
  payment,
  quote,
  bom,
  procurement_order,
  procurement_orders,
  escrow,
  logistics,
  sample,
  settlement,
  milestone_settlement,
  system,
  task_claim,
  product_card,
  orchestrator_task,
  points_card,
  narrative,
  inspection_card,
  quality_issue_card,
  progress_alert_card,
  // v1.1.22 — 补齐 12 个 Agent 专用卡片类型
  kitchen_card,
  bathroom_card,
  lighting_card,
  structural_card,
  takeoff_card,
  furniture_card,
  appliance_card,
  door_window_card,
  mep_plan_card,
  identity_card,
  voice_card,
  ifc_export_card,
  notification_card,
  // v1.1.22 — 相机/硬件传感器触发
  camera_trigger,
  ar_scan_trigger,
  voice_input_trigger,
  stats_card,
  user_card,
  user_list_card,
  product_create_card,
  product_list_card,
  quotation_card,
}

/// Agent 基本信息
class AgentInfo {
  final String key;
  final String name;
  final String emoji;
  final Color color;

  const AgentInfo({
    required this.key,
    required this.name,
    required this.emoji,
    required this.color,
  });

  static const Color masterColor = Color(0xFFC9973B);
  static const Color designColor = Color(0xFF5A7EC9);
  static const Color budgetColor = Color(0xFF4A9E6E);
  static const Color procurementColor = Color(0xFFC97A3B);
  static const Color constructionColor = Color(0xFFC94A4A);
  static const Color qualityColor = Color(0xFF4AC9A3);
  static const Color settlementColor = Color(0xFF9B6AC9);
  static const Color supportColor = Color(0xFF6A9BC9);

  static const Map<String, AgentInfo> _map = {
    'master': AgentInfo(key: 'master', name: '总控', emoji: '🏠', color: masterColor),
    'design': AgentInfo(key: 'design', name: '设计', emoji: '📐', color: designColor),
    'budget': AgentInfo(key: 'budget', name: '预算', emoji: '💰', color: budgetColor),
    'procurement': AgentInfo(key: 'procurement', name: '采购', emoji: '🛒', color: procurementColor),
    'construction': AgentInfo(key: 'construction', name: '施工', emoji: '🔨', color: constructionColor),
    'quality': AgentInfo(key: 'quality', name: '质检', emoji: '✅', color: qualityColor),
    'settlement': AgentInfo(key: 'settlement', name: '结算', emoji: '🧾', color: settlementColor),
    'support': AgentInfo(key: 'support', name: '客服', emoji: '🎧', color: supportColor),
    'admin': AgentInfo(key: 'admin', name: '管理', emoji: '⚙️', color: masterColor),
    // v1.1.22 — 补齐 12 个 Agent 信息
    'ar_measurement': AgentInfo(key: 'ar_measurement', name: 'AR测量', emoji: '📏', color: designColor),
    'floorplans': AgentInfo(key: 'floorplans', name: '户型', emoji: '📋', color: designColor),
    'structural': AgentInfo(key: 'structural', name: '土建结构', emoji: '🏗️', color: constructionColor),
    'lighting': AgentInfo(key: 'lighting', name: '灯光', emoji: '💡', color: designColor),
    'smart_home': AgentInfo(key: 'smart_home', name: '智能家居', emoji: '🤖', color: constructionColor),
    'scene_automation': AgentInfo(key: 'scene_automation', name: '场景', emoji: '🔄', color: designColor),
    'custom_furniture': AgentInfo(key: 'custom_furniture', name: '定制家具', emoji: '🪚', color: designColor),
    'tasks': AgentInfo(key: 'tasks', name: '任务', emoji: '📝', color: constructionColor),
    'change_orders': AgentInfo(key: 'change_orders', name: '变更', emoji: '📋', color: constructionColor),
    'crews': AgentInfo(key: 'crews', name: '工程队', emoji: '👷', color: constructionColor),
    'vr_panorama': AgentInfo(key: 'vr_panorama', name: 'VR全景', emoji: '🥽', color: designColor),
    'ai_render': AgentInfo(key: 'ai_render', name: 'AI渲染', emoji: '🎨', color: designColor),
    'sketch_to_3d': AgentInfo(key: 'sketch_to_3d', name: '草图转3D', emoji: '✏️', color: designColor),
    'soft_furnishing': AgentInfo(key: 'soft_furnishing', name: '软装', emoji: '🛋️', color: designColor),
    'hard_decoration': AgentInfo(key: 'hard_decoration', name: '硬装', emoji: '🧱', color: constructionColor),
    'takeoff': AgentInfo(key: 'takeoff', name: '工程量', emoji: '📊', color: constructionColor),
    'points': AgentInfo(key: 'points', name: '积分', emoji: '⭐', color: masterColor),
    'cad_import': AgentInfo(key: 'cad_import', name: 'CAD导入', emoji: '📐', color: designColor),
    'kitchen': AgentInfo(key: 'kitchen', name: '厨房', emoji: '🍳', color: designColor),
    'bathroom': AgentInfo(key: 'bathroom', name: '卫浴', emoji: '🛁', color: designColor),
    'mep': AgentInfo(key: 'mep', name: '水电暖通', emoji: '🔧', color: constructionColor),
    'appliance': AgentInfo(key: 'appliance', name: '家电', emoji: '📺', color: procurementColor),
    'furniture_catalog': AgentInfo(key: 'furniture_catalog', name: '家具', emoji: '🪑', color: procurementColor),
    'door_window_waterproof': AgentInfo(key: 'door_window_waterproof', name: '门窗防水', emoji: '🚪', color: constructionColor),
    'files': AgentInfo(key: 'files', name: '文件', emoji: '📁', color: masterColor),
    'products': AgentInfo(key: 'products', name: '产品', emoji: '🏷️', color: procurementColor),
    'identity': AgentInfo(key: 'identity', name: '身份认证', emoji: '🆔', color: masterColor),
    'voice': AgentInfo(key: 'voice', name: '语音', emoji: '🎙️', color: masterColor),
    'notifications': AgentInfo(key: 'notifications', name: '通知', emoji: '🔔', color: masterColor),
    'ifc_export': AgentInfo(key: 'ifc_export', name: 'BIM导出', emoji: '🏗️', color: designColor),
  };

  static AgentInfo getByKey(String key) {
    return _map[key] ?? _map['master']!;
  }

  static AgentInfo? tryGetByKey(String key) {
    return _map[key];
  }

  /// 获取全部 Agent（用户可见选择）
  static List<AgentInfo> get standardAgents => [
        _map['master']!,
        _map['design']!,
        _map['budget']!,
        _map['procurement']!,
        _map['construction']!,
        _map['quality']!,
        _map['settlement']!,
        _map['support']!,
        // v1.1.22: 补齐全部业务 Agent
        _map['kitchen']!,
        _map['bathroom']!,
        _map['mep']!,
        _map['appliance']!,
        _map['furniture_catalog']!,
        _map['door_window_waterproof']!,
        _map['lighting']!,
        _map['structural']!,
        _map['smart_home']!,
        _map['custom_furniture']!,
        _map['soft_furnishing']!,
        _map['hard_decoration']!,
        _map['ar_measurement']!,
        _map['vr_panorama']!,
        _map['ai_render']!,
        _map['takeoff']!,
        _map['floorplans']!,
        _map['files']!,
        _map['products']!,
        _map['identity']!,
        _map['voice']!,
        _map['notifications']!,
        _map['ifc_export']!,
        _map['cad_import']!,
        _map['admin']!,
      ];

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is AgentInfo && key == other.key;

  @override
  int get hashCode => key.hashCode;
}

/// 不可变聊天消息模型
@immutable
class ChatMessage {
  final String? id;
  final ChatMessageType type;
  final String? agent;
  final String? displayName;
  final bool isSelf;
  final String? content;
  final DateTime? timestamp;
  final Map<String, dynamic>? payload;

  /// 协作链路（已 @Agent 的动作列表）
  final List<Map<String, dynamic>>? collaboration;

  const ChatMessage({
    this.id,
    required this.type,
    this.agent,
    this.displayName,
    this.isSelf = false,
    this.content,
    this.timestamp,
    this.payload,
    this.collaboration,
  });

  /// 从 API JSON 创建消息实例
  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      id: json['id']?.toString(),
      type: _parseType(json['type']),
      agent: json['agent']?.toString(),
      displayName: json['display_name']?.toString(),
      isSelf: json['is_self'] == true,
      content: json['content']?.toString(),
      timestamp: json['timestamp'] != null
          ? DateTime.tryParse(json['timestamp'].toString())
          : null,
      payload: json['payload'] is Map<String, dynamic>
          ? json['payload'] as Map<String, dynamic>
          : null,
      collaboration: json['collaboration'] is List
          ? List<Map<String, dynamic>>.from(
              (json['collaboration'] as List)
                  .map((e) => e is Map<String, dynamic> ? e : <String, dynamic>{}))
          : null,
    );
  }

  /// 快速创建用户文本消息
  factory ChatMessage.userText({
    String? id,
    required String text,
    DateTime? timestamp,
  }) {
    return ChatMessage(
      id: id,
      type: ChatMessageType.text,
      isSelf: true,
      content: text,
      timestamp: timestamp ?? DateTime.now(),
    );
  }

  /// 快速创建 Agent 文本消息
  factory ChatMessage.agentText({
    String? id,
    required String text,
    required String agent,
    DateTime? timestamp,
  }) {
    return ChatMessage(
      id: id,
      type: ChatMessageType.text,
      agent: agent,
      content: text,
      timestamp: timestamp ?? DateTime.now(),
    );
  }

  /// 快速创建系统分割线消息
  factory ChatMessage.system({String? id, required String text}) {
    return ChatMessage(
      id: id,
      type: ChatMessageType.system,
      content: text,
      timestamp: DateTime.now(),
    );
  }

  /// 获取 Agent 信息（如果为此消息的 Agent）
  AgentInfo? get agentInfo {
    if (agent == null) return null;
    return AgentInfo.tryGetByKey(agent!);
  }

  /// Agent 分支颜色（用于气泡左侧边线等）
  Color get agentColor {
    return agentInfo?.color ?? AgentInfo.masterColor;
  }

  /// 消息是否为 Agent 发出的（非用户、非系统）
  bool get isAgent => !isSelf && type != ChatMessageType.system;

  /// 复制并修改字段
  ChatMessage copyWith({
    String? id,
    ChatMessageType? type,
    String? agent,
    String? displayName,
    bool? isSelf,
    String? content,
    DateTime? timestamp,
    Map<String, dynamic>? payload,
    List<Map<String, dynamic>>? collaboration,
  }) {
    return ChatMessage(
      id: id ?? this.id,
      type: type ?? this.type,
      agent: agent ?? this.agent,
      displayName: displayName ?? this.displayName,
      isSelf: isSelf ?? this.isSelf,
      content: content ?? this.content,
      timestamp: timestamp ?? this.timestamp,
      payload: payload ?? this.payload,
      collaboration: collaboration ?? this.collaboration,
    );
  }

  /// v1.1.26: 公共方法，从字符串解析消息类型（供 ai_chat_page 调用）
  static ChatMessageType fromString(String val) => _parseType(val);

  static ChatMessageType _parseType(dynamic val) {
    final s = val?.toString() ?? 'text';
    switch (s) {
      case 'task_card':
        return ChatMessageType.task_card;
      case 'photo':
        return ChatMessageType.photo;
      case 'approval':
        return ChatMessageType.approval;
      case 'document':
        return ChatMessageType.document;
      case 'budget':
        return ChatMessageType.budget;
      case 'payment':
        return ChatMessageType.payment;
      case 'quote':
        return ChatMessageType.quote;
      case 'bom':
        return ChatMessageType.bom;
      case 'procurement_order':
        return ChatMessageType.procurement_order;
      case 'procurement_orders':
        return ChatMessageType.procurement_orders;
      case 'escrow':
        return ChatMessageType.escrow;
      case 'logistics':
        return ChatMessageType.logistics;
      case 'sample':
        return ChatMessageType.sample;
      case 'settlement':
        return ChatMessageType.settlement;
      case 'milestone_settlement':
        return ChatMessageType.milestone_settlement;
      case 'system':
        return ChatMessageType.system;
      case 'task_claim':
        return ChatMessageType.task_claim;
      case 'product_card':
        return ChatMessageType.product_card;
      case 'orchestrator_task':
        return ChatMessageType.orchestrator_task;
      case 'points_card':
        return ChatMessageType.points_card;
      case 'narrative':
        return ChatMessageType.narrative;
      case 'inspection_card':
        return ChatMessageType.inspection_card;
      case 'quality_issue_card':
        return ChatMessageType.quality_issue_card;
      case 'progress_alert_card':
        return ChatMessageType.progress_alert_card;
      // v1.1.22: 补齐卡片类型解析
      case 'kitchen_card': return ChatMessageType.kitchen_card;
      case 'bathroom_card': return ChatMessageType.bathroom_card;
      case 'lighting_card': return ChatMessageType.lighting_card;
      case 'structural_card': return ChatMessageType.structural_card;
      case 'takeoff_card': return ChatMessageType.takeoff_card;
      case 'furniture_card': return ChatMessageType.furniture_card;
      case 'appliance_card': return ChatMessageType.appliance_card;
      case 'door_window_card': return ChatMessageType.door_window_card;
      case 'mep_plan_card': return ChatMessageType.mep_plan_card;
      case 'identity_card': return ChatMessageType.identity_card;
      case 'voice_card': return ChatMessageType.voice_card;
      case 'ifc_export_card': return ChatMessageType.ifc_export_card;
      case 'notification_card': return ChatMessageType.notification_card;
      case 'camera_trigger': return ChatMessageType.camera_trigger;
      case 'ar_scan_trigger': return ChatMessageType.ar_scan_trigger;
      case 'voice_input_trigger': return ChatMessageType.voice_input_trigger;
      case 'stats_card': return ChatMessageType.stats_card;
      case 'user_card': return ChatMessageType.user_card;
      case 'user_list_card': return ChatMessageType.user_list_card;
      case 'product_create_card': return ChatMessageType.product_create_card;
      case 'product_list_card': return ChatMessageType.product_list_card;
      case 'quotation_card': return ChatMessageType.quotation_card;
      default:
        return ChatMessageType.text;
    }
  }

  /// 消息类型对应的 API 类型字符串
  String get typeString {
    switch (type) {
      case ChatMessageType.text:
        return 'text';
      case ChatMessageType.task_card:
        return 'task_card';
      case ChatMessageType.photo:
        return 'photo';
      case ChatMessageType.approval:
        return 'approval';
      case ChatMessageType.document:
        return 'document';
      case ChatMessageType.budget:
        return 'budget';
      case ChatMessageType.payment:
        return 'payment';
      case ChatMessageType.quote:
        return 'quote';
      case ChatMessageType.bom:
        return 'bom';
      case ChatMessageType.procurement_order:
        return 'procurement_order';
      case ChatMessageType.procurement_orders:
        return 'procurement_orders';
      case ChatMessageType.escrow:
        return 'escrow';
      case ChatMessageType.logistics:
        return 'logistics';
      case ChatMessageType.sample:
        return 'sample';
      case ChatMessageType.settlement:
        return 'settlement';
      case ChatMessageType.milestone_settlement:
        return 'milestone_settlement';
      case ChatMessageType.system:
        return 'system';
      case ChatMessageType.task_claim:
        return 'task_claim';
      case ChatMessageType.product_card:
        return 'product_card';
      case ChatMessageType.orchestrator_task:
        return 'orchestrator_task';
      case ChatMessageType.points_card:
        return 'points_card';
      case ChatMessageType.narrative:
        return 'narrative';
      case ChatMessageType.inspection_card:
        return 'inspection_card';
      case ChatMessageType.quality_issue_card:
        return 'quality_issue_card';
      case ChatMessageType.progress_alert_card:
        return 'progress_alert_card';
      // v1.1.22: 补齐类型字符串
      case ChatMessageType.kitchen_card: return 'kitchen_card';
      case ChatMessageType.bathroom_card: return 'bathroom_card';
      case ChatMessageType.lighting_card: return 'lighting_card';
      case ChatMessageType.structural_card: return 'structural_card';
      case ChatMessageType.takeoff_card: return 'takeoff_card';
      case ChatMessageType.furniture_card: return 'furniture_card';
      case ChatMessageType.appliance_card: return 'appliance_card';
      case ChatMessageType.door_window_card: return 'door_window_card';
      case ChatMessageType.mep_plan_card: return 'mep_plan_card';
      case ChatMessageType.identity_card: return 'identity_card';
      case ChatMessageType.voice_card: return 'voice_card';
      case ChatMessageType.ifc_export_card: return 'ifc_export_card';
      case ChatMessageType.notification_card: return 'notification_card';
      case ChatMessageType.camera_trigger: return 'camera_trigger';
      case ChatMessageType.ar_scan_trigger: return 'ar_scan_trigger';
      case ChatMessageType.voice_input_trigger: return 'voice_input_trigger';
      case ChatMessageType.stats_card: return 'stats_card';
      case ChatMessageType.user_card: return 'user_card';
      case ChatMessageType.user_list_card: return 'user_list_card';
      case ChatMessageType.product_create_card: return 'product_create_card';
      case ChatMessageType.product_list_card: return 'product_list_card';
      case ChatMessageType.quotation_card: return 'quotation_card';
    }
  }
}
