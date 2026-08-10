import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/b2b_delivery_page.dart';

import '../test_helper.dart';
import '../mock_http.dart';

/// P1 QA — B2B 装企交付页（T1 三态 / T4 时区）
void main() {
  setUp(() => setupTestEnv());

  tearDown(() => HttpOverrides.global = null);

  // 轮询 pump 直到条件满足或超时（规避异步加载时序 flaky）
  Future<void> pumpUntil(WidgetTester tester, bool Function() cond,
      {int max = 30}) async {
    for (var i = 0; i < max; i++) {
      await tester.pump(const Duration(milliseconds: 100));
      if (cond()) return;
    }
  }

  // 使用高视口：创建表单占满默认 600px 视口，交付单卡片在懒加载
  // ListView 折叠线以下不会被构建，导致 find 找不到 → 强制拉高视口
  void useTallViewport(WidgetTester tester) {
    tester.view.physicalSize = const Size(800, 2000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
  }

  testWidgets('T1 成功态 - 加载交付单列表', (tester) async {
    useTallViewport(tester);
    // 后端 list_deliveries 直接返回 List（无 {code,data} 包装）
    final mock = MockHttpOverrides({
      '/api/b2b/delivery': jsonResponse([
        {
          'delivery_order_id': 'd1',
          'name': '朝阳丽景 3-1201',
          'status': 'draft',
          'created_at': '2026-08-09T08:00:00+08:00',
        },
      ]),
    });
    HttpOverrides.global = mock;

    await tester.pumpWidget(createTestApp(const B2BDeliveryPage()));
    await tester.pump(const Duration(milliseconds: 100));
    await pumpUntil(tester, () => tester.any(find.textContaining('朝阳丽景')));

    // 列表项渲染（页面读 name 字段，L504）
    expect(find.textContaining('朝阳丽景'), findsOneWidget);
  });

  testWidgets('T2 降级态 - 接口 503 诚实提示', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      '/api/b2b/delivery': jsonResponse({'detail': '功能未启用'}, status: 503),
    });

    await tester.pumpWidget(createTestApp(const B2BDeliveryPage()));
    await tester.pump(const Duration(milliseconds: 100));
    await pumpUntil(tester, () => tester.any(find.textContaining('功能未启用')));

    // 页面展示 result.error（ErrorRetryWidget，L296）
    expect(find.textContaining('功能未启用'), findsOneWidget);
  });

  testWidgets('T4 时区 - 交付时间走 _formatTime 格式化展示', (tester) async {
    useTallViewport(tester);
    HttpOverrides.global = MockHttpOverrides({
      '/api/b2b/delivery': jsonResponse([
        {
          'delivery_order_id': 'd1',
          'name': '朝阳丽景 3-1201',
          'area': 108.5,
          'style': 'modern',
          'status': 'draft',
          'created_at': '2026-08-09T08:00:00+08:00',
        },
      ]),
    });

    await tester.pumpWidget(createTestApp(const B2BDeliveryPage()));
    await tester.pump(const Duration(milliseconds: 100));
    await pumpUntil(tester, () => tester.any(find.textContaining('㎡')));

    // 卡片 subtitle（L513）: '{area}㎡ · {style} · {_formatTime}'，含 '㎡'；
    // 表单标签 '建筑面积（㎡，必填）' 也含 '㎡' → findsWidgets
    expect(find.textContaining('㎡'), findsWidgets);
    // _formatTime 输出 'YYYY-MM-DD HH:mm'，raw ISO 'T08:00' 不应出现在页面上
    expect(find.textContaining('T08:00'), findsNothing);
  });
}
