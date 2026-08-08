import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/b2b_delivery_page.dart';

import '../test_helper.dart';
import '../mock_http.dart';

/// P1 QA — B2B 装企交付页（T1 三态 / T4 时区）
void main() {
  setUp(() => setupTestEnv());

  tearDown(() => HttpOverrides.global = null);

  testWidgets('T1 成功态 - 加载交付单列表', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      '/api/b2b/delivery?skip=0&limit=20': {
        'code': 0,
        'data': [
          {
            'id': 'd1',
            'status': 'draft',
            'project_name': '朝阳丽景 3-1201',
            'created_at': '2026-08-09T08:00:00+08:00',
          },
        ],
      },
    });

    await tester.pumpWidget(createTestApp(const B2BDeliveryPage()));
    await tester.pump(const Duration(milliseconds: 300));

    // 列表项渲染（按页面实际字段调整）
    expect(find.textContaining('朝阳丽景'), findsOneWidget);
  });

  testWidgets('T2 降级态 - 接口 503 诚实提示', (tester) async {
    HttpOverrides.global = MockHttpOverrides.error('/api/b2b/delivery', 503);

    await tester.pumpWidget(createTestApp(const B2BDeliveryPage()));
    await tester.pump(const Duration(milliseconds: 300));

    // 降级文案以页面实现为准
    expect(find.textContaining('不可用'), findsOneWidget);
  });

  testWidgets('T4 时区 - 交付时间显示 +08:00', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      '/api/b2b/delivery?skip=0&limit=20': {
        'code': 0,
        'data': [
          {
            'id': 'd1',
            'status': 'draft',
            'project_name': '朝阳丽景 3-1201',
            'created_at': '2026-08-09T08:00:00+08:00',
          },
        ],
      },
    });

    await tester.pumpWidget(createTestApp(const B2BDeliveryPage()));
    await tester.pump(const Duration(milliseconds: 300));

    // 时间展示断言（按页面格式化实现调整）
    expect(find.textContaining('+08:00'), findsOneWidget);
  });
}
