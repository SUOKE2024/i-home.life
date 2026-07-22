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

    // 按钮文本为 '登录'（v1.1.29 去掉空格）
    expect(find.text('登录'), findsOneWidget);
    expect(find.byType(ElevatedButton), findsOneWidget);
  });

  testWidgets('表单验证 - 空输入显示错误提示', (tester) async {
    await tester.pumpWidget(createTestApp(const LoginPage()));
    await tester.pumpAndSettle();

    // 点击登录按钮（空输入，表单验证会拦截）
    await tester.tap(find.byType(ElevatedButton));
    await tester.pumpAndSettle();

    // Form 验证应显示错误信息
    expect(find.text('请输入手机号'), findsOneWidget);
    expect(find.text('请输入密码'), findsOneWidget);
  });

  testWidgets('表单交互 - 输入手机号和密码', (tester) async {
    await tester.pumpWidget(createTestApp(const LoginPage()));
    await tester.pumpAndSettle();

    // 输入新的手机号和密码
    await tester.enterText(find.byType(TextFormField).at(0), '13900139000');
    await tester.enterText(find.byType(TextFormField).at(1), 'newpassword123');
    await tester.pump();

    // 验证输入已更新
    final phoneField = tester.widget<TextFormField>(find.byType(TextFormField).at(0));
    expect(phoneField.controller!.text, '13900139000');

    final passField = tester.widget<TextFormField>(find.byType(TextFormField).at(1));
    expect(passField.controller!.text, 'newpassword123');
  });
}
