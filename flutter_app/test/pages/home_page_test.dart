import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/home_page.dart';
import 'package:ihome_app/services/project_context.dart';

import '../test_helper.dart';
import '../mock_http.dart';

void main() {
  setUp(() {
    setupTestEnv();
    mockConnectivityCheck();
    // 默认 mock：所有 API 返回空列表，避免子页面网络请求阻塞测试
    HttpOverrides.global = MockHttpOverrides({});
  });

  tearDown(() {
    HttpOverrides.global = null;
  });

  testWidgets('页面渲染 - 底部导航栏显示 6 个 tab', (tester) async {
    await tester.pumpWidget(createTestApp(const HomePage()));
    await tester.pump();

    // connectivity_plus 的 EventChannel listen 可能产生预期内的错误，清除之
    tester.takeException();
    await tester.pumpAndSettle();

    // 验证 6 个 NavigationDestination
    expect(find.byType(NavigationDestination), findsNWidgets(6));

    // 验证每个 tab 的标签文本（标签可能同时出现在子页面 AppBar 和导航栏中）
    expect(find.text('工作台'), findsAtLeastNWidgets(1));
    expect(find.text('概览'), findsAtLeastNWidgets(1));
    expect(find.text('项目'), findsAtLeastNWidgets(1));
    expect(find.text('设计台'), findsAtLeastNWidgets(1));
    expect(find.text('物料'), findsAtLeastNWidgets(1));
    expect(find.text('更多'), findsAtLeastNWidgets(1));
  });

  testWidgets('tab 切换 - 点击更多 tab 显示功能列表', (tester) async {
    await tester.pumpWidget(createTestApp(const HomePage()));
    await tester.pump();
    tester.takeException();
    await tester.pumpAndSettle();

    // 点击「更多」tab
    await tester.tap(find.text('更多'));
    await tester.pumpAndSettle();

    // 更多页面应显示标题
    expect(find.text('更多功能'), findsOneWidget);
    // 项目选择器提示
    expect(find.text('选择项目'), findsOneWidget);
  });

  testWidgets('更多页面 - 显示所有功能项', (tester) async {
    // Mock 项目列表，使功能网格可见
    HttpOverrides.global = MockHttpOverrides({
      'api/projects': jsonResponse([
        {'id': 'test-id', 'name': 'Test Project', 'status': 'in_progress'}
      ]),
    });

    // 预加载 ProjectContext，确保切换到「更多」tab 时功能网格立即可见
    final pc = ProjectContext();
    await pc.loadProjects();

    // 设置足够大的屏幕以显示所有 35 个功能项
    // 2 列 × 18 行，每张卡片约 252px 高 + 间距 + 标题/选择器 ≈ 5000px
    tester.view.physicalSize = const Size(800, 5200);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    await tester.pumpWidget(createTestApp(const HomePage(), projectContext: pc));
    await tester.pump();
    tester.takeException();
    await tester.pumpAndSettle();

    // 切换到「更多」tab
    await tester.tap(find.text('更多'));
    await tester.pumpAndSettle();

    // 验证所有 35 个功能项标题
    final expectedItems = [
      '项目详情',
      '预算',
      '施工',
      'AR扫描',
      '深化设计',
      '采购增强',
      '结算',
      '智能家居',
      'VR全景',
      'AI图片',
      '积分商城',
      '身份认证',
      '照明设计',
      '厨房设计',
      '卫浴设计',
      '软装设计',
      '电器规划',
      '硬装设计',
      '门窗防水',
      '家具品类库',
      '水电规划',
      '土建结构',
      '变更订单',
      '工程量',
      '任务管理',
      '产品库',
      '定制家具',
      '厨卫水电',
      '工程队匹配',
      '服务者匹配',
      '场景编辑',
      '协作聊天',
      '装修进度',
      '质检报告',
      '设置',
    ];

    for (final title in expectedItems) {
      expect(find.text(title), findsOneWidget, reason: '应显示功能项: $title');
    }

    // 确认功能项总数为 35
    expect(expectedItems.length, 35);
  });
}
