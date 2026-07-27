import 'package:flutter/material.dart';

/// 物料分类信息
@immutable
class MaterialCategory {
  final String code;
  final String name;

  const MaterialCategory({
    required this.code,
    required this.name,
  });

  factory MaterialCategory.fromJson(Map<String, dynamic> json) {
    return MaterialCategory(
      code: json['code']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'code': code,
      'name': name,
    };
  }

  @override
  String toString() => 'MaterialCategory(code: $code, name: $name)';
}

/// 不可变物料模型
@immutable
class Material {
  final String id;
  final String name;
  final String? sku;
  final String? brand;
  final MaterialCategory? category;
  final String? unit;
  final double? unitPrice;
  final String? spec;
  final String? imageUrl;
  final String? supplier;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  const Material({
    required this.id,
    required this.name,
    this.sku,
    this.brand,
    this.category,
    this.unit,
    this.unitPrice,
    this.spec,
    this.imageUrl,
    this.supplier,
    this.createdAt,
    this.updatedAt,
  });

  factory Material.fromJson(Map<String, dynamic> json) {
    return Material(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      sku: json['sku']?.toString(),
      brand: json['brand']?.toString(),
      category: json['category'] is Map<String, dynamic>
          ? MaterialCategory.fromJson(json['category'] as Map<String, dynamic>)
          : null,
      unit: json['unit']?.toString(),
      unitPrice: (json['unit_price'] as num?)?.toDouble(),
      spec: json['spec']?.toString(),
      imageUrl: json['image_url']?.toString(),
      supplier: json['supplier']?.toString(),
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
      'sku': sku,
      'brand': brand,
      'category': category?.toJson(),
      'unit': unit,
      'unit_price': unitPrice,
      'spec': spec,
      'image_url': imageUrl,
      'supplier': supplier,
      'created_at': createdAt?.toIso8601String(),
      'updated_at': updatedAt?.toIso8601String(),
    };
  }

  Material copyWith({
    String? id,
    String? name,
    String? sku,
    String? brand,
    MaterialCategory? category,
    String? unit,
    double? unitPrice,
    String? spec,
    String? imageUrl,
    String? supplier,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return Material(
      id: id ?? this.id,
      name: name ?? this.name,
      sku: sku ?? this.sku,
      brand: brand ?? this.brand,
      category: category ?? this.category,
      unit: unit ?? this.unit,
      unitPrice: unitPrice ?? this.unitPrice,
      spec: spec ?? this.spec,
      imageUrl: imageUrl ?? this.imageUrl,
      supplier: supplier ?? this.supplier,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  /// 单价显示字符串
  String get priceDisplay =>
      unitPrice != null ? '¥${unitPrice!.toInt()}' : '-';

  /// 单位显示
  String get unitDisplay => unit ?? '件';

  /// 类别名称
  String get categoryName => category?.name ?? '';

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is Material && id == other.id;

  @override
  int get hashCode => id.hashCode;

  @override
  String toString() => 'Material(id: $id, name: $name)';
}
