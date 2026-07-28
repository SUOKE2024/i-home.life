import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/takeoff_page.dart';

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
    HttpOverrides.global = MockHttpOverrides({});

    await tester.pumpWidget(
      createTestApp(const TakeoffPage(projectId: 'test-id')),
    );
    await tester.pumpAndSettle();

    expect(find.text('工程量计算'), findsOneWidget);
    expect(find.text('工程量汇总'), findsOneWidget);
    expect(find.text('明细列表'), findsOneWidget);
  });

  testWidgets('空态展示 - 初始状态显示空态、参数输入和自动计算按钮', (tester) async {
    HttpOverrides.global = MockHttpOverrides({});

    await tester.pumpWidget(
      createTestApp(const TakeoffPage(projectId: 'test-id')),
    );
    await tester.pumpAndSettle();

    expect(find.text('暂无工程量数据'), findsOneWidget);
    expect(find.text('请输入参数后点击「自动计算」'), findsOneWidget);
    expect(find.text('自动计算'), findsOneWidget);
    expect(find.text('参数输入'), findsOneWidget);
    expect(find.text('墙体参数'), findsOneWidget);
    expect(find.text('楼板参数'), findsOneWidget);
    expect(find.text('地面参数'), findsOneWidget);
    // Icons.calculate 出现 2 次：空态图标 + 自动计算按钮图标
    expect(find.byIcon(Icons.calculate), findsNWidgets(2));
  });

  testWidgets('自动计算 - 显示工程量汇总卡片和计算结果', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'takeoff/project': jsonResponse({
        'reply': '工程量已生成，请查看下方明细',
        'summary': {
          'total_paint_area_m2': 100.0,
          'total_formwork_m2': 50.0,
          'total_concrete_m3': 6.0,
          'total_mortar_m3': 2.4,
          'total_rebar_kg': 480.0,
          'total_brick_count': 5000,
          'total_tile_count': 140,
        },
        'walls': [
          {'length': 10.0, 'height': 3.0, 'thickness': 0.24, 'volume': 7.2, 'brick_type': 'standard_brick'}
        ],
        'slabs': [
          {'area': 50.0, 'thickness': 0.12, 'volume': 6.0, 'rebar_weight': 480.0, 'formwork_area': 50.0, 'concrete_grade': 'c25'}
        ],
        'floors': [
          {'area': 50.0, 'tile_count_600x600': 140, 'tile_count_800x800': 0, 'tile_count_750x1500': 0}
        ],
      }),
    });

    await tester.pumpWidget(
      createTestApp(const TakeoffPage(projectId: 'test-id')),
    );
    await tester.pumpAndSettle();

    // 点击「自动计算」按钮
    await tester.tap(find.text('自动计算'));
    // 点击后 _loading=true 触发 LoadingSkeleton（repeat 动画无法 pumpAndSettle）
    // 需逐步 pump 让 mock HTTP 微任务完成、_loading 归零后再 settle
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    await tester.pump(const Duration(milliseconds: 50));
    // _loading 已归零，可安全 pumpAndSettle（SnackBar 动画有限可 settle）
    await tester.pumpAndSettle();

    // 汇总卡片标题（GridView shrinkWrap，可能需滚动到可见）
    // TabBarView 本身是横向 Scrollable，需指定纵向 ListView 内的 Scrollable 避免冲突
    final listViewScrollable = find.descendant(
      of: find.byType(ListView),
      matching: find.byType(Scrollable),
    ).first;
    await tester.scrollUntilVisible(
      find.text('总面积'),
      200,
      scrollable: listViewScrollable,
    );
    expect(find.text('总面积'), findsOneWidget);
    expect(find.text('总体积'), findsOneWidget);
    expect(find.text('总重量'), findsOneWidget);
    expect(find.text('总造价'), findsOneWidget);

    // 滚动到计算结果区域
    await tester.scrollUntilVisible(
      find.text('计算结果'),
      200,
      scrollable: listViewScrollable,
    );
    expect(find.text('计算结果'), findsOneWidget);
    // reply 文本
    expect(find.text('工程量已生成，请查看下方明细'), findsOneWidget);
    // 空态应消失
    expect(find.text('暂无工程量数据'), findsNothing);
  });

}
