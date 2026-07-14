import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/login_page.dart';

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

  testWidgets('页面渲染 - 显示标题和表单字段', (tester) async {
    await tester.pumpWidget(createTestApp(const LoginPage()));
    await tester.pumpAndSettle();

    expect(find.text('i-home.life'), findsOneWidget);
    expect(find.text('索克家居 · AI 智能装修平台'), findsOneWidget);
    expect(find.text('手机号'), findsOneWidget);
    expect(find.text('密码'), findsOneWidget);
  });

  testWidgets('页面渲染 - 显示登录按钮', (tester) async {
    await tester.pumpWidget(createTestApp(const LoginPage()));
    await tester.pumpAndSettle();

    // 按钮文本为 '登 录'（含空格）
    expect(find.text('登 录'), findsOneWidget);
    expect(find.byType(ElevatedButton), findsOneWidget);
  });

  testWidgets('表单验证 - 空输入显示错误提示', (tester) async {
    // Mock 登录 API 返回错误
    HttpOverrides.global = MockHttpOverrides({
      'auth/login': jsonResponse({'detail': '手机号或密码错误'}, status: 400),
    });

    await tester.pumpWidget(createTestApp(const LoginPage()));
    await tester.pumpAndSettle();

    // 清空手机号输入
    await tester.enterText(find.byType(TextField).at(0), '');
    await tester.pump();

    // 点击登录按钮
    await tester.tap(find.byType(ElevatedButton));
    await tester.pumpAndSettle();

    // 应显示错误提示 SnackBar
    expect(find.textContaining('操作失败'), findsOneWidget);
  });

  testWidgets('表单交互 - 输入手机号和密码', (tester) async {
    await tester.pumpWidget(createTestApp(const LoginPage()));
    await tester.pumpAndSettle();

    // 输入新的手机号和密码
    await tester.enterText(find.byType(TextField).at(0), '13900139000');
    await tester.enterText(find.byType(TextField).at(1), 'newpassword123');
    await tester.pump();

    // 验证输入已更新
    final phoneField = tester.widget<TextField>(find.byType(TextField).at(0));
    expect(phoneField.controller!.text, '13900139000');

    final passField = tester.widget<TextField>(find.byType(TextField).at(1));
    expect(passField.controller!.text, 'newpassword123');
  });
}
