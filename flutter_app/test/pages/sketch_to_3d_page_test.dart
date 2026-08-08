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
      '/api/sketch-to-3d/supported-formats': {
        'code': 0,
        'data': {'formats': ['png', 'jpg', 'webp']},
      },
    });

    await tester.pumpWidget(createTestApp(const SketchTo3DPage()));
    await tester.pump(const Duration(milliseconds: 300));

    // 页面渲染（上传区/格式提示按页面实现调整）
    expect(find.byType(SketchTo3DPage), findsOneWidget);
  });

  testWidgets('T2 降级态 - sketch_to_3d_vision_enabled 关闭 503', (tester) async {
    HttpOverrides.global = MockHttpOverrides.error('/api/sketch-to-3d/supported-formats', 503);

    await tester.pumpWidget(createTestApp(const SketchTo3DPage()));
    await tester.pump(const Duration(milliseconds: 300));

    // 降级文案以页面实现为准
    expect(find.textContaining('不可用'), findsOneWidget);
  });
}
