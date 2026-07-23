import 'dart:async';
import 'package:flutter/material.dart';

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
      if (mounted) setState(() => _isOffline = !online);
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
    return Container(
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
    );
  }
}
