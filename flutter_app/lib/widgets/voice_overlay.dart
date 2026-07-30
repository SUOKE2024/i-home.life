// v1.2.8 悬浮窗常驻语音交互
//
// 借鉴 Qwen-Audio-3.0-Realtime "能聊天更能办事" 范式 + Qoder Voice 悬浮入口：
// 全局悬浮 FAB，任意页面可唤起语音，后台执行 Agent 任务不阻塞当前页面。
//
// 形态（brainstorming 决策 B）：语音+任务融合面板
// - 收起态：右下角 FAB（带 running 任务数角标）
// - 展开态：上下分层面板（上半语音对话区 + 下半任务列表复用 VoiceTaskPanel）
//
// 注入方式：Overlay.of(context).insert(OverlayEntry)，不阻塞当前页交互。
import 'package:flutter/material.dart';

import '../services/voice_realtime_service.dart';
import '../services/voice_session_scope.dart';
import 'voice_fusion_panel.dart';

/// 悬浮窗控制器：管理 OverlayEntry 的显示/隐藏/状态切换
class VoiceOverlayController {
  static final VoiceOverlayController _instance = VoiceOverlayController._();
  factory VoiceOverlayController() => _instance;
  VoiceOverlayController._();

  OverlayEntry? _entry;
  final ValueNotifier<bool> _expanded = ValueNotifier<bool>(false);
  final VoiceRealtimeService _service = VoiceRealtimeService();

  bool get isShown => _entry != null;
  ValueNotifier<bool> get expanded => _expanded;

  /// 注入悬浮窗到根 Overlay（通常在 AuthGate 登录成功后调用）
  void show(BuildContext context) {
    if (_entry != null) return;
    _entry = OverlayEntry(
      builder: (_) => VoiceOverlayWidget(
        service: _service,
        expanded: _expanded,
        onToggle: _toggle,
      ),
    );
    Overlay.of(context, rootOverlay: true).insert(_entry!);
  }

  /// 移除悬浮窗（登出时调用）
  void hide() {
    _entry?.remove();
    _entry = null;
    _expanded.value = false;
  }

  void _toggle() {
    _expanded.value = !_expanded.value;
  }

  VoiceRealtimeService get service => _service;
}

/// 悬浮窗 Widget：收起态 FAB / 展开态融合面板
class VoiceOverlayWidget extends StatelessWidget {
  const VoiceOverlayWidget({
    super.key,
    required this.service,
    required this.expanded,
    required this.onToggle,
  });

  final VoiceRealtimeService service;
  final ValueNotifier<bool> expanded;
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<bool>(
      valueListenable: expanded,
      builder: (context, isExpanded, _) {
        return Positioned(
          right: 16,
          bottom: 16,
          child: AnimatedSwitcher(
            duration: const Duration(milliseconds: 250),
            child: isExpanded
                ? VoiceSessionScope(
                    service: service,
                    child: VoiceFusionPanel(
                      service: service,
                      onCollapse: onToggle,
                    ),
                  )
                : _VoiceFab(
                    onTap: onToggle,
                    service: service,
                  ),
          ),
        );
      },
    );
  }
}

/// 收起态：悬浮语音按钮（带任务数角标）
class _VoiceFab extends StatelessWidget {
  const _VoiceFab({required this.onTap, required this.service});

  final VoidCallback onTap;
  final VoiceRealtimeService service;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 56,
        height: 56,
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Color(0xFF007AFF), Color(0xFF00C6FF)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(28),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.2),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: const Icon(Icons.mic, color: Colors.white, size: 28),
      ),
    );
  }
}
