// v1.2.8 语音+任务融合面板（悬浮窗展开态）
//
// brainstorming 决策 B：上下分层
// - 上半：VoiceConversationArea（波纹+转写，接 voice_realtime WS）
// - 下半：VoiceTaskPanelList（复用现有 VoiceTaskPanel 轮询逻辑）
//
// 监听 proposal_generated 事件 → 跳转 DesignProposalPage 展示多方案对比
import 'package:flutter/material.dart';

import '../services/voice_realtime_service.dart';
import '../theme/suoke_theme.dart';
import '../pages/design_proposal_page.dart';
import 'voice_conversation_area.dart';
import 'voice_task_panel.dart';

class VoiceFusionPanel extends StatefulWidget {
  const VoiceFusionPanel({
    super.key,
    required this.service,
    required this.onCollapse,
  });

  final VoiceRealtimeService service;
  final VoidCallback onCollapse;

  @override
  State<VoiceFusionPanel> createState() => _VoiceFusionPanelState();
}

class _VoiceFusionPanelState extends State<VoiceFusionPanel> {
  @override
  void initState() {
    super.initState();
    // 监听方案生成事件 → 跳转方案对比页
    widget.service.onProposalGenerated = _onProposalGenerated;
  }

  @override
  void dispose() {
    widget.service.onProposalGenerated = null;
    super.dispose();
  }

  void _onProposalGenerated(
      List<Map<String, dynamic>> proposals, String sessionId) {
    if (!mounted || proposals.isEmpty) return;
    // 收起悬浮窗，跳转全屏方案对比页
    widget.onCollapse();
    Navigator.of(context, rootNavigator: true).push(
      MaterialPageRoute(
        builder: (_) => DesignProposalPage(
          proposals: proposals,
          sessionId: sessionId,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Material(
      elevation: 8,
      borderRadius: BorderRadius.circular(16),
      color: Colors.white,
      child: Container(
        width: 320,
        constraints: const BoxConstraints(maxHeight: 480),
        padding: const EdgeInsets.all(12),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // 标题栏 + 收起按钮
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  '语音助手',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                Semantics(
                  label: '收起语音助手',
                  button: true,
                  child: GestureDetector(
                    onTap: widget.onCollapse,
                    // 44dp 触摸目标（WCAG 2.5.8）
                    behavior: HitTestBehavior.opaque,
                    child: const Padding(
                      padding: EdgeInsets.all(13),
                      child: Icon(Icons.close, size: 18, color: SuokeDesignTokens.textSecondary),
                    ),
                  ),
                ),
              ],
            ),
            const Divider(height: 16),
            // 上半：语音对话区
            VoiceConversationArea(service: widget.service),
            const SizedBox(height: 8),
            const Divider(height: 16),
            // 下半：任务列表（复用 VoiceTaskPanel）
            const Align(
              alignment: Alignment.centerLeft,
              child: Text(
                '后台任务',
                style: TextStyle(fontSize: 12, color: Colors.grey),
              ),
            ),
            const SizedBox(height: 4),
            const Flexible(
              child: VoiceTaskPanel(),
            ),
          ],
        ),
      ),
    );
  }
}
