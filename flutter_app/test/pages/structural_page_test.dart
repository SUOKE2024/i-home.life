import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/structural_page.dart';

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

  testWidgets('页面渲染 - 显示 AppBar 标题和 4 个 Tab', (tester) async {
    // 空映射 → 所有结构接口返回默认空数组
    HttpOverrides.global = MockHttpOverrides({});

    await tester.pumpWidget(
      createTestApp(const StructuralPage(projectId: 'test-project-id')),
    );
    await tester.pumpAndSettle();

    // AppBar 标题
    expect(find.text('土建结构'), findsOneWidget);
    // 4 个 Tab
    expect(find.text('承重墙'), findsOneWidget);
    expect(find.text('梁/柱'), findsOneWidget);
    expect(find.text('楼板'), findsOneWidget);
    expect(find.text('工程量'), findsOneWidget);
  });

  testWidgets('承重墙空态 - 无数据时显示空态和添加按钮', (tester) async {
    HttpOverrides.global = MockHttpOverrides({});

    await tester.pumpWidget(
      createTestApp(const StructuralPage(projectId: 'test-project-id')),
    );
    await tester.pumpAndSettle();

    // 空态图标
    expect(find.byIcon(Icons.foundation), findsOneWidget);
    // 空态提示
    expect(find.text('暂无承重墙'), findsOneWidget);
    // 添加按钮
    expect(find.text('添加承重墙'), findsOneWidget);
  });

  testWidgets('承重墙数据 - 渲染墙体卡片', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'projects/test-project-id/walls': jsonResponse([
        {
          'wall_name': 'W1客厅承重墙',
          'is_load_bearing': true,
          'thickness_mm': 240,
          'material': '钢筋混凝土',
        },
      ]),
    });

    await tester.pumpWidget(
      createTestApp(const StructuralPage(projectId: 'test-project-id')),
    );
    await tester.pumpAndSettle();

    // 验证墙体名称
    expect(find.text('W1客厅承重墙'), findsOneWidget);
    // 验证承重徽章
    expect(find.text('承重'), findsOneWidget);
    // 验证厚度
    expect(find.text('240 mm'), findsOneWidget);
    // 验证材质
    expect(find.text('钢筋混凝土'), findsOneWidget);
    // 不应显示空态
    expect(find.text('暂无承重墙'), findsNothing);
  });
}
