// v1.2.8 方案页底部常驻语音条
//
// 通过 VoiceSessionScope 共享悬浮窗的 WS 会话，不重连。
// 显示：麦克风按钮 + 最新语音指令状态 + 波纹进度
import 'package:flutter/material.dart';

import '../services/voice_session_scope.dart';
import '../theme/suoke_theme.dart';

class VoiceProposalBar extends StatefulWidget {
  const VoiceProposalBar({
    super.key,
    required this.onProposalUpdated,
  });

  /// 方案修订回调：proposal_id + 修订后的方案
  final void Function(String proposalId, Map<String, dynamic> proposal)
      onProposalUpdated;

  @override
  State<VoiceProposalBar> createState() => _VoiceProposalBarState();
}

class _VoiceProposalBarState extends State<VoiceProposalBar> {
  String _lastCommand = '点击麦克风说话';
  bool _isListening = false;

  @override
  Widget build(BuildContext context) {
    final service = VoiceSessionScope.of(context);
    if (service == null) {
      return _buildBar('语音服务未就绪', false);
    }

    // 注册回调（一次性，build 中注册需小心重复；用 didChangeDependencies 更稳）
    service.onTranscript = (text, isFinal) {
      if (mounted && isFinal) setState(() => _lastCommand = text);
    };
    service.onSpeechStarted = () {
      if (mounted) setState(() => _isListening = true);
    };
    service.onSpeechStopped = () {
      if (mounted) setState(() => _isListening = false);
    };
    service.onProposalUpdated = (pid, proposal) {
      widget.onProposalUpdated(pid, proposal);
      if (mounted) setState(() => _lastCommand = '方案 $pid 已更新');
    };

    return _buildBar(_lastCommand, _isListening);
  }

  Widget _buildBar(String text, bool listening) {
    return Container(
      margin: const EdgeInsets.all(12),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF007AFF), Color(0xFF00C6FF)],
        ),
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.15),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        children: [
          // 蓝色渐变底用深色图标/文字（≥4.9:1），白色在 #00C6FF 端仅 1.94:1 不达标
          Icon(listening ? Icons.graphic_eq : Icons.mic, color: SuokeDesignTokens.bgDeep),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(color: SuokeDesignTokens.bgDeep, fontSize: 12),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          if (listening)
            const SizedBox(
              width: 12,
              height: 12,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                valueColor: AlwaysStoppedAnimation(Colors.white),
              ),
            ),
        ],
      ),
    );
  }
}
