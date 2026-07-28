import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/settlement_page.dart';

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
      'settlements/project': jsonResponse({}, status: 404),
      'settlements/milestones': jsonResponse({'milestones': []}),
    });

    await tester.pumpWidget(
      createTestApp(const SettlementPage(projectId: 'test-id')),
    );
    await tester.pumpAndSettle();

    expect(find.text('结算确认'), findsOneWidget);
    expect(find.text('结算单'), findsOneWidget);
    expect(find.text('里程碑'), findsOneWidget);
    expect(find.text('异常检测'), findsOneWidget);
  });

  testWidgets('空态展示 - 无结算单时显示空态和生成按钮', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'settlements/project': jsonResponse({}, status: 404),
      'settlements/milestones': jsonResponse({'milestones': []}),
    });

    await tester.pumpWidget(
      createTestApp(const SettlementPage(projectId: 'test-id')),
    );
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.receipt_long), findsOneWidget);
    expect(find.text('暂无结算单'), findsOneWidget);
    expect(find.text('从预算生成结算'), findsOneWidget);
    expect(find.byIcon(Icons.auto_awesome), findsOneWidget);
  });

  testWidgets('结算单数据 - 渲染金额汇总、状态徽章和操作按钮', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'settlements/project': jsonResponse({
        'id': 'set-001-2026',
        'project_id': 'test-id',
        'total_amount': 200000,
        'status': 'draft',
        'contract_amount': 200000,
        'change_amount': 15000,
        'paid_amount': 80000,
        'items': [
          {'id': 'li-1', 'settlement_id': 'set-001-2026', 'amount': 100000, 'note': '一期款', 'milestone': '开工款'}
        ],
      }),
      'settlements/milestones': jsonResponse({'milestones': []}),
    });

    await tester.pumpWidget(
      createTestApp(const SettlementPage(projectId: 'test-id')),
    );
    await tester.pumpAndSettle();

    // 应付余额 = totalAmount - paidAmount = 200000 - 80000 = 120000
    expect(find.text('应付余额'), findsOneWidget);
    expect(find.text('¥120000.00'), findsOneWidget);
    // 金额行
    expect(find.text('合同金额'), findsOneWidget);
    expect(find.text('变更金额'), findsOneWidget);
    expect(find.text('¥15000.00'), findsOneWidget);
    expect(find.text('已付金额'), findsOneWidget);
    expect(find.text('¥80000.00'), findsOneWidget);
    // 合同金额与合计金额均为 200000
    expect(find.text('¥200000.00'), findsNWidgets(2));
    // 状态徽章（draft → 草稿）
    expect(find.text('草稿'), findsOneWidget);
    // 结算明细
    expect(find.text('一期款'), findsOneWidget);
    // 操作按钮（draft 状态显示）
    expect(find.text('确认结算'), findsOneWidget);
    expect(find.text('异议反馈'), findsOneWidget);
  });
}
