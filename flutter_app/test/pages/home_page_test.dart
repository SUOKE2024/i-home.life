import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/ai_chat_page.dart';
import 'package:ihome_app/pages/home_page.dart';

import '../test_helper.dart';
import '../mock_http.dart';

/// Mock connectivity_plus 的 check 方法，返回指定的连接结果。
void mockConnectivityResults(List<String> results) {
  const channel = MethodChannel('dev.fluttercommunity.plus/connectivity');
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(channel, (MethodCall call) async {
    switch (call.method) {
      case 'check':
        return results;
      default:
        return null;
    }
  });
}

void main() {
  setUp(() {
    setupTestEnv();
    // 默认 mock：所有 API 返回空列表，避免子页面网络请求阻塞测试
    HttpOverrides.global = MockHttpOverrides({});
  });

  tearDown(() {
    HttpOverrides.global = null;
  });

  testWidgets('页面渲染 - 在线时嵌入 AIChatPage 且不显示离线横幅', (tester) async {
    mockConnectivityResults(['wifi']);

    await tester.pumpWidget(createTestApp(const HomePage()));
    await tester.pump();
    // connectivity_plus EventChannel listen 失败属预期，清除之
    tester.takeException();
    await tester.pump(const Duration(milliseconds: 100));
    tester.takeException();

    // HomePage 为 AI 聊天中心架构：主体是 AIChatPage
    expect(find.byType(AIChatPage), findsOneWidget);
    // 在线时不显示离线横幅
    expect(find.text('离线模式 · 显示缓存数据'), findsNothing);
    expect(find.byIcon(Icons.cloud_off), findsNothing);
  });

  testWidgets('离线状态 - 显示离线提示横幅', (tester) async {
    mockConnectivityResults(['none']);

    await tester.pumpWidget(createTestApp(const HomePage()));
    await tester.pump();
    tester.takeException();
    await tester.pump(const Duration(milliseconds: 100));
    tester.takeException();

    // 离线时顶部显示横幅，AIChatPage 仍然渲染
    expect(find.text('离线模式 · 显示缓存数据'), findsOneWidget);
    expect(find.byIcon(Icons.cloud_off), findsOneWidget);
    expect(find.byType(AIChatPage), findsOneWidget);
  });
}
