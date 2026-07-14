import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:ui' show VoidCallback;

import '../config.dart';

/// WebSocket 连接状态
enum WsConnectionStatus {
  connected,
  disconnected,
  reconnecting,
  error,
  failed,
}

/// WebSocket 客户端服务（单例）
///
/// 连接后端 `/ws/{project_id}?token=PASETO`，
/// 支持自动重连（指数退避，最多 5 次）、事件订阅、消息去重。
class WebSocketService {
  static final WebSocketService _instance = WebSocketService._();
  factory WebSocketService() => _instance;
  WebSocketService._();

  WebSocket? _ws;
  String? _token;
  String? _projectId;
  String? _currentUserId;

  int _reconnectAttempts = 0;
  static const int _maxReconnect = 5;
  static const Duration _reconnectBaseDelay = Duration(seconds: 1);

  Timer? _reconnectTimer;
  bool _intentionalClose = false;

  // 事件订阅：event → [callback]
  final Map<String, List<Function>> _listeners = {};

  // 状态回调
  final List<void Function(WsConnectionStatus)> _statusCallbacks = [];

  // 已渲染消息 ID（防重复）
  final Set<String> _renderedIds = {};

  /// 当前是否已连接
  bool get isConnected => _ws != null && _ws!.readyState == WebSocket.open;

  // ── URL 构建 ──

  Uri _buildUri() {
    final base = AppConfig.apiBaseUrl;
    String wsBase;
    if (base.isEmpty) {
      wsBase = 'ws://localhost:8080';
    } else {
      wsBase = base
          .replaceFirst(RegExp(r'^http://'), 'ws://')
          .replaceFirst(RegExp(r'^https://'), 'wss://');
    }
    return Uri.parse(
      '$wsBase/ws/${Uri.encodeComponent(_projectId!)}?token=${Uri.encodeQueryComponent(_token!)}',
    );
  }

  // ── 连接 ──

  /// 建立 WebSocket 连接。
  ///
  /// [pasetoToken] 认证令牌，
  /// [projectId] 项目 ID，
  /// [currentUserId] 当前用户 ID（用于过滤自身消息）。
  Future<void> connect({
    required String pasetoToken,
    required String projectId,
    String currentUserId = '',
  }) async {
    _token = pasetoToken;
    _projectId = projectId;
    _currentUserId = currentUserId;
    _intentionalClose = false;

    await _doConnect();
  }

  Future<void> _doConnect() async {
    try {
      _ws = await WebSocket.connect(_buildUri().toString());
      _reconnectAttempts = 0;
      _notifyStatus(WsConnectionStatus.connected);

      _ws!.listen(
        (message) {
          _onMessage(message as String);
        },
        onError: (error) {
          _notifyStatus(WsConnectionStatus.error);
          _scheduleReconnect();
        },
        onDone: () {
          _notifyStatus(WsConnectionStatus.disconnected);
          _scheduleReconnect();
        },
        cancelOnError: false,
      );
    } catch (e) {
      _notifyStatus(WsConnectionStatus.error);
      _scheduleReconnect();
    }
  }

  void _onMessage(String raw) {
    try {
      final decoded = jsonDecode(raw) as Map<String, dynamic>;
      final evt = decoded['event'] as String? ?? 'message';
      final data = decoded['data'];

      if (evt == 'connected') return;

      _dispatch(evt, data);
    } catch (_) {
      // 忽略解析失败的消息
    }
  }

  // ── 事件订阅 ──

  /// 订阅指定事件。
  ///
  /// 返回一个取消订阅的函数（调用即可取消）。
  VoidCallback on(String event, void Function(dynamic data) callback) {
    _listeners.putIfAbsent(event, () => []);
    _listeners[event]!.add(callback);
    return () => off(event, callback);
  }

  /// 取消订阅。
  void off(String event, void Function(dynamic data) callback) {
    final arr = _listeners[event];
    if (arr == null) return;
    arr.remove(callback);
  }

  void _dispatch(String event, dynamic data) {
    final arr = _listeners[event];
    if (arr == null) return;
    for (final cb in arr) {
      try {
        cb(data);
      } catch (_) {
        // 回调异常不影响其他订阅者
      }
    }
  }

  // ── 发送消息 ──

  /// 发送 JSON 消息。
  ///
  /// 返回 true 表示发送成功，false 表示连接未就绪。
  bool send(String event, Map<String, dynamic> data) {
    if (!isConnected) {
      return false;
    }
    _ws!.add(jsonEncode({'event': event, 'data': data}));
    return true;
  }

  // ── 消息去重 ──

  /// 标记消息已渲染。
  void markRendered(String messageId) {
    if (messageId.isNotEmpty) {
      _renderedIds.add(messageId);
    }
  }

  /// 检查消息是否已渲染。
  bool hasRendered(String messageId) {
    return messageId.isNotEmpty && _renderedIds.contains(messageId);
  }

  // ── 状态监听 ──

  /// 注册状态变化回调。
  void onStatusChange(void Function(WsConnectionStatus) callback) {
    _statusCallbacks.add(callback);
  }

  void _notifyStatus(WsConnectionStatus status) {
    for (final cb in _statusCallbacks) {
      try {
        cb(status);
      } catch (_) {
        // 回调异常不影响其他监听者
      }
    }
  }

  // ── 自动重连 ──

  void _scheduleReconnect() {
    if (_intentionalClose) return;
    if (_reconnectAttempts >= _maxReconnect) {
      _notifyStatus(WsConnectionStatus.failed);
      return;
    }

    _reconnectTimer?.cancel();
    _reconnectAttempts++;
    final delay = _reconnectBaseDelay * (1 << (_reconnectAttempts - 1));
    _notifyStatus(WsConnectionStatus.reconnecting);
    _reconnectTimer = Timer(delay, () {
      if (_token != null && _projectId != null) {
        _doConnect();
      }
    });
  }

  // ── 关闭连接 ──

  /// 主动关闭连接，阻止自动重连。
  void close() {
    _intentionalClose = true;
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _ws?.close();
    _ws = null;
  }
}
