import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:ihome_app/main.dart';

void main() {
  testWidgets('App smoke test', (WidgetTester tester) async {
    // 模拟未登录状态
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(const IHomeApp());
    // 等待 AuthGate 异步检查完成，进入 LoginPage
    await tester.pumpAndSettle();
    // LoginPage 显示品牌标题
    expect(find.text('i-home.life'), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsNothing);
  });
}
