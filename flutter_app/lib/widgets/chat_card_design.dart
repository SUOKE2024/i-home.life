// F4: 设计域卡片渲染器 — 从 chat_message_card.dart 拆分
//
// 包含: 厨房 / 卫浴 / 灯光 / 结构 / 工程量 / 家具 / 家电 / 门窗 / 水电暖通
// 拆分自 chat_message_card.dart (v1.1.27), 使用 extension 方法拆分, 零行为变更,
// 私有 helper (wrapCard/row/esc 等) 跨 extension 可见, 零行为变更。
import 'package:flutter/material.dart';
import '../models/chat_message.dart';
import '../theme/suoke_theme.dart';
import 'chat_message_card.dart';

/// 设计域卡片渲染器扩展 (厨房/卫浴/灯光/结构/工程量/家具/家电/门窗/水电暖通)
extension ChatCardDesignRenderers on ChatMessageCard {


  // ═══════════════════════════════════════════
  // v1.1.22: 厨房方案卡片
  // ═══════════════════════════════════════════
  Widget buildKitchenCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('kitchen');
    return wrapCard(
      agentInfo: agentInfo,
      title: '🍳 ${ChatMessageCard.esc(p['title'] ?? '厨房方案')}',
      children: [
        if (p['layout'] != null) row('布局', ChatMessageCard.esc(p['layout']), boldValue: true),
        if (p['area'] != null) row('面积', ChatMessageCard.esc(p['area']), boldValue: true),
        if (p['cabinets'] != null) row('橱柜', ChatMessageCard.esc(p['cabinets']), boldValue: true),
        if (p['countertop'] != null) row('台面', ChatMessageCard.esc(p['countertop']), boldValue: true),
        if (p['appliances'] is List)
          row('电器', (p['appliances'] as List).join('、'), boldValue: true),
        if (p['recommendation'] != null)
          row('建议', ChatMessageCard.esc(p['recommendation']), boldValue: true, valueColor: SuokeDesignTokens.accent),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // v1.1.22: 卫浴方案卡片
  // ═══════════════════════════════════════════
  Widget buildBathroomCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('bathroom');
    return wrapCard(
      agentInfo: agentInfo,
      title: '🛁 ${ChatMessageCard.esc(p['title'] ?? '卫浴方案')}',
      children: [
        if (p['layout'] != null) row('布局', ChatMessageCard.esc(p['layout']), boldValue: true),
        if (p['area'] != null) row('面积', ChatMessageCard.esc(p['area']), boldValue: true),
        if (p['fixtures'] is List)
          row('洁具', (p['fixtures'] as List).join('、'), boldValue: true),
        if (p['waterproof'] != null) row('防水', ChatMessageCard.esc(p['waterproof']), boldValue: true),
        if (p['recommendation'] != null)
          row('建议', ChatMessageCard.esc(p['recommendation']), boldValue: true, valueColor: SuokeDesignTokens.accent),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // v1.1.22: 灯光方案卡片
  // ═══════════════════════════════════════════
  Widget buildLightingCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('lighting');
    return wrapCard(
      agentInfo: agentInfo,
      title: '💡 ${ChatMessageCard.esc(p['title'] ?? '灯光方案')}',
      children: [
        if (p['illuminance'] != null) row('照度', ChatMessageCard.esc(p['illuminance']), boldValue: true),
        if (p['color_temp'] != null) row('色温', ChatMessageCard.esc(p['color_temp']), boldValue: true),
        if (p['fixtures'] is List)
          row('灯具', (p['fixtures'] as List).join('、'), boldValue: true),
        if (p['scene'] != null) row('场景', ChatMessageCard.esc(p['scene']), boldValue: true),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // v1.1.22: 结构方案卡片
  // ═══════════════════════════════════════════
  Widget buildStructuralCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('structural');
    return wrapCard(
      agentInfo: agentInfo,
      title: '🏗️ ${ChatMessageCard.esc(p['title'] ?? '结构分析')}',
      children: [
        if (p['elements'] is List)
          row('构件', (p['elements'] as List).join('、'), boldValue: true),
        if (p['load_bearing'] != null) row('承重', ChatMessageCard.esc(p['load_bearing']), boldValue: true),
        if (p['material'] != null) row('材料', ChatMessageCard.esc(p['material']), boldValue: true),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // v1.1.22: 工程量卡片
  // ═══════════════════════════════════════════
  Widget buildTakeoffCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('takeoff');
    final items = (p['items'] as List?) ?? [];
    return wrapCard(
      agentInfo: agentInfo,
      title: '📊 ${ChatMessageCard.esc(p['title'] ?? '工程量清单')}',
      children: [
        ...items.take(6).map((it) => row(
          ChatMessageCard.esc(it['name'] ?? ''),
          '${it['quantity'] ?? ''} ${ChatMessageCard.esc(it['unit'] ?? '')}',
          boldValue: true,
        )),
        if (items.length > 6)
          Text('… 共 ${items.length} 项',
              style: const TextStyle(fontSize: 10, color: SuokeDesignTokens.textMuted)),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // v1.1.22: 家具卡片
  // ═══════════════════════════════════════════
  Widget buildFurnitureCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('furniture_catalog');
    return wrapCard(
      agentInfo: agentInfo,
      title: '🪑 ${ChatMessageCard.esc(p['title'] ?? '家具推荐')}',
      children: [
        if (p['style'] != null) row('风格', ChatMessageCard.esc(p['style']), boldValue: true),
        if (p['items'] is List)
          row('推荐', (p['items'] as List).take(5).join('、'), boldValue: true),
        if (p['brand'] != null) row('品牌', ChatMessageCard.esc(p['brand']), boldValue: true),
        if (p['price_range'] != null)
          row('价格区间', ChatMessageCard.esc(p['price_range']), boldValue: true, valueColor: SuokeDesignTokens.warning),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // v1.1.22: 家电卡片
  // ═══════════════════════════════════════════
  Widget buildApplianceCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('appliance');
    return wrapCard(
      agentInfo: agentInfo,
      title: '📺 ${ChatMessageCard.esc(p['title'] ?? '家电推荐')}',
      children: [
        if (p['items'] is List)
          row('推荐', (p['items'] as List).take(5).join('、'), boldValue: true),
        if (p['energy_rating'] != null) row('能效', ChatMessageCard.esc(p['energy_rating']), boldValue: true),
        if (p['dimensions'] != null) row('尺寸要求', ChatMessageCard.esc(p['dimensions']), boldValue: true),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // v1.1.22: 门窗卡片
  // ═══════════════════════════════════════════
  Widget buildDoorWindowCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('door_window_waterproof');
    return wrapCard(
      agentInfo: agentInfo,
      title: '🚪 ${ChatMessageCard.esc(p['title'] ?? '门窗方案')}',
      children: [
        if (p['type'] != null) row('类型', ChatMessageCard.esc(p['type']), boldValue: true),
        if (p['material'] != null) row('材质', ChatMessageCard.esc(p['material']), boldValue: true),
        if (p['dimensions'] != null) row('尺寸', ChatMessageCard.esc(p['dimensions']), boldValue: true),
        if (p['waterproof'] != null) row('防水', ChatMessageCard.esc(p['waterproof']), boldValue: true),
      ],
    );
  }

  // ═══════════════════════════════════════════
  // v1.1.22: MEP 水电暖通卡片
  // ═══════════════════════════════════════════
  Widget buildMepPlanCard() {
    final p = message.payload ?? {};
    final agentInfo = AgentInfo.getByKey('mep');
    return wrapCard(
      agentInfo: agentInfo,
      title: '🔧 ${ChatMessageCard.esc(p['title'] ?? '水电暖通方案')}',
      children: [
        if (p['electrical'] != null) row('强电', ChatMessageCard.esc(p['electrical']), boldValue: true),
        if (p['plumbing'] != null) row('给排水', ChatMessageCard.esc(p['plumbing']), boldValue: true),
        if (p['hvac'] != null) row('暖通', ChatMessageCard.esc(p['hvac']), boldValue: true),
        if (p['outlets'] != null) row('插座点位', ChatMessageCard.esc(p['outlets']), boldValue: true),
      ],
    );
  }
}
