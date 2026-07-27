import 'package:flutter/material.dart';

/// 用户角色
enum UserRole {
  homeowner,
  designer,
  constructor,
  supervisor,
  admin;

  static UserRole fromString(String? s) {
    switch (s) {
      case 'homeowner':
        return UserRole.homeowner;
      case 'designer':
        return UserRole.designer;
      case 'constructor':
        return UserRole.constructor;
      case 'supervisor':
        return UserRole.supervisor;
      case 'admin':
        return UserRole.admin;
      default:
        return UserRole.homeowner;
    }
  }

  String get value {
    switch (this) {
      case UserRole.homeowner:
        return 'homeowner';
      case UserRole.designer:
        return 'designer';
      case UserRole.constructor:
        return 'constructor';
      case UserRole.supervisor:
        return 'supervisor';
      case UserRole.admin:
        return 'admin';
    }
  }

  String get label {
    switch (this) {
      case UserRole.homeowner:
        return '业主';
      case UserRole.designer:
        return '设计师';
      case UserRole.constructor:
        return '施工方';
      case UserRole.supervisor:
        return '监理';
      case UserRole.admin:
        return '管理员';
    }
  }
}

/// 不可变用户模型
@immutable
class User {
  final String id;
  final String username;
  final String? email;
  final String? phone;
  final UserRole role;
  final String? avatar;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  const User({
    required this.id,
    required this.username,
    this.email,
    this.phone,
    this.role = UserRole.homeowner,
    this.avatar,
    this.createdAt,
    this.updatedAt,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id']?.toString() ?? '',
      username: json['username']?.toString() ?? '',
      email: json['email']?.toString(),
      phone: json['phone']?.toString(),
      role: UserRole.fromString(json['role']?.toString()),
      avatar: json['avatar']?.toString(),
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
      'username': username,
      'email': email,
      'phone': phone,
      'role': role.value,
      'avatar': avatar,
      'created_at': createdAt?.toIso8601String(),
      'updated_at': updatedAt?.toIso8601String(),
    };
  }

  User copyWith({
    String? id,
    String? username,
    String? email,
    String? phone,
    UserRole? role,
    String? avatar,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return User(
      id: id ?? this.id,
      username: username ?? this.username,
      email: email ?? this.email,
      phone: phone ?? this.phone,
      role: role ?? this.role,
      avatar: avatar ?? this.avatar,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  /// 显示名称：优先 username，否则 email
  String get displayName => username.isNotEmpty ? username : (email ?? '');

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is User && id == other.id;

  @override
  int get hashCode => id.hashCode;

  @override
  String toString() => 'User(id: $id, username: $username)';
}
