import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/tasks_page.dart';

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

  testWidgets('页面渲染 - 显示 AppBar 标题、2 个 Tab 和 FAB', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'tasks/project': jsonResponse({'tasks': []}),
    });

    await tester.pumpWidget(
      createTestApp(const TasksPage(projectId: 'test-id')),
    );
    await tester.pumpAndSettle();

    expect(find.text('任务管理'), findsOneWidget);
    expect(find.text('任务看板'), findsOneWidget);
    expect(find.text('任务列表'), findsOneWidget);
    expect(find.byType(FloatingActionButton), findsOneWidget);
    expect(find.byIcon(Icons.add), findsOneWidget);
  });

  testWidgets('空态展示 - 看板三列均无任务时显示暂无任务', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'tasks/project': jsonResponse({'tasks': []}),
    });

    await tester.pumpWidget(
      createTestApp(const TasksPage(projectId: 'test-id')),
    );
    await tester.pumpAndSettle();

    // 看板有 3 列（待办、进行中、已完成），每列空态显示「暂无任务」
    expect(find.text('暂无任务'), findsNWidgets(3));
  });

  testWidgets('任务看板 - 有数据时渲染任务卡片', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'tasks/project': jsonResponse({
        'tasks': [
          {
            'id': 'task-1',
            'project_id': 'test-id',
            'title': '水电验收',
            'status': 'pending',
            'priority': 8,
            'assigned_user_name': '李工',
          },
        ],
      }),
    });

    await tester.pumpWidget(
      createTestApp(const TasksPage(projectId: 'test-id')),
    );
    await tester.pumpAndSettle();

    expect(find.text('水电验收'), findsOneWidget);
    expect(find.text('李工'), findsOneWidget);
    expect(find.text('高'), findsOneWidget);
  });
}
