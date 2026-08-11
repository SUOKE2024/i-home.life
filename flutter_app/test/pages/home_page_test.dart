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

  testWidgets('在线 + 无项目 - 渲染「家的生命线」空态且不显示离线横幅', (tester) async {
    mockConnectivityResults(['wifi']);

    await tester.pumpWidget(createTestApp(const HomePage()));
    await tester.pump();
    // connectivity_plus EventChannel listen 失败属预期，清除之
    tester.takeException();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 200));
    tester.takeException();

    // 2026 重构：首页为「家的生命线」，无项目时显示空态，聊天为次入口
    expect(find.text('还没有项目'), findsOneWidget);
    expect(find.byType(AIChatPage), findsNothing);
    expect(find.text('离线模式 · 显示缓存数据'), findsNothing);
  });

  testWidgets('在线 + 有项目 - 渲染生命线/健康分/空间状态/主动卡片/管家入口', (tester) async {
    mockConnectivityResults(['wifi']);
    HttpOverrides.global = MockHttpOverrides({
      'projects': jsonResponse([
        {'id': 'p1', 'name': '云栖玫瑰园', 'status': 'in_progress', 'total_area': 120, 'address': '3-1202'},
      ]),
      'floorplans/project': jsonResponse([
        {'id': 'fp1', 'name': '三室两厅', 'room_count': 4, 'total_area': 120, 'is_active': true},
      ]),
      'progress-alerts': jsonResponse([
        {'id': 'a1', 'severity': 'high', 'status': 'open', 'phase': '瓦工', 'message': '地砖铺贴延期 2 天', 'suggestion': '协调加班'},
      ]),
      'construction/milestones': jsonResponse([
        {'id': 'm1', 'name': '瓦工验收', 'status': 'completed', 'actual_date': '2026-08-01'},
      ]),
    });

    await tester.pumpWidget(createTestApp(const HomePage()));
    await tester.pump();
    tester.takeException();
    // 等待项目 + 户型 + 预警 + 里程碑 并行加载完成
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 300));
    tester.takeException();

    // 生命线顶部板块
    expect(find.text('家的生命线'), findsWidgets);
    expect(find.text('施工健康分'), findsOneWidget);
    expect(find.text('空间状态'), findsOneWidget);
    // 滚动到折叠区（SliverList 懒加载）后断言主动卡片流 + 管家入口
    await tester.drag(find.byType(CustomScrollView), const Offset(0, -700));
    await tester.pump();
    expect(find.text('管家主动卡片'), findsOneWidget);
    expect(find.text('地砖铺贴延期 2 天'), findsOneWidget);
    expect(find.text('进度预警 · Health OS 自动生成'), findsOneWidget);
    expect(find.text('对话 AI 管家'), findsOneWidget);
    // 聊天为次入口：不直接内嵌
    expect(find.byType(AIChatPage), findsNothing);
  });

  testWidgets('在线 + 有项目 - 渲染「家的生命线」+ 户型图逐房间状态 + A2UI 卡片并入 feed', (tester) async {
    mockConnectivityResults(['wifi']);
    HttpOverrides.global = MockHttpOverrides({
      'projects': jsonResponse([
        {'id': 'p1', 'name': '云栖玫瑰园', 'status': 'in_progress', 'total_area': 120, 'address': '3-1202'},
      ]),
      'floorplans/project': jsonResponse([
        {
          'id': 'fp1', 'name': '三室两厅', 'room_count': 2, 'total_area': 96, 'is_active': true,
          'room_status': {'客厅': 'in_progress', '主卧': 'completed'},
        },
      ]),
      'floorplans/fp1': jsonResponse({
        'id': 'fp1', 'name': '三室两厅', 'total_area': 96, 'room_count': 2, 'is_active': true,
        'data': '{"walls":[],"rooms":[{"name":"客厅","room_type":"living_room","area":30.0},{"name":"主卧","room_type":"bedroom","area":18.0}]}',
        'room_status': {'客厅': 'in_progress', '主卧': 'completed'},
      }),
      'feed': jsonResponse({
        'cards': [
          {
            'type': 'alert_card',
            'data': {'severity': 'high', 'title': '进度预警 · 水电', 'message': '水电验收延期 3 天'},
          },
          {
            'type': 'budget_breakdown',
            'data': {'project_name': '预算测试', 'items': [], 'total': 20000.0, 'subtotal': 20000.0},
          },
        ],
        'source_note': '按现有数据生成',
      }),
    });

    await tester.pumpWidget(createTestApp(const HomePage()));
    await tester.pump();
    tester.takeException();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 300));
    tester.takeException();

    // 户型图逐房间状态（激活户型）
    expect(find.text('空间状态'), findsOneWidget);
    expect(find.text('户型图'), findsOneWidget);
    expect(find.textContaining('客厅'), findsWidgets);
    expect(find.textContaining('施工中'), findsWidgets);
    expect(find.textContaining('已完成'), findsWidgets);

    // A2UI 卡片并入首页 feed
    await tester.drag(find.byType(CustomScrollView), const Offset(0, -900));
    await tester.pump();
    expect(find.text('管家主动卡片'), findsOneWidget);
    expect(find.textContaining('水电验收延期 3 天'), findsOneWidget);
    expect(find.text('预算测试'), findsOneWidget);
    expect(find.text('卡片由项目现有数据按 A2UI 协议生成，仅供导航参考'), findsOneWidget);
  });

  testWidgets('离线状态 - 显示离线提示横幅', (tester) async {
    mockConnectivityResults(['none']);

    await tester.pumpWidget(createTestApp(const HomePage()));
    await tester.pump();
    tester.takeException();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 200));
    tester.takeException();

    // 离线时顶部显示横幅
    expect(find.text('离线模式 · 显示缓存数据'), findsOneWidget);
    expect(find.byIcon(Icons.cloud_off), findsOneWidget);
    expect(find.byType(AIChatPage), findsNothing);
  });
}
