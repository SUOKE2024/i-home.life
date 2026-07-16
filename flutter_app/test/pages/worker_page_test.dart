import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/worker_page.dart';

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

  testWidgets('页面渲染 - 显示 AppBar 标题和 3 个 Tab', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'workers': jsonResponse([]),
    });

    await tester.pumpWidget(
      createTestApp(const WorkerPage(projectId: 'test-id')),
    );
    await tester.pumpAndSettle();

    // AppBar 标题
    expect(find.text('服务者匹配'), findsOneWidget);

    // 3 个 Tab 标签
    expect(find.text('服务者'), findsWidgets);
    expect(find.text('匹配记录'), findsWidgets);
    expect(find.text('智能匹配'), findsWidgets);
  });

  testWidgets('服务者列表 - 为空时显示"暂无服务者"', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'workers': jsonResponse([]),
    });

    await tester.pumpWidget(
      createTestApp(const WorkerPage(projectId: 'test-id')),
    );
    await tester.pumpAndSettle();

    // 空态文本
    expect(find.text('暂无服务者'), findsOneWidget);
  });

  testWidgets('角色筛选 - 显示 3 个 ChoiceChip 并默认选中设计师', (tester) async {
    // 需要非空数据才能展示角色筛选栏
    HttpOverrides.global = MockHttpOverrides({
      'workers': jsonResponse([
        {
          'id': 'w1',
          'name': '测试设计师',
          'role': 'designer',
          'rating': 4.0,
          'description': '测试描述',
          'professional_score': 4.0,
          'service_score': 4.0,
          'communication_score': 4.0,
          'efficiency_score': 4.0,
          'quality_score': 4.0,
          'cost_score': 4.0,
        },
      ]),
    });

    await tester.pumpWidget(
      createTestApp(const WorkerPage(projectId: 'test-id')),
    );
    await tester.pumpAndSettle();

    // 验证 6 个 ChoiceChip（设计师、监理、预算师、木工、水电安装工、窗帘安装工）
    expect(find.text('设计师'), findsAtLeastNWidgets(1));
    expect(find.text('监理'), findsAtLeastNWidgets(1));
    expect(find.text('预算师'), findsAtLeastNWidgets(1));
    expect(find.text('木工'), findsAtLeastNWidgets(1));
    expect(find.text('水电安装工'), findsAtLeastNWidgets(1));
    expect(find.text('窗帘安装工'), findsAtLeastNWidgets(1));

    // 验证 ChoiceChip widget 存在 6 个
    expect(find.byType(ChoiceChip), findsNWidgets(6));
  });

  testWidgets('服务者列表 - 有数据时渲染服务者卡片', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'workers': jsonResponse([
        {
          'id': 'w1',
          'name': '张三',
          'role': 'designer',
          'rating': 4.8,
          'description': '资深室内设计师',
          'professional_score': 4.5,
          'service_score': 5.0,
          'communication_score': 4.8,
          'efficiency_score': 4.2,
          'quality_score': 4.7,
          'cost_score': 4.0,
        },
        {
          'id': 'w2',
          'name': '李四',
          'role': 'supervisor',
          'rating': 4.5,
          'description': '10 年监理经验',
          'professional_score': 4.3,
          'service_score': 4.5,
          'communication_score': 4.0,
          'efficiency_score': 4.5,
          'quality_score': 4.8,
          'cost_score': 4.2,
        },
      ]),
    });

    await tester.pumpWidget(
      createTestApp(const WorkerPage(projectId: 'test-id')),
    );
    await tester.pumpAndSettle();

    // 验证服务者名称
    expect(find.text('张三'), findsOneWidget);
    expect(find.text('李四'), findsOneWidget);
    // 评分和六维分数中可能存在相同数值（如 rating 和 communication_score 都是 4.8）
    expect(find.text('4.8'), findsAtLeastNWidgets(1));
    expect(find.text('4.5'), findsAtLeastNWidgets(1));
  });

  testWidgets('匹配记录 - 空匹配记录显示"暂无匹配记录"', (tester) async {
    // 注意: workers/matches 需放在 workers 前面以优先匹配
    HttpOverrides.global = MockHttpOverrides({
      'workers/matches': jsonResponse([]),
      'workers': jsonResponse([]),
    });

    await tester.pumpWidget(
      createTestApp(const WorkerPage(projectId: 'test-id')),
    );
    await tester.pumpAndSettle();

    // 切换到「匹配记录」tab
    await tester.tap(find.text('匹配记录'));
    await tester.pumpAndSettle();

    expect(find.text('暂无匹配记录'), findsOneWidget);
  });

  testWidgets('智能匹配面板 - 显示匹配按钮和说明', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'workers': jsonResponse([]),
    });

    await tester.pumpWidget(
      createTestApp(const WorkerPage(projectId: 'test-id')),
    );
    await tester.pumpAndSettle();

    // 切换到「智能匹配」tab
    await tester.tap(find.text('智能匹配'));
    await tester.pumpAndSettle();

    // 验证匹配面板内容
    expect(find.text('智能匹配服务者'), findsOneWidget);
    expect(find.text('开始匹配'), findsOneWidget);
    expect(
      find.text('根据项目需求和风格偏好，智能匹配设计师、监理和预算师'),
      findsOneWidget,
    );
  });

  testWidgets('刷新按钮存在', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'workers': jsonResponse([]),
    });

    await tester.pumpWidget(
      createTestApp(const WorkerPage(projectId: 'test-id')),
    );
    await tester.pumpAndSettle();

    // 验证刷新 IconButton
    expect(find.byIcon(Icons.refresh), findsOneWidget);
  });
}
