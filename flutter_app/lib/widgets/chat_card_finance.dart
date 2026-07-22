// F4: 财务域卡片渲染器 — 从 chat_message_card.dart 拆分
//
// 包含: 预算概览 / 支付进度 / 结算单 / 里程碑结算
// 拆分自 chat_message_card.dart (v1.1.27), 使用 extension 方法拆分, 零行为变更,
// 私有 helper (wrapCard/row/parseNum/progressBar 等) 跨 extension 可见, 零行为变更。
import 'package:flutter/material.dart';
import '../models/chat_message.dart';
import '../theme/suoke_theme.dart';
import 'chat_message_card.dart';

/// 财务域卡片渲染器扩展 (预算/支付/结算/里程碑)
extension ChatCardFinanceRenderers on ChatMessageCard {

  // ═══════════════════════════════════════════
  // 7. 预算卡片
  // ═══════════════════════════════════════════
  Widget buildBudgetCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('budget');
    final total = ChatMessageCard.parseNum(p['total']);
    final spent = ChatMessageCard.parseNum(p['spent']);
    final remaining = ChatMessageCard.parseNum(p['remaining']);
    final note = p['note'] as String?;
    final percent = total > 0 ? (spent / total * 100).round() : 0;

    return wrapCard(
      agentInfo: agentInfo,
      title: '📊 预算概览',
      children: [
        row('总预算', '¥${ChatMessageCard.fmtNum(total)}', boldValue: true),
        row('已支出', '¥${ChatMessageCard.fmtNum(spent)}（${percent}%）', boldValue: true),
        row('剩余', '¥${ChatMessageCard.fmtNum(remaining)}',
            boldValue: true, valueColor: SuokeDesignTokens.success),
        const SizedBox(height: 6),
        progressBar(percent),
        if (note != null && note.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(ChatMessageCard.esc(note),
                style: const TextStyle(fontSize: 10, color: SuokeDesignTokens.textMuted)),
          ),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 8. 支付进度卡片
  // ═══════════════════════════════════════════
  Widget buildPaymentCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('settlement');
    final stages = (p['stages'] ?? p['schedule'] as List?) ?? [];
    final totalPaid = ChatMessageCard.parseNum(p['total_paid'] ?? 0);
    final totalAmount = ChatMessageCard.parseNum(p['total_amount'] ?? 0);
    final invoiceCount = p['invoice_count'];
    final invoicedAmount = ChatMessageCard.parseNum(p['invoiced_amount']);
    final note = p['note'] as String?;
    final percent =
        totalAmount > 0 ? (totalPaid / totalAmount * 100).round() : 0;

    const stageLabels = {
      'deposit': '首付',
      'progress': '进度款',
      'final': '尾款',
      'warranty': '质保金',
    };
    const statusIcons = {
      'paid': Icons.check_circle,
      'partial': Icons.change_circle,
      'pending': Icons.radio_button_unchecked,
      'overdue': Icons.warning_rounded,
    };
    const statusColors = {
      'paid': SuokeDesignTokens.success,
      'partial': SuokeDesignTokens.warning,
      'pending': SuokeDesignTokens.textMuted,
      'overdue': SuokeDesignTokens.danger,
    };

    return wrapCard(
      agentInfo: agentInfo,
      title: '💳 支付进度',
      children: [
        row('已付', '¥${ChatMessageCard.fmtNum(totalPaid)}',
            boldValue: true, valueColor: SuokeDesignTokens.success),
        row('总额', '¥${ChatMessageCard.fmtNum(totalAmount)}', boldValue: true),
        row('进度', '$percent%', boldValue: true),
        const SizedBox(height: 4),
        progressBar(percent),
        if (stages.isNotEmpty) ...[
          const SizedBox(height: 8),
          const Divider(color: SuokeDesignTokens.border, height: 1),
          const SizedBox(height: 4),
          ...stages.map((st) {
            final stageCode = (st['stage_code'] ?? st['milestone_code'] ?? '')
                .toString();
            final label = stageLabels[stageCode] ??
                (stageCode.isNotEmpty ? stageCode : '阶段');
            final status = (st['status'] ?? 'pending').toString();
            final paid = ChatMessageCard.parseNum(st['paid_amount']);
            final ttl = ChatMessageCard.parseNum(st['total_amount']);
            final stagePct = ttl > 0 ? (paid / ttl * 100).round() : 0;
            final icon = statusIcons[status] ?? Icons.radio_button_unchecked;
            final iconColor = statusColors[status] ?? SuokeDesignTokens.textMuted;

            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 2),
              child: Row(
                children: [
                  Icon(icon, size: 14, color: iconColor),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(ChatMessageCard.esc(label),
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                            fontSize: 12, color: SuokeDesignTokens.textPrimary)),
                  ),
                  const SizedBox(width: 6),
                  Text('¥${ChatMessageCard.fmtNum(paid)} / ¥${ChatMessageCard.fmtNum(ttl)}',
                      style: const TextStyle(fontSize: 11, color: SuokeDesignTokens.textSecondary)),
                  const SizedBox(width: 6),
                  Text('$stagePct%',
                      style: const TextStyle(fontSize: 11, color: SuokeDesignTokens.textMuted)),
                ],
              ),
            );
          }),
        ],
        if (invoiceCount != null)
          row('已开票',
              '$invoiceCount 张 · ¥${ChatMessageCard.fmtNum(invoicedAmount)}', boldValue: true),
        if (note != null && note.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(ChatMessageCard.esc(note),
                style: const TextStyle(fontSize: 10, color: SuokeDesignTokens.textMuted)),
          ),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 16. 结算卡片
  // ═══════════════════════════════════════════
  Widget buildSettlementCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('settlement');
    final lines = (p['lines'] as List?) ?? [];
    final contractAmount = ChatMessageCard.parseNum(p['contract_amount']);
    final actualAmount = ChatMessageCard.parseNum(p['actual_amount']);
    final payableAmount = ChatMessageCard.parseNum(p['payable_amount']);
    final status = (p['status'] ?? 'draft').toString();
    final reviewRequired = p['review_required'] == true;
    final anomalyCount = p['anomaly_count'];
    final criticalAnomalyCount = p['critical_anomaly_count'];
    final suggestedDeduction = ChatMessageCard.parseNum(p['suggested_deduction']);
    final projectId = p['project_id'] as String?;
    final milestone = p['milestone'] as String?;

