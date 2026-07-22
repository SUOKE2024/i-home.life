import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../models/chat_message.dart';
import '../theme/suoke_theme.dart';

// F4: God Widget 拆分 — 采购/财务/设计域卡片渲染器抽取为 extension 文件
import 'chat_card_procurement.dart';
import 'chat_card_finance.dart';
import 'chat_card_design.dart';

/// 统一聊天消息卡片 —— 渲染全部消息类型
///
/// 参考 Web 端 message-renderers.js 的 HTML 结构和样式。
/// 颜色统一使用 [SuokeDesignTokens] 与 Web 端对齐。
/// v1.1.22: 补齐 18 种 v1.1.21 卡片 + 3 种硬件触发类型
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
  static const Color accent = SuokeDesignTokens.accent;
  static const Color textPrimary = SuokeDesignTokens.textPrimary;
  static const Color textSecondary = SuokeDesignTokens.textSecondary;
  static const Color textMuted = SuokeDesignTokens.textMuted;
  static const Color border = SuokeDesignTokens.border;
  static const Color success = SuokeDesignTokens.success;
  static const Color warning = SuokeDesignTokens.warning;
  static const Color danger = SuokeDesignTokens.danger;
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
        child = buildBudgetCard();
      case ChatMessageType.payment:
        child = buildPaymentCard();
      case ChatMessageType.quote:
        child = buildQuoteCard();
      case ChatMessageType.bom:
        child = buildBomCard();
      case ChatMessageType.procurement_order:
        child = buildOrderCard();
      case ChatMessageType.procurement_orders:
        child = buildOrderListCard();
      case ChatMessageType.escrow:
        child = buildEscrowCard();
      case ChatMessageType.logistics:
        child = buildLogisticsCard();
      case ChatMessageType.sample:
        child = buildSampleCard();
      case ChatMessageType.settlement:
        child = buildSettlementCard();
      case ChatMessageType.milestone_settlement:
        child = buildMilestoneCard();
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
      // v1.1.22: 补齐 13 种 Agent 专用卡片
      case ChatMessageType.kitchen_card: child = buildKitchenCard();
      case ChatMessageType.bathroom_card: child = buildBathroomCard();
      case ChatMessageType.lighting_card: child = buildLightingCard();
      case ChatMessageType.structural_card: child = buildStructuralCard();
      case ChatMessageType.takeoff_card: child = buildTakeoffCard();
      case ChatMessageType.furniture_card: child = buildFurnitureCard();
      case ChatMessageType.appliance_card: child = buildApplianceCard();
      case ChatMessageType.door_window_card: child = buildDoorWindowCard();
      case ChatMessageType.mep_plan_card: child = buildMepPlanCard();
      case ChatMessageType.identity_card: child = _buildIdentityCard();
      case ChatMessageType.voice_card: child = _buildVoiceCard();
      case ChatMessageType.ifc_export_card: child = _buildIfcExportCard();
      case ChatMessageType.notification_card: child = _buildNotificationCard();
      // v1.1.22: 硬件传感器触发卡片
      case ChatMessageType.camera_trigger: child = _buildCameraTriggerCard();
      case ChatMessageType.ar_scan_trigger: child = _buildArScanTriggerCard();
      case ChatMessageType.voice_input_trigger: child = _buildVoiceInputTriggerCard();
      // v1.1.22: 业务卡片补充
      case ChatMessageType.stats_card: child = _buildStatsCard();
      case ChatMessageType.user_card: child = _buildUserCard();
      case ChatMessageType.user_list_card: child = _buildUserListCard();
      case ChatMessageType.product_create_card: child = _buildProductCreateCard();
      case ChatMessageType.product_list_card: child = _buildProductListCard();
      case ChatMessageType.quotation_card: child = _buildQuotationCard();
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
      const PopupMenuItem<String>(
        value: 'copy',
        child: const Row(
          children: [
            Icon(Icons.copy, size: 18, color: textSecondary),
            SizedBox(width: 10),
            Text('复制', style: TextStyle(color: textPrimary, fontSize: 14)),
          ],
        ),
      ),
    ];

    if (isSelf) {
      items.add(
        const PopupMenuItem<String>(
          value: 'reply',
          child: const Row(
            children: [
              Icon(Icons.reply, size: 18, color: textSecondary),
              SizedBox(width: 10),
              Text('回复', style: TextStyle(color: textPrimary, fontSize: 14)),
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
        side: const BorderSide(color: border),
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
          border: Border.all(color: border.withValues(alpha: 0.4)),
        ),
        child: Text(
          message.content ?? '',
          style: const TextStyle(fontSize: 11, color: textMuted),
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
                color: border.withValues(alpha: 0.4),
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
                          cursorColor: leftBorderColor ?? accent,
                          style: const TextStyle(
                            fontSize: 14,
                            color: textPrimary,
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
          border: Border.all(color: border),
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

    return wrapCard(
      agentInfo: agentInfo,
      title: '📋 ${esc(title)}$progressLabel',
      children: [
        if (percent > 0) ...[
          const SizedBox(height: 2),
          progressBar(percent),
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
      color = success;
    } else if (isInProgress) {
      icon = Icons.more_horiz;
      color = warning;
    } else {
      icon = Icons.radio_button_unchecked;
      color = textMuted;
    }
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              esc(name),
              style: TextStyle(
                fontSize: 13,
                color: isDone ? textSecondary : textPrimary,
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
              border: Border.all(color: border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (note != null && note.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Text(esc(note),
                        style: const TextStyle(fontSize: 13, color: textPrimary)),
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
                        border: Border.all(color: border),
                      ),
                      child: url.isNotEmpty
                          ? ClipRRect(
                              borderRadius: BorderRadius.circular(6),
                              child: CachedNetworkImage(
                                imageUrl: url,
                                fit: BoxFit.cover,
                                placeholder: (context, url) =>
                                    _photoPlaceholder(caption),
                                errorWidget: (context, url, error) =>
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
          const Icon(Icons.image, size: 24, color: textMuted),
          const SizedBox(height: 2),
          Text(
            caption.length > 6 ? '${caption.substring(0, 6)}…' : caption,
            style: const TextStyle(fontSize: 9, color: textMuted),
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

    return wrapCard(
      agentInfo: agentInfo,
      title: '⚠ 待决策 · ${esc(title)}',
      borderColor: accent,
      children: [
        if (problem != null) row('问题', problem, boldValue: true),
        if (impactCost != null)
          row('预算影响', '+¥${fmtNum(impactCost)}',
              boldValue: true, valueColor: warning),
        if (impactDays != null)
          row('工期影响', '+$impactDays 天', boldValue: true),
        if (detail != null)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text(esc(detail),
                style: const TextStyle(fontSize: 11, color: textSecondary)),
          ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: actionButton('同意', success,
                  () => onApprovalAction?.call('approve', {'id': approvalId})),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: actionButton('整改', danger,
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
    return wrapCard(
      agentInfo: agentInfo,
      title: '📎 ${esc(f['name'] ?? '文档')}',
      children: [
        if (f['size'] != null) row('大小', esc(f['size']), boldValue: true),
        const SizedBox(height: 4),
        GestureDetector(
          onTap: () => onCardAction?.call('open_url', {'url': f['url']}),
          child: const Text('查看 →',
              style: TextStyle(fontSize: 11, color: accent)),
        ),
      ],
    );
  }

  // F4: 采购域卡片 (比价/BOM/订单/担保/物流/样品) → chat_card_procurement.dart
  // F4: 财务域卡片 (预算/支付/结算/里程碑) → chat_card_finance.dart

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

    return wrapCard(
      agentInfo: agentInfo,
      title: '📋 ${esc(title)}',
      borderColor: accent,
      children: [
        if (description != null && description.isNotEmpty)
          row('描述', esc(description), boldValue: true),
        row('任务类型', esc(roleLabels[claimRole] ?? claimRole ?? '未知'),
            boldValue: true),
        row('项目', esc(projectName ?? '—'), boldValue: true),
        row('申领人数', '${candidates.length}人', boldValue: true),
        if (candidates.isNotEmpty) ...[
          const SizedBox(height: 6),
          const Divider(color: border, height: 1),
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
                        Text(esc(userName),
                            style: const TextStyle(
                                fontSize: 13, color: textPrimary,
                                fontWeight: FontWeight.w600)),
                        Text(
                          '⭐ ${rating.toStringAsFixed(1)}  积分$points  经验${exp}年  完成${completed}个',
                          style: const TextStyle(
                              fontSize: 11, color: textSecondary),
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
                        backgroundColor: accent,
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
          row('截止', esc(claimDeadline), boldValue: true),
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

    return wrapCard(
      agentInfo: agentInfo,
      title: '📦 ${esc(p['name'] ?? '产品')}',
      children: [
        row('类别', esc(p['category'] ?? '—'), boldValue: true),
        if (p['price_range'] != null)
          row('价格', esc(p['price_range']),
              boldValue: true, valueColor: warning),
        if (p['description'] != null)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Text(esc(p['description']),
                style:
                    const TextStyle(fontSize: 12, color: textPrimary, height: 1.4)),
          ),
        if (tags.isNotEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Wrap(
              spacing: 6,
              runSpacing: 4,
              children: tags
                  .map((t) => Text(
                        '#${esc(t.toString())}',
                        style: const TextStyle(
                            fontSize: 11, color: accent),
                      ))
                  .toList(),
            ),
          ),
        if (p['supplier_name'] != null)
          row('供应商', esc(p['supplier_name']), boldValue: true),
        const SizedBox(height: 6),
        Row(
          children: [
            Expanded(
              child: actionButton('确认发布', success,
                  () => onCardAction?.call('publish_product', {'product_id': productId})),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: OutlinedButton(
                onPressed: () =>
                    onCardAction?.call('edit_product', {'product_id': productId}),
                style: OutlinedButton.styleFrom(
                  side: const BorderSide(color: border),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8)),
                  padding: const EdgeInsets.symmetric(vertical: 8),
                ),
                child: const Text('编辑',
                    style: TextStyle(fontSize: 12, color: textSecondary)),
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
      'pending': ('待处理', textMuted),
      'claimed': ('已申领', accent),
      'in_progress': ('进行中', warning),
      'completed': ('已完成', success),
      'failed': ('失败', danger),
    };
    final s = statusMap[status] ?? (status, textMuted);

    return wrapCard(
      agentInfo: agentInfo,
      title: '🔗 ${esc(p['title'] ?? '任务更新')}',
      children: [
        row('任务类型', esc(p['task_type'] ?? '—'), boldValue: true),
        row('状态', esc(s.$1), boldValue: true, valueColor: s.$2),
        if (p['assigned_user_name'] != null)
          row('负责人', esc(p['assigned_user_name']), boldValue: true),
        if (p['priority'] != null)
          row('优先级', '⭐' * (p['priority'] as int).clamp(0, 5),
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
    final lvl = levelMap[level] ?? (level ?? '—', textSecondary);

    return wrapCard(
      agentInfo: agentInfo,
      title: '💰 积分信息',
      children: [
        Row(
          children: [
            Text(esc(lvl.$1),
                style: TextStyle(
                    fontSize: 14,
                    color: lvl.$2,
                    fontWeight: FontWeight.bold)),
          ],
        ),
        const SizedBox(height: 4),
        row('当前积分', fmtNum(p['balance'] ?? 0),
            boldValue: true, valueColor: accent),
        row('累计获得', fmtNum(p['total_earned'] ?? 0), boldValue: true),
        row('年度获得', fmtNum(p['year_earned'] ?? 0), boldValue: true),
        if (p['rank'] != null)
          row('年度排名', '第${p['rank']}名', boldValue: true),
        if (p['description'] != null)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(esc(p['description']),
                style:
                    const TextStyle(fontSize: 12, color: textPrimary, height: 1.4)),
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
      return wrapCard(
        agentInfo: AgentInfo.getByKey('master'),
        displayName: senderName,
        title: esc(title),
        prelude: Text(esc(tag),
            style: const TextStyle(fontSize: 10, color: accent)),
        children: [
          if (p['stat_value'] != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Text(esc(p['stat_value']),
                  style: const TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.bold,
                      color: accent)),
            ),
          if (p['stat_label'] != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Text(esc(p['stat_label']),
                  style:
                      const TextStyle(fontSize: 12, color: textSecondary)),
            ),
          if (body != null && body.isNotEmpty)
            Text(esc(body),
                style:
                    const TextStyle(fontSize: 13, color: textPrimary, height: 1.4)),
        ],
      );
    }

    if (variant == 'cta') {
      return wrapCard(
        agentInfo: AgentInfo.getByKey('master'),
        displayName: senderName,
        title: esc(title),
        prelude: Text(esc(tag),
            style: const TextStyle(fontSize: 10, color: accent)),
        children: [
          if (body != null && body.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text(esc(body),
                  style: const TextStyle(
                      fontSize: 13, color: textPrimary, height: 1.4)),
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
                  backgroundColor: accent,
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8)),
                  padding: const EdgeInsets.symmetric(vertical: 10),
                ),
                child: Text(esc(ctaText),
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

    return wrapCard(
      agentInfo: AgentInfo.getByKey('master'),
      displayName: senderName,
      title: esc(title),
      prelude: Text(esc(tag),
          style: const TextStyle(fontSize: 10, color: accent)),
      children: [
        if (body != null && body.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Text(esc(body),
                style: const TextStyle(
                    fontSize: 13, color: textPrimary, height: 1.4)),
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
    final score = parseNum(p['score']);
    final deviation = p['deviation'];
    final deviationUnit = p['deviation_unit'] ?? 'cm';
    final summary = p['summary'] as String?;
    final recommendation = p['recommendation'] as String?;
    final photos = (p['photos'] ?? p['image_urls'] as List?) ?? [];
    final issues = p['issues'] as List?;

    const statusMap = {
      'passed': ('✅ 合格', success),
      'failed': ('❌ 不合格', danger),
      'needs_review': ('⚠️ 需复核', warning),
      'pending': ('⏳ 待检测', textMuted),
    };
    final s = statusMap[status] ?? ('❓ $status', textMuted);

    return wrapCard(
      agentInfo: agentInfo,
      title: '🔍 质检报告 · ${esc(checkItem.toString())}',
      children: [
        row('检测结果', esc(s.$1), boldValue: true, valueColor: s.$2),
        if (score > 0) ...[
          row('评分', '$score/100', boldValue: true),
          progressBar(score.toInt()),
        ],
        if (deviation != null)
          row('偏差',
              '${deviation.toString()}$deviationUnit',
              boldValue: true,
              valueColor: parseNum(deviation) > 5 ? danger : warning),
        if (summary != null && summary.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text(esc(summary),
                style:
                    const TextStyle(fontSize: 11, color: textSecondary)),
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
                    border: Border.all(color: border),
                  ),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(6),
                    child: CachedNetworkImage(
                      imageUrl: url.toString(),
                      fit: BoxFit.cover,
                      placeholder: (context, url) => const SizedBox(
                        width: 56,
                        height: 56,
                        child: Center(
                            child: CircularProgressIndicator(strokeWidth: 2)),
                      ),
                      errorWidget: (context, url, error) =>
                          const Icon(Icons.broken_image, size: 20, color: textMuted),
                    ),
                  ),
                );
              }).toList(),
            ),
          ),
        if (issues != null && issues.isNotEmpty) ...[
          const Divider(color: border, height: 1),
          ...issues.asMap().entries.map((entry) {
            final iss = entry.value as Map<String, dynamic>;
            final sevColors = {
              'critical': danger, 'major': warning,
              'minor': textSecondary, 'info': textMuted,
            };
            final sevColor = sevColors[iss['severity']?.toString()] ?? textMuted;
            return row(
              '${entry.key + 1}. ${esc(iss['description'] ?? iss['name'] ?? '')}',
              esc(iss['severity']?.toString() ?? ''),
              boldValue: true, valueColor: sevColor,
            );
          }),
        ],
        if (recommendation != null && recommendation.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text('💡 ${esc(recommendation)}',
                style: const TextStyle(fontSize: 10, color: accent)),
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

    return wrapCard(
      agentInfo: agentInfo,
      title: '⚠️ 质量问题清单 · ${issues.length} 项',
      children: [
        ...issues.take(6).toList().asMap().entries.map((entry) {
          final iss = entry.value as Map<String, dynamic>;
          final sev = iss['severity']?.toString() ?? '';
          final status = iss['status']?.toString() ?? 'open';
          return row(
            '${sevIcons[sev] ?? '⚪'} ${entry.key + 1}. ${esc(iss['description'] ?? iss['title'] ?? '问题')} ${statusIcons[status] ?? '⬜'}',
            esc(iss['location'] ?? iss['area'] ?? ''),
            boldValue: true,
          );
        }),
        if (issues.length > 6)
          Text('… 共 ${issues.length} 个问题',
              style: const TextStyle(fontSize: 10, color: textMuted)),
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
      'critical': danger, 'high': warning,
      'medium': textSecondary, 'low': textMuted,
    };

    return wrapCard(
      agentInfo: agentInfo,
      title: '📡 进度预警 · ${alerts.length} 条',
      children: [
        ...alerts.take(5).map((a) {
          final sev = a['severity']?.toString() ?? '';
          return row(
            esc(a['message'] ?? a['description'] ?? a['task_name'] ?? ''),
            esc(sev),
            boldValue: true,
            valueColor: sevColors[sev] ?? textMuted,
          );
        }),
        if (alerts.length > 5)
          Text('… 共 ${alerts.length} 条预警',
              style: const TextStyle(fontSize: 10, color: textMuted)),
      ],
    );
  }

  // F4: 设计域卡片 (厨房/卫浴/灯光/结构/工程量/家具/家电/门窗/水电暖通) → chat_card_design.dart

  // ═══════════════════════════════════════════
  // v1.1.22: 身份认证卡片
  // ═══════════════════════════════════════════
  Widget _buildIdentityCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('identity');
    return wrapCard(
      agentInfo: agentInfo,
      title: '🆔 ${esc(p['title'] ?? '身份认证')}',
      children: [
        if (p['status'] != null) row('状态', esc(p['status']), boldValue: true),
        if (p['name'] != null) row('姓名', esc(p['name']), boldValue: true),
        if (p['id_number'] != null) row('证件号', esc(p['id_number']), boldValue: true),
        if (p['message'] != null)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(esc(p['message']), style: const TextStyle(fontSize: 10, color: textMuted)),
          ),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // v1.1.22: 语音卡片
  // ═══════════════════════════════════════════
  Widget _buildVoiceCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('voice');
    return wrapCard(
      agentInfo: agentInfo,
      title: '🎙️ ${esc(p['title'] ?? '语音消息')}',
      children: [
        if (p['transcript'] != null) row('识别结果', esc(p['transcript']), boldValue: true),
        if (p['duration'] != null) row('时长', esc(p['duration']), boldValue: true),
        if (p['emotion'] != null) row('情绪', esc(p['emotion']), boldValue: true),
        if (p['audio_url'] != null)
          actionButton('🔊 播放', accent, () => onCardAction?.call('play_audio', {'url': p['audio_url']})),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // v1.1.22: IFC 导出卡片
  // ═══════════════════════════════════════════
  Widget _buildIfcExportCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('ifc_export');
    return wrapCard(
      agentInfo: agentInfo,
      title: '🏗️ ${esc(p['title'] ?? 'BIM 导出')}',
      children: [
        if (p['format'] != null) row('格式', esc(p['format']), boldValue: true),
        if (p['file_size'] != null) row('文件大小', esc(p['file_size']), boldValue: true),
        if (p['status'] != null) row('状态', esc(p['status']), boldValue: true, valueColor: accent),
        if (p['download_url'] != null)
          actionButton('📥 下载', accent, () => onCardAction?.call('download', {'url': p['download_url']})),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // v1.1.22: 通知卡片
  // ═══════════════════════════════════════════
  Widget _buildNotificationCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('notifications');
    return wrapCard(
      agentInfo: agentInfo,
      title: '🔔 ${esc(p['title'] ?? '通知')}',
      children: [
        if (p['message'] != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Text(esc(p['message']),
                style: const TextStyle(fontSize: 13, color: textPrimary)),
          ),
        if (p['type'] != null) row('类型', esc(p['type']), boldValue: true),
        if (p['action_url'] != null)
          actionButton('查看详情', accent, () => onCardAction?.call('open_url', {'url': p['action_url']})),
      ],
    );
  }

  // ╾ v1.1.22: 硬件传感器触发卡片 ╼
  // ═══════════════════════════════════════════
  // 相机触发卡片
  // ═══════════════════════════════════════════
  Widget _buildCameraTriggerCard() {
    final p = message.payload ?? {};
    final agentInfo = message.agentInfo ?? AgentInfo.getByKey('master');
    return wrapCard(
      agentInfo: agentInfo,
      title: '📷 ${esc(p['title'] ?? '拍照')}',
      children: [
        if (p['hint'] != null)
          Text(esc(p['hint']), style: const TextStyle(fontSize: 13, color: textPrimary)),
        const SizedBox(height: 8),
        actionButton('📸 打开相机', accent, () => onCardAction?.call('open_camera', p)),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // AR 扫描触发卡片
  // ═══════════════════════════════════════════
  Widget _buildArScanTriggerCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('ar_measurement');
    return wrapCard(
      agentInfo: agentInfo,
      title: '📏 ${esc(p['title'] ?? 'AR 空间扫描')}',
      children: [
        Text('使用摄像头和 ${p['sensor_type'] ?? 'LiDAR'} 传感器进行空间测量',
            style: const TextStyle(fontSize: 12, color: textSecondary)),
        const SizedBox(height: 8),
        actionButton('🔬 开始 AR 扫描', accent, () => onCardAction?.call('start_ar_scan', p)),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 语音输入触发卡片
  // ═══════════════════════════════════════════
  Widget _buildVoiceInputTriggerCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('voice');
    return wrapCard(
      agentInfo: agentInfo,
      title: '🎤 ${esc(p['title'] ?? '语音输入')}',
      children: [
        const Text('点击按钮开始语音输入，AI 将实时识别并回复',
            style: const TextStyle(fontSize: 12, color: textSecondary)),
        const SizedBox(height: 8),
        actionButton('🎙️ 开始录音', accent, () => onCardAction?.call('start_voice_input', p)),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // v1.1.22: 统计卡片
  // ═══════════════════════════════════════════
  Widget _buildStatsCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('master');
    return wrapCard(
      agentInfo: agentInfo,
      title: '📈 ${esc(p['title'] ?? '数据统计')}',
      children: [
        if (p['stats'] is Map)
          ...(p['stats'] as Map).entries.map((e) => row(
            esc(e.key.toString()), fmtNum(e.value), boldValue: true,
          )),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // v1.1.22: 用户卡片
  // ═══════════════════════════════════════════
  Widget _buildUserCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('admin');
    return wrapCard(
      agentInfo: agentInfo,
      title: '👤 ${esc(p['name'] ?? '用户信息')}',
      children: [
        if (p['role'] != null) row('角色', esc(p['role']), boldValue: true),
        if (p['phone'] != null) row('手机', esc(p['phone']), boldValue: true),
        if (p['status'] != null) row('状态', esc(p['status']), boldValue: true),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // v1.1.22: 用户列表卡片
  // ═══════════════════════════════════════════
  Widget _buildUserListCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('admin');
    final users = (p['users'] as List?) ?? [];
    return wrapCard(
      agentInfo: agentInfo,
      title: '👥 用户列表 · ${users.length} 人',
      children: users.take(6).map((u) => row(
        esc(u['name'] ?? ''), esc(u['role'] ?? ''), boldValue: true,
      )).toList(),
    );
  }

  // ═══════════════════════════════════════════
  // v1.1.22: 产品创建卡片
  // ═══════════════════════════════════════════
  Widget _buildProductCreateCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('products');
    return wrapCard(
      agentInfo: agentInfo,
      title: '📦 ${esc(p['title'] ?? '新增产品')}',
      children: [
        if (p['name'] != null) row('名称', esc(p['name']), boldValue: true),
        if (p['category'] != null) row('类别', esc(p['category']), boldValue: true),
        if (p['price'] != null) row('价格', '¥${fmtNum(p['price'])}', boldValue: true, valueColor: warning),
        actionButton('确认上架', success, () => onCardAction?.call('publish_product', p)),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // v1.1.22: 产品列表卡片
  // ═══════════════════════════════════════════
  Widget _buildProductListCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('products');
    final items = (p['items'] as List?) ?? [];
    return wrapCard(
      agentInfo: agentInfo,
      title: '📋 ${esc(p['title'] ?? '产品列表')} · ${items.length} 项',
      children: items.take(8).map((it) => row(
        esc(it['name'] ?? ''), '¥${fmtNum(it['price'] ?? 0)}', boldValue: true,
      )).toList(),
    );
  }

  // ═══════════════════════════════════════════
  // v1.1.22: 报价卡片
  // ═══════════════════════════════════════════
  Widget _buildQuotationCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('procurement');
    return wrapCard(
      agentInfo: agentInfo,
      title: '📝 ${esc(p['title'] ?? '报价单')}',
      children: [
        if (p['supplier'] != null) row('供应商', esc(p['supplier']), boldValue: true),
        if (p['total'] != null) row('总价', '¥${fmtNum(p['total'])}', boldValue: true, valueColor: warning),
        if (p['valid_until'] != null) row('有效期', esc(p['valid_until']), boldValue: true),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 公共组件
  // ═══════════════════════════════════════════

  /// 带 Agent 顶部信息的卡片容器
  Widget wrapCard({
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
                color: borderColor ?? border,
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
                      color: textPrimary,
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
        border: Border.all(color: border),
      ),
      child: Text(links,
          style: const TextStyle(fontSize: 11, color: textSecondary)),
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
                  ? accent.withValues(alpha: 0.9)
                  : (agentColor ?? textSecondary),
            ),
          ),
          const SizedBox(width: 6),
          Text(timeStr, style: const TextStyle(fontSize: 11, color: textMuted)),
        ],
      ),
    );
  }

  /// 键值行
  Widget row(String label, String value,
      {bool boldValue = false, Color? valueColor}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: [
          Expanded(
            flex: 2,
            child: Text(label,
                style: const TextStyle(fontSize: 12, color: textSecondary)),
          ),
          Expanded(
            flex: 3,
            child: Text(
              value,
              style: TextStyle(
                fontSize: 12,
                color: valueColor ?? textPrimary,
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
  Widget progressBar(int percent) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(4),
      child: LinearProgressIndicator(
        value: percent.clamp(0, 100) / 100,
        minHeight: 6,
        backgroundColor: border,
        valueColor: AlwaysStoppedAnimation<Color>(
          percent > 80
              ? success
              : percent > 50
                  ? accent
                  : warning,
        ),
      ),
    );
  }

  /// 操作按钮
  Widget actionButton(String label, Color color, VoidCallback? onTap) {
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

  static num parseNum(dynamic v) {
    if (v is num) return v;
    if (v is String) return num.tryParse(v) ?? 0;
    return 0;
  }

  static String fmtNum(dynamic v) {
    final n = parseNum(v);
    if (n == n.roundToDouble()) {
      return n.toStringAsFixed(0).replaceAllMapped(
          RegExp(r'\B(?=(\d{3})+(?!\d))'), (m) => ',');
    }
    return n.toStringAsFixed(2).replaceAllMapped(
        RegExp(r'\B(?=(\d{3})+(?!\d))'), (m) => ',');
  }

  static String esc(String s) {
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

  static Color orderStatusColor(String status) {
    switch (status) {
      case 'completed':
        return success;
      case 'cancelled':
        return danger;
      case 'shipped':
      case 'delivered':
        return accent;
      default:
        return warning;
    }
  }

  static Color escrowStatusColor(String status) {
    switch (status) {
      case 'supplier_received':
        return success;
      case 'refunded':
      case 'disputed':
        return warning;
      default:
        return accent;
    }
  }

  static Color sampleStatusColor(String status) {
    switch (status) {
      case 'received':
        return success;
      case 'rejected':
        return warning;
      default:
        return accent;
    }
  }
}
