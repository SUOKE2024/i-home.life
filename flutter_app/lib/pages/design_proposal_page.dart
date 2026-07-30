// v1.2.8 讨论式方案交互 · 全屏方案对比页
//
// brainstorming 决策 B：2-3 栏方案卡片并列对比 + 底部常驻语音条
// - 蓝色边框 = 当前选中方案
// - ✏️ 图标 = 有未确认修改（change_log 非空）
// - 语音说"方案B加中岛" → onProposalUpdated 回调 → 对应栏原地刷新
//
// 方案生成主路径：WS FunctionCall 工具 generate_design_proposals
// 方案修订主路径：WS FunctionCall 工具 update_design_proposal
// 底部语音条复用悬浮窗的 WS 会话（VoiceSessionScope），不重连
import 'package:flutter/material.dart';

import '../widgets/voice_proposal_bar.dart';

class DesignProposalPage extends StatefulWidget {
  const DesignProposalPage({
    super.key,
    required this.proposals,
    required this.sessionId,
  });

  final List<Map<String, dynamic>> proposals;
  final String sessionId;

  @override
  State<DesignProposalPage> createState() => _DesignProposalPageState();
}

class _DesignProposalPageState extends State<DesignProposalPage> {
  late List<Map<String, dynamic>> _proposals;
  String? _selectedId;

  @override
  void initState() {
    super.initState();
    _proposals = List.from(widget.proposals);
    if (_proposals.isNotEmpty) _selectedId = _proposals.first['proposal_id'];
  }

  void _onProposalUpdated(String proposalId, Map<String, dynamic> proposal) {
    setState(() {
      final idx =
          _proposals.indexWhere((p) => p['proposal_id'] == proposalId);
      if (idx >= 0) {
        _proposals[idx] = proposal;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('方案对比', style: TextStyle(fontSize: 16)),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: Stack(
        children: [
          // 方案卡片列表（横向滚动支持 2-3 栏）
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.all(12),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: _proposals
                  .map((p) => _ProposalCard(
                        proposal: p,
                        isSelected: p['proposal_id'] == _selectedId,
                        onTap: () =>
                            setState(() => _selectedId = p['proposal_id']),
                      ))
                  .toList(),
            ),
          ),
          // 底部常驻语音条
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: VoiceProposalBar(onProposalUpdated: _onProposalUpdated),
          ),
        ],
      ),
    );
  }
}

class _ProposalCard extends StatelessWidget {
  const _ProposalCard({
    required this.proposal,
    required this.isSelected,
    required this.onTap,
  });

  final Map<String, dynamic> proposal;
  final bool isSelected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final pid = proposal['proposal_id'] as String? ?? '';
    final title = proposal['title'] as String? ?? '';
    final layoutType = proposal['layout_type'] as String? ?? '';
    final areaSqm = proposal['area_sqm'] as num? ?? 0;
    final budgetCny = proposal['budget_cny'] as num? ?? 0;
    final highlights = (proposal['highlights'] as List<dynamic>? ?? [])
        .map((e) => e as String)
        .toList();
    final changeLog = (proposal['change_log'] as List<dynamic>? ?? [])
        .map((e) => e as String)
        .toList();
    final hasChanges = changeLog.isNotEmpty;

    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 220,
        margin: const EdgeInsets.only(right: 12),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isSelected ? const Color(0xFF007AFF) : Colors.grey.shade300,
            width: isSelected ? 2 : 1,
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.05),
              blurRadius: 6,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 标题行
            Row(
              children: [
                Text(
                  '方案 $pid · $title',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: isSelected ? const Color(0xFF007AFF) : Colors.black87,
                  ),
                ),
                if (hasChanges) ...[
                  const SizedBox(width: 4),
                  const Icon(Icons.edit, size: 12, color: Color(0xFF007AFF)),
                ],
              ],
            ),
            const SizedBox(height: 8),
            // 布局图占位
            Container(
              height: 80,
              decoration: BoxDecoration(
                color: const Color(0xFFE8F0FE),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Center(
                child: Icon(Icons.architecture, size: 32, color: Color(0xFF007AFF)),
              ),
            ),
            const SizedBox(height: 8),
            // 指标
            _MetricRow(label: '布局', value: layoutType),
            _MetricRow(label: '面积', value: '${areaSqm.toStringAsFixed(1)} ㎡'),
            _MetricRow(
                label: '预算', value: '¥${budgetCny.toStringAsFixed(0)}'),
            const SizedBox(height: 8),
            // 亮点
            if (highlights.isNotEmpty) ...[
              const Text(
                '亮点',
                style: TextStyle(fontSize: 11, color: Colors.grey),
              ),
              const SizedBox(height: 4),
              Wrap(
                spacing: 4,
                runSpacing: 4,
                children: highlights
                    .map((h) => Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: const Color(0xFFF0F8FF),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(h,
                              style: const TextStyle(
                                  fontSize: 10, color: Color(0xFF007AFF))),
                        ))
                    .toList(),
              ),
            ],
            // 修订历史
            if (changeLog.isNotEmpty) ...[
              const SizedBox(height: 8),
              ...changeLog.map((c) => Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('• ',
                            style:
                                TextStyle(fontSize: 10, color: Colors.orange)),
                        Expanded(
                          child: Text(c,
                              style: const TextStyle(
                                  fontSize: 10, color: Colors.grey)),
                        ),
                      ],
                    ),
                  )),
            ],
          ],
        ),
      ),
    );
  }
}

class _MetricRow extends StatelessWidget {
  const _MetricRow({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontSize: 11, color: Colors.grey)),
          Text(value,
              style: const TextStyle(fontSize: 11, color: Colors.black87)),
        ],
      ),
    );
  }
}
