import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';

import '../services/offline_cache_service.dart';
import 'ai_chat_page.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  bool _isOffline = false;
  StreamSubscription<bool>? _connectivitySub;

  @override
  void initState() {
    super.initState();
    _initConnectivity();
  }

  Future<void> _initConnectivity() async {
    final online = await OfflineCacheService().isConnected();
    if (mounted) setState(() => _isOffline = !online);
    _connectivitySub = OfflineCacheService().onConnectivityChanged.listen((online) {
      if (mounted) {
        setState(() => _isOffline = !online);
        // 无障碍：网络状态变化时主动播报，让 TalkBack/VoiceOver 用户感知
        // 使用 v3.35+ 的 sendAnnouncement（多窗口安全），取代已弃用的 announce
        unawaited(SemanticsService.sendAnnouncement(
          View.of(context),
          online ? '已恢复在线连接' : '已进入离线模式，显示缓存数据',
          TextDirection.ltr,
        ));
      }
    });
  }

  @override
  void dispose() {
    _connectivitySub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          if (_isOffline) _buildOfflineBanner(),
          const Expanded(child: AIChatPage()),
        ],
      ),
    );
  }

  Widget _buildOfflineBanner() {
    return Semantics(
      container: true,
      label: '离线模式横幅：当前离线，显示缓存数据',
      child: Container(
        color: const Color(0xFFE65100),
        padding: EdgeInsets.only(
          top: MediaQuery.of(context).padding.top,
          bottom: 8,
          left: 16,
          right: 16,
        ),
        child: const Row(
          children: [
            Icon(Icons.cloud_off, color: Colors.white, size: 16),
            SizedBox(width: 8),
            Text('离线模式 · 显示缓存数据',
                style: TextStyle(color: Colors.white, fontSize: 13)),
          ],
        ),
      ),
    );
  }
}
