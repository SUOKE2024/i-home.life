import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/dashboard_page.dart';
import 'package:ihome_app/widgets/error_retry.dart';

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

  testWidgets('页面渲染 - 显示 AppBar 标题"工作台"', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'projects': jsonResponse([]),
    });

    await tester.pumpWidget(createTestApp(const DashboardPage()));
    await tester.pumpAndSettle();

    expect(find.text('工作台'), findsOneWidget);
  });

  testWidgets('仪表盘数据 - 显示 4 张统计卡片', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'projects': jsonResponse([
        {
          'id': 'p1',
          'name': '项目 A',
          'status': 'in_progress',
          'total_area': 120,
        },
        {
          'id': 'p2',
          'name': '项目 B',
          'status': 'draft',
          'total_area': 80,
        },
      ]),
    });

    await tester.pumpWidget(createTestApp(const DashboardPage()));
    await tester.pumpAndSettle();

    // 验证统计卡片标签
    expect(find.text('项目总数'), findsOneWidget);
    expect(find.text('施工中'), findsOneWidget);
    expect(find.text('总面积'), findsOneWidget);
    expect(find.text('AI Agent'), findsOneWidget);

    // 验证统计卡片数据值
    expect(find.text('2'), findsOneWidget); // 项目总数 = 2
    expect(find.text('1'), findsOneWidget); // 施工中 = 1 (in_progress)
    expect(find.text('200㎡'), findsOneWidget); // 总面积 = 120+80
    expect(find.text('6'), findsOneWidget); // AI Agent 固定值
  });

  testWidgets('仪表盘数据 - 空项目列表时显示 0 项统计', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'projects': jsonResponse([]),
    });

    await tester.pumpWidget(createTestApp(const DashboardPage()));
    await tester.pumpAndSettle();

    // 项目总数和施工中都是 0（"0" 出现多次）
    expect(find.text('0'), findsAtLeastNWidgets(1));
    // 总面积 = 0
    expect(find.text('0㎡'), findsOneWidget);
  });

  testWidgets('仪表盘 - 显示快速入口区域', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'projects': jsonResponse([]),
    });

    await tester.pumpWidget(createTestApp(const DashboardPage()));
    await tester.pumpAndSettle();

    // 快速入口标题
    expect(find.text('快速入口'), findsOneWidget);

    // 4 个快速入口操作
    expect(find.text('设计规划'), findsOneWidget);
    expect(find.text('预算管理'), findsOneWidget);
    expect(find.text('物料采购'), findsOneWidget);
    expect(find.text('施工进度'), findsOneWidget);
  });

  testWidgets('加载失败 - 显示错误重试组件', (tester) async {
    // 返回 500 错误触发 _error 状态
    HttpOverrides.global = MockHttpOverrides({
      'projects': jsonResponse({'detail': '服务器错误'}, status: 500),
    });

    await tester.pumpWidget(createTestApp(const DashboardPage()));
    await tester.pumpAndSettle();

    // 应显示错误重试组件
    expect(find.byType(ErrorRetryWidget), findsOneWidget);
  });
}
