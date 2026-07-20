import 'dart:async';
import 'dart:convert';
import 'dart:io';

import '../config.dart';

/// 语音服务连接状态
enum VoiceConnectionStatus {
  connected,
  connecting,
  disconnected,
  error,
}

/// 实时语音双工服务
///
/// 通过 WebSocket 连接后端 `/voice/realtime`，
/// 桥接 Qwen-Audio-3.0-Realtime 真双工语音交互。
///
/// 支持两种模式：
/// - realtime: 后端有 QWEN_AUDIO_API_KEY，真双工流式语音
/// - mock: 后端无 API Key，降级为 mock 模式（依然可用）
///
/// 平台适配：
/// - iOS/Android: 支持麦克风采集（需 record 包）和音频播放
/// - HarmonyOS: 降级为文本输入模式（Platform.isAndroid/isIOS 检查）
class VoiceRealtimeService {
  static final VoiceRealtimeService _instance = VoiceRealtimeService._();
  factory VoiceRealtimeService() => _instance;
  VoiceRealtimeService._();

  WebSocket? _ws;
  String? _token;
  String? _projectId;
  String? _sessionId;
  String _mode = 'mock';

  bool _intentionalClose = false;
  Timer? _heartbeatTimer;

  // ── 状态回调 ──
  final List<void Function(VoiceConnectionStatus)> _statusCallbacks = [];
  final List<void Function(VoiceConnectionStatus)> _statusOnce = [];

  // ── 数据回调 ──
  void Function(String text, bool isFinal)? onTranscript;
  void Function(String base64Audio)? onAudioDelta;
  void Function()? onAudioDone;
  void Function()? onSpeechStarted;
  void Function()? onSpeechStopped;
  void Function(String name, Map<String, dynamic> result)? onToolCall;
  void Function()? onResponseDone;
  void Function(String message)? onError;

  // ── 情绪趋势回调 ──
  void Function(Map<String, dynamic> data)? onEmotionTrend;

  // ── 连接状态 ──
  VoiceConnectionStatus _status = VoiceConnectionStatus.disconnected;
  VoiceConnectionStatus get status => _status;

  bool get isConnected =>
      _ws != null && _ws!.readyState == WebSocket.open;

  String get mode => _mode;
  String? get sessionId => _sessionId;

  // ── URL 构建 ──

  Uri _buildUri() {
    final base = AppConfig.apiBaseUrl;
    String wsBase;
    // 优先使用构建期注入的 WebSocket 地址
    if (AppConfig.wsBaseUrl.isNotEmpty) {
      wsBase = AppConfig.wsBaseUrl;
    } else if (base.isEmpty) {
      wsBase = 'ws://localhost:8767';
    } else {
      // apiBaseUrl 以 /api 结尾，WebSocket 需剥离
      wsBase = base
          .replaceFirst(RegExp(r'^http://'), 'ws://')
          .replaceFirst(RegExp(r'^https://'), 'wss://')
          .replaceFirst(RegExp(r'/api$'), '');
      // https://i-home.life/api → wss://i-home.life
    }

    final queryParams = <String, String>{'token': _token!};
    if (_projectId != null && _projectId!.isNotEmpty) {
      queryParams['project_id'] = _projectId!;
    }
    final query = Uri(queryParameters: queryParams).query;

    return Uri.parse('$wsBase/api/voice/realtime?$query');
  }

  // ── 连接管理 ──

  /// 建立语音 WebSocket 连接
  Future<void> connect({
    required String token,
    String? projectId,
  }) async {
    _token = token;
    _projectId = projectId;

    _setStatus(VoiceConnectionStatus.connecting);
    _intentionalClose = false;

    try {
      final uri = _buildUri();
      _ws = await WebSocket.connect(uri.toString());
      _setStatus(VoiceConnectionStatus.connected);

      // 启动心跳
      _startHeartbeat();

      // 监听消息
      _ws!.listen(
        _onMessage,
        onError: (error) {
          _onError('WebSocket error: $error');
        },
        onDone: () {
          if (!_intentionalClose) {
            _setStatus(VoiceConnectionStatus.disconnected);
          }
        },
        cancelOnError: false,
      );
    } catch (e) {
      _setStatus(VoiceConnectionStatus.error);
      _onError('Connection failed: $e');
    }
  }

  /// 断开连接
  Future<void> disconnect() async {
    _intentionalClose = true;
    _stopHeartbeat();
    await _ws?.close();
    _ws = null;
    _sessionId = null;
    _mode = 'mock';
    _setStatus(VoiceConnectionStatus.disconnected);
  }

