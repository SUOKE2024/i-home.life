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

  SseEvent({required this.type, this.content, this.agentType});

  @override
  String toString() => 'SseEvent(type: $type, content: $content, agentType: $agentType)';
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
  /// [history] 可选的对话历史。
  Stream<SseEvent> streamChat(
    String message, {
    String agentType = 'orchestrator',
    String? projectId,
    List<Map<String, dynamic>>? history,
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

          if (msgType == 'meta') {
            yield SseEvent(
              type: SseEventType.meta,
              agentType: data['agent_type'] as String?,
            );
          } else if (msgType == 'token') {
            yield SseEvent(
              type: SseEventType.token,
              content: data['content'] as String? ?? '',
            );
          } else if (msgType == 'done') {
            receivedDone = true;
            yield SseEvent(type: SseEventType.done);
          } else {
            // 未知类型当作 token 文本处理
            final content = data['content'] as String?;
            if (content != null && content.isNotEmpty) {
              yield SseEvent(type: SseEventType.token, content: content);
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
      response?.stream.drain();
      client.close();
    }
  }
}
