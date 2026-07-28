// 动线分析 widget 测试 — 对齐 Web v2 DesignPage 双视图 Tab
//
// 测试覆盖：
//   1. 渲染：切到动线分析 tab，可见房间编辑器 + 分析按钮
//   2. 加载预设：点"加载典型两居室预设"，出现 8 间房行
//   3. 分析成功：mock /agents/design/circulation 返回固定响应，展示评分卡 + 动线明细 + 问题列表
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/design_deepening_page.dart';

import '../test_helper.dart';
import '../mock_http.dart';

/// 动线分析 mock 响应（对齐后端 analyze_circulation 返回结构）
Map<String, dynamic> _circMockResponse() => {
      'rooms_count': 8,
      'circulations': [
        {
          'type': 'visitor',
          'name': '访客动线',
          'description': '玄关 → 客厅 → 餐厅',
          'path': [
            {'name': '玄关', 'type': 'entryway'},
            {'name': '客厅', 'type': 'living_room'},
          ],
          'segments': [
            {'from': '玄关', 'to': '客厅', 'distance': 3.5},
          ],
          'total_length': 10.5,
          'crossed_rooms': [],
          'missing_types': [],
          'score': 82,
          'rating': 'good',
          'issues': [],
          'suggestions': ['建议玄关增设换鞋凳'],
        },
        {
          'type': 'housework',
          'name': '家务动线',
          'description': '厨房 → 餐厅 → 阳台',
          'path': [
            {'name': '厨房', 'type': 'kitchen'},
          ],
          'segments': [
            {'from': '厨房', 'to': '餐厅', 'distance': 2.5},
          ],
          'total_length': 8.0,
          'crossed_rooms': ['客厅'],
          'missing_types': [],
          'score': 68,
          'rating': 'fair',
          'issues': [
            {
              'type': 'cross_room',
              'severity': 'warning',
              'detail': '家务动线穿越客厅',
            },
          ],
          'suggestions': ['建议厨房与餐厅相邻布置'],
        },
        {
          'type': 'living',
          'name': '居住动线',
          'description': '主卧 → 主卫 → 次卧',
          'path': [
            {'name': '主卧', 'type': 'bedroom'},
          ],
          'segments': [
            {'from': '主卧', 'to': '主卫', 'distance': 2.0},
          ],
          'total_length': 5.0,
          'crossed_rooms': [],
          'missing_types': [],
          'score': 90,
          'rating': 'excellent',
          'issues': [],
          'suggestions': [],
        },
      ],
      'overall_score': 78,
      'rating': 'good',
      'rating_text': '良好',
      'total_issues': 2,
      'critical_count': 0,
      'warning_count': 2,
      'issues': [
        {
          'type': 'cross_room',
          'severity': 'warning',
          'message': '家务动线穿越客厅，可能影响私密性',
        },
        {
          'type': 'too_long',
          'severity': 'info',
          'message': '访客动线总长 10.5m，可优化',
        },
      ],
      'suggestions': [
        '建议调整厨房位置，避免穿越客厅',
        '玄关处可增加收纳功能',
      ],
      'reply': '整体动线布局良好，三大动线评分 78 分。',
    };

/// Finder：匹配 key 含 'design-circ-room-row' 的 Card（即房间行）
Finder _roomRowCards = find.byWidgetPredicate(
  (widget) =>
      widget is Card &&
      widget.key != null &&
      widget.key.toString().contains('design-circ-room-row'),
);