  void _setStatus(VoiceConnectionStatus s) {
    _status = s;
    for (final cb in _statusCallbacks) {
      cb(s);
    }
    for (final cb in _statusOnce) {
      cb(s);
    }
    _statusOnce.clear();
  }

  void onStatusChange(void Function(VoiceConnectionStatus) cb) {
    _statusCallbacks.add(cb);
  }

  /// 等待连接就绪（返回当前状态或等待下次状态变化）
  Future<VoiceConnectionStatus> waitForConnected({Duration timeout = const Duration(seconds: 10)}) {
    if (_status == VoiceConnectionStatus.connected) {
      return Future.value(_status);
    }
    final completer = Completer<VoiceConnectionStatus>();
    _statusOnce.add((s) {
      if (!completer.isCompleted) completer.complete(s);
    });
    return completer.future.timeout(timeout, onTimeout: () => _status);
  }

  // ── 心跳 ──

  void _startHeartbeat() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      _send({'type': 'ping'});
    });
  }

  void _stopHeartbeat() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = null;
  }

  // ── 发送消息 ──

  void _send(Map<String, dynamic> msg) {
    if (_ws != null && _ws!.readyState == WebSocket.open) {
      _ws!.add(jsonEncode(msg));
    }
  }

  /// 发送音频数据块（base64 PCM16 编码）
  void sendAudio(String base64Pcm16) {
    _send({
      'type': 'audio',
      'data': base64Pcm16,
      'format': 'pcm16',
    });
  }

  /// 标记音频输入结束（提交缓冲区触发推理）
  void sendAudioEnd() {
    _send({'type': 'audio_end'});
  }

  /// 打断当前 AI 响应
  void sendInterrupt() {
    _send({'type': 'interrupt'});
  }

  /// 发送文本输入（用于 mock 模式或文字备选）
  void sendText(String content) {
    _send({
      'type': 'text',
      'content': content,
    });
  }

  /// 查询情绪趋势
  void getEmotionTrend() {
    _send({'type': 'get_emotion_trend'});
  }

  // ── 消息处理 ──

  void _onMessage(dynamic data) {
    try {
      final msg = jsonDecode(data as String) as Map<String, dynamic>;
      final type = msg['type'] as String? ?? '';

      switch (type) {
        case 'connected':
          _sessionId = msg['session_id'] as String?;
          _mode = msg['mode'] as String? ?? 'mock';
          break;

        // ── 转写事件 ──
        case 'transcript_delta':
          onTranscript?.call(msg['text'] as String? ?? '', false);
          break;

        case 'transcript_done':
          onTranscript?.call(msg['text'] as String? ?? '', true);
          break;

        // ── 音频输出 ──
        case 'audio_delta':
          onAudioDelta?.call(msg['data'] as String? ?? '');
          break;

        case 'audio_done':
          onAudioDone?.call();
          break;

        // ── 语音活动 ──
        case 'speech_started':
          onSpeechStarted?.call();
          break;

        case 'speech_stopped':
          onSpeechStopped?.call();
          break;

        // ── 工具调用 ──
        case 'tool_call':
          final name = msg['name'] as String? ?? '';
          final result = msg['result'] as Map<String, dynamic>? ?? {};
          onToolCall?.call(name, result);
          break;

        // ── 响应完成 ──
        case 'response_done':
          onResponseDone?.call();
          break;

        // ── 中断确认 ──
        case 'interrupt_ack':
          // 打断已确认
          break;

        // ── 情绪趋势 ──
        case 'emotion_trend':
          onEmotionTrend?.call(msg['data'] as Map<String, dynamic>? ?? {});
          break;

        // ── 情绪检测 ──
        case 'emotion':
          // mock 模式下的情绪检测结果
          break;

        // ── 回复（mock 模式） ──
        case 'reply':
          final text = msg['text'] as String? ?? '';
          onTranscript?.call(text, true);
          break;

        // ── 升级提醒 ──
        case 'escalation':
          // 需要人工处理的通知
          break;

        // ── 错误 ──
        case 'error':
          onError?.call(msg['message'] as String? ?? 'Unknown error');
          break;

        // ── 心跳响应 ──
        case 'pong':
          break;

        default:
          break;
      }
    } catch (e) {
      _onError('Message parse error: $e');
    }
  }

  void _onError(String message) {
    onError?.call(message);
  }
}
