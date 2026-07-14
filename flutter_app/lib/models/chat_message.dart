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
  };

  static AgentInfo getByKey(String key) {
    return _map[key] ?? _map['master']!;
  }

  static AgentInfo? tryGetByKey(String key) {
    return _map[key];
  }

  /// 获取 5 个标准 Agent（用户可见选择）
  static List<AgentInfo> get standardAgents => [
        _map['master']!,
        _map['design']!,
        _map['budget']!,
        _map['procurement']!,
        _map['construction']!,
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
    }
  }
}
