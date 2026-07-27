import 'package:flutter/material.dart';

/// 场景类型
enum SceneType {
  wakeUp,
  leaveHome,
  goHome,
  sleep,
  movie,
  dinner,
  cleaning,
  security,
  custom;

  static SceneType fromString(String? s) {
    switch (s) {
      case 'wake_up':
        return SceneType.wakeUp;
      case 'leave_home':
        return SceneType.leaveHome;
      case 'go_home':
        return SceneType.goHome;
      case 'sleep':
        return SceneType.sleep;
      case 'movie':
        return SceneType.movie;
      case 'dinner':
        return SceneType.dinner;
      case 'cleaning':
        return SceneType.cleaning;
      case 'security':
        return SceneType.security;
      case 'custom':
        return SceneType.custom;
      default:
        return SceneType.custom;
    }
  }

  String get value {
    switch (this) {
      case SceneType.wakeUp:
        return 'wake_up';
      case SceneType.leaveHome:
        return 'leave_home';
      case SceneType.goHome:
        return 'go_home';
      case SceneType.sleep:
        return 'sleep';
      case SceneType.movie:
        return 'movie';
      case SceneType.dinner:
        return 'dinner';
      case SceneType.cleaning:
        return 'cleaning';
      case SceneType.security:
        return 'security';
      case SceneType.custom:
        return 'custom';
    }
  }

  String get label {
    switch (this) {
      case SceneType.wakeUp:
        return '起床';
      case SceneType.leaveHome:
        return '离家';
      case SceneType.goHome:
        return '回家';
      case SceneType.sleep:
        return '睡眠';
      case SceneType.movie:
        return '观影';
      case SceneType.dinner:
        return '用餐';
      case SceneType.cleaning:
        return '清洁';
      case SceneType.security:
        return '安防';
      case SceneType.custom:
        return '自定义';
    }
  }
}

/// 不可变场景自动化模型
@immutable
class SceneAutomation {
  final String id;
  final String projectId;
  final String sceneName;
  final SceneType sceneType;
  final String? trigger;
  final List<Map<String, dynamic>>? actions;
  final bool enabled;
  final String? ecosystemId;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  const SceneAutomation({
    required this.id,
    required this.projectId,
    required this.sceneName,
    this.sceneType = SceneType.custom,
    this.trigger,
    this.actions,
    this.enabled = true,
    this.ecosystemId,
    this.createdAt,
    this.updatedAt,
  });

  factory SceneAutomation.fromJson(Map<String, dynamic> json) {
    return SceneAutomation(
      id: json['id']?.toString() ?? '',
      projectId: json['project_id']?.toString() ?? '',
      sceneName: json['scene_name']?.toString() ?? json['name']?.toString() ?? '',
      sceneType: SceneType.fromString(json['scene_type']?.toString()),
      trigger: json['trigger']?.toString(),
      actions: json['actions'] is List
          ? List<Map<String, dynamic>>.from(
              (json['actions'] as List)
                  .map((e) => e is Map<String, dynamic> ? e : <String, dynamic>{}))
          : null,
      enabled: json['enabled'] is bool ? json['enabled'] as bool : true,
      ecosystemId: json['ecosystem_id']?.toString(),
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'].toString())
          : null,
      updatedAt: json['updated_at'] != null
          ? DateTime.tryParse(json['updated_at'].toString())
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'project_id': projectId,
      'scene_name': sceneName,
      'scene_type': sceneType.value,
      'trigger': trigger,
      'actions': actions,
      'enabled': enabled,
      'ecosystem_id': ecosystemId,
      'created_at': createdAt?.toIso8601String(),
      'updated_at': updatedAt?.toIso8601String(),
    };
  }

  SceneAutomation copyWith({
    String? id,
    String? projectId,
    String? sceneName,
    SceneType? sceneType,
    String? trigger,
    List<Map<String, dynamic>>? actions,
    bool? enabled,
    String? ecosystemId,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return SceneAutomation(
      id: id ?? this.id,
      projectId: projectId ?? this.projectId,
      sceneName: sceneName ?? this.sceneName,
      sceneType: sceneType ?? this.sceneType,
      trigger: trigger ?? this.trigger,
      actions: actions ?? this.actions,
      enabled: enabled ?? this.enabled,
      ecosystemId: ecosystemId ?? this.ecosystemId,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is SceneAutomation && id == other.id;

  @override
  int get hashCode => id.hashCode;

  @override
  String toString() =>
      'SceneAutomation(id: $id, sceneName: $sceneName, type: ${sceneType.value}, enabled: $enabled)';
}
