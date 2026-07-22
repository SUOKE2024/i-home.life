/// A2UI 卡片渲染器 — 将 A2UI JSON 转换为 Flutter Widget
///
/// 路由规则：根据 card["type"] 分发到对应的渲染方法。
///
/// 支持的卡片类型：
/// - design_plan: 设计方案卡片（房间网格、面积统计、3D 预览按钮）
/// - budget_breakdown: 预算明细卡片（费用表格、税费、质保）
/// - construction_progress: 施工进度卡片（进度条、阶段列表、班组信息）
/// - procurement_order: 采购订单卡片（物料列表、供应商、交货日期）
/// - qa_report: 质检报告卡片（检查点、通过/不通过、整改期限）
/// - settlement_summary: 结算汇总卡片（总额、已付、余额、付款历史）
/// - material_card: 材料详情卡片（规格、环保等级、价格、供应商）
/// - alert_card: 系统告警卡片（严重级别、彩色横幅、操作按钮）
library;

import 'package:flutter/material.dart';
import '../theme/suoke_theme.dart';

/// A2UI 卡片渲染器 — 将 A2UI JSON 转换为 Flutter Widget
///
/// 使用方法:
/// ```dart
/// A2UIRenderer(
///   card: {
///     "type": "design_plan",
///     "data": {...},
///   },
///   onAction: (action, payload) { ... },
/// )
/// ```
class A2UIRenderer extends StatelessWidget {
  /// A2UI JSON 卡片数据（Map 格式）
  final Map<String, dynamic> card;

  /// 操作回调：当用户点击卡片上的操作按钮时触发
  /// [action] 为按钮的 action 标识，[payload] 为附加数据
  final void Function(String action, Map<String, dynamic> payload)? onAction;

  const A2UIRenderer({
    super.key,
    required this.card,
    this.onAction,
  });

  @override
  Widget build(BuildContext context) {
    final type = card['type'] as String? ?? 'unknown';
    final data = card['data'] as Map<String, dynamic>? ?? const {};

    return switch (type) {
      'design_plan' => _DesignPlanCard(data: data, onAction: onAction),
      'budget_breakdown' => _BudgetCard(data: data, onAction: onAction),
      'construction_progress' => _ProgressCard(data: data, onAction: onAction),
      'procurement_order' => _ProcurementCard(data: data, onAction: onAction),
      'qa_report' => _QAReportCard(data: data, onAction: onAction),
      'settlement_summary' => _SettlementCard(data: data, onAction: onAction),
      'material_card' => _MaterialCard(data: data, onAction: onAction),
      'alert_card' => _AlertCard(data: data, onAction: onAction),
      _ => _UnknownCard(type: type, data: data),
    };
  }
}

// ═══════════════════════════════════════════
// 基础 Helper
// ═══════════════════════════════════════════

extension _CardHelpers on StatelessWidget {
  /// 安全的数值提取
  static double _safeDouble(dynamic v) {
    if (v is double) return v;
    if (v is int) return v.toDouble();
    if (v is num) return v.toDouble();
    return 0.0;
  }

  static int _safeInt(dynamic v) {
    if (v is int) return v;
    if (v is double) return v.toInt();
    if (v is num) return v.toInt();
    return 0;
  }

  static String _safeStr(dynamic v) {
    if (v is String) return v;
    if (v != null) return v.toString();
    return '';
  }

