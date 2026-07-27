import 'package:flutter/material.dart';

/// 施工任务状态
enum ConstructionStatus {
  pending,
  inProgress,
  completed,
  delayed;

  static ConstructionStatus fromString(String? s) {
    switch (s) {
      case 'pending':
        return ConstructionStatus.pending;
      case 'in_progress':
        return ConstructionStatus.inProgress;
      case 'completed':
        return ConstructionStatus.completed;
      case 'delayed':
        return ConstructionStatus.delayed;
      default:
        return ConstructionStatus.pending;
    }
  }

  String get value {
    switch (this) {
      case ConstructionStatus.pending:
        return 'pending';
      case ConstructionStatus.inProgress:
        return 'in_progress';
      case ConstructionStatus.completed:
        return 'completed';
      case ConstructionStatus.delayed:
        return 'delayed';
    }
  }

  String get label {
    switch (this) {
      case ConstructionStatus.pending:
        return '待施工';
      case ConstructionStatus.inProgress:
        return '施工中';
      case ConstructionStatus.completed:
        return '已完成';
      case ConstructionStatus.delayed:
        return '已延期';
    }
  }
}

/// 不可变施工任务模型
@immutable
class Construction {
  final String id;
  final String projectId;
  final String taskName;
  final String? phase;
  final ConstructionStatus status;
  final double progress;
  final DateTime? startDate;
  final DateTime? endDate;
  final String? assignee;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  const Construction({
    required this.id,
    required this.projectId,
    required this.taskName,
    this.phase,
    this.status = ConstructionStatus.pending,
    this.progress = 0,
    this.startDate,
    this.endDate,
    this.assignee,
    this.createdAt,
    this.updatedAt,
  });

  factory Construction.fromJson(Map<String, dynamic> json) {
    return Construction(
      id: json['id']?.toString() ?? '',
      projectId: json['project_id']?.toString() ?? '',
      taskName: json['task_name']?.toString() ?? json['name']?.toString() ?? '',
      phase: json['phase']?.toString(),
      status: ConstructionStatus.fromString(json['status']?.toString()),
      progress: (json['progress'] as num?)?.toDouble() ?? 0,
      startDate: json['start_date'] != null
          ? DateTime.tryParse(json['start_date'].toString())
          : null,
      endDate: json['end_date'] != null
          ? DateTime.tryParse(json['end_date'].toString())
          : null,
      assignee: json['assignee']?.toString() ?? json['assigned_to']?.toString(),
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
      'task_name': taskName,
      'phase': phase,
      'status': status.value,
      'progress': progress,
      'start_date': startDate?.toIso8601String(),
      'end_date': endDate?.toIso8601String(),
      'assignee': assignee,
      'created_at': createdAt?.toIso8601String(),
      'updated_at': updatedAt?.toIso8601String(),
    };
  }

  Construction copyWith({
    String? id,
    String? projectId,
    String? taskName,
    String? phase,
    ConstructionStatus? status,
    double? progress,
    DateTime? startDate,
    DateTime? endDate,
    String? assignee,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return Construction(
      id: id ?? this.id,
      projectId: projectId ?? this.projectId,
      taskName: taskName ?? this.taskName,
      phase: phase ?? this.phase,
      status: status ?? this.status,
      progress: progress ?? this.progress,
      startDate: startDate ?? this.startDate,
      endDate: endDate ?? this.endDate,
      assignee: assignee ?? this.assignee,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is Construction && id == other.id;

  @override
  int get hashCode => id.hashCode;

  @override
  String toString() =>
      'Construction(id: $id, taskName: $taskName, progress: $progress)';
}
