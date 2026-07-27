import 'package:flutter/material.dart';

/// 项目状态
enum ProjectStatus {
  draft,
  inProgress,
  completed;

  static ProjectStatus fromString(String? s) {
    switch (s) {
      case 'draft':
        return ProjectStatus.draft;
      case 'in_progress':
        return ProjectStatus.inProgress;
      case 'completed':
        return ProjectStatus.completed;
      default:
        return ProjectStatus.draft;
    }
  }

  String get value {
    switch (this) {
      case ProjectStatus.draft:
        return 'draft';
      case ProjectStatus.inProgress:
        return 'in_progress';
      case ProjectStatus.completed:
        return 'completed';
    }
  }

  String get label {
    switch (this) {
      case ProjectStatus.draft:
        return '草稿';
      case ProjectStatus.inProgress:
        return '施工中';
      case ProjectStatus.completed:
        return '已完成';
    }
  }
}

/// 不可变项目模型
@immutable
class Project {
  final String id;
  final String name;
  final String? address;
  final double? totalArea;
  final ProjectStatus status;
  final String? ownerId;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  const Project({
    required this.id,
    required this.name,
    this.address,
    this.totalArea,
    this.status = ProjectStatus.draft,
    this.ownerId,
    this.createdAt,
    this.updatedAt,
  });

  factory Project.fromJson(Map<String, dynamic> json) {
    return Project(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      address: json['address']?.toString(),
      totalArea: (json['total_area'] as num?)?.toDouble(),
      status: ProjectStatus.fromString(json['status']?.toString()),
      ownerId: json['owner_id']?.toString(),
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
      'name': name,
      'address': address,
      'total_area': totalArea,
      'status': status.value,
      'owner_id': ownerId,
      'created_at': createdAt?.toIso8601String(),
      'updated_at': updatedAt?.toIso8601String(),
    };
  }

  Project copyWith({
    String? id,
    String? name,
    String? address,
    double? totalArea,
    ProjectStatus? status,
    String? ownerId,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return Project(
      id: id ?? this.id,
      name: name ?? this.name,
      address: address ?? this.address,
      totalArea: totalArea ?? this.totalArea,
      status: status ?? this.status,
      ownerId: ownerId ?? this.ownerId,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is Project && id == other.id;

  @override
  int get hashCode => id.hashCode;

  @override
  String toString() => 'Project(id: $id, name: $name, status: ${status.value})';
}
