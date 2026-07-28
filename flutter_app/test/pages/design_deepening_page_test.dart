import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/design_deepening_page.dart';

import '../test_helper.dart';
import '../mock_http.dart';

/// 动线分析 mock 响应（对齐后端 analyze_circulation 真实返回结构：
/// app/agents/designer.py:185 analyze_circulation）
Map<String, dynamic> _mockCirculationResult() {
  return {
    'rooms_count': 8,
    'circulations': [
      {
        'type': 'visitor',
        'name': '访客动线',
        'description': '玄关 → 客厅 → 餐厅 → 客卫',
        'path': [
          {'name': '玄关', 'type': 'entryway'},
          {'name': '客厅', 'type': 'living_room'},
        ],
        'segments': [
          {'from': '玄关', 'to': '客厅', 'distance': 3.5},
        ],
        'total_length': 3.5,
        'crossed_rooms': <String>[],
        'missing_types': ['dining_room', 'bathroom'],
        'score': 85,
        'issues': [
          {
            'type': 'missing_room',
            'severity': 'info',
            'detail': '动线缺少房间类型：dining_room, bathroom',
          },
        ],
        'suggestions': ['访客动线布局合理，无需调整'],
      },
      {
        'type': 'housework',
        'name': '家务动线',
        'description': '厨房 → 餐厅，阳台 → 晾晒，卫生间 → 洗衣',
        'path': [
          {'name': '厨房', 'type': 'kitchen'},
          {'name': '餐厅', 'type': 'dining_room'},
        ],
        'segments': [
          {'from': '厨房', 'to': '餐厅', 'distance': 2.1},
        ],
        'total_length': 2.1,
        'crossed_rooms': <String>[],
        'missing_types': ['balcony'],
        'score': 90,
        'issues': <Map<String, dynamic>>[],
        'suggestions': ['家务动线布局合理，无需调整'],
      },
      {
        'type': 'living',
        'name': '居住动线',
        'description': '卧室 → 卫生间 → 衣帽间，私密且短捷',
        'path': [
          {'name': '主卧', 'type': 'bedroom'},
          {'name': '主卫', 'type': 'bathroom'},
        ],
        'segments': [
          {'from': '主卧', 'to': '主卫', 'distance': 1.8},
        ],
        'total_length': 1.8,
        'crossed_rooms': <String>[],
        'missing_types': ['cloakroom'],
        'score': 95,
        'issues': <Map<String, dynamic>>[],
        'suggestions': ['居住动线布局合理，无需调整'],
      },
    ],
    'overall_score': 90.0,
    'rating': 'excellent',
    'rating_text': '优秀',
    'total_issues': 1,
    'critical_count': 0,
    'warning_count': 0,
    'issues': [
      {
        'type': 'missing_room',
        'severity': 'info',
        'detail': '动线缺少房间类型：dining_room, bathroom',
      },
    ],
    'suggestions': [
      '访客动线布局合理，无需调整',
      '家务动线布局合理，无需调整',
      '居住动线布局合理，无需调整',
    ],
    'reply': '动线分析：8 个房间，综合评分 90.0（优秀），三条动线均合理',
  };
}

