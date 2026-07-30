// v1.2.8 悬浮窗常驻语音交互 + 讨论式方案交互
//
// 跨页面共享 VoiceRealtimeService 单例，避免方案页重连 WS。
// 悬浮窗创建的 WS 会话通过此 InheritedWidget 暴露给 DesignProposalPage
// 的底部 VoiceProposalBar，保证讨论式交互中语音会话连续不断开。
import 'package:flutter/widgets.dart';

import 'voice_realtime_service.dart';

class VoiceSessionScope extends InheritedWidget {
  const VoiceSessionScope({
    super.key,
    required this.service,
    required super.child,
  });

  /// 共享的语音实时服务单例
  /// 由悬浮窗控制器创建并注入；方案页底部语音条从这里读取，不重连
  final VoiceRealtimeService service;

  static VoiceRealtimeService? of(BuildContext context) {
    final scope = context
        .dependOnInheritedWidgetOfExactType<VoiceSessionScope>();
    return scope?.service;
  }

  @override
  bool updateShouldNotify(VoiceSessionScope oldWidget) =>
      service != oldWidget.service;
}
