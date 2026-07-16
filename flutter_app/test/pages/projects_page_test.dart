import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/projects_page.dart';

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

  testWidgets('页面渲染 - 显示 AppBar 标题和新增按钮', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'projects': jsonResponse([]),
    });

    await tester.pumpWidget(createTestApp(const ProjectsPage()));
    await tester.pumpAndSettle();

    // AppBar 标题
    expect(find.text('我的项目'), findsOneWidget);
    // 新增按钮（+ 图标，AppBar 中 + 空态 OutlinedButton 中共 2 个）
    expect(find.byIcon(Icons.add), findsAtLeastNWidgets(1));
  });

  testWidgets('项目列表 - 空状态显示空态图标和提示文字', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'projects': jsonResponse([]),
    });

    await tester.pumpWidget(createTestApp(const ProjectsPage()));
    await tester.pumpAndSettle();

    // 空态图标
    expect(find.byIcon(Icons.home_work_outlined), findsOneWidget);
    // 空态提示文本
    expect(find.text('还没有项目，点击下方按钮创建'), findsOneWidget);
    // 创建项目按钮
    expect(find.text('创建项目'), findsOneWidget);
    // OutlinedButton
    expect(find.byType(OutlinedButton), findsOneWidget);
  });

  testWidgets('项目列表 - 有数据时渲染项目卡片', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'projects': jsonResponse([
        {
          'id': 'proj-1',
          'name': '朝阳小区三居室',
          'address': '北京市朝阳区某某路 100 号',
          'total_area': 126,
          'status': 'in_progress',
        },
        {
          'id': 'proj-2',
          'name': '海淀区别墅',
          'address': '北京市海淀区某某路 200 号',
          'total_area': 300,
          'status': 'draft',
        },
      ]),
    });

    await tester.pumpWidget(createTestApp(const ProjectsPage()));
    await tester.pumpAndSettle();

    // 验证项目名称
    expect(find.text('朝阳小区三居室'), findsOneWidget);
    expect(find.text('海淀区别墅'), findsOneWidget);

    // 验证地址和面积
    expect(
      find.text('北京市朝阳区某某路 100 号 · 126㎡'),
      findsOneWidget,
    );
    expect(
      find.text('北京市海淀区某某路 200 号 · 300㎡'),
      findsOneWidget,
    );

    // 验证状态标签
    expect(find.text('施工中'), findsOneWidget);
    expect(find.text('草稿'), findsOneWidget);

    // 不应显示空态
    expect(find.text('还没有项目，点击下方按钮创建'), findsNothing);
    expect(find.byIcon(Icons.home_work_outlined), findsNothing);
  });

  testWidgets('项目列表 - 已完成状态正确显示', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'projects': jsonResponse([
        {
          'id': 'proj-3',
          'name': '已完成项目',
          'address': '上海市浦东新区',
          'total_area': 80,
          'status': 'completed',
        },
      ]),
    });

    await tester.pumpWidget(createTestApp(const ProjectsPage()));
    await tester.pumpAndSettle();

    expect(find.text('已完成项目'), findsOneWidget);
    expect(find.text('已完成'), findsOneWidget);
  });

  testWidgets('点击新增按钮显示创建表单', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'projects': jsonResponse([]),
    });

    await tester.pumpWidget(createTestApp(const ProjectsPage()));
    await tester.pumpAndSettle();

    // 点击 AppBar 中的 + 按钮展开表单（取第一个，避免空态中的重复图标）
    await tester.tap(find.byIcon(Icons.add).first);
    await tester.pumpAndSettle();

    // 验证创建表单各字段
    expect(find.text('项目名称'), findsOneWidget);
    expect(find.text('地址'), findsOneWidget);
    expect(find.text('面积 (㎡)'), findsOneWidget);
    // 「创建项目」在空态 OutlinedButton 和表单 ElevatedButton 中各出现一次
    expect(find.text('创建项目'), findsAtLeastNWidgets(1));

    // 按钮变为 close 图标
    expect(find.byIcon(Icons.close), findsOneWidget);
    expect(find.byType(ElevatedButton), findsOneWidget);
  });
}
