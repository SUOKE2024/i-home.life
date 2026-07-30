// v1.2.8 语音对话区（融合面板上半）
//
// 展示：波纹动画（聆听中）+ 实时转写文本
// 订阅 VoiceRealtimeService 的 onTranscript / onSpeechStarted / onSpeechStopped
import 'package:flutter/material.dart';

import '../services/voice_realtime_service.dart';

class VoiceConversationArea extends StatefulWidget {
  const VoiceConversationArea({super.key, required this.service});

  final VoiceRealtimeService service;

  @override
  State<VoiceConversationArea> createState() => _VoiceConversationAreaState();
}

class _VoiceConversationAreaState extends State<VoiceConversationArea>
    with SingleTickerProviderStateMixin {
  late AnimationController _rippleController;
  String _transcript = '';
  bool _isListening = false;

  @override
  void initState() {
    super.initState();
    _rippleController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    );
    widget.service.onTranscript = _onTranscript;
    widget.service.onSpeechStarted = _onSpeechStarted;
    widget.service.onSpeechStopped = _onSpeechStopped;
  }

  @override
  void dispose() {
    _rippleController.dispose();
    super.dispose();
  }

  void _onTranscript(String text, bool isFinal) {
    setState(() {
      _transcript = text;
    });
  }

  void _onSpeechStarted() {
    setState(() => _isListening = true);
    _rippleController.repeat();
  }

  void _onSpeechStopped() {
    setState(() => _isListening = false);
    _rippleController.stop();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // 波纹动画 + 麦克风图标
        SizedBox(
          height: 64,
          child: Center(
            child: AnimatedBuilder(
              animation: _rippleController,
              builder: (_, child) {
                return Stack(
                  alignment: Alignment.center,
                  children: [
                    // 外圈波纹
                    if (_isListening)
                      Container(
                        width: 48 + _rippleController.value * 16,
                        height: 48 + _rippleController.value * 16,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: Colors.blue.withValues(
                              alpha: 0.2 * (1 - _rippleController.value)),
                        ),
                      ),
                    child!,
                  ],
                );
              },
              child: Container(
                width: 40,
                height: 40,
                decoration: const BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: LinearGradient(
                    colors: [Color(0xFF007AFF), Color(0xFF00C6FF)],
                  ),
                ),
                child: const Icon(Icons.mic, color: Colors.white, size: 20),
              ),
            ),
          ),
        ),
        const SizedBox(height: 8),
        // 转写文本
        Container(
          constraints: const BoxConstraints(minHeight: 24),
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: Text(
            _transcript.isEmpty
                ? (_isListening ? '正在聆听…' : '点击麦克风开始说话')
                : _transcript,
            style: TextStyle(
              fontSize: 13,
              color: _transcript.isEmpty ? Colors.grey : Colors.black87,
            ),
            textAlign: TextAlign.center,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
        ),
      ],
    );
  }
}
