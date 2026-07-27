import 'package:flutter/material.dart';

/// 任务状态
enum TaskStatus {
  pending,
  claimed,
  inProgress,
  completed,
  cancelled;

  static TaskStatus fromString(String? s) {
    switch (s) {
      case 'pending':
        return TaskStatus.pending;
      case 'claimed':
        return TaskStatus.claimed;
      case 'in_progress':
        return TaskStatus.inProgress;
      case 'completed':
        return TaskStatus.completed;
      case 'cancelled':
        return TaskStatus.cancelled;
      default:
        return TaskStatus.pending;
    }
  }

  String get value {
    switch (this) {
      case TaskStatus.pending:
        return 'pending';
      case TaskStatus.claimed:
        return 'claimed';
      case TaskStatus.inProgress:
        return 'in_progress';
      case TaskStatus.completed:
        return 'completed';
      case TaskStatus.cancelled:
        return 'cancelled';
    }
  }

  String get label {
    switch (this) {
      case TaskStatus.pending:
        return '待处理';
      case TaskStatus.claimed:
        return '已认领';
      case TaskStatus.inProgress:
        return '进行中';
      case TaskStatus.completed:
        return '已完成';
      case TaskStatus.cancelled:
        return '已取消';
    }
  }
}

/// 不可变任务模型
@immutable
class Task {
  final String id;
  final String projectId;
  final String title;
  final String? description;
  final TaskStatus status;
  final String? assigneeId;
  final String? assignedAgent;
  final String? assignedUserName;
  final int priority;
  final String? taskType;
  final String? claimRole;
  final DateTime? claimDeadline;
  final DateTime? dueDate;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  const Task({
    required this.id,
    required this.projectId,
    required this.title,
    this.description,
    this.status = TaskStatus.pending,
    this.assigneeId,
    this.assignedAgent,
    this.assignedUserName,
    this.priority = 5,
    this.taskType,
    this.claimRole,
    this.claimDeadline,
    this.dueDate,
    this.createdAt,
    this.updatedAt,
  });

  factory Task.fromJson(Map<String, dynamic> json) {
    return Task(
      id: json['id']?.toString() ?? '',
      projectId: json['project_id']?.toString() ?? '',
      title: json['title']?.toString() ?? '',
      description: json['description']?.toString(),
      status: TaskStatus.fromString(json['status']?.toString()),
      assigneeId: json['assignee_id']?.toString(),
      assignedAgent: json['assigned_agent']?.toString(),
      assignedUserName: json['assigned_user_name']?.toString(),
      priority: (json['priority'] as num?)?.toInt() ?? 5,
      taskType: json['task_type']?.toString(),
      claimRole: json['claim_role']?.toString(),
      claimDeadline: json['claim_deadline'] != null
          ? DateTime.tryParse(json['claim_deadline'].toString())
          : null,
      dueDate: json['due_date'] != null
          ? DateTime.tryParse(json['due_date'].toString())
          : null,
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
      'title': title,
      'description': description,
      'status': status.value,
      'assignee_id': assigneeId,
      'assigned_agent': assignedAgent,
      'assigned_user_name': assignedUserName,
      'priority': priority,
      'task_type': taskType,
      'claim_role': claimRole,
      'claim_deadline': claimDeadline?.toIso8601String(),
      'due_date': dueDate?.toIso8601String(),
      'created_at': createdAt?.toIso8601String(),
      'updated_at': updatedAt?.toIso8601String(),
    };
  }

  Task copyWith({
    String? id,
    String? projectId,
    String? title,
    String? description,
    TaskStatus? status,
    String? assigneeId,
    String? assignedAgent,
    String? assignedUserName,
    int? priority,
    String? taskType,
    String? claimRole,
    DateTime? claimDeadline,
    DateTime? dueDate,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return Task(
      id: id ?? this.id,
      projectId: projectId ?? this.projectId,
      title: title ?? this.title,
      description: description ?? this.description,
      status: status ?? this.status,
      assigneeId: assigneeId ?? this.assigneeId,
      assignedAgent: assignedAgent ?? this.assignedAgent,
      assignedUserName: assignedUserName ?? this.assignedUserName,
      priority: priority ?? this.priority,
      taskType: taskType ?? this.taskType,
      claimRole: claimRole ?? this.claimRole,
      claimDeadline: claimDeadline ?? this.claimDeadline,
      dueDate: dueDate ?? this.dueDate,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  /// 优先级标签
  String get priorityLabel {
    if (priority <= 2) return '紧急';
    if (priority <= 4) return '高';
    if (priority <= 6) return '中';
    return '低';
  }

  /// 是否在"进行中"列
  bool get isActive => status == TaskStatus.claimed || status == TaskStatus.inProgress;

  /// 是否在"已完成"列
  bool get isDone => status == TaskStatus.completed || status == TaskStatus.cancelled;

  /// 是否在"待处理"列
  bool get isTodo => status == TaskStatus.pending;

  /// 分配对象显示名称
  String get assigneeDisplay =>
      assignedUserName ?? assignedAgent ?? '未分配';

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is Task && id == other.id;

  @override
  int get hashCode => id.hashCode;

  @override
  String toString() => 'Task(id: $id, title: $title, status: ${status.value})';
}
