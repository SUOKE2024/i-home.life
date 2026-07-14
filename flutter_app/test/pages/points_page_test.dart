import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/points_page.dart';

import '../test_helper.dart';
import '../mock_http.dart';

void main() {
  setUp(() {
    setupTestEnv();
    mockConnectivityCheck();
  });

  tearDown(() {
    HttpOverrides.global = null;
  });

  testWidgets('页面渲染 - 显示 4 个 Tab 标签', (tester) async {
    // Mock 积分接口返回空数据，确保页面正常渲染
    HttpOverrides.global = MockHttpOverrides({
      'points/account': jsonResponse(null),
      'points/mall': jsonResponse([]),
      'points/transactions': jsonResponse([]),
    });

    await tester.pumpWidget(createTestApp(const PointsPage()));
    await tester.pumpAndSettle();

    // 验证 4 个 Tab 标签
    expect(find.text('我的积分'), findsOneWidget);
    expect(find.text('商城'), findsOneWidget);
    expect(find.text('兑换记录'), findsOneWidget);
    expect(find.text('排行榜'), findsOneWidget);

    // 验证 AppBar 标题
    expect(find.text('积分商城'), findsOneWidget);
  });

  testWidgets('空态展示 - 无积分数据时显示空态', (tester) async {
    // Mock 积分账户接口返回 null → _account = null → 显示空态
    HttpOverrides.global = MockHttpOverrides({
      'points/account': jsonResponse(null),
      'points/mall': jsonResponse([]),
      'points/transactions': jsonResponse([]),
    });

    await tester.pumpWidget(createTestApp(const PointsPage()));
    await tester.pumpAndSettle();

    // 验证空态图标（在「我的积分」tab 中）
    expect(find.byIcon(Icons.stars), findsOneWidget);
    // 验证空态文本
    expect(find.text('暂无积分账户'), findsOneWidget);
    // 验证刷新按钮
    expect(find.text('刷新'), findsOneWidget);
  });
}
