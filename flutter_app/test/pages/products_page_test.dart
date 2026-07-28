import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/products_page.dart';

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

  testWidgets('页面渲染 - 显示 AppBar 标题和 2 个 Tab', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'products': jsonResponse([]),
    });

    await tester.pumpWidget(createTestApp(const ProductsPage()));
    await tester.pumpAndSettle();

    expect(find.text('产品库'), findsOneWidget);
    expect(find.text('产品浏览'), findsOneWidget);
    expect(find.text('搜索'), findsOneWidget);
  });

  testWidgets('空态展示 - 无产品时显示空态', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'products': jsonResponse([]),
    });

    await tester.pumpWidget(createTestApp(const ProductsPage()));
    await tester.pumpAndSettle();

    expect(find.text('暂无产品'), findsOneWidget);
    expect(find.byIcon(Icons.inventory_2_outlined), findsOneWidget);
  });

  testWidgets('产品列表 - 有数据时渲染产品卡片', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'products': jsonResponse([
        {
          'id': 'prod-1',
          'name': '客厅地砖',
          'category': 'tile',
          'specs': {'brand': '东鹏'},
          'price_min': 80,
          'price_max': 150,
          'unit': '片',
          'stock_status': 'in_stock',
        },
      ]),
    });

    await tester.pumpWidget(createTestApp(const ProductsPage()));
    await tester.pumpAndSettle();

    expect(find.text('客厅地砖'), findsOneWidget);
    expect(find.text('瓷砖 · 东鹏'), findsOneWidget);
    expect(find.text('有货'), findsOneWidget);
    expect(find.text('暂无产品'), findsNothing);
  });
}
