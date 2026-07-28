import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/materials_page.dart';

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

  testWidgets('页面渲染 - 显示 AppBar 标题和搜索框', (tester) async {
    // mock 顺序很重要：'materials/categories' 必须在 'materials' 之前，
    // 否则 /materials/categories 会被 'materials' 抢先匹配。
    // 注意 url.path 不含 query string，所以 /materials?limit=200 的 path 是 /materials。
    HttpOverrides.global = MockHttpOverrides({
      'materials/categories': jsonResponse([]),
      'materials': jsonResponse([]),
    });

    await tester.pumpWidget(createTestApp(const MaterialsPage()));
    await tester.pumpAndSettle();

    expect(find.text('物料库'), findsOneWidget);
    expect(find.text('搜索物料...'), findsOneWidget);
    expect(find.text('全部'), findsOneWidget);
  });

  testWidgets('物料列表 - 有数据时渲染物料卡片', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'materials/categories': jsonResponse([
        {'code': 'tile', 'name': '瓷砖'},
      ]),
      'materials': jsonResponse([
        {
          'id': 'm1',
          'name': '通体大理石瓷砖',
          'brand': '马可波罗',
          'category': {'code': 'tile', 'name': '瓷砖'},
          'unit': '片',
          'unit_price': 120,
        },
      ]),
    });

    await tester.pumpWidget(createTestApp(const MaterialsPage()));
    await tester.pumpAndSettle();

    expect(find.text('通体大理石瓷砖'), findsOneWidget);
    expect(find.text('马可波罗'), findsOneWidget);
    expect(find.text('¥120'), findsOneWidget);
    expect(find.text('瓷砖'), findsOneWidget);
  });
}
