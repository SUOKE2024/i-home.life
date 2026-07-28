import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/quality_report_page.dart';

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

  testWidgets('页面渲染 - 显示 AppBar 标题和项目选择器', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'projects': jsonResponse([
        {'id': 'p1', 'name': '测试项目'},
      ]),
    });

    await tester.pumpWidget(createTestApp(const QualityReportPage()));
    await tester.pumpAndSettle();

    expect(find.text('质检报告'), findsOneWidget);
    expect(find.text('测试项目'), findsOneWidget);
    expect(find.byIcon(Icons.refresh), findsOneWidget);
  });

  testWidgets('空态展示 - 无验收记录时显示空态卡片', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'projects': jsonResponse([
        {'id': 'p1', 'name': '测试项目'},
      ]),
    });

    await tester.pumpWidget(createTestApp(const QualityReportPage()));
    await tester.pumpAndSettle();

    // 汇总卡片显示 0
    expect(find.text('总计 (项)'), findsOneWidget);
    expect(find.text('通过 (项)'), findsOneWidget);
    expect(find.text('未通过 (项)'), findsOneWidget);
    expect(find.text('待验收 (项)'), findsOneWidget);
    // 空态卡片
    expect(find.text('暂无验收记录'), findsOneWidget);
    // 综合通过率标题
    expect(find.text('综合通过率'), findsOneWidget);
  });
}
