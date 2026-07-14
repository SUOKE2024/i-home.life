import 'dart:async';
import 'dart:convert';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// 离线缓存服务
///
/// 负责简单的键值对缓存（项目列表、用户信息等），
/// 并提供网络连接状态检查与监听。当网络不可用时，
/// 业务层可降级读取本地缓存以维持基础可用性。
class OfflineCacheService {
  static final OfflineCacheService _instance = OfflineCacheService._();
  factory OfflineCacheService() => _instance;
  OfflineCacheService._();

  /// 缓存键统一前缀，避免与 SharedPreferences 中其它数据冲突
  static const String _prefix = 'offline_cache_';

  // ── 缓存读写 ──

  /// 缓存数据（自动 JSON 序列化）
  Future<void> cacheData(String key, dynamic data) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('$_prefix$key', jsonEncode(data));
  }

  /// 读取缓存数据（反序列化为动态类型），无缓存或解析失败返回 null
  Future<dynamic> getCachedData(String key) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString('$_prefix$key');
    if (raw == null) return null;
    try {
      return jsonDecode(raw);
    } catch (_) {
      return null;
    }
  }

  /// 清除指定缓存
  Future<void> remove(String key) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('$_prefix$key');
  }

  // ── 同步队列（离线操作回放） ──
  // 使用 enqueueSyncOperation 将离线变更加入队列，网络恢复后分批回放

  static const String _syncQueueKey = '${_prefix}sync_queue';

  /// 将离线操作加入同步队列
  Future<void> enqueueSyncOperation(Map<String, dynamic> operation) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_syncQueueKey);
    final List<dynamic> queue = raw != null ? jsonDecode(raw) : [];
    queue.add({
      ...operation,
      'queued_at': DateTime.now().toIso8601String(),
      'retry_count': 0,
    });
    await prefs.setString(_syncQueueKey, jsonEncode(queue));
  }

  /// 获取待同步操作列表
  Future<List<Map<String, dynamic>>> getSyncQueue() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_syncQueueKey);
    if (raw == null) return [];
    final List<dynamic> queue = jsonDecode(raw);
    return queue.cast<Map<String, dynamic>>();
  }

  /// 移除已完成的同步操作
  Future<void> removeSyncOperation(int index) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_syncQueueKey);
    if (raw == null) return;
    final List<dynamic> queue = jsonDecode(raw);
    if (index >= 0 && index < queue.length) {
      queue.removeAt(index);
      await prefs.setString(_syncQueueKey, jsonEncode(queue));
    }
  }

  /// 清空同步队列
  Future<void> clearSyncQueue() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_syncQueueKey);
  }

  /// 获取同步队列长度
  Future<int> get syncQueueLength async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_syncQueueKey);
    if (raw == null) return 0;
    final List<dynamic> queue = jsonDecode(raw);
    return queue.length;
  }

  // ── 网络状态 ──

  /// 检查当前是否联网
  ///
  /// connectivity_plus 6.x 的 checkConnectivity 返回 List<ConnectivityResult>，
  /// 只要存在任意非 none 结果即视为在线。
  Future<bool> isConnected() async {
    final results = await Connectivity().checkConnectivity();
    return results.any((r) => r != ConnectivityResult.none);
  }

  /// 监听网络状态变化（true=在线，false=离线）
  Stream<bool> get onConnectivityChanged {
    return Connectivity().onConnectivityChanged.map(
      (results) => results.any((r) => r != ConnectivityResult.none),
    );
  }
}
