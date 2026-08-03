import 'package:flutter/material.dart';
import '../services/api.dart';
import '../theme/suoke_theme.dart';

/// F45 方案前置决策页面（v1.5.0）
class SolutionFirstPage extends StatefulWidget {
  final String projectId;
  const SolutionFirstPage({super.key, required this.projectId});

  @override
  State<SolutionFirstPage> createState() => _SolutionFirstPageState();
}

class _SolutionFirstPageState extends State<SolutionFirstPage> {
  final ApiClient _api = ApiClient();

  bool _generating = false;
  Map<String, dynamic>? _package;
  String? _error;

  Future<void> _generate() async {
    if (_generating) return;
    setState(() {
      _generating = true;
      _error = null;
    });
    final result = await _api.solutionFirstGenerate(widget.projectId);
    if (!mounted) return;
    setState(() => _generating = false);
    if (result.isSuccess && result.data is Map) {
      setState(() => _package = result.data as Map<String, dynamic>);
    } else {
      setState(() => _error = result.error ?? '生成失败，请稍后重试');
    }
  }

  List<dynamic> _layoutList() {
    if (_package == null) return [];
    final layouts = _package!['layouts'];
    if (layouts is List) return layouts;
    return [];
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: SuokeDesignTokens.bg(context),
      appBar: AppBar(
        backgroundColor: SuokeDesignTokens.card(context),
        foregroundColor: SuokeDesignTokens.text(context),
        title: const Text('方案前置'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: SuokeDesignTokens.accent,
                foregroundColor: SuokeDesignTokens.bg(context),
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
              onPressed: _generating ? null : _generate,
              icon: _generating
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: Colors.white),
                    )
                  : const Icon(Icons.auto_awesome, size: 18),
              label: Text(_generating ? '生成中...' : '生成方案'),
            ),
          ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Text(_error!,
                  textAlign: TextAlign.center,
                  style:
                      TextStyle(color: SuokeDesignTokens.textSub(context))),
            ),
          if (_package != null) ...[
            if (_package!['source_note'] != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(
                  _package!['source_note'].toString(),
                  style: TextStyle(
                      color: SuokeDesignTokens.textSub(context),
                      fontSize: 12),
                ),
              ),
            _buildBudgetCard(
                Map<String, dynamic>.from(
                    _package!['budget_range'] as Map? ?? {})),
            const SizedBox(height: 12),
            for (final layout in _layoutList())
              _buildLayoutCard(layout as Map<String, dynamic>),
            _buildRecommendationsCard(
                (_package!['recommendations'] as List?) ?? []),
          ],
        ],
      ),
    );
  }

  Widget _buildBudgetCard(Map<String, dynamic> budgetRange) {
    final lower = (budgetRange['lower'] as num?)?.toInt();
    final upper = (budgetRange['upper'] as num?)?.toInt();
    final level = (budgetRange['level'] ?? '').toString();
    return Card(
      color: SuokeDesignTokens.card(context),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: SuokeDesignTokens.borderClr(context)),
      ),
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.savings_outlined,
                    color: SuokeDesignTokens.accent, size: 20),
                const SizedBox(width: 8),
                Text('预算区间（${_levelLabel(level)}档）',
                    style: TextStyle(
                        color: SuokeDesignTokens.text(context),
                        fontSize: 15,
                        fontWeight: FontWeight.w600)),
              ],
            ),
            const SizedBox(height: 10),
            Text(
              lower != null && upper != null
                  ? '¥${_formatInt(lower)} - ¥${_formatInt(upper)}'
                  : '-',
              style: const TextStyle(
                  color: SuokeDesignTokens.accent,
                  fontSize: 20,
                  fontWeight: FontWeight.bold),
            ),
            if (budgetRange['per_sqm_lower'] != null)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  '单价参考：${budgetRange['per_sqm_lower']} - ${budgetRange['per_sqm_upper']} 元/㎡',
                  style: TextStyle(
                      color: SuokeDesignTokens.textSub(context),
                      fontSize: 12),
                ),
              ),
            if (budgetRange['note'] != null)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(budgetRange['note'].toString(),
                    style: TextStyle(
                        color: SuokeDesignTokens.textSub(context),
                        fontSize: 12)),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildLayoutCard(Map<String, dynamic> layout) {
    final points = (layout['layout_points'] as List?) ?? [];
    return Card(
      color: SuokeDesignTokens.card(context),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: SuokeDesignTokens.borderClr(context)),
      ),
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 32,
                  height: 32,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: SuokeDesignTokens.accent.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    layout['plan_no']?.toString() ?? '-',
                    style: const TextStyle(
                        color: SuokeDesignTokens.accent,
                        fontWeight: FontWeight.bold),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    layout['name'] ?? '未命名方案',
                    style: TextStyle(
                        color: SuokeDesignTokens.text(context),
                        fontSize: 16,
                        fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text(layout['summary']?.toString() ?? '',
                style: TextStyle(
                    color: SuokeDesignTokens.textSub(context),
                    fontSize: 13)),
            if (points.isNotEmpty) ...[
              const SizedBox(height: 10),
              for (final point in points)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Padding(
                        padding: EdgeInsets.only(top: 5),
                        child: Icon(Icons.circle,
                            size: 6, color: SuokeDesignTokens.accent),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(point.toString(),
                            style: TextStyle(
                                color: SuokeDesignTokens.text(context),
                                fontSize: 13)),
                      ),
                    ],
                  ),
                ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildRecommendationsCard(List<dynamic> recommendations) {
    return Card(
      color: SuokeDesignTokens.card(context),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: SuokeDesignTokens.borderClr(context)),
      ),
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.tips_and_updates_outlined,
                    color: SuokeDesignTokens.accent, size: 20),
                const SizedBox(width: 8),
                Text('推荐建议',
                    style: TextStyle(
                        color: SuokeDesignTokens.text(context),
                        fontSize: 15,
                        fontWeight: FontWeight.w600)),
              ],
            ),
            const SizedBox(height: 8),
            if (recommendations.isEmpty)
              Text('暂无推荐建议',
                  style: TextStyle(
                      color: SuokeDesignTokens.textSub(context),
                      fontSize: 13))
            else
              for (final rec in recommendations)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Text('• ${rec.toString()}',
                      style: TextStyle(
                          color: SuokeDesignTokens.textSub(context),
                          fontSize: 13)),
                ),
          ],
        ),
      ),
    );
  }

  String _levelLabel(String level) {
    switch (level) {
      case 'economic':
        return '经济';
      case 'comfort':
        return '舒适';
      case 'quality':
        return '品质';
      default:
        return level;
    }
  }

  String _formatInt(int value) {
    return value.toString().replaceAllMapped(
        RegExp(r'(\d)(?=(\d{3})+$)'), (m) => '${m[1]},');
  }
}
