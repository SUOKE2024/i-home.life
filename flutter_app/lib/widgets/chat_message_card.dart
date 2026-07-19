import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/chat_message.dart';
import '../theme/suoke_theme.dart';

/// 统一聊天消息卡片 —— 渲染全部 22 种消息类型
///
/// 参考 Web 端 message-renderers.js 的 HTML 结构和样式。
/// 颜色统一使用 [SuokeDesignTokens] 与 Web 端对齐。
class ChatMessageCard extends StatelessWidget {
  final ChatMessage message;
  final void Function(String decision, Map<String, dynamic> payload)? onApprovalAction;
  final void Function(String action, Map<String, dynamic> payload)? onCardAction;
  final void Function(String text)? onCopy;
  final void Function(ChatMessage message)? onReply;

  const ChatMessageCard({
    super.key,
    required this.message,
    this.onApprovalAction,
    this.onCardAction,
    this.onCopy,
    this.onReply,
  });

  // ── 引用统一设计令牌（与 Web 端 workbench.css 对齐） ──
  static const Color _bgDark = SuokeDesignTokens.bgDeep;
  static const Color _cardBg = SuokeDesignTokens.cardBg;
  static const Color _accent = SuokeDesignTokens.accent;
  static const Color _textPrimary = SuokeDesignTokens.textPrimary;
  static const Color _textSecondary = SuokeDesignTokens.textSecondary;
  static const Color _textMuted = SuokeDesignTokens.textMuted;
  static const Color _border = SuokeDesignTokens.border;
  static const Color _success = SuokeDesignTokens.success;
  static const Color _warning = SuokeDesignTokens.warning;
  static const Color _danger = SuokeDesignTokens.danger;
  static const Color _bubbleUser = SuokeDesignTokens.bubbleUser;
  static const Color _bubbleAgent = SuokeDesignTokens.bubbleAgent;

  @override
  Widget build(BuildContext context) {
    final type = message.type;

    if (type == ChatMessageType.system) return _buildSystemSeparator();

    Widget child;
    switch (type) {
      case ChatMessageType.text:
        child = _buildTextBubble(context);
      case ChatMessageType.task_card:
        child = _buildTaskCard();
      case ChatMessageType.photo:
        child = _buildPhotoGrid(context);
      case ChatMessageType.approval:
        child = _buildApprovalCard();
      case ChatMessageType.document:
        child = _buildDocumentCard();
      case ChatMessageType.budget:
        child = _buildBudgetCard();
      case ChatMessageType.payment:
        child = _buildPaymentCard();
      case ChatMessageType.quote:
        child = _buildQuoteCard();
      case ChatMessageType.bom:
        child = _buildBomCard();
      case ChatMessageType.procurement_order:
        child = _buildOrderCard();
      case ChatMessageType.procurement_orders:
        child = _buildOrderListCard();
      case ChatMessageType.escrow:
        child = _buildEscrowCard();
      case ChatMessageType.logistics:
        child = _buildLogisticsCard();
      case ChatMessageType.sample:
        child = _buildSampleCard();
      case ChatMessageType.settlement:
        child = _buildSettlementCard();
      case ChatMessageType.milestone_settlement:
        child = _buildMilestoneCard();
      case ChatMessageType.task_claim:
        child = _buildTaskClaimCard();
      case ChatMessageType.product_card:
        child = _buildProductCard();
      case ChatMessageType.orchestrator_task:
        child = _buildOrchestratorTaskCard();
      case ChatMessageType.points_card:
        child = _buildPointsCard();
      case ChatMessageType.narrative:
        child = _buildNarrativeCard();
      case ChatMessageType.inspection_card:
        child = _buildInspectionCard();
      case ChatMessageType.quality_issue_card:
        child = _buildQualityIssueCard();
      case ChatMessageType.progress_alert_card:
        child = _buildProgressAlertCard();
      case ChatMessageType.system:
        child = _buildSystemSeparator();
    }

    return GestureDetector(
      onLongPress: () => _showContextMenu(context),
      child: child,
    );
  }

