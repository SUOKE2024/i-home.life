import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/budget_page.dart';

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

  testWidgets('页面渲染 - 显示 3 个 Tab 标签', (tester) async {
    // Mock 预算接口返回空数据，确保页面正常渲染
    HttpOverrides.global = MockHttpOverrides({
      'budgets/project': jsonResponse({}, status: 404),
      'budgets/templates': jsonResponse({'templates': []}),
    });

    await tester.pumpWidget(
      createTestApp(const BudgetPage(projectId: 'test-id')),
    );
    await tester.pumpAndSettle();

    // 验证 3 个 Tab 标签
    expect(find.text('当前预算'), findsOneWidget);
    expect(find.text('方案对比'), findsOneWidget);
    expect(find.text('模板库'), findsOneWidget);

    // 验证 AppBar 标题
    expect(find.text('预算管理'), findsOneWidget);
  });

  testWidgets('空态展示 - 无预算时显示空态图标和按钮', (tester) async {
    // Mock 预算接口返回 404 → _budget = null → 显示空态
    HttpOverrides.global = MockHttpOverrides({
      'budgets/project': jsonResponse({}, status: 404),
      'budgets/templates': jsonResponse({'templates': []}),
    });

    await tester.pumpWidget(
      createTestApp(const BudgetPage(projectId: 'test-id')),
    );
    await tester.pumpAndSettle();

    // 验证空态图标
    expect(find.byIcon(Icons.account_balance_wallet), findsOneWidget);
    // 验证空态文本
    expect(find.text('暂无预算'), findsOneWidget);
    // 验证操作按钮
    expect(find.text('从 BOM 生成预算'), findsOneWidget);
    expect(find.byIcon(Icons.auto_awesome), findsOneWidget);
  });
}
