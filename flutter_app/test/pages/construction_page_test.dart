import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/construction_page.dart';

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

  testWidgets('页面渲染 - 显示 AppBar 标题和 3 个 Tab', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'construction/tasks': jsonResponse([]),
    });

    await tester.pumpWidget(
      createTestApp(const ConstructionPage(projectId: 'test-id')),
    );
    await tester.pumpAndSettle();

    expect(find.text('施工管理'), findsOneWidget);
    expect(find.text('任务列表'), findsOneWidget);
    expect(find.text('施工计划'), findsOneWidget);
    expect(find.text('质检清单'), findsOneWidget);
  });

  testWidgets('空态展示 - 无施工任务时显示空态图标和提示', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'construction/tasks': jsonResponse([]),
    });

    await tester.pumpWidget(
      createTestApp(const ConstructionPage(projectId: 'test-id')),
    );
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.engineering), findsOneWidget);
    expect(find.text('暂无施工任务'), findsOneWidget);
    expect(find.text('刷新'), findsOneWidget);
  });

  testWidgets('任务列表 - 有数据时渲染任务卡片', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'construction/tasks': jsonResponse([
        {
          'id': 'task-1',
          'project_id': 'test-id',
          'task_name': '水电改造',
          'phase': '水电',
          'status': 'in_progress',
          'assignee': '张师傅',
        },
        {
          'id': 'task-2',
          'project_id': 'test-id',
          'task_name': '瓦工铺贴',
          'phase': '瓦工',
          'status': 'pending',
        },
      ]),
    });

    await tester.pumpWidget(
      createTestApp(const ConstructionPage(projectId: 'test-id')),
    );
    await tester.pumpAndSettle();

    expect(find.text('水电改造'), findsOneWidget);
    expect(find.text('水电 · in_progress'), findsOneWidget);
    expect(find.text('瓦工铺贴'), findsOneWidget);
    expect(find.text('瓦工 · pending'), findsOneWidget);
    expect(find.text('暂无施工任务'), findsNothing);
  });
}
