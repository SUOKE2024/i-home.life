import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config.dart';
import 'api.dart';

/// SSE 流式事件类型
enum SseEventType {
  /// Agent 类型切换
  meta,
  /// 文本内容
  token,
  /// 流结束
  done,
}

/// 单个 SSE 事件
class SseEvent {
  final SseEventType type;
  final String? content;
  final String? agentType;
  final String? sessionId;
  // v1.1.26: 卡片类型（如 ar_scan_trigger/camera_trigger/voice_input_trigger）
  final String? messageType;
  // v1.1.26: 卡片 payload（含 title/project_id/sensor_type 等）
  final Map<String, dynamic>? cardPayload;

  SseEvent({
    required this.type,
    this.content,
    this.agentType,
    this.sessionId,
    this.messageType,
    this.cardPayload,
  });

  @override
  String toString() => 'SseEvent(type: $type, content: $content, agentType: $agentType, sessionId: $sessionId, messageType: $messageType)';
}

/// SSE 流式聊天客户端
///
/// 通过 POST 请求 `/agents/chat/stream` 获取服务端推送的 SSE 事件流，
/// 解析 `data: {json}\n\n` 格式并转换为 [SseEvent] 流。
class SseService {
  final ApiClient _api = ApiClient();

  /// 发起流式聊天请求。
  ///
  /// [message] 用户消息内容，
  /// [agentType] 目标 Agent 类型（默认 orchestrator），
  /// [projectId] 可选的项目上下文，
  /// [history] 可选的对话历史，
  /// [sessionId] 可选的会话 ID（用于会话持久化）。
  Stream<SseEvent> streamChat(
    String message, {
    String agentType = 'orchestrator',
    String? projectId,
    List<Map<String, dynamic>>? history,
    String? sessionId,
  }) async* {
    final token = _api.token;

    final uri = Uri.parse('${AppConfig.apiBaseUrl}/agents/chat/stream');

    final body = <String, dynamic>{
      'message': message,
      'agent_type': agentType,
    };
    if (projectId != null) {
      body['project_id'] = projectId;
    }
    if (history != null) {
      body['history'] = history;
    }
    if (sessionId != null) {
      body['session_id'] = sessionId;
    }

    final request = http.Request('POST', uri)
      ..headers.addAll({
        'Content-Type': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token',
      })
      ..body = jsonEncode(body);

    final client = http.Client();
    http.StreamedResponse? response;

    try {
      response = await client.send(request);

      if (response.statusCode >= 400) {
        final errorBody = await response.stream.bytesToString();
        String errorMsg;
        try {
          final decoded = jsonDecode(errorBody);
          errorMsg = decoded['detail'] ?? '请求失败 (${response.statusCode})';
        } catch (_) {
          errorMsg = '请求失败 (${response.statusCode})';
        }
        yield SseEvent(type: SseEventType.done, content: errorMsg);
        return;
      }

      final lineStream = response.stream
          .transform(utf8.decoder)
          .transform(const LineSplitter());

      // 跟踪是否已收到后端发送的 done 事件，避免重复发出
      bool receivedDone = false;

      await for (final line in lineStream) {
        if (line.isEmpty) continue;
        if (!line.startsWith('data: ')) continue;

        final jsonStr = line.substring(6);
        if (jsonStr == '[DONE]') {
          receivedDone = true;
          yield SseEvent(type: SseEventType.done);
          continue;
        }

        try {
          final data = jsonDecode(jsonStr) as Map<String, dynamic>;
          // 后端 /agents/chat/stream 使用 "event" 字段标识事件类型
          // (兼容旧版本/第三方实现也允许 "type")
          final msgType = (data['event'] ?? data['type']) as String?;
          final sid = data['session_id'] as String?;

          if (msgType == 'meta') {
            yield SseEvent(
              type: SseEventType.meta,
              agentType: data['agent_type'] as String?,
              sessionId: sid,
              messageType: data['message_type'] as String?,
              cardPayload: data['card_payload'] as Map<String, dynamic>?,
            );
          } else if (msgType == 'token') {
            yield SseEvent(
              type: SseEventType.token,
              content: data['content'] as String? ?? '',
              sessionId: sid,
            );
          } else if (msgType == 'done') {
            receivedDone = true;
            yield SseEvent(type: SseEventType.done, sessionId: sid);
          } else {
            // 未知类型当作 token 文本处理
            final content = data['content'] as String?;
            if (content != null && content.isNotEmpty) {
              yield SseEvent(type: SseEventType.token, content: content, sessionId: sid);
            }
          }
        } catch (_) {
          // 对于解析失败的 data 行，跳过
          // 但如果是纯文本行（非 JSON），可能部分 SSE 实现直接发送文本
          if (jsonStr.isNotEmpty) {
            yield SseEvent(type: SseEventType.token, content: jsonStr);
          }
        }
      }

      // 仅在后端未发送 done 事件时补发（如连接异常断开）
      if (!receivedDone) {
        yield SseEvent(type: SseEventType.done);
      }
    } finally {
      // response.stream 是单订阅流，try 块中已被完全消费（bytesToString 或 await for），
      // 再次 drain 会触发 "Stream has already been listened to"。
      // 这里仅需关闭 client，不再尝试 drain。
      client.close();
    }
  }
}
