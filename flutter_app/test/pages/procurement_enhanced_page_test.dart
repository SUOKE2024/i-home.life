import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/procurement_enhanced_page.dart';

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

  testWidgets('页面渲染 - 显示 AppBar 标题和 4 个 Tab', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'procurement-enhanced/comparisons': jsonResponse([]),
    });

    await tester.pumpWidget(
      createTestApp(const ProcurementEnhancedPage(projectId: 'test-id')),
    );
    await tester.pumpAndSettle();

    expect(find.text('采购增强'), findsOneWidget);
    expect(find.text('比价'), findsOneWidget);
    expect(find.text('托管支付'), findsOneWidget);
    expect(find.text('物流'), findsOneWidget);
    expect(find.text('样品申请'), findsOneWidget);
  });

  testWidgets('空态展示 - 比价 Tab 无数据时显示空态', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'procurement-enhanced/comparisons': jsonResponse([]),
    });

    await tester.pumpWidget(
      createTestApp(const ProcurementEnhancedPage(projectId: 'test-id')),
    );
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.compare_arrows_outlined), findsOneWidget);
    expect(find.text('暂无比价记录，点击右下角新建'), findsOneWidget);
    expect(find.byType(FloatingActionButton), findsOneWidget);
  });

  testWidgets('比价列表 - 有数据时渲染比价卡片', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'procurement-enhanced/comparisons': jsonResponse([
        {
          'id': 'cmp-1',
          'material_name': '瓷砖',
          'status': 'completed',
          'lowest_price': 80,
          'highest_price': 120,
          'offers': [
            {'supplier': 'A', 'price': 80},
            {'supplier': 'B', 'price': 120},
          ],
          'recommended_supplier': 'A',
        },
      ]),
    });

    await tester.pumpWidget(
      createTestApp(const ProcurementEnhancedPage(projectId: 'test-id')),
    );
    await tester.pumpAndSettle();

    expect(find.text('瓷砖'), findsOneWidget);
    expect(find.text('¥80'), findsOneWidget);
    expect(find.text('¥120'), findsOneWidget);
    expect(find.text('已完成'), findsOneWidget);
    expect(find.text('暂无比价记录，点击右下角新建'), findsNothing);
  });
}