  void _showContextMenu(BuildContext context) {
    final text = message.content ?? '';
    final isSelf = message.isSelf;
    final items = <PopupMenuEntry<String>>[
      PopupMenuItem<String>(
        value: 'copy',
        child: const Row(
          children: [
            Icon(Icons.copy, size: 18, color: _textSecondary),
            SizedBox(width: 10),
            Text('复制', style: TextStyle(color: _textPrimary, fontSize: 14)),
          ],
        ),
      ),
    ];

    if (isSelf) {
      items.add(
        PopupMenuItem<String>(
          value: 'reply',
          child: const Row(
            children: [
              Icon(Icons.reply, size: 18, color: _textSecondary),
              SizedBox(width: 10),
              Text('回复', style: TextStyle(color: _textPrimary, fontSize: 14)),
            ],
          ),
        ),
      );
    }

    final RenderBox renderBox = context.findRenderObject() as RenderBox;
    final offset = renderBox.localToGlobal(Offset.zero);

    showMenu<String>(
      context: context,
      color: _cardBg,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: _border),
      ),
      position: RelativeRect.fromLTRB(
        offset.dx + renderBox.size.width / 2,
        offset.dy + renderBox.size.height / 2,
        offset.dx + renderBox.size.width,
        offset.dy + renderBox.size.height,
      ),
      items: items,
    ).then((value) {
      if (value == 'copy') {
        Clipboard.setData(ClipboardData(text: text));
        onCopy?.call(text);
      } else if (value == 'reply') {
        onReply?.call(message);
      }
    });
  }

  // ═══════════════════════════════════════════
  // 1. 系统分割线
  // ═══════════════════════════════════════════
  Widget _buildSystemSeparator() {
    return Center(
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 8),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        decoration: BoxDecoration(
          color: _bgDark,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: _border.withValues(alpha: 0.4)),
        ),
        child: Text(
          message.content ?? '',
          style: const TextStyle(fontSize: 11, color: _textMuted),
        ),
      ),
    );
  }

  // ═══════════════════════════════════════════
  // 2. 文本消息气泡
  // ═══════════════════════════════════════════
  Widget _buildTextBubble(BuildContext context) {
    final isUser = message.isSelf;
    final agentInfo = message.agentInfo;
    final displayName = message.displayName ??
        (isUser ? '我' : '${agentInfo?.emoji ?? ''} ${agentInfo?.name ?? 'Agent'}');
    final bubbleColor = isUser ? _bubbleUser : _bubbleAgent;
    final leftBorderColor = isUser ? null : message.agentColor;
    final alignment = isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start;
    final radius = isUser
        ? const BorderRadius.only(
            topLeft: Radius.circular(16),
            topRight: Radius.circular(16),
            bottomLeft: Radius.circular(16),
            bottomRight: Radius.circular(4),
          )
        : const BorderRadius.only(
            topLeft: Radius.circular(16),
            topRight: Radius.circular(16),
            bottomLeft: Radius.circular(4),
            bottomRight: Radius.circular(16),
          );

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: alignment,
        children: [
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: _buildMetaRow(displayName, isUser, agentInfo?.color),
          ),
          Container(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.of(context).size.width * 0.75,
            ),
            decoration: BoxDecoration(
              color: bubbleColor,
              borderRadius: radius,
              border: Border.all(
                color: _border.withValues(alpha: 0.4),
                width: 1,
              ),
            ),
            child: ClipRRect(
              borderRadius: radius,
              child: IntrinsicHeight(
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    if (leftBorderColor != null)
                      Container(width: 3, color: leftBorderColor),
                    Expanded(
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 16, vertical: 12),
                        child: SelectableText(
                          message.content ?? '',
                          enableInteractiveSelection: true,
                          cursorColor: leftBorderColor ?? _accent,
                          style: const TextStyle(
                            fontSize: 14,
                            color: _textPrimary,
                            height: 1.5,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          // L4 自适应学习：Agent 消息底部反馈按钮
          if (!isUser && message.agent != null)
            _buildFeedbackRow(),
        ],
      ),
    );
  }

  /// L4 反馈按钮行
  Widget _buildFeedbackRow() {
    return Padding(
      padding: const EdgeInsets.only(top: 4),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _feedbackBtn('👍', 'like'),
          const SizedBox(width: 4),
          _feedbackBtn('👎', 'dislike'),
        ],
      ),
    );
  }

  Widget _feedbackBtn(String label, String type) {
    return GestureDetector(
      onTap: () => onCardAction?.call('agent_feedback', {
        'agent_key': message.agent,
        'feedback_type': type,
        'agent_reply': message.content ?? '',
      }),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
        decoration: BoxDecoration(
          color: _cardBg,
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: _border),
        ),
        child: Text(label, style: const TextStyle(fontSize: 12)),
      ),
    );
  }

  // ═══════════════════════════════════════════
  // 3. 任务卡片
  // ═══════════════════════════════════════════
  Widget _buildTaskCard() {
    final p = message.payload ?? {};
    final agentInfo = message.agentInfo ?? AgentInfo.getByKey('construction');
    final tasks = (p['tasks'] as List?) ?? [];
    final title = (p['title'] ?? '今日任务') as String;

    // 计算进度百分比
    final doneCount = tasks.where((t) {
      final s = (t['status'] ?? '').toString();
      return s == 'done' || s == 'completed';
    }).length;
    final percent = tasks.isNotEmpty ? (doneCount * 100 ~/ tasks.length) : 0;
    final progressLabel = percent > 0 ? '（$percent% 完成）' : '';

    return _wrapCard(
      agentInfo: agentInfo,
      title: '📋 ${_esc(title)}$progressLabel',
      children: [
        if (percent > 0) ...[
          const SizedBox(height: 2),
          _progressBar(percent),
          const SizedBox(height: 4),
        ],
        ...tasks.map(_buildTaskItem),
      ],
    );
  }

  Widget _buildTaskItem(dynamic t) {
    final name = (t['name'] ?? '') as String;
    final status = (t['status'] ?? 'pending') as String;
    final isDone = status == 'done';
    final isInProgress = status == 'in_progress';
    IconData icon;
    Color color;
    if (isDone) {
      icon = Icons.check_circle;
      color = _success;
    } else if (isInProgress) {
      icon = Icons.more_horiz;
      color = _warning;
    } else {
      icon = Icons.radio_button_unchecked;
      color = _textMuted;
    }
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              _esc(name),
              style: TextStyle(
                fontSize: 13,
                color: isDone ? _textSecondary : _textPrimary,
                decoration: isDone ? TextDecoration.lineThrough : null,
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ═══════════════════════════════════════════
  // 4. 照片网格
  // ═══════════════════════════════════════════
  Widget _buildPhotoGrid(BuildContext context) {
    final isUser = message.isSelf;
    final p = message.payload ?? {};
    final photos = (p['photos'] as List?) ?? [];
    final note = p['note'] as String?;
    final agentInfo = message.agentInfo;
    final displayName = isUser ? '我' : '${agentInfo?.name ?? 'Agent'} Agent';

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment:
            isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
        children: [
          _buildMetaRow(displayName, isUser, agentInfo?.color),
          const SizedBox(height: 4),
          Container(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.of(context).size.width * 0.75,
            ),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: isUser ? _bubbleUser : _bubbleAgent,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: _border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (note != null && note.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Text(_esc(note),
                        style: const TextStyle(fontSize: 13, color: _textPrimary)),
                  ),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: photos.map((ph) {
                    final url = (ph['url'] ?? '') as String;
                    final caption = (ph['caption'] ?? '现场照片') as String;
                    return Container(
                      width: 72,
                      height: 72,
                      decoration: BoxDecoration(
                        color: _cardBg,
                        borderRadius: BorderRadius.circular(6),
                        border: Border.all(color: _border),
                      ),
                      child: url.isNotEmpty
                          ? ClipRRect(
                              borderRadius: BorderRadius.circular(6),
                              child: Image.network(
                                url,
                                fit: BoxFit.cover,
                                errorBuilder: (_, __, ___) =>
                                    _photoPlaceholder(caption),
                              ),
                            )
                          : _photoPlaceholder(caption),
                    );
                  }).toList(),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _photoPlaceholder(String caption) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.image, size: 24, color: _textMuted),
          const SizedBox(height: 2),
          Text(
            caption.length > 6 ? '${caption.substring(0, 6)}…' : caption,
            style: const TextStyle(fontSize: 9, color: _textMuted),
          ),
        ],
      ),
    );
  }

  // ═══════════════════════════════════════════
  // 5. 审批卡片
  // ═══════════════════════════════════════════
  Widget _buildApprovalCard() {
    final p = message.payload ?? {};
    final agentInfo = message.agentInfo ?? AgentInfo.getByKey('master');
    final title = (p['title'] ?? '') as String;
    final problem = p['problem'] as String?;
    final impactCost = p['impact_cost'];
    final impactDays = p['impact_days'];
    final detail = p['detail'] as String?;
    final approvalId = p['id'] as String?;

    return _wrapCard(
      agentInfo: agentInfo,
      title: '⚠ 待决策 · ${_esc(title)}',
      borderColor: _accent,
      children: [
        if (problem != null) _row('问题', problem, boldValue: true),
        if (impactCost != null)
          _row('预算影响', '+¥${_fmtNum(impactCost)}',
              boldValue: true, valueColor: _warning),
        if (impactDays != null)
          _row('工期影响', '+$impactDays 天', boldValue: true),
        if (detail != null)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text(_esc(detail),
                style: const TextStyle(fontSize: 11, color: _textSecondary)),
          ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: _actionButton('同意', _success,
                  () => onApprovalAction?.call('approve', {'id': approvalId})),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: _actionButton('整改', _danger,
                  () => onApprovalAction?.call('reject', {'id': approvalId})),
            ),
          ],
        ),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 6. 文档卡片
  // ═══════════════════════════════════════════
  Widget _buildDocumentCard() {
    final f = message.payload ?? {};
    final agentInfo = message.agentInfo ?? AgentInfo.getByKey('design');
    return _wrapCard(
      agentInfo: agentInfo,
      title: '📎 ${_esc(f['name'] ?? '文档')}',
      children: [
        if (f['size'] != null) _row('大小', _esc(f['size']), boldValue: true),
        const SizedBox(height: 4),
        GestureDetector(
          onTap: () => onCardAction?.call('open_url', {'url': f['url']}),
          child: const Text('查看 →',
              style: TextStyle(fontSize: 11, color: _accent)),
        ),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 7. 预算卡片
  // ═══════════════════════════════════════════
  Widget _buildBudgetCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('budget');
    final total = _num(p['total']);
    final spent = _num(p['spent']);
    final remaining = _num(p['remaining']);
    final note = p['note'] as String?;
    final percent = total > 0 ? (spent / total * 100).round() : 0;

    return _wrapCard(
      agentInfo: agentInfo,
      title: '📊 预算概览',
      children: [
        _row('总预算', '¥${_fmtNum(total)}', boldValue: true),
        _row('已支出', '¥${_fmtNum(spent)}（${percent}%）', boldValue: true),
        _row('剩余', '¥${_fmtNum(remaining)}',
            boldValue: true, valueColor: _success),
        const SizedBox(height: 6),
        _progressBar(percent),
        if (note != null && note.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(_esc(note),
                style: const TextStyle(fontSize: 10, color: _textMuted)),
          ),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 8. 支付进度卡片
  // ═══════════════════════════════════════════
  Widget _buildPaymentCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('settlement');
    final stages = (p['stages'] ?? p['schedule'] as List?) ?? [];
    final totalPaid = _num(p['total_paid'] ?? 0);
    final totalAmount = _num(p['total_amount'] ?? 0);
    final invoiceCount = p['invoice_count'];
    final invoicedAmount = _num(p['invoiced_amount']);
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
      'paid': _success,
      'partial': _warning,
      'pending': _textMuted,
      'overdue': _danger,
    };

    return _wrapCard(
      agentInfo: agentInfo,
      title: '💳 支付进度',
      children: [
        _row('已付', '¥${_fmtNum(totalPaid)}',
            boldValue: true, valueColor: _success),
        _row('总额', '¥${_fmtNum(totalAmount)}', boldValue: true),
        _row('进度', '$percent%', boldValue: true),
        const SizedBox(height: 4),
        _progressBar(percent),
        if (stages.isNotEmpty) ...[
          const SizedBox(height: 8),
          const Divider(color: _border, height: 1),
          const SizedBox(height: 4),
          ...stages.map((st) {
            final stageCode = (st['stage_code'] ?? st['milestone_code'] ?? '')
                .toString();
            final label = stageLabels[stageCode] ??
                (stageCode.isNotEmpty ? stageCode : '阶段');
            final status = (st['status'] ?? 'pending').toString();
            final paid = _num(st['paid_amount']);
            final ttl = _num(st['total_amount']);
            final stagePct = ttl > 0 ? (paid / ttl * 100).round() : 0;
            final icon = statusIcons[status] ?? Icons.radio_button_unchecked;
            final iconColor = statusColors[status] ?? _textMuted;

            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 2),
              child: Row(
                children: [
                  Icon(icon, size: 14, color: iconColor),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(_esc(label),
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                            fontSize: 12, color: _textPrimary)),
                  ),
                  const SizedBox(width: 6),
                  Text('¥${_fmtNum(paid)} / ¥${_fmtNum(ttl)}',
                      style: const TextStyle(fontSize: 11, color: _textSecondary)),
                  const SizedBox(width: 6),
                  Text('$stagePct%',
                      style: const TextStyle(fontSize: 11, color: _textMuted)),
                ],
              ),
            );
          }),
        ],
        if (invoiceCount != null)
          _row('已开票',
              '$invoiceCount 张 · ¥${_fmtNum(invoicedAmount)}', boldValue: true),
        if (note != null && note.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(_esc(note),
                style: const TextStyle(fontSize: 10, color: _textMuted)),
          ),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 9. 比价卡片
  // ═══════════════════════════════════════════
  Widget _buildQuoteCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('procurement');
    final quotes = (p['quotes'] as List?) ?? [];
    final recommendation = p['recommendation'] as String?;

    return _wrapCard(
      agentInfo: agentInfo,
      title: '🛒 ${_esc(p['product'] ?? '比价报告')}',
      children: [
        ...quotes.map((q) {
          final supplier = (q['supplier'] ?? '') as String;
          final price = _num(q['price']);
          final isRec = q['recommended'] == true;
          return _row(supplier, '¥${_fmtNum(price)}${isRec ? ' ⭐' : ''}',
              boldValue: true);
        }),
        if (recommendation != null)
          _row('推荐', _esc(recommendation),
              boldValue: true, valueColor: _accent),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 10. BOM 物料清单
  // ═══════════════════════════════════════════
  Widget _buildBomCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('procurement');
    final items = (p['items'] as List?) ?? [];
    final totalPrice = _num(p['total_price']);
    final projectId = p['project_id'] as String?;

    return _wrapCard(
      agentInfo: agentInfo,
      title: '📦 ${_esc(p['title'] ?? 'BOM 物料清单')}',
      children: [
        if (items.isEmpty)
          _row('暂无物料', '', boldValue: true)
        else ...[
          ...items.take(8).toList().asMap().entries.map((entry) {
            final idx = entry.key;
            final it = entry.value;
            final mat = it['material'] as Map<String, dynamic>? ?? {};
            final cat = mat['category'] as Map<String, dynamic>? ?? {};
            final name = mat['name'] ?? mat['sku'] ?? '物料';
            final catName = cat['name'] ?? cat['code'] ?? '';
            final qty = it['quantity'];
            final unit = mat['unit'] ?? '';
            final itemPrice = _num(it['total_price']);
            return _row(
              '${idx + 1}. ${_esc(name)} ${catName.isNotEmpty ? "[$catName]" : ""}',
              '×$qty ${_esc(unit)} · ¥${_fmtNum(itemPrice)}',
              boldValue: true,
            );
          }),
          if (items.length > 8)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text('… 共 ${items.length} 项',
                  style: const TextStyle(fontSize: 10, color: _textMuted)),
            ),
        ],
        _row('合计', '¥${_fmtNum(totalPrice)}',
            boldValue: true, valueColor: _warning),
        if (projectId != null)
          GestureDetector(
            onTap: () => onCardAction
                ?.call('export_bom', {'project_id': projectId}),
            child: const Padding(
              padding: EdgeInsets.only(top: 4),
              child: Text('📥 导出 Excel',
                  style: TextStyle(fontSize: 11, color: _accent)),
            ),
          ),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 11. 采购订单
  // ═══════════════════════════════════════════
  Widget _buildOrderCard() {
    final o = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('procurement');
    final lines = (o['lines'] as List?) ?? [];
    final totalAmount = _num(o['total_amount']);
    final status = (o['status'] ?? 'draft').toString();
    final note = o['note'] as String?;
    final supplierName = o['supplier_name'] as String?;
    final orderId = o['id'] as String?;

    const statusMap = {
      'draft': '草稿',
      'pending': '待确认',
      'confirmed': '已确认',
      'shipped': '已发货',
      'delivered': '已送达',
      'completed': '已完成',
      'cancelled': '已取消',
    };
    final statusText = statusMap[status] ?? status;

    return _wrapCard(
      agentInfo: agentInfo,
      title:
          '🛍️ 采购订单${orderId != null ? " #${orderId.toString().substring(0, orderId.length < 8 ? orderId.length : 8)}" : ""}',
      children: [
        if (supplierName != null)
          _row('供应商', _esc(supplierName), boldValue: true),
        ...lines.asMap().entries.map((entry) {
          final l = entry.value;
          return _row(
            '${entry.key + 1}. ${_esc(l['material_name'] ?? l['material_id'] ?? '物料')}',
            '×${l['quantity']} · ¥${_fmtNum(_num(l['total_price']))}',
            boldValue: true,
          );
        }),
        _row('合计', '¥${_fmtNum(totalAmount)}',
            boldValue: true, valueColor: _warning),
        _row('状态', _esc(statusText),
            boldValue: true, valueColor: _orderStatusColor(status)),
        if (note != null && note.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(_esc(note),
                style: const TextStyle(fontSize: 10, color: _textMuted)),
          ),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 12. 采购订单列表
  // ═══════════════════════════════════════════
  Widget _buildOrderListCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('procurement');
    final orders = (p['orders'] as List?) ?? [];
    if (orders.isEmpty) return const SizedBox.shrink();

    return _wrapCard(
      agentInfo: agentInfo,
      title: '📋 采购订单列表',
      children: [
        ...orders.take(5).map((o) {
          final orderId = o['id']?.toString() ?? '';
          final shortId = orderId.length > 8
              ? orderId.substring(0, 8)
              : orderId;
          final supplier = o['supplier_name'] as String?;
          final amount = _num(o['total_amount']);
          final status = (o['status'] ?? 'draft').toString();
          const statusMap = {
            'draft': '草稿',
            'pending': '待确认',
            'confirmed': '已确认',
            'shipped': '已发货',
            'delivered': '已送达',
            'completed': '已完成',
            'cancelled': '已取消',
          };
          return _row(
            '#$shortId${supplier != null ? " · $supplier" : ""}',
            '¥${_fmtNum(amount)} · ${statusMap[status] ?? status}',
            boldValue: true,
            valueColor: _orderStatusColor(status),
          );
        }),
        if (orders.length > 5)
          Text('… 共 ${orders.length} 个订单',
              style: const TextStyle(fontSize: 10, color: _textMuted)),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 13. 担保支付
  // ═══════════════════════════════════════════
  Widget _buildEscrowCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('procurement');
    final totalAmount = _num(p['total_amount']);
    final escrowFee = _num(p['escrow_fee']);
    final status = (p['status'] ?? 'pending').toString();
    final escrowNo = p['escrow_no'] as String?;
    final disputeReason = p['dispute_reason'] as String?;

    const statusLabels = {
      'pending': '待付款',
      'buyer_paid': '买家已付款',
      'supplier_received': '已释放给供应商',
      'refunded': '已退款',
      'disputed': '争议中',
    };

    return _wrapCard(
      agentInfo: agentInfo,
      title: '🛡 担保支付 · ${_esc(escrowNo ?? '')}',
      children: [
        _row('订单金额', '¥${_fmtNum(totalAmount)}', boldValue: true),
        _row('担保手续费', '¥${_fmtNum(escrowFee)}', boldValue: true),
        _row('状态', _esc(statusLabels[status] ?? status),
            boldValue: true, valueColor: _escrowStatusColor(status)),
        if (disputeReason != null)
          _row('争议原因', _esc(disputeReason), boldValue: true),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 14. 物流追踪
  // ═══════════════════════════════════════════
  Widget _buildLogisticsCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('procurement');
    final trackingNo = p['tracking_no'] as String?;
    final carrier = p['carrier'] as String?;
    final shipFrom = p['ship_from'] as String?;
    final shipTo = p['ship_to'] as String?;
    final status = (p['status'] ?? 'pending').toString();
    final history = p['tracking_history'] as List?;

    const carrierLabels = {
      'sf_express': '顺丰',
      'yt_express': '圆通',
      'zto': '中通',
      'sto': '申通',
      'jd_logistics': '京东物流',
      'debon': '德邦',
      'self_delivery': '自送',
    };
    const statusLabels = {
      'pending': '待发货',
      'shipped': '已发货',
      'in_transit': '运输中',
      'delivered': '已签收',
      'exception': '异常',
    };

    return _wrapCard(
      agentInfo: agentInfo,
      title: '🚚 物流追踪 · ${_esc(trackingNo ?? '')}',
      children: [
        _row('承运商', _esc(carrierLabels[carrier] ?? carrier ?? ''),
            boldValue: true),
        if (shipFrom != null) _row('发货地', _esc(shipFrom), boldValue: true),
        if (shipTo != null) _row('收货地', _esc(shipTo), boldValue: true),
        _row('状态', _esc(statusLabels[status] ?? status),
            boldValue: true, valueColor: _accent),
        if (history != null && history.isNotEmpty) ...[
          const SizedBox(height: 4),
          const Divider(color: _border, height: 1),
          const SizedBox(height: 4),
          ...history.reversed.take(3).map((h) {
            return _row(
              _esc(h['location'] ?? '—'),
              _esc(h['description'] ?? h['status'] ?? ''),
              boldValue: true,
            );
          }),
        ],
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 15. 样品索要
  // ═══════════════════════════════════════════
  Widget _buildSampleCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('procurement');
    final status = (p['status'] ?? 'requested').toString();
    final sampleType = p['sample_type'] as String?;
    final materialName = p['material_name'] as String?;
    final notes = p['notes'] as String?;

    const statusLabels = {
      'requested': '已申请',
      'shipped': '已寄出',
      'received': '已收到',
      'rejected': '已拒绝',
    };

    return _wrapCard(
      agentInfo: agentInfo,
      title: '🎨 样品索要 · ${_esc(sampleType ?? '实物')}',
      children: [
        if (materialName != null)
          _row('物料', _esc(materialName), boldValue: true),
        _row('状态', _esc(statusLabels[status] ?? status),
            boldValue: true, valueColor: _sampleStatusColor(status)),
        if (notes != null) _row('备注', _esc(notes), boldValue: true),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 16. 结算卡片
  // ═══════════════════════════════════════════
  Widget _buildSettlementCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('settlement');
    final lines = (p['lines'] as List?) ?? [];
    final contractAmount = _num(p['contract_amount']);
    final actualAmount = _num(p['actual_amount']);
    final payableAmount = _num(p['payable_amount']);
    final status = (p['status'] ?? 'draft').toString();
    final reviewRequired = p['review_required'] == true;
    final anomalyCount = p['anomaly_count'];
    final criticalAnomalyCount = p['critical_anomaly_count'];
    final suggestedDeduction = _num(p['suggested_deduction']);
    final projectId = p['project_id'] as String?;
    final milestone = p['milestone'] as String?;

    const statusTexts = {
      'draft': '草稿',
      'confirmed': '已确认',
      'review': '待复核',
      'flagged': '已标记异常',
    };

    return _wrapCard(
      agentInfo: agentInfo,
      title:
          '🧾 结算单 · ${_esc(milestone ?? 'completion')} · ${_esc(statusTexts[status] ?? status)}',
      children: [
        _row('合同金额', '¥${_fmtNum(contractAmount)}', boldValue: true),
        _row('实际金额', '¥${_fmtNum(actualAmount)}', boldValue: true),
        _row('应付金额', '¥${_fmtNum(payableAmount)}',
            boldValue: true, valueColor: _accent),
        if (criticalAnomalyCount != null && criticalAnomalyCount > 0)
          _row('异常', '$criticalAnomalyCount 严重 / $anomalyCount 总',
              boldValue: true, valueColor: _warning)
        else if (anomalyCount != null && anomalyCount > 0)
          _row('异常', '$anomalyCount 警告', boldValue: true),
        if (suggestedDeduction > 0)
          _row('建议扣款', '-¥${_fmtNum(suggestedDeduction)}',
              boldValue: true, valueColor: _warning),
        if (reviewRequired)
          _row('复核状态', '⚠ 需人工复核',
              boldValue: true, valueColor: _warning),
        if (lines.isNotEmpty) ...[
          const SizedBox(height: 6),
          const Divider(color: _border, height: 1),
          const SizedBox(height: 6),
          ...lines.take(6).toList().asMap().entries.map((entry) {
            final it = entry.value;
            final name = it['name'] ?? '未命名';
            final amt = _num(it['actual_amount'] ?? it['contract_amount']);
            final isAnomaly = it['is_anomaly'] == true;
            final anomalyType = it['anomaly_type'] as String?;
            final variance =
                _num(it['actual_amount']) - _num(it['contract_amount']) - _num(it['change_amount']);
            return _row(
              '${entry.key + 1}. ${_esc(name)}${isAnomaly ? " ⚠${anomalyType ?? '异常'}" : ""}${variance != 0 ? " 偏差 ¥${_fmtNum(variance)}" : ""}',
              '¥${_fmtNum(amt)}',
              boldValue: true,
            );
          }),
          if (lines.length > 6)
            Text('… 共 ${lines.length} 项',
                style: const TextStyle(fontSize: 10, color: _textMuted)),
        ],
        if (projectId != null) ...[
          const SizedBox(height: 4),
          GestureDetector(
            onTap: () => onCardAction
                ?.call('export_settlement', {'project_id': projectId}),
            child: const Text('📤 导出对账单',
                style: TextStyle(fontSize: 11, color: _accent)),
          ),
        ],
        if ((status == 'draft' || status == 'flagged') &&
            !reviewRequired &&
            projectId != null)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: _actionButton('确认结算', _success,
                () => onCardAction?.call('confirm_settlement', {'project_id': projectId})),
          ),
        if (reviewRequired && projectId != null)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: _actionButton('通过复核', _accent,
                () => onCardAction?.call('approve_review', {'project_id': projectId})),
          ),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 17. 里程碑结算
  // ═══════════════════════════════════════════
  Widget _buildMilestoneCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('settlement');
    final contractAmount = _num(p['contract_amount']);
    final paymentRatio = _num(p['payment_ratio']);
    final basePayable = _num(p['base_payable']);
    final changeAmount = _num(p['change_amount']);
    final deductionAmount = _num(p['deduction_amount']);
    final paidAmount = _num(p['paid_amount']);
    final totalPayable = _num(p['total_payable']);
    final description = p['description'] as String?;

    final ratioPct = (paymentRatio * 100).round();

    return _wrapCard(
      agentInfo: agentInfo,
      title: '🧾 ${_esc(p['milestone_name'] ?? '里程碑结算')}',
      children: [
        _row('合同金额', '¥${_fmtNum(contractAmount)}', boldValue: true),
        _row('付款比例', '$ratioPct%', boldValue: true),
        _row('基础应付', '¥${_fmtNum(basePayable)}', boldValue: true),
        if (changeAmount != 0)
          _row('变更', '+¥${_fmtNum(changeAmount)}', boldValue: true),
        if (deductionAmount != 0)
          _row('扣款', '-¥${_fmtNum(deductionAmount)}',
              boldValue: true, valueColor: _warning),
        if (paidAmount != 0)
          _row('已付', '-¥${_fmtNum(paidAmount)}', boldValue: true),
        _row('本次应付', '¥${_fmtNum(totalPayable)}',
            boldValue: true, valueColor: _accent),
        if (description != null && description.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(_esc(description),
                style: const TextStyle(fontSize: 10, color: _textMuted)),
          ),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 18. 任务申领
  // ═══════════════════════════════════════════
  Widget _buildTaskClaimCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('master');
    final title = p['title'] as String? ?? '任务待分配';
    final description = p['description'] as String?;
    final claimRole = p['claim_role'] as String?;
    final projectName = p['project_name'] as String?;
    final candidates = (p['candidates'] as List?) ?? [];
    final claimDeadline = p['claim_deadline'] as String?;
    final taskId = p['task_id'] as String?;

    const roleLabels = {
      'designer': '设计师',
      'contractor': '工长',
      'supplier': '供应商',
    };

    return _wrapCard(
      agentInfo: agentInfo,
      title: '📋 ${_esc(title)}',
      borderColor: _accent,
      children: [
        if (description != null && description.isNotEmpty)
          _row('描述', _esc(description), boldValue: true),
        _row('任务类型', _esc(roleLabels[claimRole] ?? claimRole ?? '未知'),
            boldValue: true),
        _row('项目', _esc(projectName ?? '—'), boldValue: true),
        _row('申领人数', '${candidates.length}人', boldValue: true),
        if (candidates.isNotEmpty) ...[
          const SizedBox(height: 6),
          const Divider(color: _border, height: 1),
          const SizedBox(height: 4),
          ..._sortedCandidates(candidates)
              .asMap()
              .entries
              .map((entry) {
            final idx = entry.key;
            final c = entry.value;
            final medals = ['🥇', '🥈', '🥉'];
            final medal = idx < 3 ? medals[idx] : '${idx + 1}';
            final breakdown = c['score_breakdown'] as Map<String, dynamic>? ?? {};
            final userName = c['user_name'] ?? '候选人';
            final userId = c['user_id'] as String?;
            final rating = (c['rating_score'] ?? 0).toDouble();
            final points = breakdown['points'] ?? 0;
            final exp = breakdown['experience_years'] ?? 0;
            final completed = breakdown['completed_projects'] ?? 0;

            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                children: [
                  Text(medal, style: const TextStyle(fontSize: 14)),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(_esc(userName),
                            style: const TextStyle(
                                fontSize: 13, color: _textPrimary,
                                fontWeight: FontWeight.w600)),
                        Text(
                          '⭐ ${rating.toStringAsFixed(1)}  积分$points  经验${exp}年  完成${completed}个',
                          style: const TextStyle(
                              fontSize: 11, color: _textSecondary),
                        ),
                      ],
                    ),
                  ),
                  SizedBox(
                    height: 28,
                    child: ElevatedButton(
                      onPressed: () => onCardAction?.call('select_candidate', {
                        'candidate_id': userId,
                        'task_id': taskId,
                      }),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: _accent,
                        padding: const EdgeInsets.symmetric(horizontal: 10),
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(6)),
                      ),
                      child: const Text('选择',
                          style: TextStyle(fontSize: 11, color: Colors.black)),
                    ),
                  ),
                ],
              ),
            );
          }),
        ],
        if (claimDeadline != null)
          _row('截止', _esc(claimDeadline), boldValue: true),
      ],
    );
  }

  List<dynamic> _sortedCandidates(List candidates) {
    final list = List<dynamic>.from(candidates);
    list.sort((a, b) {
      final sa = a['composite_score'] ?? 0.0;
      final sb = b['composite_score'] ?? 0.0;
      return (sb as num).compareTo(sa as num);
    });
    return list;
  }

  // ═══════════════════════════════════════════
  // 19. 产品卡片
  // ═══════════════════════════════════════════
  Widget _buildProductCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('procurement');
    final tags = (p['tags'] as List?) ?? [];
    final productId = p['product_id'] as String?;

    return _wrapCard(
      agentInfo: agentInfo,
      title: '📦 ${_esc(p['name'] ?? '产品')}',
      children: [
        _row('类别', _esc(p['category'] ?? '—'), boldValue: true),
        if (p['price_range'] != null)
          _row('价格', _esc(p['price_range']),
              boldValue: true, valueColor: _warning),
        if (p['description'] != null)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Text(_esc(p['description']),
                style:
                    const TextStyle(fontSize: 12, color: _textPrimary, height: 1.4)),
          ),
        if (tags.isNotEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Wrap(
              spacing: 6,
              runSpacing: 4,
              children: tags
                  .map((t) => Text(
                        '#${_esc(t.toString())}',
                        style: const TextStyle(
                            fontSize: 11, color: _accent),
                      ))
                  .toList(),
            ),
          ),
        if (p['supplier_name'] != null)
          _row('供应商', _esc(p['supplier_name']), boldValue: true),
        const SizedBox(height: 6),
        Row(
          children: [
            Expanded(
              child: _actionButton('确认发布', _success,
                  () => onCardAction?.call('publish_product', {'product_id': productId})),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: OutlinedButton(
                onPressed: () =>
                    onCardAction?.call('edit_product', {'product_id': productId}),
                style: OutlinedButton.styleFrom(
                  side: const BorderSide(color: _border),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8)),
                  padding: const EdgeInsets.symmetric(vertical: 8),
                ),
                child: const Text('编辑',
                    style: TextStyle(fontSize: 12, color: _textSecondary)),
              ),
            ),
          ],
        ),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 20. 总控任务协调
  // ═══════════════════════════════════════════
  Widget _buildOrchestratorTaskCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('master');
    final status = (p['status'] ?? 'pending').toString();

    const statusMap = {
      'pending': ('待处理', _textMuted),
      'claimed': ('已申领', _accent),
      'in_progress': ('进行中', _warning),
      'completed': ('已完成', _success),
      'failed': ('失败', _danger),
    };
    final s = statusMap[status] ?? (status, _textMuted);

    return _wrapCard(
      agentInfo: agentInfo,
      title: '🔗 ${_esc(p['title'] ?? '任务更新')}',
      children: [
        _row('任务类型', _esc(p['task_type'] ?? '—'), boldValue: true),
        _row('状态', _esc(s.$1), boldValue: true, valueColor: s.$2),
        if (p['assigned_user_name'] != null)
          _row('负责人', _esc(p['assigned_user_name']), boldValue: true),
        if (p['priority'] != null)
          _row('优先级', '⭐' * (p['priority'] as int).clamp(0, 5),
              boldValue: true),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 21. 积分卡片
  // ═══════════════════════════════════════════
  Widget _buildPointsCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('master');
    final level = p['level'] as String?;

    const levelMap = {
      'bronze': ('🥉 铜牌', Color(0xFFCD7F32)),
      'silver': ('🥈 银牌', Color(0xFFC0C0C0)),
      'gold': ('🥇 金牌', Color(0xFFFFD700)),
      'platinum': ('💎 铂金', Color(0xFFE5E4E2)),
      'diamond': ('👑 钻石', Color(0xFFB9F2FF)),
    };
    final lvl = levelMap[level] ?? (level ?? '—', _textSecondary);

    return _wrapCard(
      agentInfo: agentInfo,
      title: '💰 积分信息',
      children: [
        Row(
          children: [
            Text(_esc(lvl.$1),
                style: TextStyle(
                    fontSize: 14,
                    color: lvl.$2,
                    fontWeight: FontWeight.bold)),
          ],
        ),
        const SizedBox(height: 4),
        _row('当前积分', _fmtNum(p['balance'] ?? 0),
            boldValue: true, valueColor: _accent),
        _row('累计获得', _fmtNum(p['total_earned'] ?? 0), boldValue: true),
        _row('年度获得', _fmtNum(p['year_earned'] ?? 0), boldValue: true),
        if (p['rank'] != null)
          _row('年度排名', '第${p['rank']}名', boldValue: true),
        if (p['description'] != null)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(_esc(p['description']),
                style:
                    const TextStyle(fontSize: 12, color: _textPrimary, height: 1.4)),
          ),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 22. 营销叙事卡片
  // ═══════════════════════════════════════════
  Widget _buildNarrativeCard() {
    final p = message.payload ?? {};
    final variant = (p['variant'] ?? 'brand').toString();
    final tag = p['tag'] as String? ?? '演示';
    final senderName = p['display_name'] as String? ?? '🏠 索克家居';
    final title = (p['title'] ?? '') as String;
    final body = p['body'] as String?;
    final ctaText = p['cta_text'] as String?;
    final ctaAction = p['cta_action'] as String?;
    final ctaHref = p['cta_href'] as String?;

    if (variant == 'stat') {
      return _wrapCard(
        agentInfo: AgentInfo.getByKey('master'),
        displayName: senderName,
        title: _esc(title),
        prelude: Text(_esc(tag),
            style: const TextStyle(fontSize: 10, color: _accent)),
        children: [
          if (p['stat_value'] != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Text(_esc(p['stat_value']),
                  style: const TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.bold,
                      color: _accent)),
            ),
          if (p['stat_label'] != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Text(_esc(p['stat_label']),
                  style:
                      const TextStyle(fontSize: 12, color: _textSecondary)),
            ),
          if (body != null && body.isNotEmpty)
            Text(_esc(body),
                style:
                    const TextStyle(fontSize: 13, color: _textPrimary, height: 1.4)),
        ],
      );
    }

    if (variant == 'cta') {
      return _wrapCard(
        agentInfo: AgentInfo.getByKey('master'),
        displayName: senderName,
        title: _esc(title),
        prelude: Text(_esc(tag),
            style: const TextStyle(fontSize: 10, color: _accent)),
        children: [
          if (body != null && body.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text(_esc(body),
                  style: const TextStyle(
                      fontSize: 13, color: _textPrimary, height: 1.4)),
            ),
          if (ctaText != null)
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () => onCardAction?.call('narrative_cta', {
                  'action': ctaAction,
                  'href': ctaHref,
                }),
                style: ElevatedButton.styleFrom(
                  backgroundColor: _accent,
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8)),
                  padding: const EdgeInsets.symmetric(vertical: 10),
                ),
                child: Text(_esc(ctaText),
                    style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: Colors.black)),
              ),
            ),
        ],
      );
    }

    // brand (default)
    final agents = p['agents'] as List?;

    return _wrapCard(
      agentInfo: AgentInfo.getByKey('master'),
      displayName: senderName,
      title: _esc(title),
      prelude: Text(_esc(tag),
          style: const TextStyle(fontSize: 10, color: _accent)),
      children: [
        if (body != null && body.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Text(_esc(body),
                style: const TextStyle(
                    fontSize: 13, color: _textPrimary, height: 1.4)),
          ),
        if (agents != null && agents.isNotEmpty)
          Wrap(
            spacing: 6,
            runSpacing: 4,
            children: agents.map((a) {
              final info = AgentInfo.getByKey(a.toString());
              return Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  border: Border.all(color: info.color, width: 1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text('${info.emoji} ${info.name}',
                    style: TextStyle(fontSize: 11, color: info.color)),
              );
            }).toList(),
          ),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 23. 质检报告卡片 (F38)
  // ═══════════════════════════════════════════
  Widget _buildInspectionCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('quality');
    final status = (p['status'] ?? p['result'] ?? 'pending').toString();
    final checkItem = p['check_item'] ?? p['title'] ?? p['_task_name'] ?? '';
    final score = _num(p['score']);
    final deviation = p['deviation'];
    final deviationUnit = p['deviation_unit'] ?? 'cm';
    final summary = p['summary'] as String?;
    final recommendation = p['recommendation'] as String?;
    final photos = (p['photos'] ?? p['image_urls'] as List?) ?? [];
    final issues = p['issues'] as List?;

    const statusMap = {
      'passed': ('✅ 合格', _success),
      'failed': ('❌ 不合格', _danger),
      'needs_review': ('⚠️ 需复核', _warning),
      'pending': ('⏳ 待检测', _textMuted),
    };
    final s = statusMap[status] ?? ('❓ $status', _textMuted);

    return _wrapCard(
      agentInfo: agentInfo,
      title: '🔍 质检报告 · ${_esc(checkItem.toString())}',
      children: [
        _row('检测结果', _esc(s.$1), boldValue: true, valueColor: s.$2),
        if (score > 0) ...[
          _row('评分', '$score/100', boldValue: true),
          _progressBar(score.toInt()),
        ],
        if (deviation != null)
          _row('偏差',
              '${deviation.toString()}$deviationUnit',
              boldValue: true,
              valueColor: _num(deviation) > 5 ? _danger : _warning),
        if (summary != null && summary.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text(_esc(summary),
                style:
                    const TextStyle(fontSize: 11, color: _textSecondary)),
          ),
        if (photos.isNotEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: Wrap(
              spacing: 6, runSpacing: 6,
              children: photos.map((url) {
                return Container(
                  width: 56, height: 56,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: _border),
                  ),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(6),
                    child: Image.network(
                      url.toString(),
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) =>
                          const Icon(Icons.broken_image, size: 20, color: _textMuted),
                    ),
                  ),
                );
              }).toList(),
            ),
          ),
        if (issues != null && issues.isNotEmpty) ...[
          const Divider(color: _border, height: 1),
          ...issues.asMap().entries.map((entry) {
            final iss = entry.value as Map<String, dynamic>;
            final sevColors = {
              'critical': _danger, 'major': _warning,
              'minor': _textSecondary, 'info': _textMuted,
            };
            final sevColor = sevColors[iss['severity']?.toString()] ?? _textMuted;
            return _row(
              '${entry.key + 1}. ${_esc(iss['description'] ?? iss['name'] ?? '')}',
              _esc(iss['severity']?.toString() ?? ''),
              boldValue: true, valueColor: sevColor,
            );
          }),
        ],
        if (recommendation != null && recommendation.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text('💡 ${_esc(recommendation)}',
                style: const TextStyle(fontSize: 10, color: _accent)),
          ),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 24. 质量问题清单卡片 (F38)
  // ═══════════════════════════════════════════
  Widget _buildQualityIssueCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('quality');
    final issues = (p['issues'] ?? p['items'] as List?) ?? [];
    if (issues.isEmpty) return const SizedBox.shrink();

    const sevIcons = {
      'critical': '🔴', 'major': '🟠', 'minor': '🟡', 'info': '🔵',
    };
    const statusIcons = {
      'open': '⬜', 'in_progress': '🔄', 'resolved': '✅', 'closed': '✔️',
    };

    return _wrapCard(
      agentInfo: agentInfo,
      title: '⚠️ 质量问题清单 · ${issues.length} 项',
      children: [
        ...issues.take(6).toList().asMap().entries.map((entry) {
          final iss = entry.value as Map<String, dynamic>;
          final sev = iss['severity']?.toString() ?? '';
          final status = iss['status']?.toString() ?? 'open';
          return _row(
            '${sevIcons[sev] ?? '⚪'} ${entry.key + 1}. ${_esc(iss['description'] ?? iss['title'] ?? '问题')} ${statusIcons[status] ?? '⬜'}',
            _esc(iss['location'] ?? iss['area'] ?? ''),
            boldValue: true,
          );
        }),
        if (issues.length > 6)
          Text('… 共 ${issues.length} 个问题',
              style: const TextStyle(fontSize: 10, color: _textMuted)),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 25. 进度预警卡片 (F37)
  // ═══════════════════════════════════════════
  Widget _buildProgressAlertCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('construction');
    final alerts = (p['alerts'] ?? p['items'] as List?) ?? [];
    if (alerts.isEmpty) return const SizedBox.shrink();

    const sevColors = {
      'critical': _danger, 'high': _warning,
      'medium': _textSecondary, 'low': _textMuted,
    };

    return _wrapCard(
      agentInfo: agentInfo,
      title: '📡 进度预警 · ${alerts.length} 条',
      children: [
        ...alerts.take(5).map((a) {
          final sev = a['severity']?.toString() ?? '';
          return _row(
            _esc(a['message'] ?? a['description'] ?? a['task_name'] ?? ''),
            _esc(sev),
            boldValue: true,
            valueColor: sevColors[sev] ?? _textMuted,
          );
        }),
        if (alerts.length > 5)
          Text('… 共 ${alerts.length} 条预警',
              style: const TextStyle(fontSize: 10, color: _textMuted)),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 公共组件
  // ═══════════════════════════════════════════

  /// 带 Agent 顶部信息的卡片容器
  Widget _wrapCard({
    required AgentInfo agentInfo,
    String? displayName,
    required String title,
    Color? borderColor,
    Widget? prelude,
    required List<Widget> children,
  }) {
    final name =
        displayName ?? '${agentInfo.emoji} ${agentInfo.name} Agent';

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildMetaRow(name, false, agentInfo.color),
          const SizedBox(height: 6),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: _cardBg,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: borderColor ?? _border,
                width: borderColor != null ? 1.5 : 1,
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (prelude != null) prelude,
                Text(title,
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: _textPrimary,
                    )),
                const SizedBox(height: 8),
                ...children,
              ],
            ),
          ),
          // 协作链路
          if (message.collaboration case final collab?)
            if (collab.isNotEmpty) _buildCollabSection(),
        ],
      ),
    );
  }

  /// 协作链路区域
  Widget _buildCollabSection() {
    final links = message.collaboration!.map((c) {
      final info = AgentInfo.getByKey(c['agent']?.toString() ?? 'master');
      final action = c['action'] as String? ?? '';
      return '↳ 已 @${info.emoji} ${info.name} Agent $action';
    }).join('\n');

    return Container(
      margin: const EdgeInsets.only(top: 4),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: _cardBg,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: _border),
      ),
      child: Text(links,
          style: const TextStyle(fontSize: 11, color: _textSecondary)),
    );
  }

  /// 元信息行（发送者名称 + 时间）
  Widget _buildMetaRow(String name, bool isUser, Color? agentColor) {
    final timeStr = _fmtTime(message.timestamp);
    return Padding(
      padding: const EdgeInsets.only(left: 4, right: 4),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            name,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: isUser
                  ? _accent.withValues(alpha: 0.9)
                  : (agentColor ?? _textSecondary),
            ),
          ),
          const SizedBox(width: 6),
          Text(timeStr, style: const TextStyle(fontSize: 11, color: _textMuted)),
        ],
      ),
    );
  }

  /// 键值行
  Widget _row(String label, String value,
      {bool boldValue = false, Color? valueColor}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: [
          Expanded(
            flex: 2,
            child: Text(label,
                style: const TextStyle(fontSize: 12, color: _textSecondary)),
          ),
          Expanded(
            flex: 3,
            child: Text(
              value,
              style: TextStyle(
                fontSize: 12,
                color: valueColor ?? _textPrimary,
                fontWeight: boldValue ? FontWeight.w600 : FontWeight.normal,
              ),
              textAlign: TextAlign.right,
            ),
          ),
        ],
      ),
    );
  }

  /// 进度条
  Widget _progressBar(int percent) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(4),
      child: LinearProgressIndicator(
        value: percent.clamp(0, 100) / 100,
        minHeight: 6,
        backgroundColor: _border,
        valueColor: AlwaysStoppedAnimation<Color>(
          percent > 80
              ? _success
              : percent > 50
                  ? _accent
                  : _warning,
        ),
      ),
    );
  }

  /// 操作按钮
  Widget _actionButton(String label, Color color, VoidCallback? onTap) {
    return SizedBox(
      height: 34,
      child: ElevatedButton(
        onPressed: onTap,
        style: ElevatedButton.styleFrom(
          backgroundColor: color.withValues(alpha: 0.15),
          foregroundColor: color,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
            side: BorderSide(color: color, width: 1),
          ),
          padding: const EdgeInsets.symmetric(vertical: 6),
        ),
        child: Text(label,
            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
      ),
    );
  }

  // ── 工具方法 ──

  static num _num(dynamic v) {
    if (v is num) return v;
    if (v is String) return num.tryParse(v) ?? 0;
    return 0;
  }

  static String _fmtNum(dynamic v) {
    final n = _num(v);
    if (n == n.roundToDouble()) {
      return n.toStringAsFixed(0).replaceAllMapped(
          RegExp(r'\B(?=(\d{3})+(?!\d))'), (m) => ',');
    }
    return n.toStringAsFixed(2).replaceAllMapped(
        RegExp(r'\B(?=(\d{3})+(?!\d))'), (m) => ',');
  }

  static String _esc(String s) {
    return s
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
  }

  static String _fmtTime(DateTime? ts) {
    if (ts == null) return '';
    final h = ts.hour.toString().padLeft(2, '0');
    final m = ts.minute.toString().padLeft(2, '0');
    return '$h:$m';
  }

  static Color _orderStatusColor(String status) {
    switch (status) {
      case 'completed':
        return _success;
      case 'cancelled':
        return _danger;
      case 'shipped':
      case 'delivered':
        return _accent;
      default:
        return _warning;
    }
  }

  static Color _escrowStatusColor(String status) {
    switch (status) {
      case 'supplier_received':
        return _success;
      case 'refunded':
      case 'disputed':
        return _warning;
      default:
        return _accent;
    }
  }

  static Color _sampleStatusColor(String status) {
    switch (status) {
      case 'received':
        return _success;
      case 'rejected':
        return _warning;
      default:
        return _accent;
    }
  }
}