    const statusTexts = {
      'draft': '草稿',
      'confirmed': '已确认',
      'review': '待复核',
      'flagged': '已标记异常',
    };

    return wrapCard(
      agentInfo: agentInfo,
      title:
          '🧾 结算单 · ${ChatMessageCard.esc(milestone ?? 'completion')} · ${ChatMessageCard.esc(statusTexts[status] ?? status)}',
      children: [
        row('合同金额', '¥${ChatMessageCard.fmtNum(contractAmount)}', boldValue: true),
        row('实际金额', '¥${ChatMessageCard.fmtNum(actualAmount)}', boldValue: true),
        row('应付金额', '¥${ChatMessageCard.fmtNum(payableAmount)}',
            boldValue: true, valueColor: SuokeDesignTokens.accent),
        if (criticalAnomalyCount != null && criticalAnomalyCount > 0)
          row('异常', '$criticalAnomalyCount 严重 / $anomalyCount 总',
              boldValue: true, valueColor: SuokeDesignTokens.warning)
        else if (anomalyCount != null && anomalyCount > 0)
          row('异常', '$anomalyCount 警告', boldValue: true),
        if (suggestedDeduction > 0)
          row('建议扣款', '-¥${ChatMessageCard.fmtNum(suggestedDeduction)}',
              boldValue: true, valueColor: SuokeDesignTokens.warning),
        if (reviewRequired)
          row('复核状态', '⚠ 需人工复核',
              boldValue: true, valueColor: SuokeDesignTokens.warning),
        if (lines.isNotEmpty) ...[
          const SizedBox(height: 6),
          const Divider(color: SuokeDesignTokens.border, height: 1),
          const SizedBox(height: 6),
          ...lines.take(6).toList().asMap().entries.map((entry) {
            final it = entry.value;
            final name = it['name'] ?? '未命名';
            final amt = ChatMessageCard.parseNum(it['actual_amount'] ?? it['contract_amount']);
            final isAnomaly = it['is_anomaly'] == true;
            final anomalyType = it['anomaly_type'] as String?;
            final variance =
                ChatMessageCard.parseNum(it['actual_amount']) - ChatMessageCard.parseNum(it['contract_amount']) - ChatMessageCard.parseNum(it['change_amount']);
            return row(
              '${entry.key + 1}. ${ChatMessageCard.esc(name)}${isAnomaly ? " ⚠${anomalyType ?? '异常'}" : ""}${variance != 0 ? " 偏差 ¥${ChatMessageCard.fmtNum(variance)}" : ""}',
              '¥${ChatMessageCard.fmtNum(amt)}',
              boldValue: true,
            );
          }),
          if (lines.length > 6)
            Text('… 共 ${lines.length} 项',
                style: const TextStyle(fontSize: 10, color: SuokeDesignTokens.textMuted)),
        ],
        if (projectId != null) ...[
          const SizedBox(height: 4),
          GestureDetector(
            onTap: () => onCardAction
                ?.call('export_settlement', {'project_id': projectId}),
            child: const Text('📤 导出对账单',
                style: TextStyle(fontSize: 11, color: SuokeDesignTokens.accent)),
          ),
        ],
        if ((status == 'draft' || status == 'flagged') &&
            !reviewRequired &&
            projectId != null)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: actionButton('确认结算', SuokeDesignTokens.success,
                () => onCardAction?.call('confirm_settlement', {'project_id': projectId})),
          ),
        if (reviewRequired && projectId != null)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: actionButton('通过复核', SuokeDesignTokens.accent,
                () => onCardAction?.call('approve_review', {'project_id': projectId})),
          ),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 17. 里程碑结算
  // ═══════════════════════════════════════════
  Widget buildMilestoneCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('settlement');
    final contractAmount = ChatMessageCard.parseNum(p['contract_amount']);
    final paymentRatio = ChatMessageCard.parseNum(p['payment_ratio']);
    final basePayable = ChatMessageCard.parseNum(p['base_payable']);
    final changeAmount = ChatMessageCard.parseNum(p['change_amount']);
    final deductionAmount = ChatMessageCard.parseNum(p['deduction_amount']);
    final paidAmount = ChatMessageCard.parseNum(p['paid_amount']);
    final totalPayable = ChatMessageCard.parseNum(p['total_payable']);
    final description = p['description'] as String?;

