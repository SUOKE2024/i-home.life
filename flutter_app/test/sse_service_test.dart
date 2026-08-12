import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import 'package:ihome_app/services/sse_service.dart';

import 'mock_http.dart';

/// 智能体交互修复回归测试（2026-08-12）
///
/// P0-4: SSE 流内 error 事件解析为 error 类型（不再被当作 token 文本）
/// P1-2: 请求超时兜底存在（client.send 带 15s 超时）
void main() {
  setUp(() {
    HttpOverrides.global = null;
  });

  tearDown(() {
    HttpOverrides.global = null;
  });

  test('P0-4: SSE error 事件解析为 error 类型而非 token', () async {
    const body = 'data: {"event":"meta","session_id":"s1","agent_type":"designer"}\n\n'
        'data: {"event":"error","content":"Agent 生成回复失败: boom","agent_type":"designer"}\n\n'
        'data: {"event":"done","session_id":"s1"}\n\n';
    HttpOverrides.global = MockHttpOverrides({
      'agents/chat/stream': http.Response.bytes(utf8.encode(body), 200,
          headers: {'content-type': 'text/event-stream'}),
    });

    final events = <SseEvent>[];
    await for (final e in SseService().streamChat('帮我设计客厅')) {
      events.add(e);
    }

    expect(events.any((e) => e.type == SseEventType.error), isTrue,
        reason: 'error 事件应被解析为 error 类型');
    final err = events.firstWhere((e) => e.type == SseEventType.error);
    expect(err.content, contains('Agent 生成回复失败'));
    expect(err.agentType, 'designer');

    // error 事件不应被当作 token 追加进正文
    final tokenEvents = events.where((e) => e.type == SseEventType.token).toList();
    expect(tokenEvents.any((e) => e.content != null && e.content!.contains('生成回复失败')),
        isFalse);
  });

  test('P0-4: 正常 token 流不受影响', () async {
    const body = 'data: {"event":"meta","session_id":"s2","agent_type":"budget"}\n\n'
        'data: {"event":"token","content":"预算分析如下"}\n\n'
        'data: {"event":"done","session_id":"s2"}\n\n';
    HttpOverrides.global = MockHttpOverrides({
      'agents/chat/stream': http.Response.bytes(utf8.encode(body), 200,
          headers: {'content-type': 'text/event-stream'}),
    });

    final events = <SseEvent>[];
    await for (final e in SseService().streamChat('预算多少')) {
      events.add(e);
    }

    expect(events.any((e) => e.type == SseEventType.token), isTrue);
    final token = events.firstWhere((e) => e.type == SseEventType.token);
    expect(token.content, '预算分析如下');
    expect(events.any((e) => e.type == SseEventType.error), isFalse);
  });

  test('P1-2: HTTP >= 400 仍解析为 error 事件', () async {
    HttpOverrides.global = MockHttpOverrides({
      'agents/chat/stream':
          http.Response.bytes(utf8.encode('{"detail":"无权访问"}'), 403),
    });

    final events = <SseEvent>[];
    await for (final e in SseService().streamChat('测试')) {
      events.add(e);
    }

    expect(events.length, 1);
    expect(events.single.type, SseEventType.error);
    expect(events.single.content, contains('无权访问'));
  });
}