void main() {
  setUp(() {
    setupTestEnv();
    mockConnectivityCheck();
  });

  tearDown(() {
    HttpOverrides.global = null;
  });

  // 辅助：切换到"动线分析"Tab
  Future<void> switchToCirculationTab(WidgetTester tester) async {
    await tester.tap(find.text('动线分析'));
    await tester.pumpAndSettle();
  }

  testWidgets('渲染 - 切到动线分析 tab，可见房间编辑器 + 分析按钮', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      // 平面方案 Tab 初始加载 → 空列表
      'floorplans/project': jsonResponse([]),
    });

    await tester.pumpWidget(
      createTestApp(const DesignDeepeningPage(projectId: 'test-proj')),
    );
    await tester.pumpAndSettle();

    // 默认在"平面方案"Tab，切换到"动线分析"
    await switchToCirculationTab(tester);

    // 房间布局编辑器标题
    expect(find.text('房间布局（坐标单位：米）'), findsOneWidget);
    // 默认 1 个空房间行
    expect(_roomRowCards, findsNWidgets(1));
    // 分析按钮
    expect(find.text('分析动线'), findsOneWidget);
    // 添加房间按钮
    expect(find.text('添加房间'), findsOneWidget);
    // 加载预设按钮
    expect(find.text('加载典型两居室预设'), findsOneWidget);
  });

  testWidgets('加载预设 - 点击后出现 8 间房行', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'floorplans/project': jsonResponse([]),
    });

    await tester.pumpWidget(
      createTestApp(const DesignDeepeningPage(projectId: 'test-proj')),
    );
    await tester.pumpAndSettle();

    await switchToCirculationTab(tester);

    // 初始 1 行
    expect(_roomRowCards, findsNWidgets(1));

    // 点击加载预设
    await tester.tap(find.text('加载典型两居室预设'));
    await tester.pumpAndSettle();

    // 应出现 8 间房行
    expect(_roomRowCards, findsNWidgets(8));

    // 验证预设房间名称出现在 TextField 中
    // 注意：'玄关'/'客厅' 等同时是房间名称和下拉选项标签，故 findsAtLeast(1)
    expect(find.text('玄关'), findsAtLeastNWidgets(1));
    expect(find.text('客厅'), findsAtLeastNWidgets(1));
    // '主卧'/'次卧' 不是下拉选项标签，仅出现在 TextField 中
    expect(find.text('主卧'), findsOneWidget);
    expect(find.text('次卧'), findsOneWidget);
  });

  testWidgets('分析成功 - 展示评分卡 + 动线明细 + 问题列表', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'floorplans/project': jsonResponse([]),
      'agents/design/circulation': jsonResponse(_circMockResponse()),
    });

    await tester.pumpWidget(
      createTestApp(const DesignDeepeningPage(projectId: 'test-proj')),
    );
    await tester.pumpAndSettle();

    await switchToCirculationTab(tester);

    // 加载预设（确保有 8 个有效房间）
    await tester.tap(find.text('加载典型两居室预设'));
    await tester.pumpAndSettle();

    // 滚动到分析按钮并点击（8 行后按钮可能在视口外）
    await tester.ensureVisible(find.text('分析动线'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('分析动线'));
    await tester.pumpAndSettle();

    // ── 综合评分卡 ──
    expect(find.text('综合评分'), findsOneWidget);
    // 总分 78
    expect(find.text('78'), findsOneWidget);
    // 评级文字"良好"
    expect(find.text('良好'), findsOneWidget);
    // 房间数 / 问题统计
    expect(find.textContaining('8 房间'), findsOneWidget);
    expect(find.textContaining('2 问题'), findsOneWidget);

    // ── 三大动线明细 ──
    expect(find.text('访客动线'), findsOneWidget);
    expect(find.text('家务动线'), findsOneWidget);
    expect(find.text('居住动线'), findsOneWidget);
    // 动线评分
    expect(find.text('82'), findsOneWidget);
    expect(find.text('68'), findsOneWidget);
    expect(find.text('90'), findsOneWidget);

    // ── 全局问题清单 ──
    expect(find.text('问题清单（2）'), findsOneWidget);
    // 滚动到问题清单（可能在视口外）
    await tester.ensureVisible(find.text('问题清单（2）'));
    await tester.pumpAndSettle();
    expect(
      find.text('家务动线穿越客厅，可能影响私密性'),
      findsOneWidget,
    );
    // severity 徽章
    expect(find.text('警告'), findsAtLeastNWidgets(1));
    expect(find.text('提示'), findsAtLeastNWidgets(1));

    // ── 优化建议 ──
    await tester.ensureVisible(find.text('优化建议（2）'));
    await tester.pumpAndSettle();
    expect(find.text('优化建议（2）'), findsOneWidget);
    expect(
      find.textContaining('建议调整厨房位置'),
      findsOneWidget,
    );
  });
}
