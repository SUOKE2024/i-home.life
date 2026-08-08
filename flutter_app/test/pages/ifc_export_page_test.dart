import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/ifc_export_page.dart';

import '../test_helper.dart';
import '../mock_http.dart';

/// P1 QA — IFC 导出页（T1 成功态冒烟）
void main() {
  setUp(() => setupTestEnv());

  tearDown(() => HttpOverrides.global = null);

  testWidgets('T1 成功态 - 页面渲染', (tester) async {
    HttpOverrides.global = MockHttpOverrides({});

    await tester.pumpWidget(createTestApp(const IFCExportPage()));
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.byType(IFCExportPage), findsOneWidget);
  });
}
