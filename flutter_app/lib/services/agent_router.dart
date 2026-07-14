import '../models/chat_message.dart';

/// 自然语言 → Agent 路由器
///
/// 不使用 @ 标记，纯自然语言意图识别。端口自 Web 端 agent-router.js。
class AgentRouter {
  AgentRouter._();

  static final AgentRouter _instance = AgentRouter._();
  factory AgentRouter() => _instance;

  /// 路由结果
  /// - agent: 目标 Agent key
  /// - confidence: 置信度 (0.0 ~ 1.0)
  /// - payload: 附加数据（低置信度时包含 clarify 提示）
  static RouteResult route(String text) {
    if (text.isEmpty) {
      return const RouteResult(agent: 'master', confidence: 0.0);
    }

    final lower = text.toLowerCase();
    final scores = <String, int>{};

    for (final p in _patterns) {
      scores[p.agent] = 0;
      for (final kw in p.keywords) {
        if (text.contains(kw) || lower.contains(kw.toLowerCase())) {
          scores[p.agent] = scores[p.agent]! + 1;
        }
      }
    }

    String bestAgent = 'master';
    int bestScore = 0;
    for (final entry in scores.entries) {
      if (entry.value > bestScore) {
        bestScore = entry.value;
        bestAgent = entry.key;
      }
    }

    final denom = (text.length / 20).ceil().clamp(1, 100);
    final confidence =
        bestScore == 0 ? 0.0 : (bestScore / denom).clamp(0.0, 1.0);

    if (confidence < 0.3 || bestScore == 0) {
      return RouteResult(
        agent: 'master',
        confidence: confidence,
        payload: {
          'clarify': true,
          'message': '我理解你想了解一些信息。能更具体一些吗？比如想问预算、设计、施工进度还是其他？',
        },
      );
    }

    return RouteResult(
      agent: bestAgent,
      confidence: confidence,
      payload: {'original_text': text},
    );
  }

  /// 获取 Agent 显示信息
  static AgentInfo getAgentInfo(String agentKey) {
    return AgentInfo.getByKey(agentKey);
  }

  /// Agent 关键词模式（与 Web 端 agent-router.js 同步）
  static const List<_AgentPattern> _patterns = [
    _AgentPattern(agent: 'budget', keywords: [
      '预算', '花了多少钱', '还剩多少', '支出', '费用', '超支', '成本', '价格',
      '多少钱', '报价', '账单', '付款', '支付',
    ]),
    _AgentPattern(agent: 'design', keywords: [
      '设计', '方案', '图纸', '布局', '风格', '装修风格', '效果图', '改造',
      '改', '开放式', '打通', '隔断', 'CAD', '3D',
    ]),
    _AgentPattern(agent: 'construction', keywords: [
      '施工', '进度', '开工', '水电', '木工', '瓦工', '油漆', '泥工', '贴砖',
      '刷墙', '打孔', '拆', '今天干', '任务', '工序', '阶段',
    ]),
    _AgentPattern(agent: 'procurement', keywords: [
      '采购', '买', '订购', '下单', '物流', '到货', '发货', '什么时候到',
      '供应商', '比价', '地砖', '瓷砖', '地板', '涂料', '材料',
    ]),
    _AgentPattern(agent: 'quality', keywords: [
      '质检', '验收', '检查', '问题', '毛病', '整改', '返工', '合格',
      '不合格', '检测', '偏差', '偏差多少',
    ]),
    _AgentPattern(agent: 'settlement', keywords: [
      '结算', '对账', '尾款', '结清', '结账', '完工结算', '最终账单', '总账',
    ]),
    _AgentPattern(agent: 'support', keywords: [
      '客服', '帮助', '怎么用', '怎么操作', '联系', '投诉', '建议', '反馈', '问题反馈',
    ]),
    _AgentPattern(agent: 'master', keywords: [
      '总控', '统筹', '协调', '概况', '整体', '总结', '汇报', '状态',
      '什么时候完工', '还要多久',
    ]),
  ];
}

/// 路由结果
class RouteResult {
  final String agent;
  final double confidence;
  final Map<String, dynamic>? payload;

  const RouteResult({
    required this.agent,
    required this.confidence,
    this.payload,
  });

  bool get needsClarify => payload?['clarify'] == true;
}

/// 关键词模式（内部使用）
class _AgentPattern {
  final String agent;
  final List<String> keywords;
  const _AgentPattern({required this.agent, required this.keywords});
}
