import 'package:flutter/material.dart';

/// 预算状态
enum BudgetStatus {
  draft,
  confirmed,
  inProgress,
  completed;

  static BudgetStatus fromString(String? s) {
    switch (s) {
      case 'draft':
        return BudgetStatus.draft;
      case 'confirmed':
        return BudgetStatus.confirmed;
      case 'in_progress':
        return BudgetStatus.inProgress;
      case 'completed':
        return BudgetStatus.completed;
      default:
        return BudgetStatus.draft;
    }
  }

  String get value {
    switch (this) {
      case BudgetStatus.draft:
        return 'draft';
      case BudgetStatus.confirmed:
        return 'confirmed';
      case BudgetStatus.inProgress:
        return 'in_progress';
      case BudgetStatus.completed:
        return 'completed';
    }
  }

  String get label {
    switch (this) {
      case BudgetStatus.draft:
        return '草稿';
      case BudgetStatus.confirmed:
        return '已确认';
      case BudgetStatus.inProgress:
        return '进行中';
      case BudgetStatus.completed:
        return '已完成';
    }
  }
}

/// 预算行项目
@immutable
class BudgetLine {
  final String id;
  final String budgetId;
  final String category;
  final String? lineName;
  final double amount;
  final double? unitPrice;
  final double? quantity;
  final String? unit;
  final String? note;

  const BudgetLine({
    required this.id,
    required this.budgetId,
    required this.category,
    this.lineName,
    required this.amount,
    this.unitPrice,
    this.quantity,
    this.unit,
    this.note,
  });

  factory BudgetLine.fromJson(Map<String, dynamic> json) {
    return BudgetLine(
      id: json['id']?.toString() ?? '',
      budgetId: json['budget_id']?.toString() ?? '',
      category: json['category']?.toString() ?? '',
      lineName: json['line_name']?.toString(),
      amount: (json['amount'] as num?)?.toDouble() ?? 0,
      unitPrice: (json['unit_price'] as num?)?.toDouble(),
      quantity: (json['quantity'] as num?)?.toDouble(),
      unit: json['unit']?.toString(),
      note: json['note']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'budget_id': budgetId,
      'category': category,
      'line_name': lineName,
      'amount': amount,
      'unit_price': unitPrice,
      'quantity': quantity,
      'unit': unit,
      'note': note,
    };
  }

  BudgetLine copyWith({
    String? id,
    String? budgetId,
    String? category,
    String? lineName,
    double? amount,
    double? unitPrice,
    double? quantity,
    String? unit,
    String? note,
  }) {
    return BudgetLine(
      id: id ?? this.id,
      budgetId: budgetId ?? this.budgetId,
      category: category ?? this.category,
      lineName: lineName ?? this.lineName,
      amount: amount ?? this.amount,
      unitPrice: unitPrice ?? this.unitPrice,
      quantity: quantity ?? this.quantity,
      unit: unit ?? this.unit,
      note: note ?? this.note,
    );
  }
}

/// 不可变预算模型
@immutable
class Budget {
  final String id;
  final String projectId;
  final double totalEstimated;
  final BudgetStatus status;
  final List<BudgetLine> items;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  const Budget({
    required this.id,
    required this.projectId,
    this.totalEstimated = 0,
    this.status = BudgetStatus.draft,
    this.items = const [],
    this.createdAt,
    this.updatedAt,
  });

  factory Budget.fromJson(Map<String, dynamic> json) {
    return Budget(
      id: json['id']?.toString() ?? '',
      projectId: json['project_id']?.toString() ?? '',
      totalEstimated: (json['total_estimated'] as num?)?.toDouble() ?? 0,
      status: BudgetStatus.fromString(json['status']?.toString()),
      items: json['items'] is List
          ? (json['items'] as List)
              .map((e) =>
                  BudgetLine.fromJson(e as Map<String, dynamic>))
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
      'total_estimated': totalEstimated,
      'status': status.value,
      'items': items.map((e) => e.toJson()).toList(),
      'created_at': createdAt?.toIso8601String(),
      'updated_at': updatedAt?.toIso8601String(),
    };
  }

  Budget copyWith({
    String? id,
    String? projectId,
    double? totalEstimated,
    BudgetStatus? status,
    List<BudgetLine>? items,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return Budget(
      id: id ?? this.id,
      projectId: projectId ?? this.projectId,
      totalEstimated: totalEstimated ?? this.totalEstimated,
      status: status ?? this.status,
      items: items ?? this.items,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  /// 按类别汇总
  Map<String, double> get categoryTotals {
    final map = <String, double>{};
    for (final line in items) {
      map[line.category] = (map[line.category] ?? 0) + line.amount;
    }
    return map;
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is Budget && id == other.id;

  @override
  int get hashCode => id.hashCode;

  @override
  String toString() => 'Budget(id: $id, total: $totalEstimated, items: ${items.length})';
}
