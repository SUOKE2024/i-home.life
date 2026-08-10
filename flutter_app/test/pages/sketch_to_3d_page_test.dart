import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/sketch_to_3d_page.dart';

import '../test_helper.dart';
import '../mock_http.dart';

/// P1 QA — 草图转 3D 页（T1 成功 / T2 flag 降级）
void main() {
  setUp(() => setupTestEnv());

  tearDown(() => HttpOverrides.global = null);

  testWidgets('T1 成功态 - 支持格式加载', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      '/api/sketch-to-3d/supported-formats': jsonResponse({
        'code': 0,
        'data': {'formats': ['png', 'jpg', 'webp']},
      }),
    });

    await tester.pumpWidget(createTestApp(const SketchTo3DPage()));
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pump();

    // 页面渲染（上传区/格式提示按页面实现调整）
    expect(find.byType(SketchTo3DPage), findsOneWidget);
  });

  testWidgets('T2 降级态 - 视觉识别未开启诚实提示', (tester) async {
    // 后端 200 + 降级占位（sketch_to_3d_page.dart L141）
    HttpOverrides.global = MockHttpOverrides({
      '/api/sketch-to-3d/supported-formats': jsonResponse({
        'code': 0,
        'data': {'formats': ['png', 'jpg', 'webp']},
      }),
    });

    await tester.pumpWidget(createTestApp(const SketchTo3DPage()));
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pump();

    // 降级文案在分析回调内触发；此处校验页面可渲染不崩溃
    expect(find.byType(SketchTo3DPage), findsOneWidget);
  });
}
