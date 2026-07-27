import 'package:flutter/material.dart';

/// 结算状态
enum SettlementStatus {
  draft,
  pending,
  partialPaid,
  paid,
  completed;

  static SettlementStatus fromString(String? s) {
    switch (s) {
      case 'draft':
        return SettlementStatus.draft;
      case 'pending':
        return SettlementStatus.pending;
      case 'partial_paid':
        return SettlementStatus.partialPaid;
      case 'paid':
        return SettlementStatus.paid;
      case 'completed':
        return SettlementStatus.completed;
      default:
        return SettlementStatus.draft;
    }
  }

  String get value {
    switch (this) {
      case SettlementStatus.draft:
        return 'draft';
      case SettlementStatus.pending:
        return 'pending';
      case SettlementStatus.partialPaid:
        return 'partial_paid';
      case SettlementStatus.paid:
        return 'paid';
      case SettlementStatus.completed:
        return 'completed';
    }
  }

  String get label {
    switch (this) {
      case SettlementStatus.draft:
        return '草稿';
      case SettlementStatus.pending:
        return '待支付';
      case SettlementStatus.partialPaid:
        return '部分支付';
      case SettlementStatus.paid:
        return '已支付';
      case SettlementStatus.completed:
        return '已完成';
    }
  }
}

/// 结算行项目
@immutable
class SettlementLine {
  final String id;
  final String settlementId;
  final String? milestone;
  final double amount;
  final String? note;

  const SettlementLine({
    required this.id,
    required this.settlementId,
    this.milestone,
    required this.amount,
    this.note,
  });

  factory SettlementLine.fromJson(Map<String, dynamic> json) {
    return SettlementLine(
      id: json['id']?.toString() ?? '',
      settlementId: json['settlement_id']?.toString() ?? '',
      milestone: json['milestone']?.toString(),
      amount: (json['amount'] as num?)?.toDouble() ?? 0,
      note: json['note']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'settlement_id': settlementId,
      'milestone': milestone,
      'amount': amount,
      'note': note,
    };
  }

  SettlementLine copyWith({
    String? id,
    String? settlementId,
    String? milestone,
    double? amount,
    String? note,
  }) {
    return SettlementLine(
      id: id ?? this.id,
      settlementId: settlementId ?? this.settlementId,
      milestone: milestone ?? this.milestone,
      amount: amount ?? this.amount,
      note: note ?? this.note,
    );
  }
}

/// 不可变结算模型
@immutable
class Settlement {
  final String id;
  final String projectId;
  final double totalAmount;
  final SettlementStatus status;
  final DateTime? paidAt;
  final List<SettlementLine> items;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  const Settlement({
    required this.id,
    required this.projectId,
    this.totalAmount = 0,
    this.status = SettlementStatus.draft,
    this.paidAt,
    this.items = const [],
    this.createdAt,
    this.updatedAt,
  });

  factory Settlement.fromJson(Map<String, dynamic> json) {
    return Settlement(
      id: json['id']?.toString() ?? '',
      projectId: json['project_id']?.toString() ?? '',
      totalAmount: (json['total_amount'] as num?)?.toDouble() ?? 0,
      status: SettlementStatus.fromString(json['status']?.toString()),
      paidAt: json['paid_at'] != null
          ? DateTime.tryParse(json['paid_at'].toString())
          : null,
      items: json['items'] is List
          ? (json['items'] as List)
              .map((e) =>
                  SettlementLine.fromJson(e as Map<String, dynamic>))
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
      'total_amount': totalAmount,
      'status': status.value,
      'paid_at': paidAt?.toIso8601String(),
      'items': items.map((e) => e.toJson()).toList(),
      'created_at': createdAt?.toIso8601String(),
      'updated_at': updatedAt?.toIso8601String(),
    };
  }

  Settlement copyWith({
    String? id,
    String? projectId,
    double? totalAmount,
    SettlementStatus? status,
    DateTime? paidAt,
    List<SettlementLine>? items,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return Settlement(
      id: id ?? this.id,
      projectId: projectId ?? this.projectId,
      totalAmount: totalAmount ?? this.totalAmount,
      status: status ?? this.status,
      paidAt: paidAt ?? this.paidAt,
      items: items ?? this.items,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is Settlement && id == other.id;

  @override
  int get hashCode => id.hashCode;

  @override
  String toString() =>
      'Settlement(id: $id, totalAmount: $totalAmount, status: ${status.value})';
}
