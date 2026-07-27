import 'package:flutter/material.dart';

/// 智能设备
@immutable
class SmartDevice {
  final String id;
  final String schemeId;
  final String name;
  final String? deviceType;
  final String? model;
  final String? protocol;
  final String? roomId;
  final String? roomName;
  final String? ecosystemId;
  final DateTime? createdAt;

  const SmartDevice({
    required this.id,
    required this.schemeId,
    required this.name,
    this.deviceType,
    this.model,
    this.protocol,
    this.roomId,
    this.roomName,
    this.ecosystemId,
    this.createdAt,
  });

  factory SmartDevice.fromJson(Map<String, dynamic> json) {
    return SmartDevice(
      id: json['id']?.toString() ?? '',
      schemeId: json['scheme_id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      deviceType: json['device_type']?.toString(),
      model: json['model']?.toString(),
      protocol: json['protocol']?.toString(),
      roomId: json['room_id']?.toString(),
      roomName: json['room_name']?.toString(),
      ecosystemId: json['ecosystem_id']?.toString(),
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'].toString())
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'scheme_id': schemeId,
      'name': name,
      'device_type': deviceType,
      'model': model,
      'protocol': protocol,
      'room_id': roomId,
      'room_name': roomName,
      'ecosystem_id': ecosystemId,
      'created_at': createdAt?.toIso8601String(),
    };
  }

  SmartDevice copyWith({
    String? id,
    String? schemeId,
    String? name,
    String? deviceType,
    String? model,
    String? protocol,
    String? roomId,
    String? roomName,
    String? ecosystemId,
    DateTime? createdAt,
  }) {
    return SmartDevice(
      id: id ?? this.id,
      schemeId: schemeId ?? this.schemeId,
      name: name ?? this.name,
      deviceType: deviceType ?? this.deviceType,
      model: model ?? this.model,
      protocol: protocol ?? this.protocol,
      roomId: roomId ?? this.roomId,
      roomName: roomName ?? this.roomName,
      ecosystemId: ecosystemId ?? this.ecosystemId,
      createdAt: createdAt ?? this.createdAt,
    );
  }

  @override
  String toString() => 'SmartDevice(id: $id, name: $name, type: $deviceType)';
}

/// 不可变智能家居方案模型
@immutable
class SmartHome {
  final String id;
  final String projectId;
  final String schemeName;
  final List<SmartDevice> devices;
  final String? roomId;
  final String? ecosystemId;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  const SmartHome({
    required this.id,
    required this.projectId,
    required this.schemeName,
    this.devices = const [],
    this.roomId,
    this.ecosystemId,
    this.createdAt,
    this.updatedAt,
  });

  factory SmartHome.fromJson(Map<String, dynamic> json) {
    return SmartHome(
      id: json['id']?.toString() ?? '',
      projectId: json['project_id']?.toString() ?? '',
      schemeName: json['scheme_name']?.toString() ?? json['name']?.toString() ?? '',
      devices: json['devices'] is List
          ? (json['devices'] as List)
              .map((e) =>
                  SmartDevice.fromJson(e as Map<String, dynamic>))
              .toList()
          : [],
      roomId: json['room_id']?.toString(),
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
      'scheme_name': schemeName,
      'devices': devices.map((e) => e.toJson()).toList(),
      'room_id': roomId,
      'ecosystem_id': ecosystemId,
      'created_at': createdAt?.toIso8601String(),
      'updated_at': updatedAt?.toIso8601String(),
    };
  }

  SmartHome copyWith({
    String? id,
    String? projectId,
    String? schemeName,
    List<SmartDevice>? devices,
    String? roomId,
    String? ecosystemId,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return SmartHome(
      id: id ?? this.id,
      projectId: projectId ?? this.projectId,
      schemeName: schemeName ?? this.schemeName,
      devices: devices ?? this.devices,
      roomId: roomId ?? this.roomId,
      ecosystemId: ecosystemId ?? this.ecosystemId,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is SmartHome && id == other.id;

  @override
  int get hashCode => id.hashCode;

  @override
  String toString() =>
      'SmartHome(id: $id, schemeName: $schemeName, devices: ${devices.length})';
}