void main() {
  setUp(() {
    setupTestEnv();
    mockConnectivityCheck();
  });

  tearDown(() {
    HttpOverrides.global = null;
  });

  testWidgets('渲染 - 双视图切换 + 平面方案 tab 默认', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'floorplans/project': jsonResponse([]),
    });

    await tester.pumpWidget(
        createTestApp(const DesignDeepeningPage(projectId: 'p1')));
    await tester.pumpAndSettle();

    // AppBar 标题
    expect(find.text('设计深化'), findsOneWidget);
    // 双视图 Tab
    expect(find.text('平面方案'), findsOneWidget);
    expect(find.text('动线分析'), findsOneWidget);
    // 平面方案默认空态
    expect(find.text('暂无设计方案'), findsOneWidget);
    // 平面方案 tab 下的 FAB 显示
    expect(find.byType(FloatingActionButton), findsOneWidget);
  });

  testWidgets('切换到动线分析 tab - 显示房间编辑器与分析按钮', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'floorplans/project': jsonResponse([]),
    });

    await tester.pumpWidget(
        createTestApp(const DesignDeepeningPage(projectId: 'p1')));
    await tester.pumpAndSettle();

    // 点击「动线分析」tab
    await tester.tap(find.text('动线分析'));
    await tester.pumpAndSettle();

    // 房间布局区标题
    expect(find.text('房间布局（坐标单位：米）'), findsOneWidget);
    // 默认有一行房间编辑器（名称输入框 labelText = '名称'）
    expect(find.text('名称'), findsOneWidget);
    // 类型下拉默认显示「客厅」
    expect(find.text('客厅'), findsOneWidget);
    // 操作按钮
    expect(find.text('添加房间'), findsOneWidget);
    expect(find.text('加载典型两居室预设'), findsOneWidget);
    expect(find.text('分析动线'), findsOneWidget);
    // 动线分析 tab 下不显示平面方案的 FAB
    expect(find.byType(FloatingActionButton), findsNothing);
  });

  testWidgets('加载预设 → 分析动线 → 显示评分卡与动线列表', (tester) async {
    // 扩大视口确保 8 行房间编辑器与分析按钮均可见（默认 800x600 不够）
    await tester.binding.setSurfaceSize(const Size(800, 2400));

    HttpOverrides.global = MockHttpOverrides({
      'floorplans/project': jsonResponse([]),
      'agents/design/circulation': jsonResponse(_mockCirculationResult()),
    });

    await tester.pumpWidget(
        createTestApp(const DesignDeepeningPage(projectId: 'p1')));
    await tester.pumpAndSettle();

    // 切换到动线分析 tab
    await tester.tap(find.text('动线分析'));
    await tester.pumpAndSettle();

    // 加载典型两居室预设（8 间房）
    await tester.tap(find.text('加载典型两居室预设'));
    await tester.pumpAndSettle();

    // 预设包含的房间名称出现在编辑器中
    expect(find.text('玄关'), findsWidgets);
    expect(find.text('客厅'), findsWidgets);
    expect(find.text('主卧'), findsWidgets);

    // 点击分析动线
    await tester.tap(find.text('分析动线'));
    await tester.pumpAndSettle();

    // 综合评分卡
    expect(find.text('综合评分'), findsOneWidget);
    // overall_score=90.0 → 后端返回 double，页面以 num 渲染为 "90.0"
    expect(find.byKey(const Key('design-circ-overall-score')), findsOneWidget);
    expect(find.text('90.0'), findsOneWidget);
    expect(find.text('优秀'), findsAtLeastNWidgets(1)); // rating_text
    // 统计：8 房间 · 1 问题（0 严重 / 0 警告）
    expect(find.textContaining('8 房间'), findsOneWidget);
    expect(find.textContaining('1 问题'), findsOneWidget);

    // 三大动线标题与动线名称
    expect(find.text('三大动线（3）'), findsOneWidget);
    expect(find.text('访客动线'), findsOneWidget);
    expect(find.text('家务动线'), findsOneWidget);
    expect(find.text('居住动线'), findsOneWidget);

    // 问题清单（全局 issues，severity 徽章「提示」）
    expect(find.text('问题清单（1）'), findsOneWidget);
    expect(find.text('提示'), findsAtLeastNWidgets(1));

    // 优化建议
    expect(find.text('优化建议（3）'), findsOneWidget);
  });

  testWidgets('错误降级 - 后端 500 时显示错误提示而非崩溃', (tester) async {
    // 扩大视口确保分析按钮可见
    await tester.binding.setSurfaceSize(const Size(800, 2400));

    HttpOverrides.global = MockHttpOverrides({
      'floorplans/project': jsonResponse([]),
      // 模拟后端 500 错误
      'agents/design/circulation':
          jsonResponse({'detail': '服务器内部错误'}, status: 500),
    });

    await tester.pumpWidget(
        createTestApp(const DesignDeepeningPage(projectId: 'p1')));
    await tester.pumpAndSettle();

    // 切换到动线分析 tab
    await tester.tap(find.text('动线分析'));
    await tester.pumpAndSettle();

    // 加载预设（提供有效房间数据）
    await tester.tap(find.text('加载典型两居室预设'));
    await tester.pumpAndSettle();

    // 点击分析动线 → 后端返回 500
    await tester.tap(find.text('分析动线'));
    await tester.pumpAndSettle();

    // 应显示错误提示容器（key=design-circ-error），不崩溃
    expect(find.byKey(const Key('design-circ-error')), findsOneWidget);
    // 不应显示结果区
    expect(find.byKey(const Key('design-circ-result')), findsNothing);
    expect(find.text('综合评分'), findsNothing);
  });
}
