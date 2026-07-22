// F4: 采购域卡片渲染器 — 从 chat_message_card.dart 拆分
//
// 包含: BOM 物料清单 / 采购订单 / 订单列表 / 担保支付 / 物流追踪 / 样品索要 / 比价
// 拆分自 chat_message_card.dart (v1.1.27), 使用 extension 方法拆分, 零行为变更,
// 私有 helper (wrapCard/row/parseNum/esc 等) 跨 extension 可见, 零行为变更。
import 'package:flutter/material.dart';
import '../models/chat_message.dart';
import '../theme/suoke_theme.dart';
import 'chat_message_card.dart';

/// 采购域卡片渲染器扩展 (比价/BOM/订单/担保/物流/样品)
extension ChatCardProcurementRenderers on ChatMessageCard {

  // ═══════════════════════════════════════════
  // 9. 比价卡片
  // ═══════════════════════════════════════════
  Widget buildQuoteCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('procurement');
    final quotes = (p['quotes'] as List?) ?? [];
    final recommendation = p['recommendation'] as String?;

    return wrapCard(
      agentInfo: agentInfo,
      title: '🛒 ${ChatMessageCard.esc(p['product'] ?? '比价报告')}',
      children: [
        ...quotes.map((q) {
          final supplier = (q['supplier'] ?? '') as String;
          final price = ChatMessageCard.parseNum(q['price']);
          final isRec = q['recommended'] == true;
          return row(supplier, '¥${ChatMessageCard.fmtNum(price)}${isRec ? ' ⭐' : ''}',
              boldValue: true);
        }),
        if (recommendation != null)
          row('推荐', ChatMessageCard.esc(recommendation),
              boldValue: true, valueColor: SuokeDesignTokens.accent),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 10. BOM 物料清单
  // ═══════════════════════════════════════════
  Widget buildBomCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('procurement');
    final items = (p['items'] as List?) ?? [];
    final totalPrice = ChatMessageCard.parseNum(p['total_price']);
    final projectId = p['project_id'] as String?;

    return wrapCard(
      agentInfo: agentInfo,
      title: '📦 ${ChatMessageCard.esc(p['title'] ?? 'BOM 物料清单')}',
      children: [
        if (items.isEmpty)
          row('暂无物料', '', boldValue: true)
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
            final itemPrice = ChatMessageCard.parseNum(it['total_price']);
            return row(
              '${idx + 1}. ${ChatMessageCard.esc(name)} ${catName.isNotEmpty ? "[$catName]" : ""}',
              '×$qty ${ChatMessageCard.esc(unit)} · ¥${ChatMessageCard.fmtNum(itemPrice)}',
              boldValue: true,
            );
          }),
          if (items.length > 8)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text('… 共 ${items.length} 项',
                  style: const TextStyle(fontSize: 10, color: SuokeDesignTokens.textMuted)),
            ),
        ],
        row('合计', '¥${ChatMessageCard.fmtNum(totalPrice)}',
            boldValue: true, valueColor: SuokeDesignTokens.warning),
        if (projectId != null)
          GestureDetector(
            onTap: () => onCardAction
                ?.call('export_bom', {'project_id': projectId}),
            child: const Padding(
              padding: EdgeInsets.only(top: 4),
              child: Text('📥 导出 Excel',
                  style: TextStyle(fontSize: 11, color: SuokeDesignTokens.accent)),
            ),
          ),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 11. 采购订单
  // ═══════════════════════════════════════════
  Widget buildOrderCard() {
    final o = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('procurement');
    final lines = (o['lines'] as List?) ?? [];
    final totalAmount = ChatMessageCard.parseNum(o['total_amount']);
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

    return wrapCard(
      agentInfo: agentInfo,
      title:
          '🛍️ 采购订单${orderId != null ? " #${orderId.toString().substring(0, orderId.length < 8 ? orderId.length : 8)}" : ""}',
      children: [
        if (supplierName != null)
          row('供应商', ChatMessageCard.esc(supplierName), boldValue: true),
        ...lines.asMap().entries.map((entry) {
          final l = entry.value;
          return row(
            '${entry.key + 1}. ${ChatMessageCard.esc(l['material_name'] ?? l['material_id'] ?? '物料')}',
            '×${l['quantity']} · ¥${ChatMessageCard.fmtNum(ChatMessageCard.parseNum(l['total_price']))}',
            boldValue: true,
          );
        }),
        row('合计', '¥${ChatMessageCard.fmtNum(totalAmount)}',
            boldValue: true, valueColor: SuokeDesignTokens.warning),
        row('状态', ChatMessageCard.esc(statusText),
            boldValue: true, valueColor: ChatMessageCard.orderStatusColor(status)),
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
  // 12. 采购订单列表
  // ═══════════════════════════════════════════
  Widget buildOrderListCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('procurement');
    final orders = (p['orders'] as List?) ?? [];
    if (orders.isEmpty) return const SizedBox.shrink();

    return wrapCard(
      agentInfo: agentInfo,
      title: '📋 采购订单列表',
      children: [
        ...orders.take(5).map((o) {
          final orderId = o['id']?.toString() ?? '';
          final shortId = orderId.length > 8
              ? orderId.substring(0, 8)
              : orderId;
          final supplier = o['supplier_name'] as String?;
          final amount = ChatMessageCard.parseNum(o['total_amount']);
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
          return row(
            '#$shortId${supplier != null ? " · $supplier" : ""}',
            '¥${ChatMessageCard.fmtNum(amount)} · ${statusMap[status] ?? status}',
            boldValue: true,
            valueColor: ChatMessageCard.orderStatusColor(status),
          );
        }),
        if (orders.length > 5)
          Text('… 共 ${orders.length} 个订单',
              style: const TextStyle(fontSize: 10, color: SuokeDesignTokens.textMuted)),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 13. 担保支付
  // ═══════════════════════════════════════════
  Widget buildEscrowCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('procurement');
    final totalAmount = ChatMessageCard.parseNum(p['total_amount']);
    final escrowFee = ChatMessageCard.parseNum(p['escrow_fee']);
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

    return wrapCard(
      agentInfo: agentInfo,
      title: '🛡 担保支付 · ${ChatMessageCard.esc(escrowNo ?? '')}',
      children: [
        row('订单金额', '¥${ChatMessageCard.fmtNum(totalAmount)}', boldValue: true),
        row('担保手续费', '¥${ChatMessageCard.fmtNum(escrowFee)}', boldValue: true),
        row('状态', ChatMessageCard.esc(statusLabels[status] ?? status),
            boldValue: true, valueColor: ChatMessageCard.escrowStatusColor(status)),
        if (disputeReason != null)
          row('争议原因', ChatMessageCard.esc(disputeReason), boldValue: true),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // 14. 物流追踪
  // ═══════════════════════════════════════════
  Widget buildLogisticsCard() {
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

    return wrapCard(
      agentInfo: agentInfo,
      title: '🚚 物流追踪 · ${ChatMessageCard.esc(trackingNo ?? '')}',
      children: [
        row('承运商', ChatMessageCard.esc(carrierLabels[carrier] ?? carrier ?? ''),
            boldValue: true),
        if (shipFrom != null) row('发货地', ChatMessageCard.esc(shipFrom), boldValue: true),
        if (shipTo != null) row('收货地', ChatMessageCard.esc(shipTo), boldValue: true),
        row('状态', ChatMessageCard.esc(statusLabels[status] ?? status),
            boldValue: true, valueColor: SuokeDesignTokens.accent),
        if (history != null && history.isNotEmpty) ...[
          const SizedBox(height: 4),
          const Divider(color: SuokeDesignTokens.border, height: 1),
          const SizedBox(height: 4),
          ...history.reversed.take(3).map((h) {
            return row(
              ChatMessageCard.esc(h['location'] ?? '—'),
              ChatMessageCard.esc(h['description'] ?? h['status'] ?? ''),
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
  Widget buildSampleCard() {
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

    return wrapCard(
      agentInfo: agentInfo,
      title: '🎨 样品索要 · ${ChatMessageCard.esc(sampleType ?? '实物')}',
      children: [
        if (materialName != null)
          row('物料', ChatMessageCard.esc(materialName), boldValue: true),
        row('状态', ChatMessageCard.esc(statusLabels[status] ?? status),
            boldValue: true, valueColor: ChatMessageCard.sampleStatusColor(status)),
        if (notes != null) row('备注', ChatMessageCard.esc(notes), boldValue: true),
      ],
    );
  }
}