    final ratioPct = (paymentRatio * 100).round();

    return wrapCard(
      agentInfo: agentInfo,
      title: '🧾 ${ChatMessageCard.esc(p['milestone_name'] ?? '里程碑结算')}',
      children: [
        row('合同金额', '¥${ChatMessageCard.fmtNum(contractAmount)}', boldValue: true),
        row('付款比例', '$ratioPct%', boldValue: true),
        row('基础应付', '¥${ChatMessageCard.fmtNum(basePayable)}', boldValue: true),
        if (changeAmount != 0)
          row('变更', '+¥${ChatMessageCard.fmtNum(changeAmount)}', boldValue: true),
        if (deductionAmount != 0)
          row('扣款', '-¥${ChatMessageCard.fmtNum(deductionAmount)}',
              boldValue: true, valueColor: SuokeDesignTokens.warning),
        if (paidAmount != 0)
          row('已付', '-¥${ChatMessageCard.fmtNum(paidAmount)}', boldValue: true),
        row('本次应付', '¥${ChatMessageCard.fmtNum(totalPayable)}',
            boldValue: true, valueColor: SuokeDesignTokens.accent),
        if (description != null && description.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(ChatMessageCard.esc(description),
                style: const TextStyle(fontSize: 10, color: SuokeDesignTokens.textMuted)),
          ),
      ],
    );
  }
}
