import 'package:flutter/material.dart';

/// 采购状态
enum ProcurementStatus {
  comparing,
  confirmed,
  paid,
  shipping,
  delivered,
  completed,
  cancelled;

  static ProcurementStatus fromString(String? s) {
    switch (s) {
      case 'comparing':
        return ProcurementStatus.comparing;
      case 'confirmed':
        return ProcurementStatus.confirmed;
      case 'paid':
        return ProcurementStatus.paid;
      case 'shipping':
        return ProcurementStatus.shipping;
      case 'delivered':
        return ProcurementStatus.delivered;
      case 'completed':
        return ProcurementStatus.completed;
      case 'cancelled':
        return ProcurementStatus.cancelled;
      default:
        return ProcurementStatus.comparing;
    }
  }

  String get value {
    switch (this) {
      case ProcurementStatus.comparing:
        return 'comparing';
      case ProcurementStatus.confirmed:
        return 'confirmed';
      case ProcurementStatus.paid:
        return 'paid';
      case ProcurementStatus.shipping:
        return 'shipping';
      case ProcurementStatus.delivered:
        return 'delivered';
      case ProcurementStatus.completed:
        return 'completed';
      case ProcurementStatus.cancelled:
        return 'cancelled';
    }
  }

  String get label {
    switch (this) {
      case ProcurementStatus.comparing:
        return '比价中';
      case ProcurementStatus.confirmed:
        return '已确认';
      case ProcurementStatus.paid:
        return '已付款';
      case ProcurementStatus.shipping:
        return '运输中';
      case ProcurementStatus.delivered:
        return '已送达';
      case ProcurementStatus.completed:
        return '已完成';
      case ProcurementStatus.cancelled:
        return '已取消';
    }
  }
}

/// 采购行项目
@immutable
class ProcurementLine {
  final String id;
  final String procurementId;
  final String materialName;
  final double? quantity;
  final double? unitPrice;
  final double? amount;
  final String? supplier;
  final String? status;
  final String? note;

  const ProcurementLine({
    required this.id,
    required this.procurementId,
    required this.materialName,
    this.quantity,
    this.unitPrice,
    this.amount,
    this.supplier,
    this.status,
    this.note,
  });

  factory ProcurementLine.fromJson(Map<String, dynamic> json) {
    return ProcurementLine(
      id: json['id']?.toString() ?? '',
      procurementId: json['procurement_id']?.toString() ?? '',
      materialName: json['material_name']?.toString() ?? '',
      quantity: (json['quantity'] as num?)?.toDouble(),
      unitPrice: (json['unit_price'] as num?)?.toDouble(),
      amount: (json['amount'] as num?)?.toDouble(),
      supplier: json['supplier']?.toString(),
      status: json['status']?.toString(),
      note: json['note']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'procurement_id': procurementId,
      'material_name': materialName,
      'quantity': quantity,
      'unit_price': unitPrice,
      'amount': amount,
      'supplier': supplier,
      'status': status,
      'note': note,
    };
  }

  ProcurementLine copyWith({
    String? id,
    String? procurementId,
    String? materialName,
    double? quantity,
    double? unitPrice,
    double? amount,
    String? supplier,
    String? status,
    String? note,
  }) {
    return ProcurementLine(
      id: id ?? this.id,
      procurementId: procurementId ?? this.procurementId,
      materialName: materialName ?? this.materialName,
      quantity: quantity ?? this.quantity,
      unitPrice: unitPrice ?? this.unitPrice,
      amount: amount ?? this.amount,
      supplier: supplier ?? this.supplier,
      status: status ?? this.status,
      note: note ?? this.note,
    );
  }
}

/// 不可变采购模型
@immutable
class Procurement {
  final String id;
  final String projectId;
  final String? orderNumber;
  final String? supplier;
  final double totalAmount;
  final ProcurementStatus status;
  final List<ProcurementLine> items;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  const Procurement({
    required this.id,
    required this.projectId,
    this.orderNumber,
    this.supplier,
    this.totalAmount = 0,
    this.status = ProcurementStatus.comparing,
    this.items = const [],
    this.createdAt,
    this.updatedAt,
  });

  factory Procurement.fromJson(Map<String, dynamic> json) {
    return Procurement(
      id: json['id']?.toString() ?? '',
      projectId: json['project_id']?.toString() ?? '',
      orderNumber: json['order_number']?.toString(),
      supplier: json['supplier']?.toString(),
      totalAmount: (json['total_amount'] as num?)?.toDouble() ?? 0,
      status: ProcurementStatus.fromString(json['status']?.toString()),
      items: json['items'] is List
          ? (json['items'] as List)
              .map((e) =>
                  ProcurementLine.fromJson(e as Map<String, dynamic>))
              .toList()
          : [],
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
      'order_number': orderNumber,
      'supplier': supplier,
      'total_amount': totalAmount,
      'status': status.value,
      'items': items.map((e) => e.toJson()).toList(),
      'created_at': createdAt?.toIso8601String(),
      'updated_at': updatedAt?.toIso8601String(),
    };
  }

  Procurement copyWith({
    String? id,
    String? projectId,
    String? orderNumber,
    String? supplier,
    double? totalAmount,
    ProcurementStatus? status,
    List<ProcurementLine>? items,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return Procurement(
      id: id ?? this.id,
      projectId: projectId ?? this.projectId,
      orderNumber: orderNumber ?? this.orderNumber,
      supplier: supplier ?? this.supplier,
      totalAmount: totalAmount ?? this.totalAmount,
      status: status ?? this.status,
      items: items ?? this.items,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is Procurement && id == other.id;

  @override
  int get hashCode => id.hashCode;

  @override
  String toString() =>
      'Procurement(id: $id, orderNumber: $orderNumber, totalAmount: $totalAmount)';
}