  /// 通用卡片容器
  static Widget _cardWrapper({
    required String title,
    String? subtitle,
    Color? accentColor,
    required List<Widget> children,
    required List<Map<String, dynamic>> actions,
    required void Function(String action, Map<String, dynamic> payload)? onAction,
    Map<String, dynamic> actionPayload = const {},
  }) {
    final hasActions = actions.isNotEmpty;

    return Container(
      margin: const EdgeInsets.symmetric(
        horizontal: SuokeDesignTokens.spacingLg,
        vertical: SuokeDesignTokens.spacingSm,
      ),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.cardBg,
        borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusLg),
        border: Border.all(
          color: accentColor?.withValues(alpha: 0.3) ?? SuokeDesignTokens.border,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          // 卡片头部
          Padding(
            padding: const EdgeInsets.fromLTRB(
              SuokeDesignTokens.spacingLg,
              SuokeDesignTokens.spacingLg,
              SuokeDesignTokens.spacingLg,
              SuokeDesignTokens.spacingSm,
            ),
            child: Row(
              children: [
                if (accentColor != null) ...[
                  Container(
                    width: 3,
                    height: 20,
                    decoration: BoxDecoration(
                      color: accentColor,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                  const SizedBox(width: SuokeDesignTokens.spacingSm),
                ],
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        title,
                        style: const TextStyle(
                          color: SuokeDesignTokens.textPrimary,
                          fontSize: SuokeDesignTokens.fontSizeLg,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      if (subtitle != null)
                        Padding(
                          padding: const EdgeInsets.only(top: 2),
                          child: Text(
                            subtitle,
                            style: const TextStyle(
                              color: SuokeDesignTokens.textMuted,
                              fontSize: SuokeDesignTokens.fontSizeXs,
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          // 分割线
          const Divider(
            color: SuokeDesignTokens.border,
            height: 1,
          ),
          // 卡片内容
          Padding(
            padding: const EdgeInsets.all(SuokeDesignTokens.spacingLg),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: children,
            ),
          ),
          // 操作按钮
          if (hasActions) ...[
            const Divider(color: SuokeDesignTokens.border, height: 1),
            Padding(
              padding: const EdgeInsets.all(SuokeDesignTokens.spacingMd),
              child: Wrap(
                spacing: SuokeDesignTokens.spacingSm,
                runSpacing: SuokeDesignTokens.spacingSm,
                children: actions.map((a) {
                  final label = _safeStr(a['label']);
                  final action = _safeStr(a['action']);
                  final variant = _safeStr(a['variant']);

                  if (variant == 'danger') {
                    return OutlinedButton(
                      onPressed: () => onAction?.call(action, actionPayload),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: SuokeDesignTokens.danger,
                        side: const BorderSide(color: SuokeDesignTokens.danger),
                        padding: const EdgeInsets.symmetric(
                          horizontal: SuokeDesignTokens.spacingLg,
                          vertical: 10,
                        ),
                        minimumSize: const Size(
                          SuokeDesignTokens.touchTargetMin,
                          SuokeDesignTokens.touchTargetMin,
                        ),
                      ),
                      child: Text(label),
                    );
                  }
                  return ElevatedButton(
                    onPressed: () => onAction?.call(action, actionPayload),
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(
                        horizontal: SuokeDesignTokens.spacingLg,
                        vertical: 10,
                      ),
                      minimumSize: const Size(
                        SuokeDesignTokens.touchTargetMin,
                        SuokeDesignTokens.touchTargetMin,
                      ),
                    ),
                    child: Text(label),
                  );
                }).toList(),
              ),
            ),
          ],
        ],
      ),
    );
  }

  /// 键值对行
  static Widget _infoRow(String label, String value, {Color? valueColor, bool boldValue = false}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: SuokeDesignTokens.spacingSm),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 64,
            child: Text(
              label,
              style: const TextStyle(
                color: SuokeDesignTokens.textMuted,
                fontSize: SuokeDesignTokens.fontSizeSm,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                color: valueColor ?? SuokeDesignTokens.textPrimary,
                fontSize: SuokeDesignTokens.fontSizeSm,
                fontWeight: boldValue ? FontWeight.w600 : FontWeight.w400,
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// 金额显示
  static Widget _amountText(double amount) {
    final isNegative = amount < 0;
    return Text(
      '¥${amount.toStringAsFixed(2)}',
      style: TextStyle(
        color: isNegative ? SuokeDesignTokens.danger : SuokeDesignTokens.warning,
        fontSize: SuokeDesignTokens.fontSizeLg,
        fontWeight: FontWeight.w700,
      ),
    );
  }

  /// 状态标签
  static Widget _statusBadge(String status, {double? progress}) {
    Color bgColor;
    Color fgColor;
    String label;

    if (progress != null) {
      // 进度状态
      if (progress >= 1.0) {
        bgColor = SuokeDesignTokens.success.withValues(alpha: 0.15);
        fgColor = SuokeDesignTokens.success;
        label = '已完成';
      } else if (progress > 0) {
        bgColor = SuokeDesignTokens.warning.withValues(alpha: 0.15);
        fgColor = SuokeDesignTokens.warning;
        label = '进行中';
      } else {
        bgColor = SuokeDesignTokens.textMuted.withValues(alpha: 0.15);
        fgColor = SuokeDesignTokens.textMuted;
        label = '待开始';
      }
    } else {
      // 文本状态
      switch (status.toLowerCase()) {
        case 'paid':
        case 'completed':
        case 'pass':
        case 'delivered':
        case 'in_stock':
          bgColor = SuokeDesignTokens.success.withValues(alpha: 0.15);
          fgColor = SuokeDesignTokens.success;
          break;
        case 'pending':
        case 'shipped':
        case 'ordered':
        case 'in_progress':
          bgColor = SuokeDesignTokens.warning.withValues(alpha: 0.15);
          fgColor = SuokeDesignTokens.warning;
          break;
        case 'overdue':
        case 'fail':
        case 'cancelled':
        case 'disputed':
        case 'out_of_stock':
          bgColor = SuokeDesignTokens.danger.withValues(alpha: 0.15);
          fgColor = SuokeDesignTokens.danger;
          break;
        default:
          bgColor = SuokeDesignTokens.textMuted.withValues(alpha: 0.15);
          fgColor = SuokeDesignTokens.textMuted;
      }
      label = status;
    }

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: SuokeDesignTokens.spacingSm,
        vertical: 2,
      ),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusSm),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: fgColor,
          fontSize: SuokeDesignTokens.fontSizeXs,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 设计平面图卡片 (DesignPlanCard)
// ═══════════════════════════════════════════

class _DesignPlanCard extends StatelessWidget {
  final Map<String, dynamic> data;
  final void Function(String action, Map<String, dynamic> payload)? onAction;

  const _DesignPlanCard({required this.data, this.onAction});

  @override
  Widget build(BuildContext context) {
    final projectName = _CardHelpers._safeStr(data['project_name']);
    final floorLayout = _CardHelpers._safeStr(data['floor_layout']);
    final totalArea = _CardHelpers._safeDouble(data['total_area']);
    final style = _CardHelpers._safeStr(data['style']);
    final preview3dUrl = _CardHelpers._safeStr(data['preview_3d_url']);
    final rooms = (data['rooms'] as List?)?.cast<Map<String, dynamic>>() ?? [];
    final estimatedTimeline = _CardHelpers._safeStr(data['estimated_timeline']);

    final actions = <Map<String, dynamic>>[];
    if (preview3dUrl.isNotEmpty) {
      actions.add({
        'label': '查看3D',
        'action': 'view_3d',
        'variant': 'primary',
      });
    }

    return _CardHelpers._cardWrapper(
      title: projectName.isNotEmpty ? projectName : '设计方案',
      subtitle: '$floorLayout · ${totalArea.toStringAsFixed(1)}㎡',
      accentColor: SuokeDesignTokens.agentDesign,
      onAction: onAction,
      actions: actions,
      actionPayload: {'preview_3d_url': preview3dUrl},
      children: [
        // 风格和工期
        if (style.isNotEmpty || estimatedTimeline.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: SuokeDesignTokens.spacingMd),
            child: Row(
              children: [
                if (style.isNotEmpty) ...[
                  _tagChip(style),
                  const SizedBox(width: SuokeDesignTokens.spacingSm),
                ],
                if (estimatedTimeline.isNotEmpty)
                  _tagChip('工期 $estimatedTimeline'),
              ],
            ),
          ),
        // 房间网格
        if (rooms.isNotEmpty) ...[
          const Text(
            '房间分布',
            style: TextStyle(
              color: SuokeDesignTokens.textSecondary,
              fontSize: SuokeDesignTokens.fontSizeSm,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: SuokeDesignTokens.spacingSm),
          Wrap(
            spacing: SuokeDesignTokens.spacingSm,
            runSpacing: SuokeDesignTokens.spacingSm,
            children: rooms.map((r) {
              final name = _CardHelpers._safeStr(r['name']);
              final area = _CardHelpers._safeDouble(r['area']);
              final orientation = _CardHelpers._safeStr(r['orientation']);
              return _roomTile(name, area, orientation);
            }).toList(),
          ),
        ],
      ],
    );
  }

  Widget _tagChip(String label) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: SuokeDesignTokens.spacingSm,
        vertical: 2,
      ),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.agentDesign.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusInput),
        border: Border.all(
          color: SuokeDesignTokens.agentDesign.withValues(alpha: 0.3),
        ),
      ),
      child: Text(
        label,
        style: const TextStyle(
          color: SuokeDesignTokens.agentDesign,
          fontSize: SuokeDesignTokens.fontSizeXs,
        ),
      ),
    );
  }

  Widget _roomTile(String name, double area, String orientation) {
    return Container(
      width: 96,
      padding: const EdgeInsets.all(SuokeDesignTokens.spacingSm),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.surface2,
        borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusSm),
        border: Border.all(color: SuokeDesignTokens.border),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            name,
            style: const TextStyle(
              color: SuokeDesignTokens.textPrimary,
              fontSize: SuokeDesignTokens.fontSizeSm,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            '${area.toStringAsFixed(1)}㎡',
            style: const TextStyle(
              color: SuokeDesignTokens.accent,
              fontSize: SuokeDesignTokens.fontSizeXs,
              fontWeight: FontWeight.w700,
            ),
          ),
          if (orientation.isNotEmpty)
            Text(
              orientation,
              style: const TextStyle(
                color: SuokeDesignTokens.textMuted,
                fontSize: SuokeDesignTokens.fontSizeXs,
              ),
            ),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 预算明细卡片 (BudgetCard)
// ═══════════════════════════════════════════

class _BudgetCard extends StatelessWidget {
  final Map<String, dynamic> data;
  final void Function(String action, Map<String, dynamic> payload)? onAction;

  const _BudgetCard({required this.data, this.onAction});

  @override
  Widget build(BuildContext context) {
    final projectName = _CardHelpers._safeStr(data['project_name']);
    final total = _CardHelpers._safeDouble(data['total']);
    final subtotal = _CardHelpers._safeDouble(data['subtotal']);
    final taxAmount = _CardHelpers._safeDouble(data['tax_amount']);
    final items = (data['items'] as List?)?.cast<Map<String, dynamic>>() ?? [];
    final warrantyMonths = _CardHelpers._safeInt(data['warranty_months']);
    final warrantyScope = _CardHelpers._safeStr(data['warranty_scope']);
    final paymentStages = (data['payment_stages'] as List?)?.cast<Map<String, dynamic>>() ?? [];

    return _CardHelpers._cardWrapper(
      title: projectName.isNotEmpty ? projectName : '预算明细',
      subtitle: '合计 ¥${total.toStringAsFixed(2)}',
      accentColor: SuokeDesignTokens.agentBudget,
      onAction: onAction,
      actions: [
        {'label': '查看详情', 'action': 'view_budget_detail', 'variant': 'primary'},
      ],
      actionPayload: data,
      children: [
        // 费用汇总
        _budgetSummaryRow('小计', subtotal),
        if (taxAmount > 0)
          Padding(
            padding: const EdgeInsets.only(bottom: SuokeDesignTokens.spacingSm),
            child: _budgetSummaryRow(
              '税费（${((taxAmount / subtotal * 100).toStringAsFixed(1))}%）',
              taxAmount,
            ),
          ),
        const Divider(color: SuokeDesignTokens.border, height: 16),
        _budgetSummaryRow('合计', total, isTotal: true),

        const SizedBox(height: SuokeDesignTokens.spacingMd),

        // 预算明细表格
        if (items.isNotEmpty) ...[
          const Text(
            '费用明细',
            style: TextStyle(
              color: SuokeDesignTokens.textSecondary,
              fontSize: SuokeDesignTokens.fontSizeSm,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: SuokeDesignTokens.spacingSm),
          ...items.take(5).map((item) => _budgetItemRow(item)),
          if (items.length > 5)
            Text(
              '… 共 ${items.length} 项',
              style: const TextStyle(
                color: SuokeDesignTokens.textMuted,
                fontSize: SuokeDesignTokens.fontSizeXs,
              ),
            ),
        ],

        // 质保信息
        if (warrantyMonths > 0) ...[
          const SizedBox(height: SuokeDesignTokens.spacingMd),
          Container(
            padding: const EdgeInsets.all(SuokeDesignTokens.spacingMd),
            decoration: BoxDecoration(
              color: SuokeDesignTokens.success.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusSm),
              border: Border.all(
                color: SuokeDesignTokens.success.withValues(alpha: 0.2),
              ),
            ),
            child: Row(
              children: [
                const Icon(
                  Icons.verified_user_outlined,
                  color: SuokeDesignTokens.success,
                  size: 18,
                ),
                const SizedBox(width: SuokeDesignTokens.spacingSm),
                Expanded(
                  child: Text(
                    '质保 $warrantyMonths 个月${warrantyScope.isNotEmpty ? " · $warrantyScope" : ""}',
                    style: const TextStyle(
                      color: SuokeDesignTokens.success,
                      fontSize: SuokeDesignTokens.fontSizeSm,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],

        // 付款阶段
        if (paymentStages.isNotEmpty) ...[
          const SizedBox(height: SuokeDesignTokens.spacingMd),
          const Text(
            '付款计划',
            style: TextStyle(
              color: SuokeDesignTokens.textSecondary,
              fontSize: SuokeDesignTokens.fontSizeSm,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: SuokeDesignTokens.spacingSm),
          ...paymentStages.map((stage) => _paymentStageRow(stage)),
        ],
      ],
    );
  }

  Widget _budgetSummaryRow(String label, double amount, {bool isTotal = false}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 2),
      child: Row(
        children: [
          Text(
            label,
            style: TextStyle(
              color: isTotal ? SuokeDesignTokens.textPrimary : SuokeDesignTokens.textSecondary,
              fontSize: isTotal ? SuokeDesignTokens.fontSizeMd : SuokeDesignTokens.fontSizeSm,
              fontWeight: isTotal ? FontWeight.w700 : FontWeight.w400,
            ),
          ),
          const Spacer(),
          Text(
            '¥${amount.toStringAsFixed(2)}',
            style: TextStyle(
              color: isTotal ? SuokeDesignTokens.warning : SuokeDesignTokens.textPrimary,
              fontSize: isTotal ? SuokeDesignTokens.fontSizeLg : SuokeDesignTokens.fontSizeSm,
              fontWeight: isTotal ? FontWeight.w700 : FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  Widget _budgetItemRow(Map<String, dynamic> item) {
    final category = _CardHelpers._safeStr(item['category']);
    final name = _CardHelpers._safeStr(item['name']);
    final quantity = _CardHelpers._safeDouble(item['quantity']);
    final unit = _CardHelpers._safeStr(item['unit']);
    final amount = _CardHelpers._safeDouble(item['amount']);

    return Padding(
      padding: const EdgeInsets.only(bottom: SuokeDesignTokens.spacingSm),
      child: Row(
        children: [
          if (category.isNotEmpty) ...[
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
              decoration: BoxDecoration(
                color: SuokeDesignTokens.border,
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                category,
                style: const TextStyle(
                  color: SuokeDesignTokens.textSecondary,
                  fontSize: SuokeDesignTokens.fontSizeXs,
                ),
              ),
            ),
            const SizedBox(width: SuokeDesignTokens.spacingSm),
          ],
          Expanded(
            child: Text(
              name,
              style: const TextStyle(
                color: SuokeDesignTokens.textPrimary,
                fontSize: SuokeDesignTokens.fontSizeSm,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          if (quantity > 0)
            Text(
              ' ${quantity.toStringAsFixed(0)}$unit',
              style: const TextStyle(
                color: SuokeDesignTokens.textMuted,
                fontSize: SuokeDesignTokens.fontSizeXs,
              ),
            ),
          const SizedBox(width: SuokeDesignTokens.spacingMd),
          Text(
            '¥${amount.toStringAsFixed(2)}',
            style: const TextStyle(
              color: SuokeDesignTokens.textPrimary,
              fontSize: SuokeDesignTokens.fontSizeSm,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  Widget _paymentStageRow(Map<String, dynamic> stage) {
    final stageName = _CardHelpers._safeStr(stage['stage']);
    final ratio = _CardHelpers._safeDouble(stage['ratio']);
    final amount = _CardHelpers._safeDouble(stage['amount']);
    final status = _CardHelpers._safeStr(stage['status']);

    return Padding(
      padding: const EdgeInsets.only(bottom: SuokeDesignTokens.spacingSm),
      child: Row(
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: status == 'paid' ? SuokeDesignTokens.success : SuokeDesignTokens.border,
            ),
          ),
          const SizedBox(width: SuokeDesignTokens.spacingSm),
          Expanded(
            child: Text(
              stageName,
              style: const TextStyle(
                color: SuokeDesignTokens.textPrimary,
                fontSize: SuokeDesignTokens.fontSizeSm,
              ),
            ),
          ),
          Text(
            '${(ratio * 100).toStringAsFixed(0)}%',
            style: const TextStyle(
              color: SuokeDesignTokens.textMuted,
              fontSize: SuokeDesignTokens.fontSizeXs,
            ),
          ),
          const SizedBox(width: SuokeDesignTokens.spacingMd),
          Text(
            '¥${amount.toStringAsFixed(2)}',
            style: const TextStyle(
              color: SuokeDesignTokens.textPrimary,
              fontSize: SuokeDesignTokens.fontSizeSm,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(width: SuokeDesignTokens.spacingSm),
          _CardHelpers._statusBadge(status),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 施工进度卡片 (ProgressCard)
// ═══════════════════════════════════════════

class _ProgressCard extends StatelessWidget {
  final Map<String, dynamic> data;
  final void Function(String action, Map<String, dynamic> payload)? onAction;

  const _ProgressCard({required this.data, this.onAction});

  @override
  Widget build(BuildContext context) {
    final projectName = _CardHelpers._safeStr(data['project_name']);
    final overallProgress = _CardHelpers._safeDouble(data['overall_progress']);
    final phases = (data['phases'] as List?)?.cast<Map<String, dynamic>>() ?? [];
    final crewInfo = data['crew_info'] as Map<String, dynamic>? ?? const {};
    final nextMilestone = data['next_milestone'] as Map<String, dynamic>? ?? const {};

    final percent = (overallProgress * 100).toStringAsFixed(1);

    return _CardHelpers._cardWrapper(
      title: projectName.isNotEmpty ? projectName : '施工进度',
      subtitle: '总体进度 $percent%',
      accentColor: SuokeDesignTokens.agentConstruction,
      onAction: onAction,
      actions: [
        {'label': '查看详情', 'action': 'view_progress_detail', 'variant': 'primary'},
      ],
      actionPayload: data,
      children: [
        // 总体进度条
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  '总体进度',
                  style: TextStyle(
                    color: SuokeDesignTokens.textSecondary,
                    fontSize: SuokeDesignTokens.fontSizeSm,
                  ),
                ),
                Text(
                  '$percent%',
                  style: const TextStyle(
                    color: SuokeDesignTokens.accent,
                    fontSize: SuokeDesignTokens.fontSizeLg,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
            const SizedBox(height: SuokeDesignTokens.spacingSm),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: overallProgress.clamp(0.0, 1.0),
                minHeight: 8,
                backgroundColor: SuokeDesignTokens.border,
                valueColor: const AlwaysStoppedAnimation<Color>(
                  SuokeDesignTokens.agentConstruction,
                ),
              ),
            ),
          ],
        ),

        // 班组信息
        if (crewInfo.isNotEmpty) ...[
          const SizedBox(height: SuokeDesignTokens.spacingMd),
          _crewInfoSection(crewInfo),
        ],

        // 下一里程碑
        if (nextMilestone.isNotEmpty) ...[
          const SizedBox(height: SuokeDesignTokens.spacingMd),
          Container(
            padding: const EdgeInsets.all(SuokeDesignTokens.spacingMd),
            decoration: BoxDecoration(
              color: SuokeDesignTokens.warning.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusSm),
              border: Border.all(
                color: SuokeDesignTokens.warning.withValues(alpha: 0.2),
              ),
            ),
            child: Row(
              children: [
                const Icon(
                  Icons.flag_outlined,
                  color: SuokeDesignTokens.warning,
                  size: 18,
                ),
                const SizedBox(width: SuokeDesignTokens.spacingSm),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        '下一里程碑: ${_CardHelpers._safeStr(nextMilestone['name'])}',
                        style: const TextStyle(
                          color: SuokeDesignTokens.warning,
                          fontSize: SuokeDesignTokens.fontSizeSm,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      if (_CardHelpers._safeStr(nextMilestone['date']).isNotEmpty)
                        Text(
                          _CardHelpers._safeStr(nextMilestone['date']),
                          style: const TextStyle(
                            color: SuokeDesignTokens.textMuted,
                            fontSize: SuokeDesignTokens.fontSizeXs,
                          ),
                        ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],

        // 阶段列表
        if (phases.isNotEmpty) ...[
          const SizedBox(height: SuokeDesignTokens.spacingMd),
          const Text(
            '阶段进度',
            style: TextStyle(
              color: SuokeDesignTokens.textSecondary,
              fontSize: SuokeDesignTokens.fontSizeSm,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: SuokeDesignTokens.spacingSm),
          ...phases.map((phase) => _phaseRow(phase)),
        ],
      ],
    );
  }

  Widget _phaseRow(Map<String, dynamic> phase) {
    final name = _CardHelpers._safeStr(phase['name']);
    final progress = _CardHelpers._safeDouble(phase['progress']);
    final status = _CardHelpers._safeStr(phase['status']);

    return Padding(
      padding: const EdgeInsets.only(bottom: SuokeDesignTokens.spacingSm),
      child: Row(
        children: [
          Icon(
            progress >= 1.0
                ? Icons.check_circle_outline
                : progress > 0
                    ? Icons.timelapse
                    : Icons.radio_button_unchecked,
            size: 16,
            color: progress >= 1.0
                ? SuokeDesignTokens.success
                : progress > 0
                    ? SuokeDesignTokens.warning
                    : SuokeDesignTokens.textMuted,
          ),
          const SizedBox(width: SuokeDesignTokens.spacingSm),
          Expanded(
            child: Text(
              name,
              style: const TextStyle(
                color: SuokeDesignTokens.textPrimary,
                fontSize: SuokeDesignTokens.fontSizeSm,
              ),
            ),
          ),
          Text(
            '${(progress * 100).toStringAsFixed(0)}%',
            style: const TextStyle(
              color: SuokeDesignTokens.textSecondary,
              fontSize: SuokeDesignTokens.fontSizeXs,
            ),
          ),
          const SizedBox(width: SuokeDesignTokens.spacingSm),
          _CardHelpers._statusBadge(status, progress: progress),
        ],
      ),
    );
  }

  Widget _crewInfoSection(Map<String, dynamic> crewInfo) {
    final leader = _CardHelpers._safeStr(crewInfo['leader']);
    final teamSize = _CardHelpers._safeInt(crewInfo['team_size']);
    final specialties = (crewInfo['specialties'] as List?)?.map((e) => e.toString()).toList() ?? [];

    return Container(
      padding: const EdgeInsets.all(SuokeDesignTokens.spacingMd),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.surface2,
        borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusSm),
        border: Border.all(color: SuokeDesignTokens.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          if (leader.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: SuokeDesignTokens.spacingXs),
              child: Row(
                children: [
                  const Icon(
                    Icons.person_outline,
                    size: 14,
                    color: SuokeDesignTokens.textSecondary,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    '班组长: $leader',
                    style: const TextStyle(
                      color: SuokeDesignTokens.textPrimary,
                      fontSize: SuokeDesignTokens.fontSizeSm,
                    ),
                  ),
                  if (teamSize > 0) ...[
                    const SizedBox(width: SuokeDesignTokens.spacingMd),
                    Text(
                      '团队 $teamSize 人',
                      style: const TextStyle(
                        color: SuokeDesignTokens.textMuted,
                        fontSize: SuokeDesignTokens.fontSizeXs,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          if (specialties.isNotEmpty)
            Wrap(
              spacing: 4,
              runSpacing: 4,
              children: specialties.map((s) => _crewTag(s)).toList(),
            ),
        ],
      ),
    );
  }

  Widget _crewTag(String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.agentConstruction.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        label,
        style: const TextStyle(
          color: SuokeDesignTokens.agentConstruction,
          fontSize: SuokeDesignTokens.fontSizeXs,
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 采购订单卡片 (ProcurementCard)
// ═══════════════════════════════════════════

class _ProcurementCard extends StatelessWidget {
  final Map<String, dynamic> data;
  final void Function(String action, Map<String, dynamic> payload)? onAction;

  const _ProcurementCard({required this.data, this.onAction});

  @override
  Widget build(BuildContext context) {
    final orderId = _CardHelpers._safeStr(data['order_id']);
    final totalAmount = _CardHelpers._safeDouble(data['total_amount']);
    final deliveryDate = _CardHelpers._safeStr(data['delivery_date']);
    final status = _CardHelpers._safeStr(data['status']);
    final supplier = data['supplier'] as Map<String, dynamic>? ?? const {};
    final items = (data['items'] as List?)?.cast<Map<String, dynamic>>() ?? [];

    return _CardHelpers._cardWrapper(
      title: '采购订单',
      subtitle: orderId.isNotEmpty ? '#$orderId' : null,
      accentColor: SuokeDesignTokens.agentProcurement,
      onAction: onAction,
      actions: [
        {'label': '查看详情', 'action': 'view_order_detail', 'variant': 'primary'},
      ],
      actionPayload: data,
      children: [
        // 供应商信息
        if (supplier.isNotEmpty) ...[
          Row(
            children: [
              const Icon(Icons.store_outlined, size: 16, color: SuokeDesignTokens.textSecondary),
              const SizedBox(width: SuokeDesignTokens.spacingSm),
              Expanded(
                child: Text(
                  _CardHelpers._safeStr(supplier['name']),
                  style: const TextStyle(
                    color: SuokeDesignTokens.textPrimary,
                    fontSize: SuokeDesignTokens.fontSizeSm,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              _CardHelpers._statusBadge(status),
            ],
          ),
          const SizedBox(height: SuokeDesignTokens.spacingSm),
        ],

        // 物料列表
        if (items.isNotEmpty) ...[
          ...items.map((item) => Padding(
                padding: const EdgeInsets.only(bottom: SuokeDesignTokens.spacingSm),
                child: Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            _CardHelpers._safeStr(item['name']),
                            style: const TextStyle(
                              color: SuokeDesignTokens.textPrimary,
                              fontSize: SuokeDesignTokens.fontSizeSm,
                            ),
                          ),
                          if (_CardHelpers._safeStr(item['specs']).isNotEmpty)
                            Text(
                              _CardHelpers._safeStr(item['specs']),
                              style: const TextStyle(
                                color: SuokeDesignTokens.textMuted,
                                fontSize: SuokeDesignTokens.fontSizeXs,
                              ),
                            ),
                        ],
                      ),
                    ),
                    Text(
                      '×${_CardHelpers._safeDouble(item['quantity']).toStringAsFixed(0)} '
                      '${_CardHelpers._safeStr(item['unit'])}',
                      style: const TextStyle(
                        color: SuokeDesignTokens.textSecondary,
                        fontSize: SuokeDesignTokens.fontSizeXs,
                      ),
                    ),
                  ],
                ),
              )),
        ],

        // 总金额与交货日期
        const Divider(color: SuokeDesignTokens.border, height: 16),
        Padding(
          padding: const EdgeInsets.only(top: SuokeDesignTokens.spacingXs),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    '订单总额',
                    style: TextStyle(
                      color: SuokeDesignTokens.textMuted,
                      fontSize: SuokeDesignTokens.fontSizeXs,
                    ),
                  ),
                  _CardHelpers._amountText(totalAmount),
                ],
              ),
              if (deliveryDate.isNotEmpty)
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text(
                      '预计交货',
                      style: TextStyle(
                        color: SuokeDesignTokens.textMuted,
                        fontSize: SuokeDesignTokens.fontSizeXs,
                      ),
                    ),
                    Text(
                      deliveryDate,
                      style: const TextStyle(
                        color: SuokeDesignTokens.textPrimary,
                        fontSize: SuokeDesignTokens.fontSizeSm,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
            ],
          ),
        ),
      ],
    );
  }
}

// ═══════════════════════════════════════════
// 质检报告卡片 (QAReportCard)
// ═══════════════════════════════════════════

class _QAReportCard extends StatelessWidget {
  final Map<String, dynamic> data;
  final void Function(String action, Map<String, dynamic> payload)? onAction;

  const _QAReportCard({required this.data, this.onAction});

  @override
  Widget build(BuildContext context) {
    final projectName = _CardHelpers._safeStr(data['project_name']);
    final inspector = _CardHelpers._safeStr(data['inspector']);
    final inspectionDate = _CardHelpers._safeStr(data['inspection_date']);
    final fixDeadline = _CardHelpers._safeStr(data['fix_deadline']);
    final overallResult = _CardHelpers._safeStr(data['overall_result']);
    final passedCount = _CardHelpers._safeInt(data['passed_count']);
    final failedCount = _CardHelpers._safeInt(data['failed_count']);
    final checkpoints = (data['checkpoints'] as List?)?.cast<Map<String, dynamic>>() ?? [];

    final isPassed = overallResult == 'pass';
    final resultColor = isPassed ? SuokeDesignTokens.success : SuokeDesignTokens.danger;
    final resultIcon = isPassed ? Icons.check_circle : Icons.error_outline;
    final resultText = isPassed ? '验收通过' : '需整改';

    return _CardHelpers._cardWrapper(
      title: projectName.isNotEmpty ? projectName : '质检报告',
      subtitle: '$inspector · $inspectionDate',
      accentColor: SuokeDesignTokens.agentQuality,
      onAction: onAction,
      actions: [
        {'label': '查看详情', 'action': 'view_qa_detail', 'variant': 'primary'},
      ],
      actionPayload: data,
      children: [
        // 总体结果
        Container(
          padding: const EdgeInsets.all(SuokeDesignTokens.spacingMd),
          decoration: BoxDecoration(
            color: resultColor.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusSm),
            border: Border.all(color: resultColor.withValues(alpha: 0.3)),
          ),
          child: Row(
            children: [
              Icon(resultIcon, color: resultColor, size: 24),
              const SizedBox(width: SuokeDesignTokens.spacingMd),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    resultText,
                    style: TextStyle(
                      color: resultColor,
                      fontSize: SuokeDesignTokens.fontSizeLg,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  Text(
                    '通过 $passedCount / 不通过 $failedCount',
                    style: const TextStyle(
                      color: SuokeDesignTokens.textSecondary,
                      fontSize: SuokeDesignTokens.fontSizeXs,
                    ),
                  ),
                ],
              ),
              const Spacer(),
              Text(
                '${(passedCount / (passedCount + failedCount).clamp(1, 999) * 100).toStringAsFixed(0)}%',
                style: TextStyle(
                  color: resultColor,
                  fontSize: 22,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
        ),

        // 整改期限
        if (!isPassed && fixDeadline.isNotEmpty) ...[
          const SizedBox(height: SuokeDesignTokens.spacingMd),
          Container(
            padding: const EdgeInsets.all(SuokeDesignTokens.spacingSm),
            decoration: BoxDecoration(
              color: SuokeDesignTokens.danger.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusSm),
            ),
            child: Row(
              children: [
                const Icon(Icons.schedule, size: 14, color: SuokeDesignTokens.danger),
                const SizedBox(width: SuokeDesignTokens.spacingSm),
                Text(
                  '整改截止: $fixDeadline',
                  style: const TextStyle(
                    color: SuokeDesignTokens.danger,
                    fontSize: SuokeDesignTokens.fontSizeSm,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
        ],

        // 检查点列表
        if (checkpoints.isNotEmpty) ...[
          const SizedBox(height: SuokeDesignTokens.spacingMd),
          ...checkpoints.map((cp) => _checkpointRow(cp)),
        ],
      ],
    );
  }

  Widget _checkpointRow(Map<String, dynamic> cp) {
    final name = _CardHelpers._safeStr(cp['name']);
    final result = _CardHelpers._safeStr(cp['result']);
    final standard = _CardHelpers._safeStr(cp['standard']);
    final actual = _CardHelpers._safeStr(cp['actual']);

    final isPass = result == 'pass';
    final icon = isPass
        ? Icons.check_circle_outline
        : result == 'fail'
            ? Icons.cancel_outlined
            : Icons.help_outline;
    final iconColor = isPass
        ? SuokeDesignTokens.success
        : result == 'fail'
            ? SuokeDesignTokens.danger
            : SuokeDesignTokens.textMuted;

    return Padding(
      padding: const EdgeInsets.only(bottom: SuokeDesignTokens.spacingSm),
      child: Row(
        children: [
          Icon(icon, size: 16, color: iconColor),
          const SizedBox(width: SuokeDesignTokens.spacingSm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  name,
                  style: const TextStyle(
                    color: SuokeDesignTokens.textPrimary,
                    fontSize: SuokeDesignTokens.fontSizeSm,
                  ),
                ),
                if (standard.isNotEmpty || actual.isNotEmpty)
                  Text(
                    '标准: $standard${actual.isNotEmpty ? " · 实测: $actual" : ""}',
                    style: const TextStyle(
                      color: SuokeDesignTokens.textMuted,
                      fontSize: SuokeDesignTokens.fontSizeXs,
                    ),
                  ),
              ],
            ),
          ),
          _CardHelpers._statusBadge(result),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 结算汇总卡片 (SettlementCard)
// ═══════════════════════════════════════════

class _SettlementCard extends StatelessWidget {
  final Map<String, dynamic> data;
  final void Function(String action, Map<String, dynamic> payload)? onAction;

  const _SettlementCard({required this.data, this.onAction});

  @override
  Widget build(BuildContext context) {
    final projectName = _CardHelpers._safeStr(data['project_name']);
    final totalAmount = _CardHelpers._safeDouble(data['total_amount']);
    final paidAmount = _CardHelpers._safeDouble(data['paid_amount']);
    final balanceAmount = _CardHelpers._safeDouble(data['balance_amount']);
    final paymentHistory = (data['payment_history'] as List?)?.cast<Map<String, dynamic>>() ?? [];
    final nextPayment = data['next_payment'] as Map<String, dynamic>? ?? const {};

    return _CardHelpers._cardWrapper(
      title: projectName.isNotEmpty ? projectName : '结算汇总',
      accentColor: SuokeDesignTokens.agentSettlement,
      onAction: onAction,
      actions: [
        {'label': '查看详情', 'action': 'view_settlement_detail', 'variant': 'primary'},
      ],
      actionPayload: data,
      children: [
        // 金额概览
        Row(
          children: [
            _amountBox('合同总额', totalAmount, SuokeDesignTokens.textPrimary),
            const SizedBox(width: SuokeDesignTokens.spacingSm),
            _amountBox('已付金额', paidAmount, SuokeDesignTokens.success),
            const SizedBox(width: SuokeDesignTokens.spacingSm),
            _amountBox('待付余额', balanceAmount, SuokeDesignTokens.warning),
          ],
        ),

        // 待付信息
        if (nextPayment.isNotEmpty) ...[
          const SizedBox(height: SuokeDesignTokens.spacingMd),
          Container(
            padding: const EdgeInsets.all(SuokeDesignTokens.spacingMd),
            decoration: BoxDecoration(
              color: SuokeDesignTokens.warning.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusSm),
              border: Border.all(
                color: SuokeDesignTokens.warning.withValues(alpha: 0.2),
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  children: [
                    const Icon(Icons.payment, size: 14, color: SuokeDesignTokens.warning),
                    const SizedBox(width: SuokeDesignTokens.spacingSm),
                    Text(
                      '下一笔付款: ¥${_CardHelpers._safeDouble(nextPayment['amount']).toStringAsFixed(2)}',
                      style: const TextStyle(
                        color: SuokeDesignTokens.warning,
                        fontSize: SuokeDesignTokens.fontSizeSm,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
                if (_CardHelpers._safeStr(nextPayment['due_date']).isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 4, left: 20),
                    child: Text(
                      '到期日: ${_CardHelpers._safeStr(nextPayment['due_date'])}',
                      style: const TextStyle(
                        color: SuokeDesignTokens.textMuted,
                        fontSize: SuokeDesignTokens.fontSizeXs,
                      ),
                    ),
                  ),
                if (_CardHelpers._safeStr(nextPayment['condition']).isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 2, left: 20),
                    child: Text(
                      '条件: ${_CardHelpers._safeStr(nextPayment['condition'])}',
                      style: const TextStyle(
                        color: SuokeDesignTokens.textMuted,
                        fontSize: SuokeDesignTokens.fontSizeXs,
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ],

        // 付款历史
        if (paymentHistory.isNotEmpty) ...[
          const SizedBox(height: SuokeDesignTokens.spacingMd),
          const Text(
            '付款历史',
            style: TextStyle(
              color: SuokeDesignTokens.textSecondary,
              fontSize: SuokeDesignTokens.fontSizeSm,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: SuokeDesignTokens.spacingSm),
          ...paymentHistory.take(5).map((p) => Padding(
                padding: const EdgeInsets.only(bottom: SuokeDesignTokens.spacingSm),
                child: Row(
                  children: [
                    Text(
                      _CardHelpers._safeStr(p['date']),
                      style: const TextStyle(
                        color: SuokeDesignTokens.textMuted,
                        fontSize: SuokeDesignTokens.fontSizeXs,
                      ),
                    ),
                    const SizedBox(width: SuokeDesignTokens.spacingMd),
                    Text(
                      _CardHelpers._safeStr(p['method']),
                      style: const TextStyle(
                        color: SuokeDesignTokens.textSecondary,
                        fontSize: SuokeDesignTokens.fontSizeXs,
                      ),
                    ),
                    const Spacer(),
                    Text(
                      '¥${_CardHelpers._safeDouble(p['amount']).toStringAsFixed(2)}',
                      style: const TextStyle(
                        color: SuokeDesignTokens.textPrimary,
                        fontSize: SuokeDesignTokens.fontSizeSm,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(width: SuokeDesignTokens.spacingSm),
                    _CardHelpers._statusBadge(_CardHelpers._safeStr(p['status'])),
                  ],
                ),
              )),
        ],
      ],
    );
  }

  Widget _amountBox(String label, double amount, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(SuokeDesignTokens.spacingSm),
        decoration: BoxDecoration(
          color: SuokeDesignTokens.surface2,
          borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusSm),
          border: Border.all(color: SuokeDesignTokens.border),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              label,
              style: const TextStyle(
                color: SuokeDesignTokens.textMuted,
                fontSize: SuokeDesignTokens.fontSizeXs,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              '¥${amount.toStringAsFixed(0)}',
              style: TextStyle(
                color: color,
                fontSize: SuokeDesignTokens.fontSizeMd,
                fontWeight: FontWeight.w700,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 材料详情卡片 (MaterialCard)
// ═══════════════════════════════════════════

class _MaterialCard extends StatelessWidget {
  final Map<String, dynamic> data;
  final void Function(String action, Map<String, dynamic> payload)? onAction;

  const _MaterialCard({required this.data, this.onAction});

  @override
  Widget build(BuildContext context) {
    final name = _CardHelpers._safeStr(data['name']);
    final category = _CardHelpers._safeStr(data['category']);
    final specs = _CardHelpers._safeStr(data['specs']);
    final ecoLevel = _CardHelpers._safeStr(data['eco_level']);
    final unitPrice = _CardHelpers._safeDouble(data['unit_price']);
    final unit = _CardHelpers._safeStr(data['unit']);
    final supplier = _CardHelpers._safeStr(data['supplier']);
    final stockStatus = _CardHelpers._safeStr(data['stock_status']);
    final description = _CardHelpers._safeStr(data['description']);
    final certifications = (data['certifications'] as List?)?.map((e) => e.toString()).toList() ?? [];

    return _CardHelpers._cardWrapper(
      title: name.isNotEmpty ? name : '材料详情',
      subtitle: category.isNotEmpty ? category : null,
      accentColor: SuokeDesignTokens.agentMaster,
      onAction: onAction,
      actions: [
        {'label': '查看详情', 'action': 'view_material_detail', 'variant': 'primary'},
      ],
      actionPayload: data,
      children: [
        // 价格行
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            _CardHelpers._amountText(unitPrice),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  '/$unit',
                  style: const TextStyle(
                    color: SuokeDesignTokens.textMuted,
                    fontSize: SuokeDesignTokens.fontSizeSm,
                  ),
                ),
                const SizedBox(width: SuokeDesignTokens.spacingSm),
                _CardHelpers._statusBadge(stockStatus),
              ],
            ),
          ],
        ),

        const SizedBox(height: SuokeDesignTokens.spacingMd),

        // 规格和环保等级
        if (specs.isNotEmpty)
          _CardHelpers._infoRow('规格', specs),
        if (ecoLevel.isNotEmpty)
          _CardHelpers._infoRow(
            '环保等级',
            ecoLevel,
            valueColor: SuokeDesignTokens.success,
            boldValue: true,
          ),
        if (supplier.isNotEmpty)
          _CardHelpers._infoRow('供应商', supplier),

        // 认证
        if (certifications.isNotEmpty) ...[
          const SizedBox(height: SuokeDesignTokens.spacingXs),
          Wrap(
            spacing: 4,
            runSpacing: 4,
            children: certifications.map((c) => Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: SuokeDesignTokens.success.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(
                      color: SuokeDesignTokens.success.withValues(alpha: 0.3),
                    ),
                  ),
                  child: Text(
                    c,
                    style: const TextStyle(
                      color: SuokeDesignTokens.success,
                      fontSize: SuokeDesignTokens.fontSizeXs,
                    ),
                  ),
                )).toList(),
          ),
        ],

        // 描述
        if (description.isNotEmpty) ...[
          const SizedBox(height: SuokeDesignTokens.spacingMd),
          Text(
            description,
            style: const TextStyle(
              color: SuokeDesignTokens.textSecondary,
              fontSize: SuokeDesignTokens.fontSizeSm,
              height: 1.5,
            ),
          ),
        ],
      ],
    );
  }
}

// ═══════════════════════════════════════════
// 系统告警卡片 (AlertCard)
// ═══════════════════════════════════════════

class _AlertCard extends StatelessWidget {
  final Map<String, dynamic> data;
  final void Function(String action, Map<String, dynamic> payload)? onAction;

  const _AlertCard({required this.data, this.onAction});

  @override
  Widget build(BuildContext context) {
    final title = _CardHelpers._safeStr(data['title']);
    final message = _CardHelpers._safeStr(data['message']);
    final severity = _CardHelpers._safeStr(data['severity']);
    final actions = (data['actions'] as List?)?.cast<Map<String, dynamic>>() ?? [];
    final sourceAgent = _CardHelpers._safeStr(data['source_agent']);

    final severityInfo = _getSeverityStyle(severity);

    return Container(
      margin: const EdgeInsets.symmetric(
        horizontal: SuokeDesignTokens.spacingLg,
        vertical: SuokeDesignTokens.spacingSm,
      ),
      decoration: BoxDecoration(
        color: severityInfo.bgColor,
        borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusLg),
        border: Border.all(color: severityInfo.borderColor),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          // 告警头部
          Padding(
            padding: const EdgeInsets.fromLTRB(
              SuokeDesignTokens.spacingLg,
              SuokeDesignTokens.spacingMd,
              SuokeDesignTokens.spacingLg,
              SuokeDesignTokens.spacingSm,
            ),
            child: Row(
              children: [
                Icon(severityInfo.icon, color: severityInfo.iconColor, size: 20),
                const SizedBox(width: SuokeDesignTokens.spacingSm),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 6,
                              vertical: 1,
                            ),
                            decoration: BoxDecoration(
                              color: severityInfo.iconColor.withValues(alpha: 0.2),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              severityInfo.label,
                              style: TextStyle(
                                color: severityInfo.iconColor,
                                fontSize: SuokeDesignTokens.fontSizeXs,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                          if (sourceAgent.isNotEmpty) ...[
                            const SizedBox(width: SuokeDesignTokens.spacingSm),
                            Text(
                              sourceAgent,
                              style: const TextStyle(
                                color: SuokeDesignTokens.textMuted,
                                fontSize: SuokeDesignTokens.fontSizeXs,
                              ),
                            ),
                          ],
                        ],
                      ),
                      if (title.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 4),
                          child: Text(
                            title,
                            style: const TextStyle(
                              color: SuokeDesignTokens.textPrimary,
                              fontSize: SuokeDesignTokens.fontSizeMd,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          // 消息正文
          if (message.isNotEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(
                SuokeDesignTokens.spacingLg,
                0,
                SuokeDesignTokens.spacingLg,
                SuokeDesignTokens.spacingMd,
              ),
              child: Text(
                message,
                style: const TextStyle(
                  color: SuokeDesignTokens.textSecondary,
                  fontSize: SuokeDesignTokens.fontSizeSm,
                  height: 1.5,
                ),
              ),
            ),
          // 操作按钮
          if (actions.isNotEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(
                SuokeDesignTokens.spacingLg,
                0,
                SuokeDesignTokens.spacingLg,
                SuokeDesignTokens.spacingMd,
              ),
              child: Wrap(
                spacing: SuokeDesignTokens.spacingSm,
                runSpacing: SuokeDesignTokens.spacingSm,
                children: actions.map((a) {
                  final label = _CardHelpers._safeStr(a['label']);
                  final action = _CardHelpers._safeStr(a['action']);
                  if (label.isEmpty) return const SizedBox.shrink();
                  return OutlinedButton(
                    onPressed: () => onAction?.call(action, data),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: severityInfo.iconColor,
                      side: BorderSide(color: severityInfo.iconColor.withValues(alpha: 0.5)),
                      padding: const EdgeInsets.symmetric(
                        horizontal: SuokeDesignTokens.spacingMd,
                        vertical: SuokeDesignTokens.spacingSm,
                      ),
                      minimumSize: const Size(
                        SuokeDesignTokens.touchTargetMin,
                        SuokeDesignTokens.touchTargetMin,
                      ),
                    ),
                    child: Text(label),
                  );
                }).toList(),
              ),
            ),
        ],
      ),
    );
  }

  _SeverityStyle _getSeverityStyle(String severity) {
    return switch (severity) {
      'critical' => _SeverityStyle(
          label: '严重',
          icon: Icons.report,
          iconColor: SuokeDesignTokens.danger,
          bgColor: SuokeDesignTokens.danger.withValues(alpha: 0.08),
          borderColor: SuokeDesignTokens.danger.withValues(alpha: 0.3),
        ),
      'error' => _SeverityStyle(
          label: '错误',
          icon: Icons.error_outline,
          iconColor: SuokeDesignTokens.danger,
          bgColor: SuokeDesignTokens.danger.withValues(alpha: 0.06),
          borderColor: SuokeDesignTokens.danger.withValues(alpha: 0.2),
        ),
      'warning' => _SeverityStyle(
          label: '警告',
          icon: Icons.warning_amber_rounded,
          iconColor: SuokeDesignTokens.warning,
          bgColor: SuokeDesignTokens.warning.withValues(alpha: 0.08),
          borderColor: SuokeDesignTokens.warning.withValues(alpha: 0.3),
        ),
      _ => _SeverityStyle(
          label: '信息',
          icon: Icons.info_outline,
          iconColor: SuokeDesignTokens.info,
          bgColor: SuokeDesignTokens.info.withValues(alpha: 0.06),
          borderColor: SuokeDesignTokens.info.withValues(alpha: 0.2),
        ),
    };
  }
}

/// 告警严重级别样式
class _SeverityStyle {
  final String label;
  final IconData icon;
  final Color iconColor;
  final Color bgColor;
  final Color borderColor;

  const _SeverityStyle({
    required this.label,
    required this.icon,
    required this.iconColor,
    required this.bgColor,
    required this.borderColor,
  });
}

// ═══════════════════════════════════════════
// 未知类型卡片 (fallback)
// ═══════════════════════════════════════════

class _UnknownCard extends StatelessWidget {
  final String type;
  final Map<String, dynamic> data;

  const _UnknownCard({required this.type, required this.data});

  @override
  Widget build(BuildContext context) {
    return _CardHelpers._cardWrapper(
      title: '未知卡片类型',
      subtitle: type,
      onAction: null,
      actions: const [],
      children: [
        Text(
          data.toString(),
          style: const TextStyle(
            color: SuokeDesignTokens.textMuted,
            fontSize: SuokeDesignTokens.fontSizeSm,
          ),
        ),
      ],
    );
  }
}
